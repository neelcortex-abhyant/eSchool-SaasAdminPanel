"""Safe helpers for Neon PostgreSQL URL handling.

All runtime DB connections use NEON_DATABASE_URL (single Neon database).
Never log or return passwords from these helpers.
"""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def normalize_neon_database_url(url: str) -> str:
    """Ensure Neon URLs use the installed psycopg (v3) SQLAlchemy driver.

    Accepts both postgresql:// and postgresql+psycopg://.
    Rejects MySQL URLs — this project is PostgreSQL-only at runtime.
    """
    raw = (url or "").strip()
    if not raw:
        raise RuntimeError(
            "NEON_DATABASE_URL is not set. Configure Neon PostgreSQL for the backend."
        )

    lower = raw.lower()
    if lower.startswith("mysql:") or "+pymysql" in lower or "+mysql" in lower:
        raise RuntimeError(
            "NEON_DATABASE_URL must be a PostgreSQL URL. MySQL is no longer supported."
        )
    if lower.startswith("sqlite:"):
        raise RuntimeError(
            "SQLite is not supported at runtime. Set NEON_DATABASE_URL / TEST_DATABASE_URL "
            "to an isolated PostgreSQL database."
        )

    if lower.startswith("postgresql+psycopg://") or lower.startswith("postgres+psycopg://"):
        return raw

    if lower.startswith("postgresql://"):
        return "postgresql+psycopg://" + raw[len("postgresql://") :]
    if lower.startswith("postgres://"):
        return "postgresql+psycopg://" + raw[len("postgres://") :]

    raise RuntimeError(
        "NEON_DATABASE_URL must start with postgresql:// or postgresql+psycopg://."
    )


def safe_url_target(url: str) -> dict[str, str | None]:
    """Return non-secret connection target fields for diagnostics."""
    try:
        normalized = url.replace("postgresql+psycopg://", "postgresql://", 1)
        parsed = urlparse(normalized)
        return {
            "scheme": (parsed.scheme or None),
            "host": parsed.hostname,
            "port": str(parsed.port) if parsed.port else None,
            "database": (parsed.path or "/").lstrip("/") or None,
        }
    except Exception:
        return {"scheme": None, "host": None, "port": None, "database": None}


def replace_database_name(url: str, database_name: str) -> str:
    """Return a URL pointing at a different database on the same host (tests)."""
    normalized = normalize_neon_database_url(url)
    parseable = normalized.replace("postgresql+psycopg://", "postgresql://", 1)
    parsed = urlparse(parseable)
    new_path = "/" + database_name.lstrip("/")
    rebuilt = urlunparse(
        (parsed.scheme, parsed.netloc, new_path, parsed.params, parsed.query, parsed.fragment)
    )
    return normalize_neon_database_url(rebuilt)
