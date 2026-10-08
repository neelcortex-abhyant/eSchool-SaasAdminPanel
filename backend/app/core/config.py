from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings — single Neon PostgreSQL database for all APIs.

    NEON_DATABASE_URL is required for runtime. Legacy MySQL and SQLite are removed.
    School isolation is logical (school_id), not physical (separate databases).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "eSchool SaaS"
    app_env: str = "local"
    app_debug: bool = True
    # Comma-separated browser origins for admin + student web local/dev.
    frontend_origin: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://127.0.0.1:3001"
    )
    session_secret: str = "dev-session-secret"
    session_lifetime_minutes: int = 120
    log_level: str = "INFO"

    redis_url: str = "redis://127.0.0.1:6380/0"
    app_url: str = "https://eschool-saas.wrteam.me"
    # NEVER true in production. create_schema is unit-test only.
    allow_ddl: bool = False
    pool_size: int = 5
    max_overflow: int = 10

    # Single Neon PostgreSQL for /api/v1 + legacy /api/student|admin|...
    neon_database_url: str = ""
    # Optional isolated Postgres URL for pytest (never the live app DB).
    test_database_url: str = ""
    v1_session_ttl_minutes: int = 10080
    # If set, matching existing v1_users.email is promoted to super_admin on startup.
    # Does not create users; never accept role from public signup.
    v1_super_admin_email: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]

    @property
    def neon_configured(self) -> bool:
        return bool((self.neon_database_url or "").strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
