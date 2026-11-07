"""Offline tests for Super Admin branch quota and creation enforcement. No database."""

from __future__ import annotations

import threading
import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.v1 import school_admin_branches as school_routes
from app.api.v1.deps import require_super_admin
from app.api.v1.super_admin import schools as super_routes
from app.models.tables import School
from app.schemas.v1.school_branches import BranchCreateBody
from app.services.v1 import rbac
from app.services.v1 import school_branches as branches
from app.services.v1.school_branches import BranchError


class _Rows:
    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _Result:
    def __init__(self, value=None, rows=None):
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._value

    def all(self):
        return list(self._rows)


class QuotaDB:
    """Enough of a Session for quota service calls, including a real row lock."""

    def __init__(self, school, branch_rows):
        self.school = school
        self.branches = list(branch_rows)
        self.lock = threading.Lock()
        self._held = False
        self.pending = []
        self._next_id = 50

    def execute(self, stmt):
        sql = " ".join(str(stmt).split()).upper()
        if "FOR UPDATE" in sql:
            self.lock.acquire()
            self._held = True
            return _Result(self.school)
        return _Result(rows=[])

    def get(self, model, pk):
        name = getattr(model, "__name__", "")
        if name == "School":
            return self.school if self.school.id == pk else None
        for row in self.branches:
            if row.id == pk and row.deleted_at is None:
                return row
        return None

    def scalar(self, stmt):
        sql = " ".join(str(stmt).split()).lower()
        rows = [b for b in self.branches if b.deleted_at is None and b.school_id == self.school.id]
        if "status" in sql:
            rows = [b for b in rows if b.status == 1]
        return len(rows)

    def scalars(self, stmt):
        sql = " ".join(str(stmt).split()).lower()
        if "from schools" in sql:
            return _Rows([self.school])
        live = [b for b in self.branches if b.deleted_at is None and b.school_id == self.school.id]
        if sql.startswith("select school_branches.id from"):
            return _Rows([b.id for b in live])
        return _Rows(live)

    def add(self, row):
        self.pending.append(row)

    def flush(self):
        for row in self.pending:
            if getattr(row, "id", None) is None:
                row.id = self._next_id
                self._next_id += 1
            row._committed = False
            self.branches.append(row)
        self.pending = []

    def commit(self):
        self.flush()
        for row in self.branches:
            row._committed = True
        self._release()

    def rollback(self):
        self.pending = []
        self.branches = [b for b in self.branches if getattr(b, "_committed", False)]
        self._release()

    def refresh(self, row):
        if getattr(row, "id", None) is None:
            row.id = self._next_id
            self._next_id += 1

    def _release(self):
        if self._held:
            self._held = False
            self.lock.release()


