import base64
from dataclasses import replace
from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.exc import OperationalError

from config import get_settings, validate_production
from database import make_engine
from main import create_app
from scripts.start_server import server_options


def production_settings(root):
    return replace(get_settings(), environment="production", data_dir=root,
                   database_url=f"sqlite:///{(root / 'database.db').as_posix()}",
                   upload_dir=root / "uploads", allowed_hosts=("testserver", "127.0.0.1"),
                   access_username="campus", access_password="test-only-strong-password",
                   gemini_api_key="test-only-key", cors_origins=(), api_docs_enabled=False)


def credentials(settings):
    value = base64.b64encode((settings.access_username + ":" + settings.access_password).encode()).decode()
    return {"Authorization":"Basic " + value, "X-Owner-Token":"a" * 64}


def test_production_auth_static_boundaries_and_health(tmp_path):
    settings = production_settings(tmp_path / "persistent")
    app = create_app(db_engine=make_engine(settings.database_url), settings=settings)
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status":"ok"}
        for path in ("/", "/api/items", "/assets/js/app.js"):
            assert client.get(path).status_code == 401
            assert client.get(path, headers=credentials(settings)).status_code == 200
        for path in ("/docs", "/openapi.json", "/.env", "/database.db", "/assets/uploads/test.png"):
            assert client.get(path, headers=credentials(settings)).status_code == 404
        assert client.get("/", headers={"Host":"unexpected.example"}).status_code == 400
        response = client.get("/", headers=credentials(settings))
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert settings.gemini_api_key not in response.text
        assert settings.access_password not in repr(settings)


def test_restart_retains_database_photos_and_owner(tmp_path, payload, png):
    settings = production_settings(tmp_path / "persistent")
    headers = credentials(settings)
    app = create_app(db_engine=make_engine(settings.database_url), settings=settings)
    with TestClient(app, headers=headers) as client:
        upload = client.post("/api/images", files={"file":("test.png", png, "image/png")}).json()["image_path"]
        saved = client.post("/api/items", json={**payload, "image_path":upload}).json()
        assert saved["is_mine"] is True
    new_app = create_app(db_engine=make_engine(settings.database_url), settings=settings)
    with TestClient(new_app, headers=headers) as client:
        assert client.get(f"/api/items/{saved['id']}").json() == saved
        assert client.get(upload).content == png
    assert settings.upload_dir.joinpath(upload.rsplit("/", 1)[-1]).exists()


def test_production_rejects_unowned_registration_and_legacy_edit(tmp_path, payload):
    from models import Item
    settings = production_settings(tmp_path)
    app = create_app(db_engine=make_engine(settings.database_url), settings=settings)
    headers = credentials(settings)
    no_owner = {"Authorization":headers["Authorization"]}
    with TestClient(app) as client:
        assert client.post("/api/items", headers=no_owner, json=payload).status_code == 401
        with app.state.session_factory() as db:
            legacy = Item(**payload)
            db.add(legacy)
            db.commit()
            legacy_id = legacy.id
        assert client.put(f"/api/items/{legacy_id}", headers=headers, json=payload).status_code == 403


@pytest.mark.parametrize("change", [
    {"data_dir":None}, {"access_password":""}, {"access_password":"short"},
    {"access_password":"change_this_password_please"}, {"access_username":""},
    {"gemini_api_key":""}, {"gemini_api_key":"your_gemini_api_key"},
    {"allowed_hosts":()}, {"allowed_hosts":("*",)},
    {"database_url":"sqlite:///:memory:"},
])
def test_incomplete_production_configuration_is_rejected(tmp_path, change):
    settings = replace(production_settings(tmp_path), **change)
    with pytest.raises(ValueError):
        validate_production(settings)


def test_ephemeral_storage_paths_are_rejected(tmp_path):
    settings = production_settings(tmp_path / "persistent")
    with pytest.raises(ValueError):
        validate_production(replace(settings, upload_dir=tmp_path / "ephemeral"))
    with pytest.raises(ValueError):
        validate_production(replace(settings, database_url=f"sqlite:///{(tmp_path / 'outside.db').as_posix()}"))


def test_environment_paths_and_platform_host(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "campus.example.onrender.com")
    for name in ("DATABASE_URL", "UPLOAD_DIR", "ALLOWED_HOSTS", "CORS_ORIGINS", "ENABLE_API_DOCS"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.upload_dir == tmp_path / "uploads"
        assert settings.database_url == f"sqlite:///{(tmp_path / 'database.db').as_posix()}"
        assert settings.allowed_hosts == ("campus.example.onrender.com", "localhost", "127.0.0.1", "[::1]")
        assert settings.api_docs_enabled is False
        assert settings.cors_origins == ()
    finally:
        get_settings.cache_clear()


def test_health_reports_database_failure_without_leaking_details(tmp_path, monkeypatch):
    settings = production_settings(tmp_path)
    engine = make_engine(settings.database_url)
    app = create_app(db_engine=engine, settings=settings)
    with TestClient(app) as client:
        monkeypatch.setattr(engine, "connect", Mock(side_effect=OperationalError("secret-database-url", {}, Exception("detail"))))
        response = client.get("/api/health")
        assert response.status_code == 503
        assert response.json() == {"status":"unavailable"}
        assert "secret" not in response.text


def test_cloud_port_and_single_worker(monkeypatch):
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("WEB_CONCURRENCY", "8")
    assert server_options()["port"] == 10000
    assert server_options()["workers"] == 1
    assert server_options()["host"] == "0.0.0.0"
    monkeypatch.setenv("PORT", "70000")
    with pytest.raises(ValueError):
        server_options()
