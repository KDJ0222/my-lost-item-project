from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
import pytest
from sqlalchemy import create_engine

from main import create_app


@pytest.fixture
def client(tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    app = create_app(db_engine=engine, static_dir=tmp_path / "static")
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def png():
    output = BytesIO()
    Image.new("RGB", (16, 16), "blue").save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def payload():
    return {
        "title": "검정 지갑", "category": "지갑", "location": "중앙도서관",
        "author": "테스트 사용자", "contact": "test@example.com",
        "keywords": ["가죽", "카드수납"], "report_type": "found",
    }
