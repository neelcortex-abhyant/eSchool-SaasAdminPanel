from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.models.v1 import AuthSession, User  # noqa: F401
from app.models.v1.base import V1Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = V1Base.metadata


def get_url() -> str:
    url = os.environ.get("NEON_DATABASE_URL", "").strip()
    if not url:
        url = config.get_main_option("sqlalchemy.url") or ""
    if not url or url.startswith("driver://"):
        raise RuntimeError(
            "Set NEON_DATABASE_URL for Alembic (postgresql+psycopg://...?sslmode=require)."
        )
    return url


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
