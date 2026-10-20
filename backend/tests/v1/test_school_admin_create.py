"""POST /api/v1/super-admin/schools/{school_id}/admins — creation rules."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select

from app.core.security import verify_password
from app.models.tables import AuditLog, School
from app.models.v1.roles import ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN
from app.models.v1.user import STATUS_ACTIVE, User
from app.services.v1 import school_admin_service

SAFE_FIELDS = {
    "id", "email", "first_name", "last_name", "mobile", "role", "school_id", "school_name",
    "status", "roles", "permissions", "created_at", "invite_sent",
}


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str):
    return client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "secret123", "first_name": "Create", "last_name": "Admin"},
    )


def _user_headers(client, email: str = "create-user@eschool.com") -> dict[str, str]:
    res = _signup(client, email)
    assert res.status_code == 201, res.text
    return _auth_header(res.json()["access_token"])


def _super_admin_headers(client, v1_db, email: str = "create-sa@eschool.com") -> dict[str, str]:
    assert _signup(client, email).status_code == 201
    user = v1_db.scalar(select(User).where(User.email == email))
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200, login.text
    return _auth_header(login.json()["access_token"])


def _create_school(client, headers, code: str = "CRT01", email: str = "crt@eschool.com") -> int:
    res = client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": "Create School", "address": "1 Main", "support_phone": "111", "support_email": email, "code": code},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _admin_body(**overrides):
    body = {
        "email": "new-admin@eschool.com",
        "password": "adminpass1",
        "first_name": "New",
        "last_name": "Admin",
        "mobile": "9999999999",
    }
    body.update(overrides)
    return body


def _url(school_id: int) -> str:
    return f"/api/v1/super-admin/schools/{school_id}/admins"


def _count(v1_db, model, *where) -> int:
    v1_db.expire_all()
    query = select(func.count()).select_from(model)
    for clause in where:
        query = query.where(clause)
    return int(v1_db.scalar(query) or 0)


def test_create_returns_safe_fields_and_stores_hashed_password(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers)

    res = v1_client.post(_url(school_id), headers=headers, json=_admin_body(email="New-Admin@ESchool.com"))

    assert res.status_code == 201, res.text
    data = res.json()
    assert set(data) == SAFE_FIELDS
    assert data["email"] == "new-admin@eschool.com"
    assert data["first_name"] == "New"
    assert data["last_name"] == "Admin"
    assert data["mobile"] == "9999999999"
    assert data["role"] == ROLE_SCHOOL_ADMIN
    assert data["school_id"] == school_id
    assert data["status"] == STATUS_ACTIVE
    assert data["school_name"] == "Create School"
    assert data["roles"] == ["school_admin"]
    assert "students.manage" in data["permissions"]
    assert data["created_at"]
    assert "adminpass1" not in res.text

    user = v1_db.scalar(select(User).where(User.email == "new-admin@eschool.com"))
    assert str(user.id) == data["id"]
    assert user.role == ROLE_SCHOOL_ADMIN
    assert user.school_id == school_id
    assert user.password_hash.startswith("$2")
    assert user.password_hash not in res.text
    assert verify_password("adminpass1", user.password_hash)


def test_create_writes_audit_row_without_password(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers)

    res = v1_client.post(_url(school_id), headers=headers, json=_admin_body())
    assert res.status_code == 201, res.text

    v1_db.expire_all()
    row = v1_db.scalar(select(AuditLog).where(AuditLog.action == "school_admin.create"))
    assert row is not None
    assert row.entity_id == res.json()["id"]
    assert row.school_id == school_id
    assert row.actor_email == "create-sa@eschool.com"
    assert json.loads(row.metadata_json) == {
        "email": "new-admin@eschool.com",
        "roles": ["school_admin"],
        "status": 1,
        "invitation": False,
    }
    assert "adminpass1" not in (row.metadata_json or "")


@pytest.mark.parametrize("missing", ["email", "first_name", "last_name"])
def test_missing_required_field_422(v1_client, v1_db, missing):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers)
    body = _admin_body()
    body.pop(missing)

    res = v1_client.post(_url(school_id), headers=headers, json=body)

    assert res.status_code == 422
    assert _count(v1_db, User, User.role == ROLE_SCHOOL_ADMIN) == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"email": "not-an-email"},
        {"email": ""},
        {"password": "short"},
        {"first_name": ""},
        {"first_name": "   "},
        {"last_name": "   "},
        {"mobile": "1" * 33},
        {"status": 2},
        {"roles": []},
        {"roles": ["super_admin"]},
        {"roles": ["owner"]},
    ],
)
def test_invalid_field_422(v1_client, v1_db, overrides):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers)

    res = v1_client.post(_url(school_id), headers=headers, json=_admin_body(**overrides))

    assert res.status_code == 422
    assert _count(v1_db, User, User.role == ROLE_SCHOOL_ADMIN) == 0


def test_mobile_is_optional(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers)
    body = _admin_body()
    body.pop("mobile")

    res = v1_client.post(_url(school_id), headers=headers, json=body)

    assert res.status_code == 201, res.text
    assert res.json()["mobile"] is None


def test_create_with_roles_and_inactive_status(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers)

    res = v1_client.post(
        _url(school_id), headers=headers, json=_admin_body(roles=["accounts_admin"], status=0)
    )

    assert res.status_code == 201, res.text
    assert res.json()["roles"] == ["accounts_admin"]
    assert res.json()["permissions"] == ["dashboard.view", "fees.manage", "reports.view"]
    assert res.json()["status"] == 0
    assert res.json()["invite_sent"] is None  # a password was given, so no invitation
    login = v1_client.post("/api/v1/auth/login", json={"email": "new-admin@eschool.com", "password": "adminpass1"})
    assert login.status_code == 403


@pytest.mark.parametrize(
    "extra",
    [{"role": "super_admin"}, {"school_id": 999}, {"id": "00000000-0000-0000-0000-000000000000"}],
)
def test_client_cannot_set_role_school_or_id(v1_client, v1_db, extra):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers)

    res = v1_client.post(_url(school_id), headers=headers, json=_admin_body(**extra))

    assert res.status_code == 422
    assert _count(v1_db, User, User.role == ROLE_SCHOOL_ADMIN) == 0


def test_duplicate_email_is_case_insensitive_and_global(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    first_school = _create_school(v1_client, headers)
    second_school = _create_school(v1_client, headers, code="CRT02", email="crt2@eschool.com")
    assert v1_client.post(_url(first_school), headers=headers, json=_admin_body()).status_code == 201

    same_school = v1_client.post(_url(first_school), headers=headers, json=_admin_body(email="NEW-ADMIN@eschool.com"))
    other_school = v1_client.post(_url(second_school), headers=headers, json=_admin_body())
    super_admin_email = v1_client.post(_url(second_school), headers=headers, json=_admin_body(email="create-sa@eschool.com"))

    for res in (same_school, other_school, super_admin_email):
        assert res.status_code == 409
        assert res.json() == {"detail": "Email already registered"}
    assert _count(v1_db, User, User.role == ROLE_SCHOOL_ADMIN) == 1


def test_duplicate_email_race_returns_409_and_rolls_back(v1_client, v1_db, monkeypatch):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers)
    assert v1_client.post(_url(school_id), headers=headers, json=_admin_body()).status_code == 201
    v1_db.expire_all()
    first_admin_id = v1_db.get(School, school_id).v1_admin_id

    # Skip the first check once, as if another request inserted the email just after it.
    calls = {"n": 0}
    real = school_admin_service._email_taken

    def stale_check(db, email):
        calls["n"] += 1
        return False if calls["n"] == 1 else real(db, email)

    monkeypatch.setattr(school_admin_service, "_email_taken", stale_check)

    res = v1_client.post(_url(school_id), headers=headers, json=_admin_body(first_name="Racer"))

    assert res.status_code == 409
    assert res.json() == {"detail": "Email already registered"}
    assert _count(v1_db, User, User.email == "new-admin@eschool.com") == 1
    assert _count(v1_db, User, User.first_name == "Racer") == 0
    assert _count(v1_db, AuditLog, AuditLog.action == "school_admin.create") == 1
    assert v1_db.get(School, school_id).v1_admin_id == first_admin_id


def test_audit_failure_rolls_back_admin(v1_client, v1_db, monkeypatch):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers)

    def fail(*args, **kwargs):
        raise RuntimeError("forced audit failure")

    monkeypatch.setattr("app.api.v1.super_admin.schools.audit_service.record_audit", fail)

    res = v1_client.post(_url(school_id), headers=headers, json=_admin_body())

    assert res.status_code == 500
    assert res.json() == {"detail": "School admin could not be created"}
    assert "forced audit failure" not in res.text
    assert _count(v1_db, User, User.email == "new-admin@eschool.com") == 0
    assert v1_db.get(School, school_id).v1_admin_id is None


def test_missing_school_404(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)

    res = v1_client.post(_url(999999), headers=headers, json=_admin_body())

    assert res.status_code == 404
    assert res.json() == {"detail": "School not found"}
    assert _count(v1_db, User, User.role == ROLE_SCHOOL_ADMIN) == 0


def test_soft_deleted_school_404(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers)
    assert v1_client.delete(f"/api/v1/super-admin/schools/{school_id}", headers=headers).status_code == 200

    res = v1_client.post(_url(school_id), headers=headers, json=_admin_body())

    assert res.status_code == 404
    assert _count(v1_db, User, User.role == ROLE_SCHOOL_ADMIN) == 0


def test_inactive_school_still_accepts_admin(v1_client, v1_db):
    """Existing rule: registration and the school form add admins to schools that are not active yet."""
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers)
    assert v1_client.post(f"/api/v1/super-admin/schools/{school_id}/deactivate", headers=headers).status_code == 200

    res = v1_client.post(_url(school_id), headers=headers, json=_admin_body())

    assert res.status_code == 201, res.text
    assert res.json()["school_id"] == school_id


def test_unauthenticated_401(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers)

    missing = v1_client.post(_url(school_id), json=_admin_body())
    invalid = v1_client.post(_url(school_id), headers=_auth_header("not-a-token"), json=_admin_body())

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert _count(v1_db, User, User.role == ROLE_SCHOOL_ADMIN) == 0


def test_non_super_admin_403(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers)
    assert v1_client.post(_url(school_id), headers=headers, json=_admin_body()).status_code == 201
    login = v1_client.post("/api/v1/auth/login", json={"email": "new-admin@eschool.com", "password": "adminpass1"})
    assert login.status_code == 200, login.text

    plain_user = v1_client.post(_url(school_id), headers=_user_headers(v1_client), json=_admin_body(email="u@eschool.com"))
    school_admin = v1_client.post(
        _url(school_id),
        headers=_auth_header(login.json()["access_token"]),
        json=_admin_body(email="sa2@eschool.com"),
    )

    assert plain_user.status_code == 403
    assert school_admin.status_code == 403
    assert _count(v1_db, User, User.role == ROLE_SCHOOL_ADMIN) == 1
