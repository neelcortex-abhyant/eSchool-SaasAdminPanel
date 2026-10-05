"""V1 session helpers — same Neon engine as legacy (app.core.database)."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import get_engine, reset_engines, session_factory


def v1_database_url() -> str:
    from app.core.database import database_url

    return database_url()


def get_v1_engine() -> Engine:
    return get_engine()


def get_v1_session_factory() -> sessionmaker[Session]:
    return session_factory()


def reset_v1_engine() -> None:
    reset_engines()


def get_v1_db() -> Generator[Session, None, None]:
    db = session_factory()()
    try:
        yield db
    finally:
        db.close()
