"""v1 School Admin tokens on the legacy /api/admin API: RBAC, platform lists, tenant checks.

Legacy cookie sessions keep their behavior (tests/test_api.py, tests/test_role_auth.py).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from sqlalchemy import func, select

from app.api import admin as legacy_admin
from app.api import admin_writes
from app.api.deps import admin_context
from app.models.tables import SchoolClass
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User

DENIED = {"detail": "Permission denied"}


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str):
    res = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "secret123", "first_name": "Leg", "last_name": "Acy"},
    )
    assert res.status_code == 201, res.text
    return res


def _super_admin(client, v1_db, email: str = "legacy-sa@eschool.com") -> dict[str, str]:
    _signup(client, email)
    user = v1_db.scalar(select(User).where(User.email == email))
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200, login.text
    return _h(login.json()["access_token"])


def _school(client, sa, code: str) -> int:
    res = client.post(
        "/api/v1/super-admin/schools",
        headers=sa,
        json={"name": f"School {code}", "address": "1", "support_phone": "1", "support_email": f"{code.lower()}@eschool.com", "code": code},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _admin(client, sa, school_id: int, email: str, roles: list[str] | None) -> tuple[str, dict]:
    created = client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=sa,
        json={"email": email, "password": "adminpass1", "first_name": "A", "last_name": "B", **({"roles": roles} if roles else {})},
    )
    assert created.status_code == 201, created.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "adminpass1"})
    assert login.status_code == 200, login.text
    return created.json()["id"], _h(login.json()["access_token"])


@pytest.fixture()
def legacy(v1_client, v1_db):
    sa = _super_admin(v1_client, v1_db)
    school_a = _school(v1_client, sa, "LEGA01")
    school_b = _school(v1_client, sa, "LEGB01")
    _, full = _admin(v1_client, sa, school_a, "full@lega.edu", None)  # no role rows -> school_admin
    academic_id, academic = _admin(v1_client, sa, school_a, "academic@lega.edu", ["academic_admin"])
    _, accounts = _admin(v1_client, sa, school_a, "accounts@lega.edu", ["accounts_admin"])
    _, other = _admin(v1_client, sa, school_b, "other@legb.edu", None)
    return SimpleNamespace(
        sa=sa, school_a=school_a, school_b=school_b, full=full, academic=academic,
        academic_id=academic_id, accounts=accounts, other=other,
    )


def _medium(client, headers, name: str) -> int:
    res = client.post("/api/v1/school-admin/academics/mediums", headers=headers, json={"name": name})
    assert res.status_code == 201, res.text
    return res.json()["id"]


# --- reads ---


@pytest.mark.parametrize(
    "who,path,allowed",
    [
        ("accounts", "/students", False),
        ("accounts", "/exams", False),
        ("accounts", "/attendances", False),
        ("accounts", "/announcements", False),
        ("accounts", "/leaves", False),
        ("accounts", "/fees", True),
        ("accounts", "/expenses", True),
        ("academic", "/fees", False),
        ("academic", "/expenses", False),
        ("academic", "/announcements", False),
        ("academic", "/students", True),
        ("academic", "/exams", True),
        ("academic", "/attendances", True),
        ("academic", "/leaves", True),
        ("full", "/students", True),
        ("full", "/fees", True),
        ("full", "/announcements", True),
    ],
)
def test_legacy_reads_follow_role(v1_client, legacy, who, path, allowed):
    res = v1_client.get(f"/api/admin{path}", headers=getattr(legacy, who))
    if allowed:
        assert res.status_code == 200, res.text
        assert res.json()["error"] is False  # legacy response shape unchanged
    else:
        assert res.status_code == 403 and res.json() == DENIED, res.text


@pytest.mark.parametrize("who", ["full", "academic", "accounts"])
def test_every_role_reads_structure_dashboard_own_school(v1_client, legacy, who):
    headers = getattr(legacy, who)
    for path in ("/classes", "/subjects", "/dashboard", f"/schools/{legacy.school_a}", "/me"):
        assert v1_client.get(f"/api/admin{path}", headers=headers).status_code == 200, path
    assert v1_client.get(f"/api/admin/schools/{legacy.school_b}", headers=headers).status_code == 403


# --- writes ---


def test_denied_writes_change_nothing(v1_client, v1_db, legacy):
    medium = _medium(v1_client, legacy.full, "English")
    before = v1_db.scalar(select(func.count()).select_from(SchoolClass))
    for who in ("academic", "accounts"):
        res = v1_client.post("/api/admin/classes", headers=getattr(legacy, who), json={"name": "C", "medium_id": medium})
        assert res.status_code == 403 and res.json() == DENIED
    student = v1_client.post(
        "/api/admin/students",
        headers=legacy.accounts,
        json={
            "first_name": "S", "last_name": "T", "email": "s@lega.edu", "admission_no": "1",
            "class_section_id": 1, "session_year_id": 1, "guardian_id": 1, "admission_date": "2026-01-01",
        },
    )
    assert student.status_code == 403
    fee = v1_client.post(
        "/api/admin/fees", headers=legacy.academic,
        json={"name": "Term", "due_date": "2026-12-01", "session_year_id": 1},
    )
    assert fee.status_code == 403
    v1_db.expire_all()
    assert v1_db.scalar(select(func.count()).select_from(SchoolClass)) == before


def test_allowed_write_and_delete_need_the_permission(v1_client, legacy):
    medium = _medium(v1_client, legacy.full, "Hindi")
    created = v1_client.post("/api/admin/classes", headers=legacy.full, json={"name": "Grade 1", "medium_id": medium})
    assert created.status_code == 201, created.text
    class_id = created.json()["data"]["id"]
    for who in ("academic", "accounts"):
        headers = getattr(legacy, who)
        assert v1_client.patch(f"/api/admin/classes/{class_id}", headers=headers, json={"name": "X", "medium_id": medium}).status_code == 403
        assert v1_client.delete(f"/api/admin/classes/{class_id}", headers=headers).status_code == 403
    assert v1_client.delete(f"/api/admin/classes/{class_id}", headers=legacy.full).status_code == 200


# --- tenant ---


def test_related_ids_from_another_school_rejected(v1_client, legacy):
    own = _medium(v1_client, legacy.full, "Own")
    foreign = _medium(v1_client, legacy.other, "Foreign")

    create = v1_client.post("/api/admin/classes", headers=legacy.full, json={"name": "C1", "medium_id": foreign})
    assert create.status_code == 422
    assert create.json() == {"detail": "Medium does not belong to this school"}

    created = v1_client.post("/api/admin/classes", headers=legacy.full, json={"name": "C1", "medium_id": own})
    class_id = created.json()["data"]["id"]
    update = v1_client.patch(f"/api/admin/classes/{class_id}", headers=legacy.full, json={"name": "C1", "medium_id": foreign})
    assert update.status_code == 422
    rows = v1_client.get("/api/admin/classes", headers=legacy.full).json()["data"]
    assert [r for r in rows if r["id"] == class_id][0]["name"] == "C1"


def test_other_schools_rows_and_body_school_id_rejected(v1_client, legacy):
    own = _medium(v1_client, legacy.full, "Own")
    class_id = v1_client.post("/api/admin/classes", headers=legacy.full, json={"name": "Mine", "medium_id": own}).json()["data"]["id"]
    other_medium = _medium(v1_client, legacy.other, "Theirs")

    assert v1_client.patch(f"/api/admin/classes/{class_id}", headers=legacy.other, json={"name": "Hijack", "medium_id": other_medium}).status_code == 403
    assert v1_client.delete(f"/api/admin/classes/{class_id}", headers=legacy.other).status_code == 403
    body_school = v1_client.post(
        "/api/admin/classes", headers=legacy.full, json={"name": "Elsewhere", "medium_id": own, "school_id": legacy.school_b}
    )
    assert body_school.status_code == 403


def test_null_school_id_rows_are_not_owned():
    row = SimpleNamespace(school_id=None, deleted_at=None)
    db = SimpleNamespace(get=lambda model, row_id: row)
    with pytest.raises(HTTPException) as exc:
        admin_writes._get_owned(db, SchoolClass, 1, 5)
    assert exc.value.status_code == 403
    assert admin_writes._get_owned(db, SchoolClass, 1, None) is row  # platform admin unchanged


# --- platform-wide lists ---


@pytest.mark.parametrize("who", ["full", "academic", "accounts"])
def test_school_admins_cannot_list_all_schools_or_packages(v1_client, legacy, who):
    headers = getattr(legacy, who)
    for path in ("/schools", "/packages"):
        assert v1_client.get(f"/api/admin{path}", headers=headers).status_code == 403
    assert v1_client.post("/api/admin/packages", headers=headers, json={"name": "P"}).status_code == 403


def test_super_admin_legacy_access_unchanged(v1_client, legacy):
    schools = v1_client.get("/api/admin/schools", headers=legacy.sa)
    assert schools.status_code == 200
    assert {legacy.school_a, legacy.school_b} <= {row["id"] for row in schools.json()["data"]}
    assert v1_client.get("/api/admin/packages", headers=legacy.sa).status_code == 200
    assert v1_client.get("/api/admin/students", headers=legacy.sa).status_code == 200


DASHBOARD_KEYS = {
    "students", "classes", "subjects", "attendances", "exams", "fees",
    "announcements", "leaves", "expenses", "schools", "packages",
}


@pytest.mark.parametrize("who", ["full", "academic", "accounts"])
def test_school_scoped_dashboard_hides_platform_totals(v1_client, legacy, who):
    _medium(v1_client, legacy.full, "Counted")  # school A has data, school B exists too
    res = v1_client.get("/api/admin/dashboard", headers=getattr(legacy, who))

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["error"] is False
    assert set(body["data"]) == DASHBOARD_KEYS  # shape unchanged
    assert body["data"]["schools"] == 0
    assert body["data"]["packages"] == 0


def test_platform_admin_dashboard_keeps_platform_totals(v1_client, legacy):
    res = v1_client.get("/api/admin/dashboard", headers=legacy.sa)

    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert set(data) == DASHBOARD_KEYS
    assert data["schools"] >= 2  # school A and school B from the fixture


# --- role lifecycle ---


def test_role_change_applies_to_existing_legacy_session(v1_client, legacy):
    assert v1_client.get("/api/admin/fees", headers=legacy.academic).status_code == 403
    res = v1_client.patch(
        f"/api/v1/super-admin/schools/{legacy.school_a}/admins/{legacy.academic_id}/roles",
        headers=legacy.sa,
        json={"roles": ["academic_admin", "accounts_admin"]},
    )
    assert res.status_code == 200, res.text
    assert v1_client.get("/api/admin/fees", headers=legacy.academic).status_code == 200


def test_deactivated_admin_token_rejected_on_legacy_api(v1_client, legacy):
    res = v1_client.patch(
        f"/api/v1/super-admin/schools/{legacy.school_a}/admins/{legacy.academic_id}/status",
        headers=legacy.sa,
        json={"status": 0},
    )
    assert res.status_code == 200
    assert v1_client.get("/api/admin/students", headers=legacy.academic).status_code == 401


def test_unauthenticated_and_plain_user(v1_client, legacy):
    assert v1_client.get("/api/admin/students").status_code == 401
    plain = _h(_signup(v1_client, "plain@lega.edu").json()["access_token"])
    assert v1_client.get("/api/admin/students", headers=plain).status_code == 403


# --- fail closed (no HTTP) ---


def test_unknown_permission_cannot_build_a_guard():
    with pytest.raises(ValueError):
        legacy_admin._guard_for("students.read_everything")


def test_every_legacy_admin_route_has_an_explicit_guard():
    """New /api/admin routes must pick a guard; the plain guard is platform-only."""
    from app.main import app

    permission_guards = {
        legacy_admin.dashboard_guard, legacy_admin.structure_read_guard, legacy_admin.structure_write_guard,
        legacy_admin.students_guard, legacy_admin.attendance_guard, legacy_admin.exams_guard,
        legacy_admin.fees_guard, legacy_admin.announcements_guard, legacy_admin.leaves_guard,
    }
    platform_only = {
        "create_school", "update_school", "delete_school", "create_package", "update_package", "delete_package",
    }
    public_or_identity = {"login", "logout", "me"}
    for route in app.routes:
        if not (isinstance(route, APIRoute) and route.path.startswith("/api/admin")):
            continue
        calls = {dep.call for dep in route.dependant.dependencies}
        name = route.endpoint.__name__
        if name in public_or_identity:
            assert not calls & permission_guards, name
            if name == "me":
                assert admin_context in calls
            continue
        if calls & permission_guards or legacy_admin._platform_guard in calls:
            continue
        assert legacy_admin._guard in calls and name in platform_only, f"{route.path} {name} has no explicit guard"


def test_guard_rejects_v1_school_admin_identity():
    v1_admin = User(role="school_admin", school_id=1)
    with pytest.raises(HTTPException) as exc:
        legacy_admin._guard(None, (None, v1_admin, 1))
    assert exc.value.status_code == 403
    legacy_user = SimpleNamespace(role="school_admin", school_id=1)  # legacy model, same role text
    assert legacy_admin._guard(None, (None, legacy_user, 1))[1] is legacy_user
