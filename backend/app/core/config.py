from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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

    # Production must use mysql. sqlite is for isolated unit tests only.
    db_connection: str = "mysql"
    sqlite_dir: str = "./data"
    db_host: str = "127.0.0.1"
    db_port: int = 3307
    db_database: str = "eschool_central"
    db_username: str = "eschool"
    db_password: str = "eschool"

    redis_url: str = "redis://127.0.0.1:6380/0"
    app_url: str = "https://eschool-saas.wrteam.me"
    # NEVER true in production. create_schema is unit-test only.
    allow_ddl: bool = False
    pool_size: int = 5
    max_overflow: int = 10

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]

    def sqlalchemy_url(self, database_name: str | None = None) -> str:
        if self.db_connection == "sqlite":
            from pathlib import Path

            root = Path(self.sqlite_dir)
            root.mkdir(parents=True, exist_ok=True)
            name = database_name or self.db_database
            return f"sqlite:///{root / f'{name}.db'}"
        name = database_name or self.db_database
        return (
            f"mysql+pymysql://{self.db_username}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
