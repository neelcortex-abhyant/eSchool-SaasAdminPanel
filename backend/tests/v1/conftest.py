from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Configure before app/settings import.
_V1_DB = Path(__file__).resolve().parent / "tmp-data" / "v1_test.db"
_V1_DB.parent.mkdir(parents=True, exist_ok=True)
os.environ["NEON_DATABASE_URL"] = f"sqlite:///{_V1_DB.as_posix()}"
os.environ.setdefault("DB_CONNECTION", "sqlite")
os.environ.setdefault("SQLITE_DIR", str(Path(__file__).resolve().parent.parent / "tmp-data"))
os.environ.setdefault("DB_DATABASE", "laravel")
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("ALLOW_DDL", "true")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("V1_SESSION_TTL_MINUTES", "10080")

from app.core.config import get_settings
from app.core.database import reset_engines
from app.core.v1_database import get_v1_engine, reset_v1_engine
from app.models.v1 import AuthSession, User  # noqa: F401
from app.models.v1.base import V1Base


@pytest.fixture()
def v1_client():
    get_settings.cache_clear()
    reset_v1_engine()
    reset_engines()
    if _V1_DB.exists():
        try:
            _V1_DB.unlink()
        except PermissionError:
            reset_v1_engine()
            _V1_DB.unlink()
    engine = get_v1_engine()
    V1Base.metadata.create_all(bind=engine)

    from app.main import app

    with TestClient(app) as client:
        yield client

    reset_v1_engine()
    reset_engines()
    if _V1_DB.exists():
        try:
            _V1_DB.unlink()
        except PermissionError:
            pass
    get_settings.cache_clear()


@pytest.fixture()
def v1_db(v1_client):
    """Direct DB session against the same SQLite file used by the app."""
    from app.core.v1_database import get_v1_session_factory

    db = get_v1_session_factory()()
    try:
        yield db
    finally:
        db.close()
