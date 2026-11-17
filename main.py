from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from config import BASE_DIR, get_settings
from database import engine, initialize_database
from routers import ai_vision, items


STATIC_DIR = BASE_DIR / "static"


def create_app(*, db_engine: Engine = engine, static_dir: Path = STATIC_DIR) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.upload_dir.mkdir(parents=True, exist_ok=True)
        initialize_database(db_engine)
        yield
        db_engine.dispose()

    app = FastAPI(title="스마트 캠퍼스 분실물 API", version="0.1.0", lifespan=lifespan)
    app.state.upload_dir = static_dir / "uploads"
    app.state.session_factory = sessionmaker(
        bind=db_engine, autoflush=False, expire_on_commit=False
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(get_settings().cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-Owner-Token"],
    )
    app.include_router(items.router)
    app.include_router(ai_vision.router)
    app.mount("/static", StaticFiles(directory=str(static_dir), check_dir=False), name="static")
    # Shared assets remain available when a test app uses an isolated upload folder.
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR), check_dir=False), name="assets")

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(BASE_DIR / "templates" / "index.html")

    @app.get("/api/health", tags=["health"])
    def health():
        return {"status": "ok"}

    return app


app = create_app()
