import base64
from dataclasses import replace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from scripts.share_preview import protected_preview, seed_demo


def test_preview_password_overrides_optional_local_access_password(tmp_path, monkeypatch):
    import scripts.share_preview as preview
    from config import get_settings
    monkeypatch.setattr(preview, "get_settings", lambda: replace(get_settings(), access_password="different-local-password"))
    engine = create_engine(f"sqlite:///{(tmp_path / 'preview.db').as_posix()}", connect_args={"check_same_thread":False})
    app = protected_preview(db_engine=engine, static_dir=tmp_path / "static", password="preview-password")
    encoded = base64.b64encode(b"campus:preview-password").decode()
    with TestClient(app) as client:
        assert client.get("/", headers={"Authorization":"Basic " + encoded}).status_code == 200


def test_team_preview_protects_pages_assets_and_api(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'preview.db').as_posix()}", connect_args={"check_same_thread":False})
    app = protected_preview(db_engine=engine, static_dir=tmp_path / "static", password="test-password")
    with TestClient(app) as client:
        seed_demo(engine)
        for path in ("/", "/api/items", "/assets/js/app.js", "/docs"):
            assert client.get(path).status_code == 401
            encoded = base64.b64encode(b"campus:wrong-password").decode()
            assert client.get(path, headers={"Authorization":"Basic " + encoded}).status_code == 401
            encoded = base64.b64encode(b"campus:test-password").decode()
            assert client.get(path, headers={"Authorization":"Basic " + encoded}).status_code == 200
        for header in ("Basic !not-base64!", "Basic " + base64.b64encode(b"no-colon").decode()):
            assert client.get("/", headers={"Authorization":header}).status_code == 401


def test_team_preview_demo_data_is_temporary_and_not_mine(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'preview.db').as_posix()}", connect_args={"check_same_thread":False})
    app = protected_preview(db_engine=engine, static_dir=tmp_path / "static", password="test-password")
    encoded = base64.b64encode(b"campus:test-password").decode()
    with TestClient(app, headers={"Authorization":"Basic " + encoded}) as client:
        seed_demo(engine)
        response = client.get("/api/items")
        assert len(response.json()) == 3
        assert all(item["contact"] == "demo@example.com" for item in response.json())
        assert all(item["is_mine"] is False for item in response.json())
