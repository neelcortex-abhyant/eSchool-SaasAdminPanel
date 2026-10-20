"""School Admin RBAC: role/permission catalog."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User
from app.services.v1 import rbac


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str):
    res = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "secret123", "first_name": "Rbac", "last_name": "User"},
    )
    assert res.status_code == 201, res.text
    return res


def _super_admin_headers(client, v1_db, email: str = "rbac-sa@eschool.com") -> dict[str, str]:
    _signup(client, email)
    user = v1_db.scalar(select(User).where(User.email == email))
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200, login.text
    return _auth_header(login.json()["access_token"])


def _school_admin_headers(client, sa_headers) -> dict[str, str]:
    school = client.post(
        "/api/v1/super-admin/schools",
        headers=sa_headers,
        json={"name": "Rbac School", "address": "1", "support_phone": "1", "support_email": "rbac@eschool.com", "code": "RBAC01"},
    )
    assert school.status_code == 201, school.text
    admin = client.post(
        f"/api/v1/super-admin/schools/{school.json()['id']}/admins",
        headers=sa_headers,
        json={"email": "rbac-admin@eschool.com", "password": "adminpass1", "first_name": "R", "last_name": "A"},
    )
    assert admin.status_code == 201, admin.text
    login = client.post("/api/v1/auth/login", json={"email": "rbac-admin@eschool.com", "password": "adminpass1"})
    assert login.status_code == 200, login.text
    return _auth_header(login.json()["access_token"])


# --- catalog endpoints ---


def test_roles_catalog(v1_client, v1_db):
    res = v1_client.get("/api/v1/super-admin/roles", headers=_super_admin_headers(v1_client, v1_db))

    assert res.status_code == 200
    items = res.json()["items"]
    assert [r["key"] for r in items] == ["school_admin", "academic_admin", "accounts_admin"]
    by_key = {r["key"]: r for r in items}
    assert by_key["school_admin"]["permissions"] == list(rbac.PERMISSIONS)
    assert by_key["accounts_admin"]["permissions"] == ["dashboard.view", "fees.manage", "reports.view"]
    assert "students.manage" not in by_key["accounts_admin"]["permissions"]
    assert "fees.manage" not in by_key["academic_admin"]["permissions"]
    assert all("super_admin" != r["key"] for r in items)


def test_permissions_catalog(v1_client, v1_db):
    res = v1_client.get("/api/v1/super-admin/permissions", headers=_super_admin_headers(v1_client, v1_db))

    assert res.status_code == 200
    assert res.json()["items"] == [{"key": k, "label": v} for k, v in rbac.PERMISSIONS.items()]
    assert len(res.json()["items"]) == 9


@pytest.mark.parametrize("path", ["/api/v1/super-admin/roles", "/api/v1/super-admin/permissions"])
def test_catalog_requires_super_admin(v1_client, v1_db, path):
    sa_headers = _super_admin_headers(v1_client, v1_db)
    user_headers = _auth_header(_signup(v1_client, "rbac-plain@eschool.com").json()["access_token"])

    assert v1_client.get(path).status_code == 401
    assert v1_client.get(path, headers=_auth_header("bad-token")).status_code == 401
    assert v1_client.get(path, headers=user_headers).status_code == 403
    assert v1_client.get(path, headers=_school_admin_headers(v1_client, sa_headers)).status_code == 403


# --- catalog rules (no HTTP) ---


def test_every_role_permission_is_in_the_catalog():
    for role in rbac.ADMIN_ROLES.values():
        assert set(role["permissions"]) <= set(rbac.PERMISSIONS)


def test_normalize_roles_dedupes_in_catalog_order():
    assert rbac.normalize_roles(["accounts_admin", "school_admin", "accounts_admin"]) == [
        "school_admin",
        "accounts_admin",
    ]


@pytest.mark.parametrize("roles", [[], ["super_admin"], ["user"], ["school_admin", "owner"]])
def test_normalize_roles_rejects_empty_and_unknown(roles):
    with pytest.raises(rbac.RbacError) as exc:
        rbac.normalize_roles(roles)
    assert exc.value.status_code == 422


def test_permissions_for_roles_is_a_union_in_catalog_order():
    perms = rbac.permissions_for_roles(["accounts_admin", "academic_admin"])
    assert perms == [p for p in rbac.PERMISSIONS if p not in {"school.manage", "settings.manage"}]


# --- backend enforcement ---


def _school(client, sa_headers, code: str) -> int:
    res = client.post(
        "/api/v1/super-admin/schools",
        headers=sa_headers,
        json={"name": f"School {code}", "address": "1", "support_phone": "1", "support_email": f"{code.lower()}@eschool.com", "code": code},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _admin_with_roles(client, sa_headers, school_id: int, email: str, roles: list[str] | None) -> tuple[str, dict]:
    created = client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=sa_headers,
        json={"email": email, "password": "adminpass1", "first_name": "Role", "last_name": "Admin"},
    )
    assert created.status_code == 201, created.text
    admin_id = created.json()["id"]
    if roles is not None:
        res = client.patch(
            f"/api/v1/super-admin/schools/{school_id}/admins/{admin_id}/roles",
            headers=sa_headers,
            json={"roles": roles},
        )
        assert res.status_code == 200, res.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "adminpass1"})
    assert login.status_code == 200, login.text
    return admin_id, _auth_header(login.json()["access_token"])


@pytest.fixture()
def role_setup(v1_client, v1_db):
    sa = _super_admin_headers(v1_client, v1_db)
    school_id = _school(v1_client, sa, "ENF01")
    _, full = _admin_with_roles(v1_client, sa, school_id, "full@enf.edu", None)
    academic_id, academic = _admin_with_roles(v1_client, sa, school_id, "academic@enf.edu", ["academic_admin"])
    _, accounts = _admin_with_roles(v1_client, sa, school_id, "accounts@enf.edu", ["accounts_admin"])
    return {
        "sa": sa,
        "school_id": school_id,
        "full": full,
        "academic": academic,
        "academic_id": academic_id,
        "accounts": accounts,
    }


ACADEMICS = "/api/v1/school-admin/academics"


def _denied(res) -> bool:
    return res.status_code == 403 and res.json() == {"detail": "Permission denied"}


@pytest.mark.parametrize(
    "who,resource,allowed",
    [
        ("accounts", "students", False),
        ("accounts", "parents", False),
        ("accounts", "teachers", False),
        ("accounts", "exams", False),
        ("accounts", "attendances", False),
        ("accounts", "notices", False),
        ("accounts", "fees", True),
        ("accounts", "expenses", True),
        ("academic", "fees", False),
        ("academic", "expenses", False),
        ("academic", "notices", False),
        ("academic", "students", True),
        ("academic", "teachers", True),
        ("academic", "leaves", True),
        ("academic", "exams", True),
        ("academic", "attendances", True),
        ("full", "students", True),
        ("full", "fees", True),
        ("full", "notices", True),
    ],
)
def test_module_reads_follow_role(v1_client, role_setup, who, resource, allowed):
    res = v1_client.get(f"{ACADEMICS}/{resource}", headers=role_setup[who])
    if allowed:
        assert res.status_code == 200, res.text
    else:
        assert _denied(res), res.text


@pytest.mark.parametrize("who", ["academic", "accounts", "full"])
def test_every_role_can_read_structure_and_context(v1_client, role_setup, who):
    headers = role_setup[who]
    for resource in ("classes", "sections", "subjects", "mediums", "sessions", "class-sections"):
        assert v1_client.get(f"{ACADEMICS}/{resource}", headers=headers).status_code == 200
    assert v1_client.get(f"{ACADEMICS}/summary", headers=headers).status_code == 200
    for path in ("/api/v1/school-admin/me", "/api/v1/school-admin/school", "/api/v1/school-admin/sessions"):
        assert v1_client.get(path, headers=headers).status_code == 200


def test_structure_writes_need_school_manage(v1_client, role_setup):
    for who in ("academic", "accounts"):
        assert _denied(v1_client.post(f"{ACADEMICS}/mediums", headers=role_setup[who], json={"name": "Hindi"}))
    created = v1_client.post(f"{ACADEMICS}/mediums", headers=role_setup["full"], json={"name": "English"})
    assert created.status_code == 201, created.text
    medium_id = created.json()["id"]
    for who in ("academic", "accounts"):
        assert _denied(v1_client.patch(f"{ACADEMICS}/mediums/{medium_id}", headers=role_setup[who], json={"name": "X"}))
        assert _denied(v1_client.delete(f"{ACADEMICS}/mediums/{medium_id}", headers=role_setup[who]))


def test_denied_writes_change_nothing(v1_client, role_setup):
    before = v1_client.get(f"{ACADEMICS}/fees", headers=role_setup["full"]).json()["total"]
    res = v1_client.post(
        f"{ACADEMICS}/fees", headers=role_setup["academic"], json={"name": "Term", "due_date": "2026-12-01", "due_charges": 1, "session_year_id": 1}
    )
    assert _denied(res)
    assert v1_client.get(f"{ACADEMICS}/fees", headers=role_setup["full"]).json()["total"] == before


def test_subscription_billing_needs_settings_manage(v1_client, role_setup):
    school_id = role_setup["school_id"]
    for path in (f"/api/v1/schools/{school_id}/payments", f"/api/v1/schools/{school_id}/invoices"):
        assert _denied(v1_client.get(path, headers=role_setup["academic"]))
        assert _denied(v1_client.get(path, headers=role_setup["accounts"]))
        assert v1_client.get(path, headers=role_setup["full"]).status_code != 403
        assert v1_client.get(path, headers=role_setup["sa"]).status_code != 403  # Super Admin unchanged
    assert _denied(v1_client.post("/api/v1/payments/initiate", headers=role_setup["accounts"], json={}))


def test_role_change_applies_to_existing_session(v1_client, role_setup):
    headers = role_setup["academic"]
    assert _denied(v1_client.get(f"{ACADEMICS}/fees", headers=headers))
    res = v1_client.patch(
        f"/api/v1/super-admin/schools/{role_setup['school_id']}/admins/{role_setup['academic_id']}/roles",
        headers=role_setup["sa"],
        json={"roles": ["academic_admin", "accounts_admin"]},
    )
    assert res.status_code == 200, res.text
    assert v1_client.get(f"{ACADEMICS}/fees", headers=headers).status_code == 200


def test_unknown_resource_still_404(v1_client, role_setup):
    assert v1_client.get(f"{ACADEMICS}/salaries", headers=role_setup["accounts"]).status_code == 404


def test_super_admin_and_plain_user_cannot_use_school_admin_modules(v1_client, role_setup):
    plain = _auth_header(_signup(v1_client, "enf-plain@eschool.com").json()["access_token"])
    for headers in (role_setup["sa"], plain):
        assert v1_client.get(f"{ACADEMICS}/students", headers=headers).status_code == 403
    assert v1_client.get(f"{ACADEMICS}/students").status_code == 401


# --- tenant: academics PATCH cannot point at another school's rows ---


def test_patch_rejects_other_school_reference(v1_client, role_setup):
    sa = role_setup["sa"]
    other_school = _school(v1_client, sa, "ENF02")
    _, other = _admin_with_roles(v1_client, sa, other_school, "other@enf2.edu", None)
    own_medium = v1_client.post(f"{ACADEMICS}/mediums", headers=role_setup["full"], json={"name": "Own"}).json()["id"]
    foreign_medium = v1_client.post(f"{ACADEMICS}/mediums", headers=other, json={"name": "Foreign"}).json()["id"]
    created = v1_client.post(
        f"{ACADEMICS}/classes", headers=role_setup["full"], json={"name": "Class 1", "medium_id": own_medium}
    )
    assert created.status_code == 201, created.text
    class_id = created.json()["id"]

    rejected = v1_client.patch(
        f"{ACADEMICS}/classes/{class_id}", headers=role_setup["full"], json={"medium_id": foreign_medium}
    )
    assert rejected.status_code == 422
    assert rejected.json() == {"detail": "Medium does not belong to this school"}
    listed = v1_client.get(f"{ACADEMICS}/classes", headers=role_setup["full"]).json()["items"]
    assert [row["medium_id"] for row in listed if row["id"] == class_id] == [own_medium]

    second_medium = v1_client.post(f"{ACADEMICS}/mediums", headers=role_setup["full"], json={"name": "Own 2"}).json()["id"]
    accepted = v1_client.patch(
        f"{ACADEMICS}/classes/{class_id}", headers=role_setup["full"], json={"medium_id": second_medium}
    )
    assert accepted.status_code == 200, accepted.text

    # The other school's admin cannot touch this school's class at all.
    assert v1_client.patch(f"{ACADEMICS}/classes/{class_id}", headers=other, json={"name": "Hijack"}).status_code == 404
