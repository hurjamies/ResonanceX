"""Alembic environment. Runs with a connection supplied by app.database.migrate."""

from __future__ import annotations

from alembic import context
from sqlmodel import SQLModel

from app import models  # noqa: F401 - register tables

target_metadata = SQLModel.metadata


def run() -> None:
    connectable = context.config.attributes.get("connection")
    if connectable is None:
        from app.database.session import get_engine

        with get_engine().connect() as connection:
            _configure(connection)
    else:
        _configure(connectable)


def _configure(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


run()
