from contextlib import asynccontextmanager
from pathlib import Path

import os

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from config import BASE_DIR, Settings, get_settings, validate_production
from database import engine, initialize_database
from routers import ai_vision, items
from services.access import install_access_gate


STATIC_DIR = BASE_DIR / "static"


def create_app(*, db_engine: Engine = engine, static_dir: Path | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        validate_production(settings)
        app.state.upload_dir.mkdir(parents=True, exist_ok=True)
        initialize_database(db_engine)
        try:
            yield
        finally:
            db_engine.dispose()

    app = FastAPI(title="스마트 캠퍼스 분실물 API", version="0.1.0", lifespan=lifespan,
                  docs_url="/docs" if settings.api_docs_enabled else None,
                  redoc_url=None, openapi_url="/openapi.json" if settings.api_docs_enabled else None)
    app.state.upload_dir = static_dir / "uploads" if static_dir is not None else settings.upload_dir
    app.state.production = settings.environment == "production"
    app.state.session_factory = sessionmaker(
        bind=db_engine, autoflush=False, expire_on_commit=False
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Owner-Token"],
    )
    app.include_router(items.router)
    app.include_router(ai_vision.router)
    app.mount("/static/uploads", StaticFiles(directory=str(app.state.upload_dir), check_dir=False), name="uploads")
    for directory in ("css", "js", "vendor"):
        app.mount(f"/assets/{directory}", StaticFiles(directory=str(STATIC_DIR / directory)), name=f"assets_{directory}")
    if settings.access_password:
        install_access_gate(app, settings.access_username, settings.access_password, public_health=True)

    @app.middleware("http")
    async def response_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(BASE_DIR / "templates" / "index.html")

    @app.get("/api/health", tags=["health"])
    def health(response: Response):
        try:
            with db_engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            if not app.state.upload_dir.is_dir() or not os.access(app.state.upload_dir, os.W_OK):
                raise OSError("Upload storage unavailable")
        except (SQLAlchemyError, OSError):
            response.status_code = 503
            return {"status":"unavailable"}
        return {"status": "ok"}

    return app


app = create_app()
