"""Password-protected team preview, isolated from the real database.

Run python -m scripts.share_preview, then forward 127.0.0.1:8002 using a tunnel.
The credentials and temporary data last only for this server process.
"""

from datetime import date
from dataclasses import replace
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import uvicorn

from database import initialize_database
from main import create_app
from models import Item
from services.access import install_access_gate
from config import get_settings


def protected_preview(*, db_engine, static_dir: Path, password: str):
    settings = get_settings()
    if settings.environment == "production":
        raise ValueError("Temporary previews are development-only; use scripts.start_server for production.")
    app = create_app(db_engine=db_engine, static_dir=static_dir,
                     settings=replace(settings, access_password=""))

    install_access_gate(app, "campus", password)
    return app


def seed_demo(engine):
    with Session(engine) as db:
        db.add_all([
            Item(title="검정 지갑", category="지갑", color="검정", material="가죽",
                 location="중앙도서관 1층 안내 데스크", keywords=["지갑", "검정", "가죽"],
                 description="화면 시연을 위한 예시 물품입니다.", author="캠퍼스 찾음 팀",
                 contact="demo@example.com", report_type="found", event_date=date.today()),
            Item(title="파란 접이식 우산", category="우산", color="파랑", material=None,
                 location="형남공학관 2층 휴게 공간", keywords=["우산", "파랑", "접이식"],
                 description="화면 시연을 위한 예시 물품입니다.", author="캠퍼스 찾음 팀",
                 contact="demo@example.com", report_type="lost", event_date=date.today()),
            Item(title="무선 이어폰 케이스", category="이어폰", color="흰색", material="플라스틱",
                 location="학생회관 1층", keywords=["이어폰", "흰색", "케이스"],
                 description="화면 시연을 위한 예시 물품입니다.", author="캠퍼스 찾음 팀",
                 contact="demo@example.com", report_type="found", event_date=date.today()),
        ])
        db.commit()


def main():
    password = secrets.token_urlsafe(12)
    with TemporaryDirectory(prefix="campus-team-preview-") as directory:
        root = Path(directory)
        engine = create_engine(f"sqlite:///{(root / 'preview.db').as_posix()}", connect_args={"check_same_thread":False})
        initialize_database(engine)
        seed_demo(engine)
        app = protected_preview(db_engine=engine, static_dir=root / "static", password=password)
        print("TEAM_PREVIEW_USERNAME=campus", flush=True)
        print(f"TEAM_PREVIEW_PASSWORD={password}", flush=True)
        print("TEAM_PREVIEW_ORIGIN=http://127.0.0.1:8002", flush=True)
        uvicorn.run(app, host="127.0.0.1", port=8002)


if __name__ == "__main__":
    main()
