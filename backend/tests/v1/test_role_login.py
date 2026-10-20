"""Role-specific login, session tokens and tenant isolation on /api/v1."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.security import hash_password, utcnow
from app.models.tables import School
from app.models.v1.roles import ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN, ROLE_USER
from app.models.v1.session import AuthSession
from app.models.v1.user import STATUS_ACTIVE, STATUS_INACTIVE, User

PASSWORD = "secret123"
GENERIC = "Invalid email or password"


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _school(db, code: str) -> School:
    school = School(
        name=f"School {code}",
        code=code,
        database_name=f"legacy_{code.lower()}",
        status=1,
        installed=1,
        created_at=utcnow(),
    )
    db.add(school)
    db.commit()
    return school


def _user(db, email: str, role: str, *, school_id: int | None = None, status: int = STATUS_ACTIVE) -> User:
    user = User(
        email=email,
        password_hash=hash_password(PASSWORD),
        first_name="Role",
        last_name="Test",
        role=role,
        school_id=school_id,
        status=status,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def accounts(v1_client, v1_db):
    a = _school(v1_db, "ROLEA")
    b = _school(v1_db, "ROLEB")
    _user(v1_db, "sa@role.test", ROLE_SUPER_ADMIN)
    _user(v1_db, "admin-a@role.test", ROLE_SCHOOL_ADMIN, school_id=a.id)
    _user(v1_db, "admin-b@role.test", ROLE_SCHOOL_ADMIN, school_id=b.id)
    _user(v1_db, "plain@role.test", ROLE_USER)
    return {"a": a.id, "b": b.id}


def _login(client, path: str, email: str, password: str = PASSWORD):
    return client.post(path, json={"email": email, "password": password})


def _token(client, email: str) -> str:
    res = _login(client, "/api/v1/auth/login", email)
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


# --- Super Admin login ---


def test_super_admin_login_only_for_super_admin(v1_client, accounts):
    ok = _login(v1_client, "/api/v1/super-admin/login", "sa@role.test")
    assert ok.status_code == 200
    assert ok.json()["user"]["role"] == ROLE_SUPER_ADMIN

    responses = [
        _login(v1_client, "/api/v1/super-admin/login", "admin-a@role.test"),
        _login(v1_client, "/api/v1/super-admin/login", "plain@role.test"),
        _login(v1_client, "/api/v1/super-admin/login", "sa@role.test", "wrong-password"),
        _login(v1_client, "/api/v1/super-admin/login", "ghost@role.test"),
    ]
    for res in responses:
        assert res.status_code == 401
        assert res.json() == {"detail": GENERIC}


def test_super_admin_login_inactive(v1_client, v1_db, accounts):
    _user(v1_db, "sa-off@role.test", ROLE_SUPER_ADMIN, status=STATUS_INACTIVE)
    res = _login(v1_client, "/api/v1/super-admin/login", "sa-off@role.test")
    assert res.status_code == 403
    assert "access_token" not in res.json()


@pytest.mark.parametrize("path", ["/api/v1/super-admin/login", "/api/v1/auth/login"])
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"email": "sa@role.test"},
        {"password": PASSWORD},
        {"email": "not-an-email", "password": PASSWORD},
        {"email": "sa@role.test", "password": ""},
    ],
)
def test_login_missing_or_malformed_credentials(v1_client, accounts, path, body):
    assert v1_client.post(path, json=body).status_code == 422


@pytest.mark.parametrize("path", ["/api/v1/super-admin/login", "/api/v1/auth/login"])
def test_login_rejects_client_supplied_role(v1_client, accounts, path):
    res = v1_client.post(
        path,
        json={"email": "plain@role.test", "password": PASSWORD, "role": ROLE_SUPER_ADMIN},
    )
    assert res.status_code == 422


def test_signup_cannot_choose_role_or_school(v1_client, accounts):
    res = v1_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "new@role.test",
            "password": PASSWORD,
            "first_name": "N",
            "last_name": "U",
            "role": ROLE_SUPER_ADMIN,
            "school_id": accounts["a"],
        },
    )
    assert res.status_code == 422


# --- Shared login (admin web) ---


def test_shared_login_returns_server_side_role(v1_client, accounts):
    """The admin web routes school_admin to /school and others to /dashboard from user.role."""
    sa = _login(v1_client, "/api/v1/auth/login", "sa@role.test").json()
    assert sa["user"]["role"] == ROLE_SUPER_ADMIN
    admin = _login(v1_client, "/api/v1/auth/login", "admin-a@role.test").json()
    assert admin["user"]["role"] == ROLE_SCHOOL_ADMIN
    assert admin["user"]["school_id"] == accounts["a"]

    assert v1_client.get("/api/v1/super-admin/dashboard", headers=_h(sa["access_token"])).status_code == 200
    assert v1_client.get("/api/v1/school-admin/school", headers=_h(admin["access_token"])).status_code == 200


def test_shared_login_generic_failures(v1_client, accounts):
    wrong = _login(v1_client, "/api/v1/auth/login", "admin-a@role.test", "wrong-password")
    ghost = _login(v1_client, "/api/v1/auth/login", "ghost@role.test")
    assert wrong.status_code == ghost.status_code == 401
    assert wrong.json() == ghost.json() == {"detail": GENERIC}


def test_school_admin_login_inactive(v1_client, v1_db, accounts):
    _user(v1_db, "admin-off@role.test", ROLE_SCHOOL_ADMIN, school_id=accounts["a"], status=STATUS_INACTIVE)
    res = _login(v1_client, "/api/v1/auth/login", "admin-off@role.test")
    assert res.status_code == 403
    assert "access_token" not in res.json()


# --- Tokens ---


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": ""},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer not-a-real-token"},
        {"Authorization": "Basic dXNlcjpwYXNz"},
    ],
)
def test_missing_or_invalid_token(v1_client, accounts, headers):
    assert v1_client.get("/api/v1/super-admin/ping", headers=headers).status_code == 401
    assert v1_client.get("/api/v1/school-admin/me", headers=headers).status_code == 401


def test_tampered_expired_and_revoked_tokens(v1_client, v1_db, accounts):
    token = _token(v1_client, "sa@role.test")
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert v1_client.get("/api/v1/super-admin/ping", headers=_h(tampered)).status_code == 401

    for session in v1_db.scalars(select(AuthSession)):
        session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    v1_db.commit()
    assert v1_client.get("/api/v1/super-admin/ping", headers=_h(token)).status_code == 401

    fresh = _token(v1_client, "sa@role.test")
    assert v1_client.post("/api/v1/auth/logout", headers=_h(fresh)).status_code == 204
    assert v1_client.get("/api/v1/super-admin/ping", headers=_h(fresh)).status_code == 401


def test_token_stops_working_after_deactivation(v1_client, v1_db, accounts):
    token = _token(v1_client, "admin-a@role.test")
    assert v1_client.get("/api/v1/school-admin/me", headers=_h(token)).status_code == 200
    user = v1_db.scalar(select(User).where(User.email == "admin-a@role.test"))
    user.status = STATUS_INACTIVE
    v1_db.commit()
    assert v1_client.get("/api/v1/school-admin/me", headers=_h(token)).status_code == 403


# --- Cross-role and tenant isolation ---


def test_roles_cannot_use_each_others_api(v1_client, accounts):
    sa = _h(_token(v1_client, "sa@role.test"))
    admin = _h(_token(v1_client, "admin-a@role.test"))
    plain = _h(_token(v1_client, "plain@role.test"))
    for headers in (admin, plain):
        assert v1_client.get("/api/v1/super-admin/ping", headers=headers).status_code == 403
        assert v1_client.get("/api/v1/super-admin/schools", headers=headers).status_code == 403
    for headers in (sa, plain):
        assert v1_client.get("/api/v1/school-admin/me", headers=headers).status_code == 403


def test_role_spoofing_headers_and_query_ignored(v1_client, accounts):
    admin = {
        **_h(_token(v1_client, "admin-a@role.test")),
        "X-Role": ROLE_SUPER_ADMIN,
        "role": ROLE_SUPER_ADMIN,
    }
    res = v1_client.get(f"/api/v1/super-admin/ping?role={ROLE_SUPER_ADMIN}", headers=admin)
    assert res.status_code == 403


def test_school_admin_cannot_reach_other_school(v1_client, accounts):
    admin = _h(_token(v1_client, "admin-a@role.test"))
    own, other = accounts["a"], accounts["b"]
    assert v1_client.get(f"/api/v1/school-admin/schools/{own}", headers=admin).status_code == 200
    assert v1_client.get(f"/api/v1/school-admin/schools/{other}", headers=admin).status_code == 403
    assert v1_client.get(f"/api/v1/schools/{own}/payments", headers=admin).status_code == 200
    assert v1_client.get(f"/api/v1/schools/{other}/payments", headers=admin).status_code == 403
    assert v1_client.get(f"/api/v1/schools/{other}/invoices", headers=admin).status_code == 403


def test_school_admin_scope_on_legacy_admin_api(v1_client, accounts):
    """/api/admin reads use the account's school, not a school sent by the client."""
    admin = _h(_token(v1_client, "admin-a@role.test"))
    me = v1_client.get("/api/admin/me", headers=admin)
    assert me.status_code == 200
    assert me.json()["data"]["school_id"] == accounts["a"]
    plain = _h(_token(v1_client, "plain@role.test"))
    assert v1_client.get("/api/admin/me", headers=plain).status_code == 403
