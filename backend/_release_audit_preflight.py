"""Read-only preflight for academic unique indexes (0017–0022). Safe IDs/counts only."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, text

from app.core.db_urls import normalize_neon_database_url, safe_url_target


def _neon_url() -> str:
    dotenv: dict[str, str] = {}
    path = Path(__file__).resolve().parent / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            dotenv[k.strip()] = v.strip().strip('"').strip("'")
    url = (os.environ.get("NEON_DATABASE_URL") or dotenv.get("NEON_DATABASE_URL") or "").strip()
    if not url:
        raise SystemExit("NEON_DATABASE_URL unset — cannot preflight")
    return normalize_neon_database_url(url)


CHECKS = [
    (
        "dup_session_names",
        """
        SELECT school_id, lower(btrim(name)) AS n, COUNT(*) AS c,
               array_agg(id ORDER BY id) AS ids
        FROM session_years
        WHERE deleted_at IS NULL
        GROUP BY school_id, lower(btrim(name))
        HAVING COUNT(*) > 1
        """,
    ),
    (
        "multi_default_sessions",
        """
        SELECT school_id, COUNT(*) AS c, array_agg(id ORDER BY id) AS ids
        FROM session_years
        WHERE deleted_at IS NULL AND "default" = 1
        GROUP BY school_id
        HAVING COUNT(*) > 1
        """,
    ),
    (
        "dup_class_names",
        """
        SELECT school_id, medium_id, lower(btrim(name)) AS n, COUNT(*) AS c,
               array_agg(id ORDER BY id) AS ids
        FROM classes
        WHERE deleted_at IS NULL
        GROUP BY school_id, medium_id, lower(btrim(name))
        HAVING COUNT(*) > 1
        """,
    ),
    (
        "dup_subject_codes",
        """
        SELECT school_id, medium_id, lower(btrim(code)) AS n, COUNT(*) AS c,
               array_agg(id ORDER BY id) AS ids
        FROM subjects
        WHERE deleted_at IS NULL AND code IS NOT NULL AND btrim(code) <> ''
        GROUP BY school_id, medium_id, lower(btrim(code))
        HAVING COUNT(*) > 1
        """,
    ),
    (
        "dup_class_sections",
        """
        SELECT school_id, class_id, section_id, COUNT(*) AS c,
               array_agg(id ORDER BY id) AS ids
        FROM class_sections
        WHERE deleted_at IS NULL
        GROUP BY school_id, class_id, section_id
        HAVING COUNT(*) > 1
        """,
    ),
]


OPTIONAL_CHECKS = [
    (
        "dup_class_subjects",
        "class_subjects",
        """
        SELECT school_id, class_id, subject_id, COUNT(*) AS c,
               array_agg(id ORDER BY id) AS ids
        FROM class_subjects
        WHERE deleted_at IS NULL
        GROUP BY school_id, class_id, subject_id
        HAVING COUNT(*) > 1
        """,
    ),
    (
        "dup_teacher_assignments",
        "teacher_assignments",
        """
        SELECT school_id, staff_id, subject_id, class_section_id, session_year_id,
               COUNT(*) AS c, array_agg(id ORDER BY id) AS ids
        FROM teacher_assignments
        WHERE deleted_at IS NULL
        GROUP BY school_id, staff_id, subject_id, class_section_id, session_year_id
        HAVING COUNT(*) > 1
        """,
    ),
]


def main() -> None:
    url = _neon_url()
    target = safe_url_target(url)
    print(f"PREFLIGHT_TARGET database={target.get('database')!r}")
    engine = create_engine(url, pool_pre_ping=True)
    conflicts = 0
    try:
        with engine.connect() as conn:
            for name, sql in CHECKS:
                rows = conn.execute(text(sql)).mappings().all()
                print(f"{name}: conflict_groups={len(rows)}")
                for row in rows[:20]:
                    print(f"  ids={list(row['ids'])} count={row['c']}")
                    conflicts += 1
            for name, table, sql in OPTIONAL_CHECKS:
                exists = conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema='public' AND table_name=:t"
                    ),
                    {"t": table},
                ).scalar()
                if not exists:
                    print(f"{name}: SKIP (table absent — expected before 0017)")
                    continue
                rows = conn.execute(text(sql)).mappings().all()
                print(f"{name}: conflict_groups={len(rows)}")
                for row in rows[:20]:
                    print(f"  ids={list(row['ids'])} count={row['c']}")
                    conflicts += 1
            # existing index name collisions for pending migrations
            for idx in (
                "uq_session_years_school_name_active",
                "uq_session_years_school_default_active",
                "uq_classes_school_medium_name_active",
                "uq_class_sections_school_class_section_active",
                "uq_subjects_school_medium_code_active",
                "uq_class_subjects_school_class_subject_active",
                "uq_teacher_assignments_active",
                "class_subjects",
                "teacher_assignments",
            ):
                if idx in ("class_subjects", "teacher_assignments"):
                    exists = conn.execute(
                        text(
                            "SELECT 1 FROM information_schema.tables "
                            "WHERE table_schema='public' AND table_name=:t"
                        ),
                        {"t": idx},
                    ).scalar()
                    print(f"table_exists_{idx}={bool(exists)}")
                else:
                    exists = conn.execute(
                        text("SELECT 1 FROM pg_class WHERE relname=:n AND relkind='i'"),
                        {"n": idx},
                    ).scalar()
                    print(f"index_exists_{idx}={bool(exists)}")
            lookup_indexes = (
                "ix_class_sections_class_id",
                "ix_class_sections_section_id",
                "ix_class_sections_medium_id",
                "ix_classes_medium_id",
                "ix_subjects_medium_id",
            )
            for idx in lookup_indexes:
                exists = conn.execute(
                    text("SELECT 1 FROM pg_class WHERE relname=:n AND relkind='i'"),
                    {"n": idx},
                ).scalar()
                print(f"index_exists_{idx}={bool(exists)}")
                if exists:
                    conflicts += 1  # 0022 would fail on duplicate name
            for table in ("staffs", "users", "schools", "class_sections", "mediums"):
                exists = conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema='public' AND table_name=:t"
                    ),
                    {"t": table},
                ).scalar()
                print(f"fk_parent_table_{table}={bool(exists)}")
    finally:
        engine.dispose()
    print(f"TOTAL_CONFLICT_GROUPS={conflicts}")
    print("PREFLIGHT_OK" if conflicts == 0 else "PREFLIGHT_BLOCKED")


if __name__ == "__main__":
    main()
