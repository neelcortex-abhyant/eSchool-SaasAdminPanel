"""Phase 7: direct /api/v1/school-admin/teacher-assignments."""

from __future__ import annotations

from fastapi.routing import APIRoute
from sqlalchemy import select

from app.main import app
from app.models.tables import TeacherAssignment
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User

ASSIGNMENTS = "/api/v1/school-admin/teacher-assignments"
CLASSES = "/api/v1/school-admin/classes"
SECTIONS = "/api/v1/school-admin/sections"
SUBJECTS = "/api/v1/school-admin/subjects"
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
    klass = client.post(CLASSES, headers=headers, json={"name": "Grade 1", "medium_id": medium_id})
    assert klass.status_code == 201, klass.text
    class_id = klass.json()["id"]
    section = client.post(SECTIONS, headers=headers, json={"name": "A", "class_id": class_id})
    assert section.status_code == 201, section.text
    subject = client.post(
        SUBJECTS,
        headers=headers,
        json={"name": "Math", "code": "M1", "medium_id": medium_id},
    )
    assert subject.status_code == 201, subject.text
    subject_id = subject.json()["id"]
    mapped = client.put(
        f"{SUBJECTS}/{subject_id}/classes",
        headers=headers,
        json={"class_ids": [class_id]},
    )
    assert mapped.status_code == 200, mapped.text
    session = client.post(
        f"{ACADEMICS}/sessions",
        headers=headers,
        json={"name": "2026-27", "start_date": "2026-04-01", "end_date": "2027-03-31", "default": 1},
    )
    assert session.status_code == 201, session.text
    teacher = client.post(
        f"{ACADEMICS}/teachers",
        headers=headers,
        json={
            "first_name": "T",
            "last_name": "One",
            "email": f"t-{class_id}@eschool.com",
            "password": "teacherpass1",
        },
    )
    assert teacher.status_code == 201, teacher.text
    return {
        "medium_id": medium_id,
        "class_id": class_id,
        "section_id": section.json()["id"],
        "subject_id": subject_id,
        "session_id": session.json()["id"],
        "teacher_id": teacher.json()["id"],
    }


