"""Shared pytest helpers for isolated PostgreSQL (never the live app DB)."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import create_engine, text

from app.core.db_urls import normalize_neon_database_url, replace_database_name, safe_url_target


def _load_dotenv_values() -> dict[str, str]:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip()] = val.strip()
    return values


def resolve_test_database_url() -> str:
    """Return isolated Postgres URL for tests.

    Prefer TEST_DATABASE_URL. If unset, derive ``eschool_saas_test`` from
    NEON_DATABASE_URL on the same host (still isolated from the live app DB name).
    """
    dotenv = _load_dotenv_values()
    explicit = (os.environ.get("TEST_DATABASE_URL") or dotenv.get("TEST_DATABASE_URL") or "").strip()
    if explicit:
        url = normalize_neon_database_url(explicit)
    else:
        neon = (os.environ.get("NEON_DATABASE_URL") or dotenv.get("NEON_DATABASE_URL") or "").strip()
        if not neon:
            raise RuntimeError(
                "Set TEST_DATABASE_URL (or NEON_DATABASE_URL to derive eschool_saas_test). "
                "Do not run pytest against the live app database."
            )
        url = replace_database_name(neon, "eschool_saas_test")

    target = safe_url_target(url)
    live = safe_url_target(
        normalize_neon_database_url(
            (os.environ.get("NEON_DATABASE_URL") or dotenv.get("NEON_DATABASE_URL") or url)
        )
    )
    if target.get("database") and live.get("database") and target["database"] == live["database"]:
        # Only block when both resolve to the same DB name AND caller did not
        # explicitly set a different TEST URL pointing at a dedicated test DB.
        if not (os.environ.get("ALLOW_LIVE_DB_TESTS") == "1"):
            if (target.get("database") or "").endswith("_test"):
                pass
            else:
                raise RuntimeError(
                    f"Refusing to run tests against live database {target.get('database')!r}. "
                    "Set TEST_DATABASE_URL to an isolated Postgres database (name ending _test)."
                )
    return url


def ensure_postgres_database(url: str) -> None:
    """Create the target database on the Neon/Postgres host if missing."""
    normalized = normalize_neon_database_url(url)
    target = safe_url_target(normalized)
    db_name = target.get("database")
    if not db_name:
        raise RuntimeError("TEST_DATABASE_URL missing database name")

    parseable = normalized.replace("postgresql+psycopg://", "postgresql://", 1)
    parsed = urlparse(parseable)
    # Connect to the default maintenance DB on the same host.
    admin_url = replace_database_name(normalized, "postgres")
    try:
        admin = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"),
                {"n": db_name},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
        admin.dispose()
    except Exception:
        # Neon may not allow connecting to "postgres"; try neondb.
        admin_url = replace_database_name(normalized, "neondb")
        admin = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"),
                {"n": db_name},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
        admin.dispose()


def wipe_public_schema(url: str) -> None:
    engine = create_engine(normalize_neon_database_url(url), pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
    engine.dispose()
