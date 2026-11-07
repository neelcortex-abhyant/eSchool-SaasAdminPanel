"""Offline (DB-free) unit tests for multi-branch isolation helpers.

Does not require Neon. Run with::

    pytest --noconftest -p no:cacheprovider tests/v1/test_school_branches_offline.py
"""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.services.v1 import rbac
from app.services.v1 import school_branches as branches
from app.services.v1.school_branches import BranchContext, BranchError

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_alembic_head_is_0046():
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert heads == ["20261106_0048"]
    assert script.get_revision("20261106_0048").down_revision == "20261106_0047"
    assert script.get_revision("20261106_0047").down_revision == "20261105_0046"
    assert script.get_revision("20261105_0046").down_revision == "20261030_0045"


def test_branch_admin_role_in_catalog():
    assert rbac.ADMIN_ROLE_BRANCH in rbac.ADMIN_ROLES
    perms = set(rbac.ADMIN_ROLES[rbac.ADMIN_ROLE_BRANCH]["permissions"])
    assert rbac.PERM_SCHOOL not in perms
    assert rbac.PERM_STUDENTS in perms
    assert rbac.PERM_FEES in perms


def test_assert_same_branch_rejects_cross_branch():
    ctx = BranchContext(
        school_id=10,
        branch_id=2,
        allowed_branch_ids=(1, 2),
        is_full_school_admin=True,
    )
    branches.assert_same_branch(10, 2, ctx)
    with pytest.raises(BranchError) as exc:
        branches.assert_same_branch(10, 1, ctx)
    assert exc.value.status_code == 404
    with pytest.raises(BranchError):
        branches.assert_same_branch(99, 2, ctx)


def test_assert_same_branch_consolidated_uses_allowed_set():
    ctx = BranchContext(
        school_id=10,
        branch_id=0,
        allowed_branch_ids=(1, 2),
        is_full_school_admin=True,
    )
    branches.assert_same_branch(10, 1, ctx)
    with pytest.raises(BranchError):
        branches.assert_same_branch(10, 99, ctx)


def test_resolve_branch_context_rejects_foreign_school_branch():
    user = SimpleNamespace(id=uuid.uuid4(), school_id=5, role="school_admin")
    db = MagicMock()

    foreign = SimpleNamespace(id=77, school_id=99, deleted_at=None, status=1, is_default=0)
    db.get.return_value = foreign

    # allowed_branch_ids_for_user path — stub via monkeypatch on module
    def _allowed(_db, _user):
        return [1, 2], True

    original = branches.allowed_branch_ids_for_user
    branches.allowed_branch_ids_for_user = _allowed  # type: ignore[assignment]
    try:
        with pytest.raises(BranchError) as exc:
            branches.resolve_branch_context(db, user, header_branch_id=77)
        assert exc.value.status_code == 403
    finally:
        branches.allowed_branch_ids_for_user = original  # type: ignore[assignment]


def test_resolve_branch_context_branch_admin_denied_other():
    user = SimpleNamespace(id=uuid.uuid4(), school_id=5, role="school_admin")
    db = MagicMock()
    other = SimpleNamespace(id=2, school_id=5, deleted_at=None, status=1, is_default=0)
    db.get.return_value = other

    def _allowed(_db, _user):
        return [1], False

    original = branches.allowed_branch_ids_for_user
    branches.allowed_branch_ids_for_user = _allowed  # type: ignore[assignment]
    try:
        with pytest.raises(BranchError) as exc:
            branches.resolve_branch_context(db, user, header_branch_id=2)
        assert exc.value.status_code == 403
        assert "Not authorized" in exc.value.detail
    finally:
        branches.allowed_branch_ids_for_user = original  # type: ignore[assignment]


def test_migration_docstring_documents_downgrade_data_loss():
    path = BACKEND_ROOT / "alembic" / "versions" / "20261105_0046_school_branches.py"
    text = path.read_text(encoding="utf-8")
    assert "destroyed" in text.lower() or "DESTROYS" in text
    assert "Do not apply to Neon" in text
    assert "BRANCH_SCOPED" in text
    assert "v1_user_branch_access" in text
    assert "idempotent" in text.lower() or "Idempotent" in text


def test_school_branch_model_exists():
    from app.models.tables import SchoolBranch
    from app.models.v1.branch_access import UserBranchAccess

    assert SchoolBranch.__tablename__ == "school_branches"
    assert UserBranchAccess.__tablename__ == "v1_user_branch_access"
    assert "user_id" in UserBranchAccess.__table__.c
    assert UserBranchAccess.__table__.c.user_id.primary_key


def test_student_and_fee_models_have_branch_id():
    from app.models.tables import FeePayment, FeeStructure, Student

    assert hasattr(Student, "branch_id")
    assert hasattr(FeeStructure, "branch_id")
    assert hasattr(FeePayment, "branch_id")
