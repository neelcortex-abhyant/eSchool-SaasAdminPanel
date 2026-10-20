"""School Admin management: listing, profile edit, status, role assignment."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.core.security import hash_token
from app.models.tables import AuditLog
from app.models.v1.admin_role import UserAdminRole
from app.models.v1.reset_token import PasswordResetToken
from app.models.v1.session import AuthSession
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str):
    res = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "secret123", "first_name": "Mgmt", "last_name": "User"},
    )
    assert res.status_code == 201, res.text
    return res


def _super_admin_headers(client, v1_db, email: str = "mgmt-sa@eschool.com") -> dict[str, str]:
    _signup(client, email)
    user = v1_db.scalar(select(User).where(User.email == email))
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200, login.text
    return _auth_header(login.json()["access_token"])


def _school(client, headers, name: str, code: str) -> int:
    res = client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": name, "address": "1", "support_phone": "1", "support_email": f"{code.lower()}@eschool.com", "code": code},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _admin(client, headers, school_id: int, email: str, first: str, last: str) -> str:
    res = client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=headers,
        json={"email": email, "password": "adminpass1", "first_name": first, "last_name": last},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


@pytest.fixture()
def seeded(v1_client, v1_db):
    """Two schools, four admins with distinct created_at, roles and status."""
    headers = _super_admin_headers(v1_client, v1_db)
    north = _school(v1_client, headers, "North School", "NORTH1")
    south = _school(v1_client, headers, "South School", "SOUTH1")
    ids = {
        "asha": _admin(v1_client, headers, north, "asha@north.edu", "Asha", "Rao"),
        "bina": _admin(v1_client, headers, north, "bina@north.edu", "Bina", "Shah"),
        "chand": _admin(v1_client, headers, north, "chand@north.edu", "Chand", "Kumar"),
        "dev": _admin(v1_client, headers, south, "dev@south.edu", "Dev", "Mehta"),
    }
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for offset, key in enumerate(["asha", "bina", "chand", "dev"]):
        user = v1_db.get(User, uuid.UUID(ids[key]))
        user.created_at = base + timedelta(days=offset)
        if key == "bina":
            user.status = 0
    v1_db.add(UserAdminRole(user_id=uuid.UUID(ids["chand"]), role="accounts_admin"))
    v1_db.commit()
    return {"headers": headers, "north": north, "south": south, "ids": ids}


def _emails(res) -> list[str]:
    return [item["email"] for item in res.json()["items"]]


def test_per_school_list_has_pagination_metadata(v1_client, seeded):
    res = v1_client.get(
        f"/api/v1/super-admin/schools/{seeded['north']}/admins",
        headers=seeded["headers"],
        params={"page": 1, "page_size": 2},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 3
    assert body["page"] == 1 and body["page_size"] == 2
    assert _emails(res) == ["chand@north.edu", "bina@north.edu"]  # default -created_at

    page2 = v1_client.get(
        f"/api/v1/super-admin/schools/{seeded['north']}/admins",
        headers=seeded["headers"],
        params={"page": 2, "page_size": 2},
    )
    assert _emails(page2) == ["asha@north.edu"]
    assert page2.json()["total"] == 3


def test_list_item_fields(v1_client, seeded):
    res = v1_client.get(f"/api/v1/super-admin/schools/{seeded['south']}/admins", headers=seeded["headers"])
    item = res.json()["items"][0]
    assert item["school_name"] == "South School"
    assert item["school_id"] == seeded["south"]
    assert item["roles"] == ["school_admin"]
    assert item["created_at"].startswith("2026-01-04")
    assert "password_hash" not in item and "password" not in item


def test_cross_school_list_and_school_filter(v1_client, seeded):
    all_admins = v1_client.get("/api/v1/super-admin/school-admins", headers=seeded["headers"])
    assert all_admins.status_code == 200
    assert all_admins.json()["total"] == 4

    south = v1_client.get(
        "/api/v1/super-admin/school-admins", headers=seeded["headers"], params={"school_id": seeded["south"]}
    )
    assert _emails(south) == ["dev@south.edu"]

    missing = v1_client.get(
        "/api/v1/super-admin/school-admins", headers=seeded["headers"], params={"school_id": 999999}
    )
    assert missing.status_code == 404


@pytest.mark.parametrize(
    "q,expected",
    [
        ("asha", ["asha@north.edu"]),
        ("SHAH", ["bina@north.edu"]),
        ("dev@south", ["dev@south.edu"]),
        ("Chand Kumar", ["chand@north.edu"]),
        ("north.edu", ["chand@north.edu", "bina@north.edu", "asha@north.edu"]),
        ("nobody", []),
    ],
)
def test_search_name_and_email(v1_client, seeded, q, expected):
    res = v1_client.get("/api/v1/super-admin/school-admins", headers=seeded["headers"], params={"q": q})
    assert _emails(res) == expected
    assert res.json()["total"] == len(expected)


def test_status_filter(v1_client, seeded):
    inactive = v1_client.get("/api/v1/super-admin/school-admins", headers=seeded["headers"], params={"status": 0})
    active = v1_client.get("/api/v1/super-admin/school-admins", headers=seeded["headers"], params={"status": 1})
    assert _emails(inactive) == ["bina@north.edu"]
    assert active.json()["total"] == 3


def test_role_filter_treats_no_rows_as_school_admin(v1_client, seeded):
    accounts = v1_client.get(
        "/api/v1/super-admin/school-admins", headers=seeded["headers"], params={"role": "accounts_admin"}
    )
    default = v1_client.get(
        "/api/v1/super-admin/school-admins", headers=seeded["headers"], params={"role": "school_admin"}
    )
    academic = v1_client.get(
        "/api/v1/super-admin/school-admins", headers=seeded["headers"], params={"role": "academic_admin"}
    )
    assert _emails(accounts) == ["chand@north.edu"]
    assert accounts.json()["items"][0]["roles"] == ["accounts_admin"]
    assert accounts.json()["items"][0]["permissions"] == ["dashboard.view", "fees.manage", "reports.view"]
    assert set(_emails(default)) == {"asha@north.edu", "bina@north.edu", "dev@south.edu"}
    assert academic.json()["total"] == 0


@pytest.mark.parametrize(
    "sort,expected",
    [
        ("name", ["asha@north.edu", "bina@north.edu", "chand@north.edu", "dev@south.edu"]),
        ("-name", ["dev@south.edu", "chand@north.edu", "bina@north.edu", "asha@north.edu"]),
        ("created_at", ["asha@north.edu", "bina@north.edu", "chand@north.edu", "dev@south.edu"]),
        ("-created_at", ["dev@south.edu", "chand@north.edu", "bina@north.edu", "asha@north.edu"]),
    ],
)
def test_sorting(v1_client, seeded, sort, expected):
    res = v1_client.get("/api/v1/super-admin/school-admins", headers=seeded["headers"], params={"sort": sort})
    assert _emails(res) == expected


@pytest.mark.parametrize(
    "params",
    [{"sort": "email"}, {"role": "super_admin"}, {"status": 2}, {"page": 0}, {"page_size": 101}],
)
def test_invalid_list_params_422(v1_client, seeded, params):
    res = v1_client.get("/api/v1/super-admin/school-admins", headers=seeded["headers"], params=params)
    assert res.status_code == 422
    per_school = v1_client.get(
        f"/api/v1/super-admin/schools/{seeded['north']}/admins", headers=seeded["headers"], params=params
    )
    assert per_school.status_code == 422


def test_lists_require_super_admin(v1_client, seeded):
    user_headers = _auth_header(_signup(v1_client, "mgmt-plain@eschool.com").json()["access_token"])
    admin_login = v1_client.post("/api/v1/auth/login", json={"email": "asha@north.edu", "password": "adminpass1"})
    assert admin_login.status_code == 200, admin_login.text
    admin_headers = _auth_header(admin_login.json()["access_token"])
    for path in ("/api/v1/super-admin/school-admins", f"/api/v1/super-admin/schools/{seeded['north']}/admins"):
        assert v1_client.get(path).status_code == 401
        assert v1_client.get(path, headers=user_headers).status_code == 403
        assert v1_client.get(path, headers=admin_headers).status_code == 403


# --- profile edit, status, roles ---


def _url(seeded, key: str, suffix: str = "") -> str:
    return f"/api/v1/super-admin/schools/{seeded['north']}/admins/{seeded['ids'][key]}{suffix}"


def _login(client, email: str, password: str = "adminpass1"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def _audit(v1_db, action: str) -> list[AuditLog]:
    v1_db.expire_all()
    return list(v1_db.scalars(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)))


def _open_sessions(v1_db, user_id: str) -> int:
    v1_db.expire_all()
    return int(
        v1_db.scalar(
            select(func.count())
            .select_from(AuthSession)
            .where(AuthSession.user_id == uuid.UUID(user_id), AuthSession.revoked_at.is_(None))
        )
        or 0
    )


def _reset_token(v1_db, user_id: str, plain: str) -> None:
    v1_db.add(
        PasswordResetToken(
            user_id=uuid.UUID(user_id),
            token_hash=hash_token(plain),
            purpose="reset",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    v1_db.commit()


def _token_row(v1_db, plain: str) -> PasswordResetToken:
    v1_db.expire_all()
    return v1_db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(plain)))


def test_get_admin_profile(v1_client, seeded):
    res = v1_client.get(_url(seeded, "chand"), headers=seeded["headers"])
    assert res.status_code == 200
    assert res.json()["roles"] == ["accounts_admin"]
    assert res.json()["school_name"] == "North School"

    other_school = v1_client.get(
        f"/api/v1/super-admin/schools/{seeded['south']}/admins/{seeded['ids']['chand']}", headers=seeded["headers"]
    )
    assert other_school.status_code == 404


def test_profile_edit_audits_changed_fields(v1_client, v1_db, seeded):
    res = v1_client.patch(
        _url(seeded, "asha"), headers=seeded["headers"], json={"first_name": "Asha", "last_name": "Iyer", "mobile": "123"}
    )
    assert res.status_code == 200, res.text
    assert res.json()["last_name"] == "Iyer"
    assert res.json()["roles"] == ["school_admin"]  # roles untouched by profile edits

    rows = _audit(v1_db, "school_admin.update")
    assert len(rows) == 1
    meta = json.loads(rows[0].metadata_json)
    assert meta["changed_fields"] == ["last_name", "mobile"]  # unchanged first_name is not listed
    assert rows[0].entity_id == seeded["ids"]["asha"]
    assert rows[0].actor_email == "mgmt-sa@eschool.com"


@pytest.mark.parametrize(
    "body",
    [{"school_id": 999}, {"role": "super_admin"}, {"roles": ["school_admin"]}, {"email": "x@y.com"}, {"status": 0}],
)
def test_profile_edit_rejects_protected_fields(v1_client, v1_db, seeded, body):
    res = v1_client.patch(_url(seeded, "asha"), headers=seeded["headers"], json=body)
    assert res.status_code == 422
    v1_db.expire_all()
    user = v1_db.get(User, uuid.UUID(seeded["ids"]["asha"]))
    assert user.school_id == seeded["north"]
    assert user.email == "asha@north.edu"
    assert user.status == 1


def test_password_change_by_super_admin_revokes_sessions_and_links(v1_client, v1_db, seeded):
    old = _login(v1_client, "asha@north.edu")
    assert old.status_code == 200
    old_headers = _auth_header(old.json()["access_token"])
    _reset_token(v1_db, seeded["ids"]["asha"], "pending-link")

    res = v1_client.patch(_url(seeded, "asha"), headers=seeded["headers"], json={"password": "brandnew99"})
    assert res.status_code == 200, res.text
    assert "brandnew99" not in res.text

    assert v1_client.get("/api/v1/auth/me", headers=old_headers).status_code == 401
    assert _open_sessions(v1_db, seeded["ids"]["asha"]) == 0
    assert _token_row(v1_db, "pending-link").used_at is not None
    assert _login(v1_client, "asha@north.edu").status_code == 401
    assert _login(v1_client, "asha@north.edu", "brandnew99").status_code == 200

    meta = _audit(v1_db, "school_admin.update")[-1].metadata_json
    assert json.loads(meta)["changed_fields"] == ["password"]
    assert "brandnew99" not in meta


def test_deactivate_blocks_access_revokes_and_keeps_record(v1_client, v1_db, seeded):
    first = _login(v1_client, "asha@north.edu")
    second = _login(v1_client, "asha@north.edu")
    _reset_token(v1_db, seeded["ids"]["asha"], "deactivate-link")

    res = v1_client.patch(_url(seeded, "asha", "/status"), headers=seeded["headers"], json={"status": 0})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == 0

    for login in (first, second):
        headers = _auth_header(login.json()["access_token"])
        assert v1_client.get("/api/v1/school-admin/me", headers=headers).status_code == 401
    assert _login(v1_client, "asha@north.edu").status_code == 403
    assert _open_sessions(v1_db, seeded["ids"]["asha"]) == 0
    assert _token_row(v1_db, "deactivate-link").used_at is not None
    assert v1_db.get(User, uuid.UUID(seeded["ids"]["asha"])) is not None  # record preserved

    meta = json.loads(_audit(v1_db, "school_admin.status")[-1].metadata_json)
    assert meta == {"previous_status": 1, "status": 0, "sessions_revoked": 2}


def test_reactivate_allows_new_login_only(v1_client, v1_db, seeded):
    old = _login(v1_client, "asha@north.edu")
    old_headers = _auth_header(old.json()["access_token"])
    v1_client.patch(_url(seeded, "asha", "/status"), headers=seeded["headers"], json={"status": 0})

    res = v1_client.patch(_url(seeded, "asha", "/status"), headers=seeded["headers"], json={"status": 1})
    assert res.status_code == 200

    assert v1_client.get("/api/v1/auth/me", headers=old_headers).status_code == 401  # revoked stays revoked
    assert _login(v1_client, "asha@north.edu").status_code == 200
    meta = json.loads(_audit(v1_db, "school_admin.status")[-1].metadata_json)
    assert meta == {"previous_status": 0, "status": 1, "sessions_revoked": 0}


def test_assign_and_replace_roles(v1_client, v1_db, seeded):
    res = v1_client.patch(
        _url(seeded, "asha", "/roles"),
        headers=seeded["headers"],
        json={"roles": ["accounts_admin", "academic_admin", "accounts_admin"]},
    )
    assert res.status_code == 200, res.text
    assert res.json()["roles"] == ["academic_admin", "accounts_admin"]
    assert "fees.manage" in res.json()["permissions"]
    assert "school.manage" not in res.json()["permissions"]

    replaced = v1_client.patch(_url(seeded, "asha", "/roles"), headers=seeded["headers"], json={"roles": ["school_admin"]})
    assert replaced.json()["roles"] == ["school_admin"]
    v1_db.expire_all()
    stored = list(v1_db.scalars(select(UserAdminRole.role).where(UserAdminRole.user_id == uuid.UUID(seeded["ids"]["asha"]))))
    assert stored == ["school_admin"]

    rows = _audit(v1_db, "school_admin.roles")
    assert [json.loads(r.metadata_json) for r in rows] == [
        {"previous_roles": ["school_admin"], "roles": ["academic_admin", "accounts_admin"]},
        {"previous_roles": ["academic_admin", "accounts_admin"], "roles": ["school_admin"]},
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"roles": []},
        {"roles": ["super_admin"]},
        {"roles": ["owner"]},
        {"roles": "school_admin"},
        {"roles": ["school_admin"], "school_id": 2},
    ],
)
def test_role_assignment_rejects_invalid_and_escalation(v1_client, v1_db, seeded, body):
    res = v1_client.patch(_url(seeded, "chand", "/roles"), headers=seeded["headers"], json=body)
    assert res.status_code == 422
    v1_db.expire_all()
    user = v1_db.get(User, uuid.UUID(seeded["ids"]["chand"]))
    assert user.role == "school_admin"
    assert list(v1_db.scalars(select(UserAdminRole.role).where(UserAdminRole.user_id == user.id))) == ["accounts_admin"]
    assert _audit(v1_db, "school_admin.roles") == []


def test_role_assignment_only_by_super_admin(v1_client, seeded):
    admin_headers = _auth_header(_login(v1_client, "asha@north.edu").json()["access_token"])
    # A school admin cannot change its own or a colleague's roles.
    for key in ("asha", "chand"):
        res = v1_client.patch(_url(seeded, key, "/roles"), headers=admin_headers, json={"roles": ["school_admin"]})
        assert res.status_code == 403
    assert v1_client.patch(_url(seeded, "chand", "/roles"), json={"roles": ["school_admin"]}).status_code == 401
    wrong_school = v1_client.patch(
        f"/api/v1/super-admin/schools/{seeded['south']}/admins/{seeded['ids']['chand']}/roles",
        headers=seeded["headers"],
        json={"roles": ["school_admin"]},
    )
    assert wrong_school.status_code == 404


@pytest.mark.parametrize(
    "suffix,body,detail",
    [
        ("", {"last_name": "Unsaved"}, "School admin could not be updated"),
        ("/status", {"status": 0}, "School admin status could not be changed"),
        ("/roles", {"roles": ["academic_admin"]}, "School admin roles could not be changed"),
    ],
)
def test_audit_failure_rolls_back_change(v1_client, v1_db, seeded, monkeypatch, suffix, body, detail):
    def fail(*args, **kwargs):
        raise RuntimeError("forced audit failure")

    monkeypatch.setattr("app.api.v1.super_admin.schools.audit_service.record_audit", fail)
    res = v1_client.patch(_url(seeded, "asha", suffix), headers=seeded["headers"], json=body)

    assert res.status_code == 500
    assert res.json() == {"detail": detail}
    v1_db.expire_all()
    user = v1_db.get(User, uuid.UUID(seeded["ids"]["asha"]))
    assert user.last_name == "Rao" and user.status == 1
    assert list(v1_db.scalars(select(UserAdminRole.role).where(UserAdminRole.user_id == user.id))) == []
