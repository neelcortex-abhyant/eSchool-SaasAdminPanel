from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

_engines: dict[str, object] = {}


class Base(DeclarativeBase):
    pass


def reset_engines() -> None:
    for engine in list(_engines.values()):
        engine.dispose()
    _engines.clear()


def get_engine(database_name: str | None = None):
    settings = get_settings()
    url = settings.sqlalchemy_url(database_name)
    engine = _engines.get(url)
    if engine is None:
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        kwargs = {"pool_pre_ping": True, "connect_args": connect_args}
        if not url.startswith("sqlite"):
            kwargs["pool_size"] = settings.pool_size
            kwargs["max_overflow"] = settings.max_overflow
        engine = create_engine(url, **kwargs)
        _engines[url] = engine
    return engine


def session_factory(database_name: str | None = None):
    return sessionmaker(bind=get_engine(database_name), autoflush=False, expire_on_commit=False)


def create_schema(database_name: str | None = None) -> None:
    """Unit-test helper only. Hard-blocked unless allow_ddl=True and not production."""
    settings = get_settings()
    if not settings.allow_ddl:
        raise RuntimeError("create_schema is disabled (allow_ddl=false). Use MySQL migrations.")
    if settings.app_env == "production":
        raise RuntimeError("create_schema must never run in production")
    from app.models import tables  # noqa: F401

    Base.metadata.create_all(get_engine(database_name))
