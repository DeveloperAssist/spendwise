"""Alembic: versioned changes to the database schema (like git, for tables)."""

from alembic import context
from sqlalchemy import create_engine, pool
from sqlmodel import SQLModel

from spendwise import models  # noqa: F401  (registers every table on SQLModel.metadata)
from spendwise.config import get_settings

url = context.config.get_main_option("sqlalchemy.url") or get_settings().database_url
target_metadata = SQLModel.metadata


def run_offline() -> None:
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True, render_as_batch=url.startswith("sqlite")
    )
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        # SQLite can't ALTER most things in place: "batch" mode rebuilds the table instead
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=url.startswith("sqlite")
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
