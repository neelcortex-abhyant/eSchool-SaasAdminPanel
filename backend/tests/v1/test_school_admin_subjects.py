"""Phase 6: direct /api/v1/school-admin/subjects management."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.routing import APIRoute
from sqlalchemy import select

from app.main import app
from app.models.tables import ClassSubject, Subject
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User

SUBJECTS = "/api/v1/school-admin/subjects"
CLASSES = "/api/v1/school-admin/classes"
SECTIONS = "/api/v1/school-admin/sections"
ACADEMICS = "/api/v1/school-admin/academics"
SESSIONS_COMPACT = "/api/v1/school-admin/sessions"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _super(client, v1_db, email: str) -> dict[str, str]:
    created = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "secret123", "first_name": "A", "last_name": "B"},
    )
    assert created.status_code == 201, created.text
    user = v1_db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200, login.text
    return _auth(login.json()["access_token"])


def _school_admin(client, sa_headers, school_id: int, email: str) -> dict[str, str]:
    created = client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=sa_headers,
        json={"email": email, "password": "adminpass1", "first_name": "School", "last_name": "Admin"},
    )
    assert created.status_code == 201, created.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "adminpass1"})
    assert login.status_code == 200, login.text
    return _auth(login.json()["access_token"])


def _school(client, sa_headers, code: str) -> int:
    school = client.post(
        "/api/v1/super-admin/schools",
        headers=sa_headers,
        json={"name": f"School {code}", "code": code},
    )
    assert school.status_code == 201, school.text
    return school.json()["id"]


def _seed(client, headers):
    medium = client.post(f"{ACADEMICS}/mediums", headers=headers, json={"name": "English"})
    assert medium.status_code == 201, medium.text
    medium_id = medium.json()["id"]
    other_medium = client.post(f"{ACADEMICS}/mediums", headers=headers, json={"name": "Hindi"})
    assert other_medium.status_code == 201
    c1 = client.post(CLASSES, headers=headers, json={"name": "Grade 1", "medium_id": medium_id})
    c2 = client.post(CLASSES, headers=headers, json={"name": "Grade 2", "medium_id": medium_id})
    c_other = client.post(
        CLASSES, headers=headers, json={"name": "Grade 1 H", "medium_id": other_medium.json()["id"]}
    )
    assert c1.status_code == 201 and c2.status_code == 201 and c_other.status_code == 201
    return {
        "medium_id": medium_id,
        "other_medium_id": other_medium.json()["id"],
        "class_1": c1.json()["id"],
        "class_2": c2.json()["id"],
        "class_other_medium": c_other.json()["id"],
    }


def test_subject_crud_search_filter_and_codes(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "sub-sa@eschool.com")
    school_id = _school(v1_client, sa, "SUB01")
    admin = _school_admin(v1_client, sa, school_id, "sub-admin@eschool.com")
    ids = _seed(v1_client, admin)

    assert v1_client.post(SUBJECTS, headers=admin, json={"name": "  "}).status_code == 422
    assert (
        v1_client.post(
            SUBJECTS,
            headers=admin,
            json={"name": "Math", "medium_id": ids["medium_id"], "type": "Elective"},
        ).status_code
        == 422
    )

    created = v1_client.post(
        SUBJECTS,
        headers=admin,
        json={"name": "  Math  ", "code": " m1 ", "type": "Theory", "medium_id": ids["medium_id"]},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "Math"
    assert body["code"] == "m1"
    assert body["type"] == "Theory"
    subject_id = body["id"]

    assert (
        v1_client.post(
            SUBJECTS,
            headers=admin,
            json={"name": "Math 2", "code": "M1", "medium_id": ids["medium_id"]},
        ).status_code
        == 409
    )
    # Same code under another medium is allowed.
    other = v1_client.post(
        SUBJECTS,
        headers=admin,
        json={"name": "Math H", "code": "M1", "medium_id": ids["other_medium_id"]},
    )
    assert other.status_code == 201, other.text

    practical = v1_client.post(
        SUBJECTS,
        headers=admin,
        json={"name": "Lab", "code": "L1", "type": "Practical", "medium_id": ids["medium_id"]},
    )
    assert practical.status_code == 201, practical.text

    listed = v1_client.get(SUBJECTS, headers=admin, params={"q": "m1"})
    assert listed.status_code == 200
    assert set(listed.json().keys()) == {"items", "total", "page", "page_size"}
    assert any(item["id"] == subject_id for item in listed.json()["items"])

    # Associate then filter by class.
    replaced = v1_client.put(
        f"{SUBJECTS}/{subject_id}/classes",
        headers=admin,
        json={"class_ids": [ids["class_1"], ids["class_2"]]},
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["total"] == 2

    filtered = v1_client.get(SUBJECTS, headers=admin, params={"class_id": ids["class_1"]})
    assert filtered.status_code == 200
    assert {item["id"] for item in filtered.json()["items"]} == {subject_id}

    detail = v1_client.get(f"{SUBJECTS}/{subject_id}", headers=admin)
    assert detail.status_code == 200
    assert {c["class_id"] for c in detail.json()["classes"]} == {ids["class_1"], ids["class_2"]}

    patched = v1_client.patch(
        f"{SUBJECTS}/{subject_id}",
        headers=admin,
        json={"name": "Mathematics", "type": "Practical"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["name"] == "Mathematics"
    assert patched.json()["type"] == "Practical"
    assert patched.json()["code"] == "m1"

    # Soft-delete preserves class_subjects history rows; subject disappears from lists.
    row = v1_db.get(Subject, subject_id)
    assert row is not None
    row.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    v1_db.commit()
    assert subject_id not in {
        item["id"] for item in v1_client.get(SUBJECTS, headers=admin).json()["items"]
    }
    assert v1_client.get(f"{SUBJECTS}/{subject_id}", headers=admin).status_code == 404
    history = list(
        v1_db.scalars(select(ClassSubject).where(ClassSubject.subject_id == subject_id))
    )
    assert len(history) >= 1


def test_subject_class_replace_soft_delete_and_revive(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "sub-map-sa@eschool.com")
    school_id = _school(v1_client, sa, "SUBM")
    admin = _school_admin(v1_client, sa, school_id, "sub-map-admin@eschool.com")
    ids = _seed(v1_client, admin)
    created = v1_client.post(
        SUBJECTS,
        headers=admin,
        json={"name": "Sci", "code": "S1", "medium_id": ids["medium_id"]},
    )
    assert created.status_code == 201
    subject_id = created.json()["id"]

    assert (
        v1_client.put(
            f"{SUBJECTS}/{subject_id}/classes",
            headers=admin,
            json={"class_ids": [ids["class_other_medium"]]},
        ).status_code
        == 422
    )

    first = v1_client.put(
        f"{SUBJECTS}/{subject_id}/classes",
        headers=admin,
        json={"class_ids": [ids["class_1"], ids["class_2"]]},
    )
    assert first.status_code == 200
    link_ids = {
        row.id: row
        for row in v1_db.scalars(
            select(ClassSubject).where(
                ClassSubject.subject_id == subject_id, ClassSubject.deleted_at.is_(None)
            )
        )
    }
    assert len(link_ids) == 2
    class_1_link = next(row for row in link_ids.values() if row.class_id == ids["class_1"])

    # Remove class_1 (soft-delete), keep class_2.
    second = v1_client.put(
        f"{SUBJECTS}/{subject_id}/classes",
        headers=admin,
        json={"class_ids": [ids["class_2"]]},
    )
    assert second.status_code == 200
    assert second.json()["total"] == 1
    v1_db.expire_all()
    soft = v1_db.get(ClassSubject, class_1_link.id)
    assert soft is not None and soft.deleted_at is not None

    # Revive class_1 by including it again (same row id).
    third = v1_client.put(
        f"{SUBJECTS}/{subject_id}/classes",
        headers=admin,
        json={"class_ids": [ids["class_1"], ids["class_2"]]},
    )
    assert third.status_code == 200
    assert third.json()["total"] == 2
    v1_db.expire_all()
    revived = v1_db.get(ClassSubject, class_1_link.id)
    assert revived is not None and revived.deleted_at is None

    classes = v1_client.get(f"{SUBJECTS}/{subject_id}/classes", headers=admin)
    assert classes.status_code == 200
    assert classes.json()["total"] == 2


def test_subject_cross_school_and_rbac(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "sub-x-sa@eschool.com")
    school_a = _school(v1_client, sa, "SUBA")
    school_b = _school(v1_client, sa, "SUBB")
    admin_a = _school_admin(v1_client, sa, school_a, "sub-a@eschool.com")
    admin_b = _school_admin(v1_client, sa, school_b, "sub-b@eschool.com")
    ids_a = _seed(v1_client, admin_a)
    ids_b = _seed(v1_client, admin_b)

    created = v1_client.post(
        SUBJECTS,
        headers=admin_a,
        json={"name": "Mine", "code": "X1", "medium_id": ids_a["medium_id"]},
    )
    assert created.status_code == 201
    subject_id = created.json()["id"]

    assert v1_client.get(f"{SUBJECTS}/{subject_id}", headers=admin_b).status_code == 404
    assert (
        v1_client.put(
            f"{SUBJECTS}/{subject_id}/classes",
            headers=admin_a,
            json={"class_ids": [ids_b["class_1"]]},
        ).status_code
        == 404
    )
    assert (
        v1_client.get(SUBJECTS, headers=admin_a, params={"class_id": ids_b["class_1"]}).status_code
        == 404
    )

    created_admin = v1_client.post(
        f"/api/v1/super-admin/schools/{school_a}/admins",
        headers=sa,
        json={
            "email": "sub-academic@eschool.com",
            "password": "adminpass1",
            "first_name": "Acad",
            "last_name": "Admin",
        },
    )
    assert created_admin.status_code == 201
    assert (
        v1_client.patch(
            f"/api/v1/super-admin/schools/{school_a}/admins/{created_admin.json()['id']}/roles",
            headers=sa,
            json={"roles": ["academic_admin"]},
        ).status_code
        == 200
    )
    login = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "sub-academic@eschool.com", "password": "adminpass1"},
    )
    academic = _auth(login.json()["access_token"])
    assert v1_client.get(SUBJECTS, headers=academic).status_code == 200
    assert (
        v1_client.post(
            SUBJECTS,
            headers=academic,
            json={"name": "Nope", "medium_id": ids_a["medium_id"]},
        ).status_code
        == 403
    )


def test_direct_subject_routes_openapi():
    routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/v1/school-admin/subjects")
    ]
    method_paths = {(frozenset(route.methods), route.path) for route in routes}
    assert any("GET" in m and p == "/api/v1/school-admin/subjects" for m, p in method_paths)
    assert any("POST" in m and p == "/api/v1/school-admin/subjects" for m, p in method_paths)
    assert any("GET" in m and p == "/api/v1/school-admin/subjects/{subject_id}" for m, p in method_paths)
    assert any("PATCH" in m and p == "/api/v1/school-admin/subjects/{subject_id}" for m, p in method_paths)
    assert any(
        "GET" in m and p == "/api/v1/school-admin/subjects/{subject_id}/classes" for m, p in method_paths
    )
    assert any(
        "PUT" in m and p == "/api/v1/school-admin/subjects/{subject_id}/classes" for m, p in method_paths
    )
    assert len(routes) == len({(frozenset(r.methods), r.path) for r in routes})
    for route in routes:
        assert route.tags == ["v1-school-admin"], route.path


def test_phase3_to_5_regressions(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "sub-reg-sa@eschool.com")
    school_id = _school(v1_client, sa, "SUBR")
    admin = _school_admin(v1_client, sa, school_id, "sub-reg-admin@eschool.com")

    session = v1_client.post(
        f"{ACADEMICS}/sessions",
        headers=admin,
        json={
            "name": "2026-27",
            "start_date": "2026-04-01",
            "end_date": "2027-03-31",
            "default": 1,
        },
    )
    assert session.status_code == 201, session.text
    compact = v1_client.get(SESSIONS_COMPACT, headers=admin)
    assert compact.status_code == 200
    for item in compact.json()["items"]:
        assert set(item.keys()) == {"id", "name", "default"}

    medium = v1_client.post(f"{ACADEMICS}/mediums", headers=admin, json={"name": "Eng"})
    assert medium.status_code == 201
    medium_id = medium.json()["id"]
    klass = v1_client.post(CLASSES, headers=admin, json={"name": "Reg", "medium_id": medium_id})
    assert klass.status_code == 201
    section = v1_client.post(
        SECTIONS, headers=admin, json={"name": "A", "class_id": klass.json()["id"]}
    )
    assert section.status_code == 201, section.text
    assert v1_client.get(f"{CLASSES}/{klass.json()['id']}", headers=admin).status_code == 200
    assert v1_client.get(f"{SECTIONS}/{section.json()['id']}", headers=admin).status_code == 200
