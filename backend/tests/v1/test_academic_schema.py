"""Phase 8: academic schema / Alembic graph consistency (DB-free checks)."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Index

from app.models.tables import (
    ClassSection,
    ClassSubject,
    SchoolClass,
    SessionYear,
    Subject,
    TeacherAssignment,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _script() -> ScriptDirectory:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    return ScriptDirectory.from_config(cfg)


def test_alembic_academic_revision_chain_is_linear():
    script = _script()
    heads = script.get_heads()
    assert heads == ["20261025_0038"], heads

    latest = script.get_revision("20261025_0038")
    assert latest is not None
    assert latest.down_revision == "20261024_0037"
    assert script.get_revision("20261024_0037").down_revision == "20261023_0036"
    assert script.get_revision("20261023_0036").down_revision == "20261023_0035"

    expected = [
        ("20261021_0022", "20261021_0021"),
        ("20261021_0021", "20261021_0020"),
        ("20261021_0020", "20261021_0019"),
        ("20261021_0019", "20261021_0018"),
        ("20261021_0018", "20261021_0017"),
        ("20261021_0017", "20261020_0016"),
    ]
    for revision, parent in expected:
        rev = script.get_revision(revision)
        assert rev is not None, revision
        assert rev.down_revision == parent, (revision, rev.down_revision)

def test_orm_unique_indexes_match_documented_migration_names():
    def names(model) -> set[str]:
        return {idx.name for idx in model.__table__.indexes if isinstance(idx, Index)}

    assert "uq_session_years_school_name_active" in names(SessionYear)
    assert "uq_session_years_school_default_active" in names(SessionYear)
    assert "uq_classes_school_medium_name_active" in names(SchoolClass)
    assert "ix_classes_medium_id" in names(SchoolClass)
    assert "uq_class_sections_school_class_section_active" in names(ClassSection)
    assert "ix_class_sections_class_id" in names(ClassSection)
    assert "ix_class_sections_section_id" in names(ClassSection)
    assert "uq_subjects_school_medium_code_active" in names(Subject)
    assert "ix_subjects_medium_id" in names(Subject)
    assert "uq_class_subjects_school_class_subject_active" in names(ClassSubject)
    assert "uq_teacher_assignments_active" in names(TeacherAssignment)


def test_teacher_assignment_unique_includes_staff_not_class_only():
    """Team-teaching: uniqueness includes staff_id so two teachers may share a section/subject."""
    idx = next(
        i for i in TeacherAssignment.__table__.indexes if i.name == "uq_teacher_assignments_active"
    )
    cols = [c.name if hasattr(c, "name") else str(c) for c in idx.columns]
    assert cols == [
        "school_id",
        "staff_id",
        "subject_id",
        "class_section_id",
        "session_year_id",
    ]
    assert idx.unique is True


def test_class_subject_and_assignment_fks_point_at_expected_tables():
    by_col = {fk.parent.name: fk.column.table.name for fk in ClassSubject.__table__.foreign_keys}
    assert by_col["school_id"] == "schools"
    assert by_col["class_id"] == "classes"
    assert by_col["subject_id"] == "subjects"

    ta = {fk.parent.name: fk.column.table.name for fk in TeacherAssignment.__table__.foreign_keys}
    assert ta["school_id"] == "schools"
    assert ta["staff_id"] == "staffs"
    assert ta["teacher_user_id"] == "users"
    assert ta["subject_id"] == "subjects"
    assert ta["class_section_id"] == "class_sections"
    assert ta["session_year_id"] == "session_years"


def test_legacy_academic_tables_remain_integer_scoped_without_school_fk():
    """Documented gap: legacy tables use school_id integers without DB FK to schools."""
    for model in (SessionYear, SchoolClass, ClassSection, Subject):
        fks = {fk.parent.name for fk in model.__table__.foreign_keys}
        assert "school_id" not in fks, model.__tablename__
