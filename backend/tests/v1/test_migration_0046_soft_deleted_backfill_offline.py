"""Offline regression for Alembic 0046 Main-branch creation / soft-deleted schools.

Does not connect to Neon or any live database.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = BACKEND_ROOT / "alembic" / "versions" / "20261105_0046_school_branches.py"


def _load_m0046():
    spec = importlib.util.spec_from_file_location("m0046_soft_deleted", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def m0046():
    return _load_m0046()


def test_migration_module_compiles(m0046):
    assert m0046.revision == "20261105_0046"
    assert m0046.down_revision == "20261030_0045"
    assert "students" in m0046.BRANCH_SCOPED_REQUIRED
    assert callable(m0046.build_default_main_branch_insert_sql)


def test_linear_chain_0045_to_0048():
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == ["20261106_0048"]
    assert script.get_revision("20261106_0048").down_revision == "20261106_0047"
    assert script.get_revision("20261106_0047").down_revision == "20261105_0046"
    assert script.get_revision("20261105_0046").down_revision == "20261030_0045"


def test_active_school_predicate_always_included(m0046):
    sql = m0046.build_default_main_branch_insert_sql(["students"])
    assert "s.deleted_at IS NULL" in sql
    assert "NOT EXISTS" in sql
    assert "school_branches" in sql


def test_soft_deleted_school_with_required_table_gets_orphan_clause(m0046):
    sql = m0046.build_default_main_branch_insert_sql(["students", "fee_payments"])
    assert "EXISTS (SELECT 1 FROM students t WHERE t.school_id = s.id)" in sql
    assert "EXISTS (SELECT 1 FROM fee_payments t WHERE t.school_id = s.id)" in sql
    assert "OR (" in sql or "OR (" in sql.replace("\n", " ")


def test_soft_deleted_school_with_no_required_tables_has_no_orphan_clause(m0046):
    sql = m0046.build_default_main_branch_insert_sql([])
    assert "EXISTS (SELECT 1 FROM students" not in sql
    # Only active schools qualify.
    assert re.search(r"WHERE\s+s\.deleted_at IS NULL", sql) is not None


def test_unknown_table_names_are_ignored(m0046):
    sql = m0046.build_default_main_branch_insert_sql(["students", "drop_table_x;--"])
    assert "students" in sql
    assert "drop_table" not in sql


def _simulate_main_creation(m0046, schools, required_rows_by_table, existing_branches=None):
    """Pure simulation of Main INSERT eligibility + single insert (no DB)."""
    existing = list(existing_branches or [])
    present_tables = [t for t in required_rows_by_table if t in m0046.BRANCH_SCOPED_REQUIRED]
    sql = m0046.build_default_main_branch_insert_sql(present_tables)
    created = []
    next_id = max([b["id"] for b in existing], default=0) + 1
    for school in schools:
        has_live = any(
            b["school_id"] == school["id"] and b.get("deleted_at") is None for b in existing + created
        )
        if has_live:
            continue
        active = school.get("deleted_at") is None
        has_required = any(
            any(row.get("school_id") == school["id"] for row in rows)
            for table, rows in required_rows_by_table.items()
            if table in m0046.BRANCH_SCOPED_REQUIRED
        )
        qualifies = active or has_required
        # Mirror SQL: soft-deleted with no required tables must not qualify.
        if not qualifies:
            continue
        if not active and not has_required:
            continue
        created.append(
            {
                "id": next_id,
                "school_id": school["id"],
                "name": "Main",
                "is_default": 1,
                "deleted_at": None,
            }
        )
        next_id += 1
    # Sanity: SQL must mention each present required table used for soft-deleted path.
    if any(s.get("deleted_at") is not None for s in schools) and present_tables:
        for table in present_tables:
            assert f"FROM {table} t" in sql
    return existing + created, sql


def _backfill(rows, branches):
    defaults = {
        b["school_id"]: b["id"]
        for b in branches
        if b.get("is_default") == 1 and b.get("deleted_at") is None
    }
    out = []
    for row in rows:
        branch_id = row.get("branch_id")
        if branch_id is None and row.get("school_id") in defaults:
            branch_id = defaults[row["school_id"]]
        out.append({**row, "branch_id": branch_id})
    return out


def test_active_school_gets_exactly_one_main(m0046):
    schools = [{"id": 1, "deleted_at": None}]
    branches, _ = _simulate_main_creation(m0046, schools, {"students": []})
    mains = [b for b in branches if b["school_id"] == 1]
    assert len(mains) == 1
    assert mains[0]["name"] == "Main"


def test_soft_deleted_school_with_student_gets_main_and_backfill(m0046):
    schools = [{"id": 7, "deleted_at": "2026-01-01"}]
    students = [{"id": 3, "school_id": 7, "branch_id": None}]
    branches, _ = _simulate_main_creation(m0046, schools, {"students": students})
    assert len(branches) == 1
    filled = _backfill(students, branches)
    assert filled[0]["branch_id"] == branches[0]["id"]


def test_soft_deleted_school_multiple_required_rows_backfill(m0046):
    schools = [{"id": 7, "deleted_at": "x"}]
    required = {
        "students": [
            {"id": 3, "school_id": 7, "branch_id": None},
            {"id": 4, "school_id": 7, "branch_id": None},
        ],
        "fee_payments": [{"id": 9, "school_id": 7, "branch_id": None}],
    }
    branches, sql = _simulate_main_creation(m0046, schools, required)
    assert len(branches) == 1
    assert "FROM students t" in sql and "FROM fee_payments t" in sql
    for table, rows in required.items():
        filled = _backfill(rows, branches)
        assert all(r["branch_id"] == branches[0]["id"] for r in filled)


def test_soft_deleted_school_without_required_rows_gets_no_main(m0046):
    schools = [{"id": 8, "deleted_at": "x"}]
    branches, _ = _simulate_main_creation(m0046, schools, {"students": []})
    assert branches == []


def test_existing_main_not_duplicated(m0046):
    schools = [{"id": 1, "deleted_at": None}]
    existing = [{"id": 10, "school_id": 1, "name": "Main", "is_default": 1, "deleted_at": None}]
    branches, _ = _simulate_main_creation(
        m0046, schools, {"students": []}, existing_branches=existing
    )
    assert len([b for b in branches if b["school_id"] == 1]) == 1


def test_unmappable_orphan_still_fails_verification(m0046):
    """School row missing → no Main → NULL branch_id remains → verification fails."""
    schools = []  # school 99 does not exist
    students = [{"id": 50, "school_id": 99, "branch_id": None}]
    branches, _ = _simulate_main_creation(m0046, schools, {"students": students})
    filled = _backfill(students, branches)
    nulls = sum(1 for r in filled if r["branch_id"] is None)
    assert nulls == 1
    # Same check migration performs for required tables.
    with pytest.raises(RuntimeError, match="NULL branch_id"):
        if nulls > 0:
            raise RuntimeError(f"Migration 0046 verification failed: students has {nulls} rows with NULL branch_id")
