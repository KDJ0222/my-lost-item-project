from unittest.mock import Mock

from fastapi import HTTPException
import pytest
from sqlalchemy.exc import SQLAlchemyError

from database import get_db
from routers import items
from schemas import ImageAnalysis


def analysis():
    return ImageAnalysis(
        title="파란 우산", category="우산", color="파랑", material=None,
        description="접이식 우산", keywords=["우산", "파랑", "접이식"],
    )


def test_register_get_update_and_missing_item(client, payload):
    response = client.post("/api/items", json=payload)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["contact"] == payload["contact"]
    assert saved["created_at"]
    assert client.get(f"/api/items/{saved['id']}").json() == saved
    updated = client.put(f"/api/items/{saved['id']}", json={**payload, "status": "resolved"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "resolved"
    assert client.get("/api/items/9999").status_code == 404
    assert client.put("/api/items/9999", json=payload).status_code == 404


def test_search_unicode_keywords_filters_and_pagination(client, payload):
    first = client.post("/api/items", json={**payload, "color": "검정"}).json()
    second = client.post("/api/items", json={
        **payload, "title": "빨간 파우치", "category": "가방", "location": "학생회관",
        "keywords": ["100%_면"], "report_type": "lost", "status": "resolved",
    }).json()
    for word in ("검정", "지갑", "가죽", "카드수납", "도서관"):
        result = client.get("/api/items", params={"keyword": word})
        assert result.status_code == 200, result.text
        assert [row["id"] for row in result.json()] == [first["id"]]
    assert client.get("/api/items", params={"keyword": "%_"}).json()[0]["id"] == second["id"]
    for name, value in (("location", "도서관"), ("category", "지갑"), ("color", "검정"),
                        ("report_type", "found"), ("status", "open")):
        assert client.get("/api/items", params={name: value}).json()[0]["id"] == first["id"]
    assert client.get("/api/items", params={"category": "지갑", "location": "학생"}).json() == []
    assert client.get("/api/items", params={"limit": 1}).json()[0]["id"] == second["id"]
    assert client.get("/api/items", params={"offset": 1, "limit": 1}).json()[0]["id"] == first["id"]
    assert client.get("/api/items", params={"keyword": "없는물건"}).json() == []


@pytest.mark.parametrize("change", [
    {"title": "   "}, {"contact": "   "}, {"latitude": 37.5},
    {"latitude": 91, "longitude": 127}, {"keywords": ["  "]},
    {"keywords": ["x" * 51]}, {"report_type": "invalid"}, {"status": "invalid"},
])
def test_invalid_item_is_not_saved(client, payload, change):
    assert client.post("/api/items", json={**payload, **change}).status_code == 422
    assert client.get("/api/items").json() == []


@pytest.mark.parametrize("query", [{"limit": 101}, {"offset": -1}, {"status": "invalid"}])
def test_invalid_query(client, query):
    assert client.get("/api/items", params=query).status_code == 422


def test_one_step_report_persists_ai_fields_and_image(client, png, monkeypatch):
    ai = Mock(return_value=analysis())
    monkeypatch.setattr(items, "analyze_image", ai)
    response = client.post("/api/items/report", data={
        "location": " 형남공학관 ", "contact": "test@example.com", "author": "테스터",
        "latitude": "37.496", "longitude": "126.957", "title": "내 우산",
    }, files={"file": ("../../photo.txt", png, "text/plain")})
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["title"] == "내 우산"
    assert saved["location"] == "형남공학관"
    assert saved["latitude"] == 37.496
    assert saved["longitude"] == 126.957
    assert saved["category"] == "우산"
    assert saved["keywords"] == ["우산", "파랑", "접이식"]
    assert saved["status"] == "open"
    assert client.get(saved["image_path"]).content == png
    assert client.get("/api/items").json() == [saved]
    ai.assert_called_once_with(png, "image/png")


@pytest.mark.parametrize("change", [{"location": " "}, {"contact": " "},
                                    {"latitude": "37"}, {"longitude": "nan"}])
def test_report_validation_precedes_ai(client, png, monkeypatch, change):
    ai = Mock(return_value=analysis())
    monkeypatch.setattr(items, "analyze_image", ai)
    response = client.post("/api/items/report", data={
        "location": "도서관", "contact": "test@example.com", "author": "테스터", **change,
    }, files={"file": ("item.png", png, "image/png")})
    assert response.status_code == 422, response.text
    ai.assert_not_called()
    assert list(client.app.state.upload_dir.iterdir()) == []


def test_report_ai_failure_leaves_no_record_or_file(client, png, monkeypatch):
    monkeypatch.setattr(items, "analyze_image", Mock(side_effect=HTTPException(502, "AI 실패")))
    response = client.post("/api/items/report", data={
        "location": "도서관", "contact": "test@example.com", "author": "테스터",
    }, files={"file": ("item.png", png, "image/png")})
    assert response.status_code == 502
    assert client.get("/api/items").json() == []
    assert list(client.app.state.upload_dir.iterdir()) == []


def test_report_database_failure_removes_new_file(client, png, monkeypatch):
    monkeypatch.setattr(items, "analyze_image", Mock(return_value=analysis()))
    session = Mock()
    session.commit.side_effect = SQLAlchemyError("simulated failure")
    client.app.dependency_overrides[get_db] = lambda: session
    try:
        response = client.post("/api/items/report", data={
            "location": "도서관", "contact": "test@example.com", "author": "테스터",
        }, files={"file": ("item.png", png, "image/png")})
        assert response.status_code == 500
        session.rollback.assert_called_once()
        assert list(client.app.state.upload_dir.iterdir()) == []
    finally:
        client.app.dependency_overrides.clear()
    assert client.get("/api/items").json() == []


def test_two_step_analysis_can_be_edited_then_registered(client, png, monkeypatch, payload):
    from routers import ai_vision

    monkeypatch.setattr(ai_vision, "analyze_image", Mock(return_value=analysis()))
    result = client.post("/api/images/analyze", files={"file": ("photo.png", png, "image/png")})
    assert result.status_code == 201
    assert client.get("/api/items").json() == []
    registered = client.post("/api/items", json={**payload, **result.json(), "color": "남색"})
    assert registered.status_code == 201, registered.text
    assert registered.json()["color"] == "남색"
    assert registered.json()["keywords"] == analysis().keywords


@pytest.mark.parametrize("image_path", ["/etc/passwd", "https://example.com/image.png",
                                      "/static/uploads/" + "a" * 32 + ".png"])
def test_untrusted_or_missing_image_path(client, payload, image_path):
    assert client.post("/api/items", json={**payload, "image_path": image_path}).status_code == 422
