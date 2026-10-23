"""Module 3: Teacher & non-teaching Staff CRUD, RBAC, isolation, deactivation."""

from __future__ import annotations

from fastapi.routing import APIRoute
from sqlalchemy import select

from app.core.security import verify_password
from app.main import app
from app.models.tables import (
    USER_MODEL,
    ModelHasRole,
    PersonalAccessToken,
    Role,
    Staff,
    TeacherAssignment,
    User,
)
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User as V1User
from app.services.mobile_auth import issue_token

TEACHERS = "/api/v1/school-admin/teachers"
STAFF = "/api/v1/school-admin/staff"
PEOPLE = "/api/v1/school-admin/people"
ASSIGNMENTS = "/api/v1/school-admin/teacher-assignments"
ACADEMICS = "/api/v1/school-admin/academics"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _super(client, v1_db, email: str) -> dict[str, str]:
    created = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "secret123", "first_name": "A", "last_name": "B"},
    )
    assert created.status_code == 201, created.text
    user = v1_db.scalar(select(V1User).where(V1User.email == email))
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
        json={
            "email": email,
            "password": "adminpass1",
            "first_name": "School",
            "last_name": "Admin",
        },
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


def _teacher_payload(email: str, **extra):
    body = {
        "first_name": "Tea",
        "last_name": "Cher",
        "email": email,
        "password": "teacherpass1",
        "qualification": "M.Ed",
        "employee_id": extra.pop("employee_id", "EMP-T1"),
        "joining_date": "2024-06-01",
        "employment_status": "active",
        "department": "Academics",
        "designation": "Senior Teacher",
        "mobile": "9000000001",
    }
    body.update(extra)
    return body


def _staff_payload(email: str, **extra):
    body = {
        "first_name": "Non",
        "last_name": "Teach",
        "email": email,
        "password": "staffpass12",
        "department": "Accounts",
        "designation": "Clerk",
        "employee_id": extra.pop("employee_id", "EMP-S1"),
        "joining_date": "2023-01-15",
        "employment_status": "active",
    }
    body.update(extra)
    return body


def test_openapi_registers_teacher_staff_people_routes():
    paths = app.openapi()["paths"]
    for path in (
        TEACHERS,
        f"{TEACHERS}/{{teacher_id}}",
        f"{TEACHERS}/{{teacher_id}}/status",
        STAFF,
        f"{STAFF}/{{staff_id}}",
        f"{STAFF}/{{staff_id}}/status",
        PEOPLE,
    ):
        assert path in paths, path
    route_paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    assert "/api/v1/school-admin/teachers" in route_paths
    assert "/api/v1/school-admin/staff" in route_paths