def test_assignment_crud_filters_duplicate_and_soft_delete(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "ta-sa@eschool.com")
    school_id = _school(v1_client, sa, "TA01")
    admin = _school_admin(v1_client, sa, school_id, "ta-admin@eschool.com")
    ids = _seed(v1_client, admin)

    assert (
        v1_client.post(
            ASSIGNMENTS, headers=admin, json={"teacher_id": ids["teacher_id"]}
        ).status_code
        == 422
    )
    # class without section
    assert (
        v1_client.post(
            ASSIGNMENTS,
            headers=admin,
            json={
                "teacher_id": ids["teacher_id"],
                "subject_id": ids["subject_id"],
                "class_id": ids["class_id"],
            },
        ).status_code
        == 422
    )

    created = v1_client.post(
        ASSIGNMENTS,
        headers=admin,
        json={
            "teacher_id": ids["teacher_id"],
            "subject_id": ids["subject_id"],
            "class_id": ids["class_id"],
            "section_id": ids["section_id"],
            "session_id": ids["session_id"],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["teacher_id"] == ids["teacher_id"]
    assert body["subject_id"] == ids["subject_id"]
    assert body["class_id"] == ids["class_id"]
    assert body["section_id"] == ids["section_id"]
    assert body["session_id"] == ids["session_id"]
    assert body["class_section_id"]
    assignment_id = body["id"]

    assert (
        v1_client.post(
            ASSIGNMENTS,
            headers=admin,
            json={
                "teacher_id": ids["teacher_id"],
                "subject_id": ids["subject_id"],
                "class_id": ids["class_id"],
                "section_id": ids["section_id"],
                "session_id": ids["session_id"],
            },
        ).status_code
        == 409
    )

    # Team-teaching: second teacher same class/section/subject/session is allowed.
    teacher2 = v1_client.post(
        f"{ACADEMICS}/teachers",
        headers=admin,
        json={
            "first_name": "T",
            "last_name": "Two",
            "email": "t2-ta@eschool.com",
            "password": "teacherpass1",
        },
    )
    assert teacher2.status_code == 201
    team = v1_client.post(
        ASSIGNMENTS,
        headers=admin,
        json={
            "teacher_id": teacher2.json()["id"],
            "subject_id": ids["subject_id"],
            "class_id": ids["class_id"],
            "section_id": ids["section_id"],
            "session_id": ids["session_id"],
        },
    )
    assert team.status_code == 201, team.text

    listed = v1_client.get(ASSIGNMENTS, headers=admin)
    assert listed.status_code == 200
    assert set(listed.json().keys()) == {"items", "total", "page", "page_size"}
    assert listed.json()["total"] == 2

    for param, value in (
        ("teacher_id", ids["teacher_id"]),
        ("class_id", ids["class_id"]),
        ("section_id", ids["section_id"]),
        ("subject_id", ids["subject_id"]),
        ("session_id", ids["session_id"]),
    ):
        filtered = v1_client.get(ASSIGNMENTS, headers=admin, params={param: value})
        assert filtered.status_code == 200, param
        assert filtered.json()["total"] >= 1

    detail = v1_client.get(f"{ASSIGNMENTS}/{assignment_id}", headers=admin)
    assert detail.status_code == 200
    assert detail.json()["class_name"] == "Grade 1"
    assert detail.json()["section_name"] == "A"

    patched = v1_client.patch(
        f"{ASSIGNMENTS}/{assignment_id}",
        headers=admin,
        json={"session_id": ids["session_id"]},
    )
    assert patched.status_code == 200

    deleted = v1_client.delete(f"{ASSIGNMENTS}/{assignment_id}", headers=admin)
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
    row = v1_db.get(TeacherAssignment, assignment_id)
    assert row is not None and row.deleted_at is not None
    assert assignment_id not in {
        item["id"] for item in v1_client.get(ASSIGNMENTS, headers=admin).json()["items"]
    }
    assert v1_client.get(f"{ASSIGNMENTS}/{assignment_id}", headers=admin).status_code == 404


def test_assignment_mismatch_and_cross_school(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "ta-x-sa@eschool.com")
    school_a = _school(v1_client, sa, "TAA")
    school_b = _school(v1_client, sa, "TAB")
    admin_a = _school_admin(v1_client, sa, school_a, "ta-a@eschool.com")
    admin_b = _school_admin(v1_client, sa, school_b, "ta-b@eschool.com")
    ids_a = _seed(v1_client, admin_a)
    ids_b = _seed(v1_client, admin_b)

    # Section not linked to a different class in same school.
    other_class = v1_client.post(
        CLASSES, headers=admin_a, json={"name": "Grade 2", "medium_id": ids_a["medium_id"]}
    )
    assert other_class.status_code == 201
    mismatch = v1_client.post(
        ASSIGNMENTS,
        headers=admin_a,
        json={
            "teacher_id": ids_a["teacher_id"],
            "subject_id": ids_a["subject_id"],
            "class_id": other_class.json()["id"],
            "section_id": ids_a["section_id"],
            "session_id": ids_a["session_id"],
        },
    )
    assert mismatch.status_code == 422

    # Subject not mapped to class.
    unmapped = v1_client.post(
        SUBJECTS,
        headers=admin_a,
        json={"name": "Hist", "code": "H1", "medium_id": ids_a["medium_id"]},
    )
    assert unmapped.status_code == 201
    no_map = v1_client.post(
        ASSIGNMENTS,
        headers=admin_a,
        json={
            "teacher_id": ids_a["teacher_id"],
            "subject_id": unmapped.json()["id"],
            "class_id": ids_a["class_id"],
            "section_id": ids_a["section_id"],
            "session_id": ids_a["session_id"],
        },
    )
    assert no_map.status_code == 422

    created = v1_client.post(
        ASSIGNMENTS,
        headers=admin_a,
        json={
            "teacher_id": ids_a["teacher_id"],
            "subject_id": ids_a["subject_id"],
            "class_id": ids_a["class_id"],
            "section_id": ids_a["section_id"],
            "session_id": ids_a["session_id"],
        },
    )
    assert created.status_code == 201
    assignment_id = created.json()["id"]
    assert v1_client.get(f"{ASSIGNMENTS}/{assignment_id}", headers=admin_b).status_code == 404
    assert (
        v1_client.post(
            ASSIGNMENTS,
            headers=admin_a,
            json={
                "teacher_id": ids_a["teacher_id"],
                "subject_id": ids_b["subject_id"],
            },
        ).status_code
        == 422
    )


def test_assignment_rbac_accounts_denied(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "ta-rbac-sa@eschool.com")
    school_id = _school(v1_client, sa, "TARB")
    full = _school_admin(v1_client, sa, school_id, "ta-full@eschool.com")
    ids = _seed(v1_client, full)

    created_admin = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=sa,
        json={
            "email": "ta-accounts@eschool.com",
            "password": "adminpass1",
            "first_name": "Acc",
            "last_name": "Admin",
        },
    )
    assert created_admin.status_code == 201
    assert (
        v1_client.patch(
            f"/api/v1/super-admin/schools/{school_id}/admins/{created_admin.json()['id']}/roles",
            headers=sa,
            json={"roles": ["accounts_admin"]},
        ).status_code
        == 200
    )
    login = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "ta-accounts@eschool.com", "password": "adminpass1"},
    )
    accounts = _auth(login.json()["access_token"])
    assert v1_client.get(ASSIGNMENTS, headers=accounts).status_code == 403
    assert (
        v1_client.post(
            ASSIGNMENTS,
            headers=accounts,
            json={"teacher_id": ids["teacher_id"], "subject_id": ids["subject_id"]},
        ).status_code
        == 403
    )


def test_direct_assignment_routes_openapi():
    routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path.startswith("/api/v1/school-admin/teacher-assignments")
    ]
    method_paths = {(frozenset(route.methods), route.path) for route in routes}
    assert any("GET" in m and p == "/api/v1/school-admin/teacher-assignments" for m, p in method_paths)
    assert any("POST" in m and p == "/api/v1/school-admin/teacher-assignments" for m, p in method_paths)
    assert any(
        "GET" in m and p == "/api/v1/school-admin/teacher-assignments/{assignment_id}"
        for m, p in method_paths
    )
    assert any(
        "PATCH" in m and p == "/api/v1/school-admin/teacher-assignments/{assignment_id}"
        for m, p in method_paths
    )
    assert any(
        "DELETE" in m and p == "/api/v1/school-admin/teacher-assignments/{assignment_id}"
        for m, p in method_paths
    )
    for route in routes:
        assert route.tags == ["v1-school-admin"], route.path


def test_phase3_to_6_regressions(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "ta-reg-sa@eschool.com")
    school_id = _school(v1_client, sa, "TARG")
    admin = _school_admin(v1_client, sa, school_id, "ta-reg-admin@eschool.com")
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
    assert session.status_code == 201
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
    assert section.status_code == 201
    subject = v1_client.post(
        SUBJECTS, headers=admin, json={"name": "Sci", "code": "S1", "medium_id": medium_id}
    )
    assert subject.status_code == 201
