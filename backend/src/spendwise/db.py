"""Database engine and sessions. SQLite on a laptop, PostgreSQL in production: same code."""

from collections.abc import Iterator

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(conn, _):
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys = ON")  # SQLite ignores foreign keys unless asked
            cur.execute("PRAGMA journal_mode = WAL")  # readers don't block the writer
            cur.close()

        return engine
    return create_engine(url, pool_pre_ping=True)


_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = make_engine(get_settings().database_url)
    return _engine


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, closed afterwards."""
    with Session(get_engine()) as session:
        yield session


def create_tables(engine: Engine) -> None:
    """Tests and quick experiments only. Real databases are built by Alembic migrations."""
    from . import models  # noqa: F401  (registers the tables)

    SQLModel.metadata.create_all(engine)
