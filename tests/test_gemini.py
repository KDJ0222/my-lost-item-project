from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException
from google import genai
from google.genai import errors
from google.genai import types
import httpx2
import pytest

from config import get_settings
from services import gemini


@pytest.fixture
def provider(monkeypatch):
    settings = replace(get_settings(), gemini_api_key="test-key", gemini_model="test-model")
    monkeypatch.setattr(gemini, "get_settings", lambda: settings)
    factory = MagicMock()
    monkeypatch.setattr(gemini.genai, "Client", factory)
    return factory.return_value.__enter__.return_value.models.generate_content


def test_valid_json_response(provider, png):
    provider.return_value = SimpleNamespace(text='{"title":"지갑","category":"지갑","keywords":["가죽","가죽"]}')
    result = gemini.analyze_image(png, "image/png")
    assert result.title == "지갑"
    assert result.keywords == ["가죽"]
    request = provider.call_args.kwargs
    assert request["model"] == "test-model"
    assert request["contents"][1].inline_data.data == png
    assert request["contents"][1].inline_data.mime_type == "image/png"


@pytest.mark.parametrize("body", [None, "not json", "{}", '{"title":"지갑","category":"지갑","keywords":[]}'])
def test_invalid_provider_response(provider, png, body):
    provider.return_value = SimpleNamespace(text=body)
    with pytest.raises(HTTPException) as error:
        gemini.analyze_image(png, "image/png")
    assert error.value.status_code == 502


@pytest.mark.parametrize("exception,status", [
    (errors.ClientError(429, {"error": {"message": "secret provider detail"}}), 503),
    (errors.ClientError(403, {"error": {"message": "secret provider detail"}}), 502),
    (errors.ServerError(503, {"error": {"message": "secret provider detail"}}), 503),
    (errors.ClientError(400, {"error": {"message": "API key not valid. Please pass a valid API key."}}), 503),
    (errors.ClientError(404, {"error": {"message": "model not found"}}), 503),
    (errors.ServerError(504, {"error": {"message": "deadline expired"}}), 504),
    (httpx2.ReadTimeout("secret provider detail"), 504),
    (httpx2.ConnectError("secret provider detail"), 502),
])
def test_provider_failures_are_sanitized(provider, png, exception, status):
    provider.side_effect = exception
    with pytest.raises(HTTPException) as error:
        gemini.analyze_image(png, "image/png")
    assert error.value.status_code == status
    assert "secret" not in error.value.detail


def test_missing_key_does_not_call_provider(monkeypatch, png):
    settings = replace(get_settings(), gemini_api_key="")
    monkeypatch.setattr(gemini, "get_settings", lambda: settings)
    factory = MagicMock()
    monkeypatch.setattr(gemini.genai, "Client", factory)
    with pytest.raises(HTTPException) as error:
        gemini.analyze_image(png, "image/png")
    assert error.value.status_code == 503
    factory.assert_not_called()


def test_real_sdk_serializes_supported_json_schema(monkeypatch, png):
    """Exercise SDK serialization, which a mocked generate_content call misses."""
    settings = replace(get_settings(), gemini_api_key="test-key", gemini_model="test-model")
    monkeypatch.setattr(gemini, "get_settings", lambda: settings)

    def handle(request):
        body = json.loads(request.content)
        config = body["generationConfig"]
        assert config["responseJsonSchema"]["additionalProperties"] is False
        assert "responseSchema" not in config
        return httpx2.Response(200, json={"candidates": [{
            "content": {"role": "model", "parts": [{
                "text": json.dumps({"title": "파란 지갑", "category": "지갑", "keywords": ["파랑", "지갑"]}),
            }]}, "finishReason": "STOP",
        }]})

    transport = httpx2.Client(transport=httpx2.MockTransport(handle))
    sdk_client = genai.Client(api_key="test-key", http_options=types.HttpOptions(httpx_client=transport))
    monkeypatch.setattr(gemini.genai, "Client", lambda **kwargs: sdk_client)
    result = gemini.analyze_image(png, "image/png")
    assert result.keywords == ["파랑", "지갑"]
