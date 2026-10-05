"""Single Neon PostgreSQL engine for the entire backend.

Legacy /api/student|admin|* and /api/v1 share this engine.
School isolation is enforced via school_id filters — never via separate databases.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings
from app.core.db_urls import normalize_neon_database_url

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


class Base(DeclarativeBase):
    """Legacy Laravel-compatible ORM metadata (school-scoped tables)."""


def database_url() -> str:
    settings = get_settings()
    return normalize_neon_database_url(settings.neon_database_url)


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        url = database_url()
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=settings.pool_size,
            max_overflow=settings.max_overflow,
        )
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def reset_engines() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_db() -> Generator[Session, None, None]:
    db = session_factory()()
    try:
        yield db
    finally:
        db.close()


def create_schema() -> None:
    """Unit-test helper only. Hard-blocked unless allow_ddl=True and not production."""
    settings = get_settings()
    if not settings.allow_ddl:
        raise RuntimeError("create_schema is disabled (allow_ddl=false). Use Alembic migrations.")
    if settings.app_env == "production":
        raise RuntimeError("create_schema must never run in production")
    from app.models import tables  # noqa: F401
    from app.models.v1 import AuthSession, User  # noqa: F401
    from app.models.v1.base import V1Base

    engine = get_engine()
    Base.metadata.create_all(engine)
    V1Base.metadata.create_all(engine)
