"""Safe DB identity probe — prints names/kinds only, never URLs or credentials."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from app.core.db_urls import normalize_neon_database_url, safe_url_target
from tests.pg_test_utils import resolve_test_database_url


def _dotenv() -> dict[str, str]:
    path = Path(__file__).resolve().parent / ".env"
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def _meta(label: str, url: str | None) -> dict:
    if not url:
        print(f"{label}: UNSET")
        return {}
    target = safe_url_target(normalize_neon_database_url(url))
    db = target.get("database")
    host = target.get("host") or ""
    if host in ("localhost", "127.0.0.1"):
        host_kind = "localhost"
    elif "neon" in host.lower():
        host_kind = "neon"
    else:
        host_kind = "remote"
    print(
        f"{label}: database={db!r} host_kind={host_kind} "
        f"ends_with_test={str(db).endswith('_test') if db else None}"
    )
    return {"database": db, "host_kind": host_kind}


def main() -> None:
    dotenv = _dotenv()
    neon = (os.environ.get("NEON_DATABASE_URL") or dotenv.get("NEON_DATABASE_URL") or "").strip()
    test_explicit = (
        os.environ.get("TEST_DATABASE_URL") or dotenv.get("TEST_DATABASE_URL") or ""
    ).strip()
    test_resolved = resolve_test_database_url()

    neon_m = _meta("ALEMBIC_TARGET(NEON_DATABASE_URL)", neon or None)
    _meta("TEST_EXPLICIT(TEST_DATABASE_URL)", test_explicit or None)
    test_m = _meta("TEST_RESOLVED", test_resolved)

    same = neon_m.get("database") and neon_m.get("database") == test_m.get("database")
    print(f"TEST_SAME_NAME_AS_ALEMBIC_TARGET={bool(same)}")
    print(f"WIPE_SCHEMA_USED_BY_PYTEST=yes (DROP SCHEMA public CASCADE)")

    # Alembic current revision on NEON target (migration target)
    if not neon:
        print("ALEMBIC_CURRENT: BLOCKED (NEON_DATABASE_URL unset)")
        return

    engine = create_engine(normalize_neon_database_url(neon), pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current = context.get_current_revision()
            print(f"ALEMBIC_CURRENT_REVISION={current!r}")
            # existence of alembic_version + sample academic tables
            tables = conn.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                    "AND tablename IN ('alembic_version','class_subjects',"
                    "'teacher_assignments','session_years','classes','subjects')"
                    " ORDER BY 1"
                )
            ).fetchall()
            print("PUBLIC_TABLES_SAMPLE=", [r[0] for r in tables])
            # row counts (safe aggregates only)
            for table in ("session_years", "classes", "subjects", "class_sections"):
                exists = conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema='public' AND table_name=:t"
                    ),
                    {"t": table},
                ).scalar()
                if exists:
                    n = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
                    print(f"COUNT_{table}={n}")
    finally:
        engine.dispose()

    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    print(f"SCRIPT_HEADS={script.get_heads()}")


if __name__ == "__main__":
    main()
