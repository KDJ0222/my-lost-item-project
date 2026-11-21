import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
if os.getenv("APP_ENV", "development").lower() != "production":
    load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    database_url: str
    gemini_api_key: str = field(repr=False)
    gemini_model: str
    cors_origins: tuple[str, ...]
    environment: str
    data_dir: Path | None
    upload_dir: Path
    allowed_hosts: tuple[str, ...]
    access_username: str
    access_password: str = field(repr=False)
    api_docs_enabled: bool


def configured_path(value: str) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else BASE_DIR / path).resolve()


def validate_production(settings: Settings):
    if settings.environment != "production":
        return
    if settings.data_dir is None:
        raise ValueError("Production requires DATA_DIR on a persistent volume.")
    if len(settings.access_password) < 16 or settings.access_password.lower().startswith(("change_", "your_", "replace_")):
        raise ValueError("Production requires an APP_ACCESS_PASSWORD of at least 16 characters.")
    if not settings.access_username:
        raise ValueError("APP_ACCESS_USERNAME must not be empty.")
    if not settings.gemini_api_key or settings.gemini_api_key.lower().startswith(("your_", "replace_", "change_")):
        raise ValueError("Production requires GEMINI_API_KEY in the server environment.")
    if not settings.allowed_hosts or "*" in settings.allowed_hosts:
        raise ValueError("Production requires explicit ALLOWED_HOSTS or a platform hostname.")
    from sqlalchemy.engine import make_url
    url = make_url(settings.database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise ValueError("This deployment supports a file-backed SQLite database.")
    for path in (configured_path(url.database), settings.upload_dir):
        if not path.is_relative_to(settings.data_dir):
            raise ValueError("Production database and uploads must both be inside DATA_DIR.")


@lru_cache
def get_settings() -> Settings:
    environment = os.getenv("APP_ENV", "development").strip().lower()
    if environment not in ("development", "production"):
        raise ValueError("APP_ENV must be development or production.")
    data_dir = configured_path(os.environ["DATA_DIR"]) if os.getenv("DATA_DIR") else None
    database_path = (data_dir or BASE_DIR) / "database.db"
    upload_default = data_dir / "uploads" if data_dir else BASE_DIR / "static" / "uploads"
    default_hosts = os.getenv("RENDER_EXTERNAL_HOSTNAME", "") if environment == "production" else "*"
    allowed_hosts = tuple(host.strip() for host in os.getenv("ALLOWED_HOSTS", default_hosts).split(",") if host.strip())
    if environment == "production" and allowed_hosts:
        allowed_hosts = tuple(dict.fromkeys((*allowed_hosts, "localhost", "127.0.0.1", "[::1]")))
    return Settings(
        database_url=os.getenv(
            "DATABASE_URL", f"sqlite:///{database_path.as_posix()}"
        ),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip(),
        cors_origins=tuple(
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS", "" if environment == "production" else "http://localhost:5500,http://127.0.0.1:5500"
            ).split(",")
            if origin.strip()
        ),
        environment=environment,
        data_dir=data_dir,
        upload_dir=configured_path(os.getenv("UPLOAD_DIR", str(upload_default))),
        allowed_hosts=allowed_hosts,
        access_username=os.getenv("APP_ACCESS_USERNAME", "campus").strip(),
        access_password=os.getenv("APP_ACCESS_PASSWORD", ""),
        api_docs_enabled=os.getenv("ENABLE_API_DOCS", "false" if environment == "production" else "true").lower() == "true",
    )
