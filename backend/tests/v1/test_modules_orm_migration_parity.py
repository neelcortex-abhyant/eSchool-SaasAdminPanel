"""Modules 1–6 ORM ↔ Alembic DDL parity (DB-free metadata checks).

Does not import app conftest wipe/create_all paths. Run with::

    pytest --noconftest -p no:cacheprovider tests/v1/test_modules_orm_migration_parity.py
"""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Index
from sqlalchemy.sql.schema import DefaultClause

from app.models.tables import (
    Homework,
    HomeworkSubmission,
    OfflineExamMark,
    OfflineExamResult,
    OfflineExamSchedule,
    OnlineAssessment,
    OnlineAssessmentAnswer,
    OnlineAssessmentAttempt,
    OnlineAssessmentChoice,
    OnlineAssessmentQuestion,
    School,
    StudyMaterial,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _index_names(model) -> set[str]:
    return {idx.name for idx in model.__table__.indexes if isinstance(idx, Index)}


def _server_default_text(model, column: str) -> str | None:
    col = model.__table__.c[column]
    default = col.server_default
    if default is None:
        return None
    if isinstance(default, DefaultClause):
        arg = default.arg
        if hasattr(arg, "text"):
            return str(arg.text)
        return str(arg)
    return str(default)


def test_offline_exam_schedule_staff_id_index_matches_0036_name():
    """index=True → ix_<table>_<col>; must match migration 20261023_0036."""
    names = _index_names(OfflineExamSchedule)
    assert "ix_offline_exam_schedules_staff_id" in names
    # Single index on staff_id only (no duplicate explicit Index + index=True).
    staff_indexes = [
        idx
        for idx in OfflineExamSchedule.__table__.indexes
        if list(idx.columns.keys()) == ["staff_id"]
    ]
    assert len(staff_indexes) == 1
    assert staff_indexes[0].name == "ix_offline_exam_schedules_staff_id"


def test_online_assessment_answer_choice_id_index_matches_0035_name():
    names = _index_names(OnlineAssessmentAnswer)
    assert "ix_online_assessment_answers_choice_id" in names
    choice_indexes = [
        idx
        for idx in OnlineAssessmentAnswer.__table__.indexes
        if list(idx.columns.keys()) == ["choice_id"]
    ]
    assert len(choice_indexes) == 1
    assert choice_indexes[0].name == "ix_online_assessment_answers_choice_id"


def test_module3_server_defaults_match_0033():
    assert _server_default_text(Homework, "allow_late") == "1"
    assert _server_default_text(HomeworkSubmission, "status") == "submitted"
    assert _server_default_text(HomeworkSubmission, "is_late") == "0"


def test_module4_study_materials_have_no_orm_server_defaults():
    """Migration 0034 specifies no column server defaults — ORM must not invent any."""
    for col in StudyMaterial.__table__.columns:
        assert col.server_default is None, col.name


def test_module5_server_defaults_match_0035():
    assert _server_default_text(OnlineAssessment, "status") == "draft"
    assert _server_default_text(OnlineAssessment, "results_published") == "0"
    assert _server_default_text(OnlineAssessmentQuestion, "question_type") == "mcq"
    assert _server_default_text(OnlineAssessmentQuestion, "sort_order") == "0"
    assert _server_default_text(OnlineAssessmentQuestion, "version") == "1"
    assert _server_default_text(OnlineAssessmentChoice, "is_correct") == "0"
    assert _server_default_text(OnlineAssessmentChoice, "sort_order") == "0"
    assert _server_default_text(OnlineAssessmentAttempt, "status") == "in_progress"


def test_module6_server_defaults_match_0036():
    assert _server_default_text(OfflineExamMark, "status") == "present"
    assert _server_default_text(OfflineExamResult, "total_max_marks") == "0"
    assert _server_default_text(OfflineExamResult, "total_obtained") == "0"
    assert _server_default_text(OfflineExamResult, "percentage") == "0"
    assert _server_default_text(OfflineExamResult, "passed") == "0"


def test_modules_revision_chain_0032_through_0038_is_linear():
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    expected = [
        ("20261023_0032", "20261022_0031"),
        ("20261023_0033", "20261023_0032"),
        ("20261023_0034", "20261023_0033"),
        ("20261023_0035", "20261023_0034"),
        ("20261023_0036", "20261023_0035"),
        ("20261024_0037", "20261023_0036"),
        ("20261025_0038", "20261024_0037"),
        ("20261027_0039", "20261025_0038"),
        ("20261028_0040", "20261027_0039"),
        ("20261029_0041", "20261028_0040"),
    ]
    for revision, parent in expected:
        rev = script.get_revision(revision)
        assert rev is not None, revision
        assert rev.down_revision == parent, (revision, rev.down_revision)
    assert script.get_heads() == ["20261029_0041"]


def test_school_domain_columns_match_migration_0038():
    """ORM expects schools.domain_type / domain_verified / school_website (Alembic 0038).

    Login loads School via assert_school_admin_login_allowed; missing DB columns → 500.
    """
    cols = School.__table__.c
    assert "domain_type" in cols
    assert cols.domain_type.type.length == 16
    assert cols.domain_type.nullable is True

    assert "domain_verified" in cols
    assert _server_default_text(School, "domain_verified") == "0"
    assert cols.domain_verified.nullable is False

    assert "school_website" in cols
    assert cols.school_website.type.length == 512
    assert _server_default_text(School, "school_website") == ""
    assert cols.school_website.nullable is False

    assert "ix_schools_domain_nonblank" in _index_names(School)

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    rev = script.get_revision("20261025_0038")
    assert rev is not None
    assert rev.down_revision == "20261024_0037"
    # Migration module must add the same three columns (source inspection).
    path = Path(rev.path)
    text = path.read_text(encoding="utf-8")
    assert 'add_column(\n        "schools"' in text or 'add_column("schools"' in text or "schools" in text
    assert "school_website" in text and "domain_type" in text and "domain_verified" in text
    assert "ix_schools_domain_nonblank" in text
    assert "op.drop_table" not in text
    assert "DROP TABLE" not in text.upper()
