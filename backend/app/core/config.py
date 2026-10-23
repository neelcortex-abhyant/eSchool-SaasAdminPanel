from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr
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

    # Razorpay. One deployment uses one key pair: test processes use rzp_test_
    # key ids, and production uses rzp_live_. The secret and webhook secret stay
    # on the server. Order creation does not read the webhook secret.
    razorpay_key_id: str = ""
    razorpay_key_secret: SecretStr = SecretStr("")
    razorpay_webhook_secret: SecretStr = SecretStr("")
    razorpay_currency: str = "INR"

    # Outgoing mail for School Admin invitations and password resets. Mail is
    # only sent when smtp_host, smtp_from and admin_reset_url are all set.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = ""
    # STARTTLS on smtp_port (587). Set smtp_use_ssl for implicit TLS (465) instead.
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    # Admin panel page that accepts ?token=. Never taken from the client request.
    admin_reset_url: str = ""
    password_reset_ttl_minutes: int = 60
    invite_ttl_minutes: int = 4320

    # Teacher/staff private document storage. Default ``none`` → uploads return 503
    # until backend=local and DOCUMENT_STORAGE_PATH point at a private directory.
    document_storage_backend: str = "none"
    document_storage_path: str = ""
    document_max_image_bytes: int = 5_242_880
    document_max_file_bytes: int = 10_485_760

    @property
    def mail_configured(self) -> bool:
        return bool(self.smtp_host.strip() and self.smtp_from.strip() and self.admin_reset_url.strip())

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]

    @property
    def neon_configured(self) -> bool:
        return bool((self.neon_database_url or "").strip())

    @property
    def document_storage_configured(self) -> bool:
        backend = (self.document_storage_backend or "").strip().lower()
        path = (self.document_storage_path or "").strip()
        return backend == "local" and bool(path)


@lru_cache
def get_settings() -> Settings:
    return Settings()
