from __future__ import annotations

import pytest

from app.core.db_urls import normalize_neon_database_url, safe_url_target


def test_normalize_adds_psycopg_driver():
    url = normalize_neon_database_url(
        "postgresql://user:pass@ep-example.neon.tech/eschool_saas_v1?sslmode=require"
    )
    assert url.startswith("postgresql+psycopg://")
    assert "user:pass@" in url
    assert url.endswith("eschool_saas_v1?sslmode=require")


def test_normalize_keeps_psycopg_driver():
    raw = "postgresql+psycopg://user:pass@host/db?sslmode=require"
    assert normalize_neon_database_url(raw) == raw


def test_normalize_rejects_mysql():
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        normalize_neon_database_url("mysql+pymysql://user:pass@127.0.0.1:3307/eschool_central")


def test_normalize_rejects_sqlite():
    with pytest.raises(RuntimeError, match="SQLite"):
        normalize_neon_database_url("sqlite:///tmp/test.db")


def test_safe_url_target_omits_credentials():
    target = safe_url_target(
        "postgresql+psycopg://user:secret@ep-example.neon.tech/eschool_saas_v1?sslmode=require"
    )
    assert target["host"] == "ep-example.neon.tech"
    assert target["database"] == "eschool_saas_v1"
    assert "secret" not in str(target)
    assert "user" not in str(target)
