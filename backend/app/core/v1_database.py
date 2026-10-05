from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def v1_database_url() -> str:
    settings = get_settings()
    url = (settings.neon_database_url or "").strip()
    if not url:
        raise RuntimeError(
            "NEON_DATABASE_URL is not set. Configure Neon PostgreSQL for the /api/v1 slice."
        )
    return url


def get_v1_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        url = v1_database_url()
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        kwargs: dict = {"pool_pre_ping": True, "connect_args": connect_args}
        if not url.startswith("sqlite"):
            settings = get_settings()
            kwargs["pool_size"] = settings.pool_size
            kwargs["max_overflow"] = settings.max_overflow
        _engine = create_engine(url, **kwargs)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_v1_session_factory() -> sessionmaker[Session]:
    get_v1_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def reset_v1_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_v1_db() -> Generator[Session, None, None]:
    db = get_v1_session_factory()()
    try:
        yield db
    finally:
        db.close()
