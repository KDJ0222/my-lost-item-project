import sqlite3

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from database import initialize_database
from main import create_app


def test_original_database_upgrade_preserves_rows(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE items (
            id INTEGER PRIMARY KEY, title VARCHAR(100) NOT NULL,
            category VARCHAR(50) NOT NULL, color VARCHAR(50), material VARCHAR(100),
            description TEXT, image_path VARCHAR(255), keywords JSON NOT NULL,
            location VARCHAR(200) NOT NULL, latitude FLOAT, longitude FLOAT,
            author VARCHAR(50) NOT NULL, report_type VARCHAR(10) NOT NULL,
            status VARCHAR(10) NOT NULL, created_at DATETIME NOT NULL
        )""")
        connection.execute("""INSERT INTO items
            (title, category, keywords, location, author, report_type, status, created_at)
            VALUES ('legacy wallet', 'wallet', '[]', 'library', 'tester', 'found', 'open',
                    '2026-11-17 00:00:00')""")
    engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"check_same_thread": False})
    initialize_database(engine)
    initialize_database(engine)
    app = create_app(db_engine=engine, static_dir=tmp_path / "static")
    with TestClient(app) as client:
        response = client.get("/api/items")
        assert response.status_code == 200, response.text
        assert len(response.json()) == 1
        assert response.json()[0]["title"] == "legacy wallet"
        assert response.json()[0]["contact"] is None
        assert response.json()[0]["event_date"] is None
        assert response.json()[0]["is_mine"] is False


def test_health_docs_and_openapi(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    assert "/api/items/report" in schema.json()["paths"]
    assert "/api/images/analyze" in schema.json()["paths"]