def _school(**kwargs):
    base = dict(
        id=10,
        name="Hill School",
        deleted_at=None,
        branch_creation_enabled=False,
        max_branches=1,
        updated_at=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def _branch(branch_id, name="Main", status=1, default=1):
    row = SimpleNamespace(
        id=branch_id,
        school_id=10,
        name=name,
        code="MAIN" if default else "B",
        address="",
        status=status,
        is_default=default,
        deleted_at=None,
        created_at=None,
        updated_at=None,
    )
    row._committed = True
    return row


def test_super_admin_summary_counts_active_and_inactive(monkeypatch):
    db = QuotaDB(_school(max_branches=3, branch_creation_enabled=True), [_branch(1), _branch(2, "East", 0, 0)])
    monkeypatch.setattr(branches, "_branch_people_counts", lambda *_a, **_k: {1: {"student_count": 4, "teacher_count": 2}})
    out = branches.school_branch_summary(db, 10)
    assert out["school_id"] == 10
    assert out["school_name"] == "Hill School"
    assert out["total_branches"] == 2
    assert out["active_branches"] == 1
    assert out["inactive_branches"] == 1
    assert out["max_branches"] == 3
    assert out["remaining_capacity"] == 2
    assert out["branches"][0]["student_count"] == 4
    assert out["branches"][0]["teacher_count"] == 2


def test_unknown_school_summary_is_404():
    db = QuotaDB(_school(), [])
    db.school = None

    def _get(model, pk):
        return None

    db.get = _get
    with pytest.raises(BranchError) as exc:
        branches.school_branch_summary(db, 99)
    assert exc.value.status_code == 404


def test_super_admin_can_enable_and_raise_limit(monkeypatch):
    main = _branch(1)
    db = QuotaDB(_school(), [main])
    monkeypatch.setattr(branches, "_branch_people_counts", lambda *_a, **_k: {})
    out = branches.update_branch_settings(db, 10, max_branches=3, branch_creation_enabled=True)
    assert db.school.max_branches == 3
    assert db.school.branch_creation_enabled is True
    assert out["remaining_capacity"] == 2
    assert main.deleted_at is None


def test_disable_permission_does_not_delete_branches(monkeypatch):
    main = _branch(1)
    extra = _branch(2, "East", 1, 0)
    db = QuotaDB(_school(max_branches=2, branch_creation_enabled=True), [main, extra])
    monkeypatch.setattr(branches, "_branch_people_counts", lambda *_a, **_k: {})
    branches.update_branch_settings(db, 10, max_branches=2, branch_creation_enabled=False)
    assert db.school.branch_creation_enabled is False
    assert [b.id for b in db.branches] == [1, 2]
    assert all(b.deleted_at is None for b in db.branches)


def test_limit_below_active_count_rejected(monkeypatch):
    db = QuotaDB(_school(max_branches=2, branch_creation_enabled=True), [_branch(1), _branch(2, "East", 1, 0)])
    with pytest.raises(BranchError) as exc:
        branches.update_branch_settings(db, 10, max_branches=1, branch_creation_enabled=True)
    assert exc.value.status_code == 422
    assert db.school.max_branches == 2


def test_branch_settings_route_is_super_admin_only():
    route = next(
        r
        for r in super_routes.router.routes
        if str(getattr(r, "path", "")).endswith("/{school_id}/branch-settings")
    )
    calls = [getattr(dep, "call", None) for dep in route.dependant.dependencies]
    assert require_super_admin in calls
    school_paths = [getattr(r, "path", "") for r in school_routes.router.routes]
    assert not any("branch-settings" in path for path in school_paths)


def test_default_permission_blocks_additional_branch():
    db = QuotaDB(_school(), [_branch(1)])
    with pytest.raises(BranchError) as exc:
        branches.create_branch(db, 10, name="East")
    assert exc.value.status_code == 403
    assert [b.name for b in db.branches] == ["Main"]


def test_enabled_create_below_limit():
    db = QuotaDB(_school(branch_creation_enabled=True, max_branches=2), [_branch(1)])
    out = branches.create_branch(db, 10, name="East", code="E", address="Road")
    assert out["name"] == "East"
    assert out["is_default"] is False
    assert len(db.branches) == 2


def test_create_at_limit_rejected():
    db = QuotaDB(
        _school(branch_creation_enabled=True, max_branches=2),
        [_branch(1), _branch(2, "East", 1, 0)],
    )
    with pytest.raises(BranchError) as exc:
        branches.create_branch(db, 10, name="West")
    assert exc.value.status_code == 403
    assert len(db.branches) == 2


def test_school_admin_cannot_send_school_id():
    with pytest.raises(ValidationError):
        BranchCreateBody.model_validate({"name": "East", "school_id": 99})


def test_other_school_branch_hidden_by_ownership():
    db = QuotaDB(_school(), [_branch(1)])
    foreign = _branch(9, "Other", 1, 0)
    foreign.school_id = 99
    db.branches.append(foreign)
    with pytest.raises(BranchError) as exc:
        branches.get_branch(db, 10, 9)
    assert exc.value.status_code == 404


def test_branch_admin_role_cannot_manage_school():
    perms = set(rbac.ADMIN_ROLES[rbac.ADMIN_ROLE_BRANCH]["permissions"])
    assert rbac.PERM_SCHOOL not in perms
    source = school_routes.create_branch.__doc__ or ""
    assert "school_admin" in source or rbac.ADMIN_ROLE_SCHOOL


def test_capability_payload_for_full_admin(monkeypatch):
    db = QuotaDB(_school(branch_creation_enabled=True, max_branches=2), [_branch(1)])
    user = SimpleNamespace(id=uuid.uuid4(), school_id=10)
    monkeypatch.setattr(branches, "allowed_branch_ids_for_user", lambda *_a, **_k: ([1], True))
    out = branches.me_branches_payload(db, user)
    assert out["can_create_branch"] is True
    assert out["remaining_capacity"] == 1
    assert out["active_branches"] == 1
    assert out["branch_creation_enabled"] is True


def test_capability_denies_branch_admin(monkeypatch):
    db = QuotaDB(_school(branch_creation_enabled=True, max_branches=5), [_branch(1), _branch(2, "East", 1, 0)])
    user = SimpleNamespace(id=uuid.uuid4(), school_id=10)
    monkeypatch.setattr(branches, "allowed_branch_ids_for_user", lambda *_a, **_k: ([1], False))
    out = branches.me_branches_payload(db, user)
    assert out["can_create_branch"] is False
    assert [item["id"] for item in out["branches"]] == [1]


def test_failed_create_rolls_back_provisional_main():
    db = QuotaDB(_school(branch_creation_enabled=False, max_branches=1), [])
    with pytest.raises(BranchError):
        branches.create_branch(db, 10, name="East")
    assert db.branches == []


def test_ensure_default_branch_still_creates_one_main():
    db = QuotaDB(_school(), [])
    first = branches.ensure_default_branch(db, 10)
    second = branches.ensure_default_branch(db, 10)
    mains = [b for b in db.branches if b.name == "Main"]
    assert first.name == "Main"
    assert second.id == first.id
    assert len(mains) == 1


def test_two_concurrent_creates_cannot_pass_one_slot():
    db = QuotaDB(_school(branch_creation_enabled=True, max_branches=2), [_branch(1)])
    errors = []
    created = []

    def _run():
        try:
            created.append(branches.create_branch(db, 10, name=f"B-{threading.get_ident()}"))
        except BranchError as exc:
            errors.append(exc.status_code)

    threads = [threading.Thread(target=_run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(created) == 1
    assert errors == [403]
    assert sum(1 for b in db.branches if b.status == 1 and b.deleted_at is None) == 2


def test_orm_quota_columns_exist():
    cols = School.__table__.c
    assert cols.branch_creation_enabled.nullable is False
    assert cols.max_branches.nullable is False
    names = {c.name for c in School.__table__.constraints}
    assert "ck_schools_max_branches_at_least_one" in names
