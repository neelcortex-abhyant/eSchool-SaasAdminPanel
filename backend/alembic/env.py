from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import MetaData, engine_from_config, pool

from app.core.database import Base
from app.models import tables  # noqa: F401
from app.models.v1 import AuthSession, User  # noqa: F401
from app.models.v1.base import V1Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Combine V1 + legacy metadata for autogenerate/support; migrations are explicit.
target_metadata = MetaData()
for md in (V1Base.metadata, Base.metadata):
    for table in md.tables.values():
        table.to_metadata(target_metadata)


def get_url() -> str:
    from app.core.db_urls import normalize_neon_database_url

    url = os.environ.get("NEON_DATABASE_URL", "").strip()
    # TEST_DATABASE_URL must NOT silently override live migrations.
    # Only honor it when explicitly opted in (pytest / intentional test runs).
    if os.environ.get("ALLOW_TEST_MIGRATIONS", "").strip() == "1":
        test_url = os.environ.get("TEST_DATABASE_URL", "").strip()
        if test_url:
            url = test_url
    if not url or url.startswith("driver://"):
        raise RuntimeError(
            "Set NEON_DATABASE_URL for Alembic (postgresql+psycopg://...?sslmode=require). "
            "For isolated test DB migrations set ALLOW_TEST_MIGRATIONS=1 and TEST_DATABASE_URL."
        )
    return normalize_neon_database_url(url)


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
