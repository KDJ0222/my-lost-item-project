from fastapi import Request
from pathlib import Path
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import get_settings

DATABASE_URL = get_settings().database_url
def make_engine(url: str) -> Engine:
    db_engine = create_engine(
        url, connect_args={"check_same_thread": False, "timeout":30} if url.startswith("sqlite") else {},
    )
    if db_engine.dialect.name == "sqlite":
        @event.listens_for(db_engine, "connect")
        def configure_sqlite(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=30000")
    return db_engine


engine = make_engine(DATABASE_URL)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def initialize_database(db_engine: Engine = engine):
    """Create tables and preserve rows in the original SQLite schema."""
    import models  # noqa: F401 -- register tables before create_all

    if db_engine.dialect.name == "sqlite" and db_engine.url.database not in (None, "", ":memory:"):
        Path(db_engine.url.database).resolve().parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=db_engine)
    if db_engine.dialect.name == "sqlite":
        with db_engine.begin() as connection:
            columns = {column["name"] for column in inspect(connection).get_columns("items")}
            if "contact" not in columns:
                connection.execute(text("ALTER TABLE items ADD COLUMN contact VARCHAR(200)"))
            if "event_date" not in columns:
                connection.execute(text("ALTER TABLE items ADD COLUMN event_date DATE"))
            if "owner_token_hash" not in columns:
                connection.execute(text("ALTER TABLE items ADD COLUMN owner_token_hash VARCHAR(64)"))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_items_owner_token_hash ON items (owner_token_hash)"
            ))


def get_db(request: Request):
    with request.app.state.session_factory() as db:
        yield db
