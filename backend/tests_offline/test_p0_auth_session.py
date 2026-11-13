"""P0 regression: School Admin login, route gate and session handling (DB-free).

Covers the QA retest defects:
- login and the /school-admin route gate use ONE eligibility rule, so a login that
  succeeds is never followed by 403s on the dashboard (status=1, installed=0 case);
- clear errors for wrong password / pending / suspended / setup-incomplete / subscription;
- token resolution: revoked, expired, deactivated -> refused; valid -> reusable
  (refresh / new tab), and last_used_at is not written on every request;
- logout revokes the session.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1 import deps
from app.models.v1.roles import ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN
from app.services.v1 import auth_service

NOW = datetime(2026, 11, 12, 9, 0, tzinfo=timezone.utc)


def _user(**overrides):
    base = dict(id=uuid4(), role=ROLE_SCHOOL_ADMIN, status=1, school_id=7, password_hash="x")
    base.update(overrides)
    return SimpleNamespace(**base)


def _school(**overrides):
    base = dict(id=7, status=1, installed=1, deleted_at=None)
    base.update(overrides)
    return SimpleNamespace(**base)


def _db_with_school(school):
    db = MagicMock()
    db.get.return_value = school
    return db


@pytest.fixture(autouse=True)
def _no_subscription_block(monkeypatch):
    monkeypatch.setattr(
        "app.services.v1.subscription_access.subscription_expiry_blocks_access", lambda _sid: False
    )


# --- one eligibility rule -------------------------------------------------------------

CASES = [
    ("active+installed", _school(), None),
    ("pending", _school(status=0, installed=0), auth_service.SCHOOL_PENDING_DETAIL),
    ("suspended", _school(status=0, installed=1), auth_service.SCHOOL_SUSPENDED_DETAIL),
    ("setup incomplete", _school(status=1, installed=0), auth_service.SCHOOL_SETUP_INCOMPLETE_DETAIL),
    ("deleted", _school(deleted_at=NOW.replace(tzinfo=None)), auth_service.SCHOOL_SUSPENDED_DETAIL),
    ("missing", None, auth_service.SCHOOL_SUSPENDED_DETAIL),
]


@pytest.mark.parametrize("label,school,expected", CASES, ids=[c[0] for c in CASES])
def test_login_and_route_gate_agree(label, school, expected):
    """The H2 bug: login used to allow status=1/installed=0, then every route said 403."""
    db = _db_with_school(school)
    user = _user()

    if expected is None:
        auth_service.assert_school_admin_login_allowed(db, user)
        ctx = deps.AuthContext(user=user, session=SimpleNamespace())
        assert deps.require_school_admin(ctx, db) is ctx
        return

    with pytest.raises(auth_service.AuthError) as login_err:
        auth_service.assert_school_admin_login_allowed(db, user)
    with pytest.raises(HTTPException) as route_err:
        deps.require_school_admin(deps.AuthContext(user=user, session=SimpleNamespace()), db)
    assert login_err.value.status_code == route_err.value.status_code == 403
    assert login_err.value.detail == route_err.value.detail == expected


def test_subscription_block_applies_to_login_and_routes(monkeypatch):
    monkeypatch.setattr(
        "app.services.v1.subscription_access.subscription_expiry_blocks_access", lambda _sid: True
    )
    db = _db_with_school(_school())
    user = _user()
    with pytest.raises(auth_service.AuthError) as login_err:
        auth_service.assert_school_admin_login_allowed(db, user)
    with pytest.raises(HTTPException) as route_err:
        deps.require_school_admin(deps.AuthContext(user=user, session=SimpleNamespace()), db)
    assert login_err.value.detail == route_err.value.detail == auth_service.SUBSCRIPTION_BLOCKED_DETAIL


def test_no_school_assigned_and_inactive_account():
    db = _db_with_school(_school())
    with pytest.raises(auth_service.AuthError, match="No school assigned"):
        auth_service.assert_school_admin_login_allowed(db, _user(school_id=None))
    with pytest.raises(auth_service.AuthError, match="Account inactive"):
        auth_service.assert_school_admin_login_allowed(db, _user(status=0))


def test_non_school_admin_roles_skip_school_gate():
    db = _db_with_school(None)
    auth_service.assert_school_admin_login_allowed(db, _user(role=ROLE_SUPER_ADMIN, school_id=None))


def test_route_gate_rejects_other_roles():
    with pytest.raises(HTTPException) as err:
        deps.require_school_admin(
            deps.AuthContext(user=_user(role=ROLE_SUPER_ADMIN), session=SimpleNamespace()),
            _db_with_school(_school()),
        )
    assert err.value.status_code == 403


# --- login credentials ----------------------------------------------------------------


def _login_db(user):
    db = MagicMock()
    db.scalar.return_value = user
    db.get.return_value = _school()
    return db


def test_invalid_password_and_unknown_email_return_same_401(monkeypatch):
    monkeypatch.setattr(auth_service, "verify_password", lambda _p, _h: False)
    for db in (_login_db(_user()), _login_db(None)):
        with pytest.raises(auth_service.AuthError) as err:
            auth_service.login(db, email="Admin@School.com ", password="wrong")
        assert err.value.status_code == 401
        assert err.value.detail == "Invalid email or password"


def test_valid_login_issues_session_for_school_admin(monkeypatch):
    monkeypatch.setattr(auth_service, "verify_password", lambda _p, _h: True)
    user = _user()
    db = _login_db(user)
    issued = auth_service.login(db, email="admin@school.com", password="right")
    assert issued.user is user
    assert issued.plain_token
    assert issued.expires_at > datetime.now(timezone.utc)
    db.add.assert_called_once()
    db.commit.assert_called()


def test_valid_password_but_pending_school_is_403_not_200(monkeypatch):
    monkeypatch.setattr(auth_service, "verify_password", lambda _p, _h: True)
    db = _login_db(_user())
    db.get.return_value = _school(status=1, installed=0)
    with pytest.raises(auth_service.AuthError) as err:
        auth_service.login(db, email="admin@school.com", password="right")
    assert err.value.status_code == 403
    db.add.assert_not_called()  # no session is created for a panel that would refuse it


# --- token resolution / session lifecycle ---------------------------------------------


def _session(**overrides):
    base = dict(id=1, user_id=uuid4(), revoked_at=None, expires_at=NOW + timedelta(days=1), last_used_at=None)
    base.update(overrides)
    return SimpleNamespace(**base)


def _token_db(session, user):
    db = MagicMock()
    db.scalar.return_value = session
    db.get.return_value = user
    return db


@pytest.fixture
def frozen_now(monkeypatch):
    monkeypatch.setattr(auth_service, "_utcnow", lambda: NOW)


def test_valid_token_resolves_repeatedly_for_refresh_and_new_tab(frozen_now):
    session, user = _session(), _user()
    db = _token_db(session, user)
    for _ in range(3):
        assert auth_service.resolve_user_from_token(db, "tok") == (user, session)


def test_last_used_written_once_then_throttled(frozen_now):
    session = _session(last_used_at=None)
    db = _token_db(session, _user())
    auth_service.resolve_user_from_token(db, "tok")
    assert session.last_used_at == NOW
    assert db.commit.call_count == 1
    auth_service.resolve_user_from_token(db, "tok")
    auth_service.resolve_user_from_token(db, "tok")
    assert db.commit.call_count == 1  # no write per request


def test_last_used_refreshed_after_interval(frozen_now):
    stale = NOW - auth_service.LAST_USED_WRITE_INTERVAL - timedelta(seconds=1)
    session = _session(last_used_at=stale.replace(tzinfo=None))  # naive value from DB
    db = _token_db(session, _user())
    auth_service.resolve_user_from_token(db, "tok")
    assert session.last_used_at == NOW
    assert db.commit.call_count == 1


@pytest.mark.parametrize(
    "session,user,status",
    [
        (None, _user(), 401),
        (_session(revoked_at=NOW), _user(), 401),
        (_session(expires_at=NOW - timedelta(seconds=1)), _user(), 401),
        (_session(expires_at=(NOW - timedelta(seconds=1)).replace(tzinfo=None)), _user(), 401),
        (_session(), None, 401),
        (_session(), _user(status=0), 403),
    ],
    ids=["unknown", "revoked(logout)", "expired", "expired-naive", "user-gone", "user-inactive"],
)
def test_refused_tokens(frozen_now, session, user, status):
    with pytest.raises(auth_service.AuthError) as err:
        auth_service.resolve_user_from_token(_token_db(session, user), "tok")
    assert err.value.status_code == status


def test_logout_revokes_and_token_is_then_refused(frozen_now):
    session, user = _session(), _user()
    db = _token_db(session, user)
    auth_service.logout(db, session)
    assert session.revoked_at == NOW
    with pytest.raises(auth_service.AuthError) as err:
        auth_service.resolve_user_from_token(db, "tok")
    assert err.value.status_code == 401


def test_cross_school_scope_denied():
    ctx = deps.AuthContext(user=_user(school_id=7), session=SimpleNamespace())
    deps.assert_school_scope(ctx, 7)
    with pytest.raises(HTTPException) as err:
        deps.assert_school_scope(ctx, 8)
    assert err.value.status_code == 403
