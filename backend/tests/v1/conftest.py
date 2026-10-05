from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from tests.pg_test_utils import ensure_postgres_database, resolve_test_database_url, wipe_public_schema

_TEST_URL = resolve_test_database_url()
os.environ["TEST_DATABASE_URL"] = _TEST_URL
os.environ["NEON_DATABASE_URL"] = _TEST_URL
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("ALLOW_DDL", "true")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("V1_SESSION_TTL_MINUTES", "10080")

ensure_postgres_database(_TEST_URL)

from app.core.config import get_settings
from app.core.database import create_schema, reset_engines
from app.core.v1_database import reset_v1_engine


@pytest.fixture()
def v1_client():
    get_settings.cache_clear()
    reset_v1_engine()
    reset_engines()
    wipe_public_schema(_TEST_URL)
    create_schema()

    from app.main import app

    with TestClient(app) as client:
        yield client

    reset_v1_engine()
    reset_engines()
    get_settings.cache_clear()


@pytest.fixture()
def v1_db(v1_client):
    from app.core.v1_database import get_v1_session_factory

    db = get_v1_session_factory()()
    try:
        yield db
    finally:
        db.close()
