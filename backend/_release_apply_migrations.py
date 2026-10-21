"""Load .env and apply Alembic upgrade head to NEON_DATABASE_URL only.

Never prints URLs or credentials. Refuses test DB unless ALLOW_TEST_MIGRATIONS=1
is already set by the caller (this script does not set it).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from app.core.db_urls import normalize_neon_database_url, safe_url_target


def _load_dotenv() -> None:
    path = Path(__file__).resolve().parent / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        # Do not override an explicit shell export.
        if key and key not in os.environ:
            os.environ[key] = val


def main() -> int:
    _load_dotenv()
    if os.environ.get("ALLOW_TEST_MIGRATIONS", "").strip() == "1":
        print("REFUSING: ALLOW_TEST_MIGRATIONS=1 would redirect Alembic; unset it for app DB.")
        return 2

    url = (os.environ.get("NEON_DATABASE_URL") or "").strip()
    if not url:
        print("BLOCKED: NEON_DATABASE_URL unset")
        return 2

    target = safe_url_target(normalize_neon_database_url(url))
    db = target.get("database")
    print(f"APPLY_TARGET database={db!r} APP_ENV={os.environ.get('APP_ENV')!r}")
    if str(db).endswith("_test"):
        print("BLOCKED: refusing to migrate a *_test database via this script")
        return 2

    cfg = Config(str(Path(__file__).resolve().parent / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    engine = create_engine(normalize_neon_database_url(url), pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
        print(f"BEFORE_REVISION={current!r}")
        print(f"SCRIPT_HEADS={script.get_heads()}")
        if current == script.get_heads()[0]:
            print("ALREADY_AT_HEAD — nothing to apply")
            return 0

        command.upgrade(cfg, "head")

        with engine.connect() as conn:
            after = MigrationContext.configure(conn).get_current_revision()
            print(f"AFTER_REVISION={after!r}")
            for idx in (
                "uq_session_years_school_name_active",
                "uq_session_years_school_default_active",
                "uq_classes_school_medium_name_active",
                "uq_class_sections_school_class_section_active",
                "uq_subjects_school_medium_code_active",
                "uq_class_subjects_school_class_subject_active",
                "uq_teacher_assignments_active",
                "ix_class_sections_class_id",
                "ix_classes_medium_id",
                "ix_subjects_medium_id",
            ):
                exists = conn.execute(
                    text("SELECT 1 FROM pg_class WHERE relname=:n AND relkind='i'"),
                    {"n": idx},
                ).scalar()
                print(f"post_index_{idx}={bool(exists)}")
            for table in ("class_subjects", "teacher_assignments"):
                exists = conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema='public' AND table_name=:t"
                    ),
                    {"t": table},
                ).scalar()
                print(f"post_table_{table}={bool(exists)}")
    finally:
        engine.dispose()

    print("APPLY_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
