"""Legacy /api/admin school checks in admin_context. Does not open a database."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import deps
from app.models.tables import School, User
from app.models.v1.roles import ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN
from app.services.v1 import auth_service

ACTIVE = {"status": 1, "installed": 1, "deleted_at": None}
SUSPENDED = {"status": 0, "installed": 1, "deleted_at": None}
DEACTIVATED = {"status": 0, "installed": 0, "deleted_at": None}
DELETED = {"status": 1, "installed": 1, "deleted_at": "2026-10-01"}


class FakeDb:
    def __init__(self, school: dict | None, legacy_user=None):
        self.school = None if school is None else SimpleNamespace(id=7, **school)
        self.legacy_user = legacy_user

    def get(self, model, key):
        if model is School:
            return self.school if key == 7 else None
        if model is User:
            return self.legacy_user
        raise AssertionError(model)


def _request(*, bearer: str | None = None, cookie: str | None = None):
    return SimpleNamespace(
        cookies={"eschool_session": cookie} if cookie else {},
        headers={"authorization": f"Bearer {bearer}"} if bearer else {},
        state=SimpleNamespace(),
    )


def _bearer_user(monkeypatch, role: str, school_id: int | None):
    user = SimpleNamespace(role=role, school_id=school_id, status=1)
    monkeypatch.setattr(auth_service, "resolve_user_from_token", lambda _db, _token: (user, object()))
    return user


def test_active_school_admin_keeps_access(monkeypatch):
    user = _bearer_user(monkeypatch, ROLE_SCHOOL_ADMIN, 7)
    db = FakeDb(ACTIVE)
    assert deps.admin_context(_request(bearer="t"), db) == (db, user, 7)


@pytest.mark.parametrize(
    ("school", "detail"),
    [
        (SUSPENDED, "School access is suspended"),
        (DEACTIVATED, "This school is waiting for approval. You can sign in after it is activated."),
        (DELETED, "School access is suspended"),
        (None, "School access is suspended"),
    ],
)
def test_existing_token_is_refused_for_an_unavailable_school(monkeypatch, school, detail):
    _bearer_user(monkeypatch, ROLE_SCHOOL_ADMIN, 7)
    with pytest.raises(HTTPException) as caught:
        deps.admin_context(_request(bearer="t"), FakeDb(school))
    assert caught.value.status_code == 403
    assert caught.value.detail == detail


def test_reactivated_school_works_again_with_the_same_token(monkeypatch):
    _bearer_user(monkeypatch, ROLE_SCHOOL_ADMIN, 7)
    db = FakeDb(SUSPENDED)
    with pytest.raises(HTTPException):
        deps.admin_context(_request(bearer="t"), db)
    db.school.status = 1
    assert deps.admin_context(_request(bearer="t"), db)[2] == 7


def test_super_admin_is_not_bound_to_a_school(monkeypatch):
    user = _bearer_user(monkeypatch, ROLE_SUPER_ADMIN, None)
    db = FakeDb(SUSPENDED)
    assert deps.admin_context(_request(bearer="t"), db) == (db, user, None)


def test_other_roles_and_missing_tokens_are_still_refused(monkeypatch):
    _bearer_user(monkeypatch, "user", 7)
    with pytest.raises(HTTPException) as role:
        deps.admin_context(_request(bearer="t"), FakeDb(ACTIVE))
    assert role.value.status_code == 403
    with pytest.raises(HTTPException) as anonymous:
        deps.admin_context(_request(), FakeDb(ACTIVE))
    assert anonymous.value.status_code == 401


def test_legacy_cookie_session_is_refused_for_a_suspended_school(monkeypatch):
    legacy = SimpleNamespace(id=3, school_id=7, deleted_at=None)
    monkeypatch.setattr(deps, "read_session", lambda _token: {"uid": 3})
    with pytest.raises(HTTPException) as caught:
        deps.admin_context(_request(cookie="c"), FakeDb(SUSPENDED, legacy_user=legacy))
    assert caught.value.status_code == 403
    db = FakeDb(ACTIVE, legacy_user=legacy)
    assert deps.admin_context(_request(cookie="c"), db) == (db, legacy, 7)


def test_legacy_cookie_without_a_school_is_unchanged(monkeypatch):
    legacy = SimpleNamespace(id=1, school_id=None, deleted_at=None)
    monkeypatch.setattr(deps, "read_session", lambda _token: {"uid": 1})
    db = FakeDb(None, legacy_user=legacy)
    assert deps.admin_context(_request(cookie="c"), db) == (db, legacy, None)
