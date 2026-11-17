from io import BytesIO
from unittest.mock import Mock

from fastapi import HTTPException
from PIL import Image
import pytest

from routers import ai_vision
from services import images


@pytest.mark.parametrize("format,extension", [("PNG", ".png"), ("JPEG", ".jpg"), ("WEBP", ".webp")])
def test_upload_supported_image_and_static_url(client, format, extension):
    output = BytesIO()
    Image.new("RGB", (8, 8), "red").save(output, format=format)
    data = output.getvalue()
    response = client.post("/api/images", files={"file": ("../../wrong.svg", data, "image/svg+xml")})
    assert response.status_code == 201, response.text
    path = response.json()["image_path"]
    assert path.startswith("/static/uploads/") and path.endswith(extension)
    assert client.get(path).content == data


@pytest.mark.parametrize("data,status", [(b"", 400), (b"<script>alert(1)</script>", 415),
                                         (b"\x89PNG\r\n\x1a\ninvalid", 415)])
def test_invalid_upload(client, data, status):
    assert client.post("/api/images", files={"file": ("photo.png", data, "image/png")}).status_code == status
    assert list(client.app.state.upload_dir.iterdir()) == []


def test_oversized_upload(client):
    response = client.post("/api/images", files={
        "file": ("big.png", b"x" * (images.MAX_IMAGE_SIZE + 1), "image/png"),
    })
    assert response.status_code == 413
    assert list(client.app.state.upload_dir.iterdir()) == []


def test_pixel_limit(client, png, monkeypatch):
    monkeypatch.setattr(images, "MAX_IMAGE_PIXELS", 10)
    response = client.post("/api/images", files={"file": ("photo.png", png, "image/png")})
    assert response.status_code == 413


def test_analysis_failure_does_not_save_file(client, png, monkeypatch):
    monkeypatch.setattr(ai_vision, "analyze_image", Mock(side_effect=HTTPException(503, "키 미설정")))
    response = client.post("/api/images/analyze", files={"file": ("photo.png", png, "image/png")})
    assert response.status_code == 503
    assert list(client.app.state.upload_dir.iterdir()) == []