def test_teacher_crud_filters_pagination_and_usable_password(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "m3-t-sa@eschool.com")
    school_id = _school(v1_client, sa, "M3T1")
    admin = _school_admin(v1_client, sa, school_id, "m3-t-admin@eschool.com")

    missing_pw = v1_client.post(
        TEACHERS,
        headers=admin,
        json={"first_name": "A", "last_name": "B", "email": "nopw@eschool.com"},
    )
    assert missing_pw.status_code == 422

    created = v1_client.post(
        TEACHERS,
        headers=admin,
        json=_teacher_payload("m3-teacher@eschool.com"),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["email"] == "m3-teacher@eschool.com"
    assert body["role"] == "Teacher"
    assert body["qualification"] == "M.Ed"
    assert body["employee_id"] == "EMP-T1"
    assert body["joining_date"] == "2024-06-01"
    assert body["employment_status"] == "active"
    assert body["department"] == "Academics"
    assert body["designation"] == "Senior Teacher"
    assert body["status"] == 1
    assert "password" not in body
    teacher_id = body["id"]

    user = v1_db.get(User, teacher_id)
    assert user is not None
    assert verify_password("teacherpass1", user.password)
    role = v1_db.scalar(
        select(Role).where(
            Role.name == "Teacher", Role.school_id == school_id, Role.guard_name == "web"
        )
    )
    assert role is not None
    assert (
        v1_db.scalar(
            select(ModelHasRole).where(
                ModelHasRole.role_id == role.id,
                ModelHasRole.model_id == teacher_id,
                ModelHasRole.model_type == USER_MODEL,
            )
        )
        is not None
    )
    staff = v1_db.scalar(select(Staff).where(Staff.user_id == teacher_id, Staff.school_id == school_id))
    assert staff is not None

    dup_email = v1_client.post(
        TEACHERS,
        headers=admin,
        json=_teacher_payload("m3-teacher@eschool.com", employee_id="EMP-T2"),
    )
    assert dup_email.status_code == 409

    dup_emp = v1_client.post(
        TEACHERS,
        headers=admin,
        json=_teacher_payload("m3-teacher2@eschool.com", employee_id="EMP-T1"),
    )
    assert dup_emp.status_code == 409

    second = v1_client.post(
        TEACHERS,
        headers=admin,
        json=_teacher_payload(
            "m3-teacher2@eschool.com",
            employee_id="EMP-T2",
            department="Science",
            designation="Lab Teacher",
            employment_status="on_leave",
        ),
    )
    assert second.status_code == 201, second.text

    listed = v1_client.get(TEACHERS, headers=admin)
    assert listed.status_code == 200
    assert set(listed.json().keys()) == {"items", "total", "page", "page_size"}
    assert listed.json()["total"] == 2

    filtered = v1_client.get(
        TEACHERS, headers=admin, params={"department": "Science", "employment_status": "on_leave"}
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["email"] == "m3-teacher2@eschool.com"

    searched = v1_client.get(TEACHERS, headers=admin, params={"q": "EMP-T1"})
    assert searched.status_code == 200
    assert searched.json()["total"] == 1

    paged = v1_client.get(TEACHERS, headers=admin, params={"page": 1, "page_size": 1})
    assert paged.status_code == 200
    assert paged.json()["page_size"] == 1
    assert len(paged.json()["items"]) == 1
    assert paged.json()["total"] == 2

    profile = v1_client.get(f"{TEACHERS}/{teacher_id}", headers=admin)
    assert profile.status_code == 200
    assert "assignments" in profile.json()

    updated = v1_client.patch(
        f"{TEACHERS}/{teacher_id}",
        headers=admin,
        json={"qualification": "PhD", "designation": "HOD", "employment_status": "active"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["qualification"] == "PhD"
    assert updated.json()["designation"] == "HOD"

    bad_status_in_patch = v1_client.patch(
        f"{TEACHERS}/{teacher_id}", headers=admin, json={"status": 0}
    )
    assert bad_status_in_patch.status_code == 422


def test_staff_crud_and_not_listed_as_teacher(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "m3-s-sa@eschool.com")
    school_id = _school(v1_client, sa, "M3S1")
    admin = _school_admin(v1_client, sa, school_id, "m3-s-admin@eschool.com")

    created = v1_client.post(STAFF, headers=admin, json=_staff_payload("m3-staff@eschool.com"))
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["role"] == "Staff"
    assert body["department"] == "Accounts"
    assert body["designation"] == "Clerk"
    assert "password" not in body
    staff_id = body["id"]

    user = v1_db.get(User, staff_id)
    assert verify_password("staffpass12", user.password)
    role = v1_db.scalar(
        select(Role).where(Role.name == "Staff", Role.school_id == school_id, Role.guard_name == "web")
    )
    assert role is not None
    teacher_role = v1_db.scalar(
        select(Role).where(
            Role.name == "Teacher", Role.school_id == school_id, Role.guard_name == "web"
        )
    )
    if teacher_role is not None:
        assert (
            v1_db.scalar(
                select(ModelHasRole).where(
                    ModelHasRole.role_id == teacher_role.id,
                    ModelHasRole.model_id == staff_id,
                    ModelHasRole.model_type == USER_MODEL,
                )
            )
            is None
        )

    teachers = v1_client.get(TEACHERS, headers=admin)
    assert teachers.status_code == 200
    assert teachers.json()["total"] == 0

    profile = v1_client.get(f"{STAFF}/{staff_id}", headers=admin)
    assert profile.status_code == 200
    assert profile.json()["email"] == "m3-staff@eschool.com"

    updated = v1_client.patch(
        f"{STAFF}/{staff_id}",
        headers=admin,
        json={"department": "Admin", "designation": "Office Manager"},
    )
    assert updated.status_code == 200
    assert updated.json()["department"] == "Admin"

    people = v1_client.get(PEOPLE, headers=admin, params={"role": "staff"})
    assert people.status_code == 200
    assert people.json()["total"] == 1


def test_cross_school_isolation_and_deactivation_revokes_tokens(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "m3-x-sa@eschool.com")
    school_a = _school(v1_client, sa, "M3XA")
    school_b = _school(v1_client, sa, "M3XB")
    admin_a = _school_admin(v1_client, sa, school_a, "m3-xa@eschool.com")
    admin_b = _school_admin(v1_client, sa, school_b, "m3-xb@eschool.com")

    teacher = v1_client.post(
        TEACHERS, headers=admin_a, json=_teacher_payload("m3-xa-t@eschool.com", employee_id="XA-T1")
    )
    assert teacher.status_code == 201
    teacher_id = teacher.json()["id"]

    staff = v1_client.post(
        STAFF, headers=admin_a, json=_staff_payload("m3-xa-s@eschool.com", employee_id="XA-S1")
    )
    assert staff.status_code == 201
    staff_id = staff.json()["id"]

    assert v1_client.get(f"{TEACHERS}/{teacher_id}", headers=admin_b).status_code == 404
    assert v1_client.get(f"{STAFF}/{staff_id}", headers=admin_b).status_code == 404
    assert (
        v1_client.patch(
            f"{TEACHERS}/{teacher_id}", headers=admin_b, json={"qualification": "X"}
        ).status_code
        == 404
    )

    token = issue_token(v1_db, v1_db.get(User, teacher_id))
    assert (
        v1_db.query(PersonalAccessToken)
        .filter(
            PersonalAccessToken.tokenable_type == USER_MODEL,
            PersonalAccessToken.tokenable_id == teacher_id,
        )
        .count()
        == 1
    )

    deactivated = v1_client.patch(
        f"{TEACHERS}/{teacher_id}/status", headers=admin_a, json={"status": 0}
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == 0
    assert v1_db.get(User, teacher_id).status == 0
    assert v1_db.get(Staff, teacher.json()["staff_id"]) is not None or v1_db.scalar(
        select(Staff).where(Staff.user_id == teacher_id)
    )
    assert (
        v1_db.query(PersonalAccessToken)
        .filter(
            PersonalAccessToken.tokenable_type == USER_MODEL,
            PersonalAccessToken.tokenable_id == teacher_id,
        )
        .count()
        == 0
    )
    # token string unused but issued before revoke
    assert "|" in token

    staff_off = v1_client.patch(
        f"{STAFF}/{staff_id}/status", headers=admin_a, json={"status": 0}
    )
    assert staff_off.status_code == 200
    assert staff_off.json()["status"] == 0
    assert v1_db.scalar(select(Staff).where(Staff.user_id == staff_id)) is not None


def test_inactive_teacher_cannot_get_new_assignment_history_preserved(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "m3-asg-sa@eschool.com")
    school_id = _school(v1_client, sa, "M3AS")
    admin = _school_admin(v1_client, sa, school_id, "m3-asg-admin@eschool.com")

    medium = v1_client.post(f"{ACADEMICS}/mediums", headers=admin, json={"name": "English"})
    assert medium.status_code == 201
    klass = v1_client.post(
        "/api/v1/school-admin/classes",
        headers=admin,
        json={"name": "G1", "medium_id": medium.json()["id"]},
    )
    assert klass.status_code == 201
    section = v1_client.post(
        "/api/v1/school-admin/sections",
        headers=admin,
        json={"name": "A", "class_id": klass.json()["id"]},
    )
    assert section.status_code == 201
    subject = v1_client.post(
        "/api/v1/school-admin/subjects",
        headers=admin,
        json={"name": "Math", "code": "M", "medium_id": medium.json()["id"]},
    )
    assert subject.status_code == 201
    assert (
        v1_client.put(
            f"/api/v1/school-admin/subjects/{subject.json()['id']}/classes",
            headers=admin,
            json={"class_ids": [klass.json()["id"]]},
        ).status_code
        == 200
    )
    session = v1_client.post(
        f"{ACADEMICS}/sessions",
        headers=admin,
        json={"name": "Y", "start_date": "2026-04-01", "end_date": "2027-03-31", "default": 1},
    )
    assert session.status_code == 201

    teacher = v1_client.post(
        TEACHERS, headers=admin, json=_teacher_payload("m3-asg-t@eschool.com", employee_id="ASG1")
    )
    assert teacher.status_code == 201
    teacher_id = teacher.json()["id"]

    # Non-teaching staff must not be assignable as teacher.
    staff = v1_client.post(
        STAFF, headers=admin, json=_staff_payload("m3-asg-s@eschool.com", employee_id="ASG-S")
    )
    assert staff.status_code == 201
    bad = v1_client.post(
        ASSIGNMENTS,
        headers=admin,
        json={
            "teacher_id": staff.json()["id"],
            "subject_id": subject.json()["id"],
            "class_id": klass.json()["id"],
            "section_id": section.json()["id"],
            "session_id": session.json()["id"],
        },
    )
    assert bad.status_code == 422

    created = v1_client.post(
        ASSIGNMENTS,
        headers=admin,
        json={
            "teacher_id": teacher_id,
            "subject_id": subject.json()["id"],
            "class_id": klass.json()["id"],
            "section_id": section.json()["id"],
            "session_id": session.json()["id"],
        },
    )
    assert created.status_code == 201, created.text
    assignment_id = created.json()["id"]

    assert (
        v1_client.patch(
            f"{TEACHERS}/{teacher_id}/status", headers=admin, json={"status": 0}
        ).status_code
        == 200
    )
    assert v1_db.get(TeacherAssignment, assignment_id) is not None
    assert v1_db.get(TeacherAssignment, assignment_id).deleted_at is None

    blocked = v1_client.post(
        ASSIGNMENTS,
        headers=admin,
        json={
            "teacher_id": teacher_id,
            "subject_id": subject.json()["id"],
            "class_id": klass.json()["id"],
            "section_id": section.json()["id"],
            "session_id": session.json()["id"],
        },
    )
    assert blocked.status_code == 422
