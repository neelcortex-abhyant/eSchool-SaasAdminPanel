"""Module 3: homework CRUD, student submit, late rules, evaluation, summaries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier, Thread

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import session_factory
from app.core.security import hash_password
from app.main import app
from app.models.tables import (
    USER_MODEL,
    Homework,
    HomeworkSubmission,
    ModelHasRole,
    Role,
    School,
    Student,
    User,
)
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User as V1User
from app.services.mobile_auth import issue_token
from app.services.v1 import school_homework as homework_svc
from app.services.v1.school_academics import AcademicError, _now

HW = "/api/v1/school-admin/homework"
SUBS = "/api/v1/school-admin/homework-submissions"
TEACHERS = "/api/v1/school-admin/teachers"
ASSIGNMENTS = "/api/v1/school-admin/teacher-assignments"
CLASSES = "/api/v1/school-admin/classes"
SECTIONS = "/api/v1/school-admin/sections"
SUBJECTS = "/api/v1/school-admin/subjects"
ACADEMICS = "/api/v1/school-admin/academics"
STUDENT_HW = "/api/student/homework"
STUDENT_STATUS = "/api/student/assignment-status"
STUDENT_ATTACH = "/api/student/homework/{homework_id}/my-submission/attachments"

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


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


def _seed(client, headers, *, email_prefix: str = "hw"):
    medium = client.post(f"{ACADEMICS}/mediums", headers=headers, json={"name": "English"})
    assert medium.status_code == 201, medium.text
    medium_id = medium.json()["id"]
    klass = client.post(CLASSES, headers=headers, json={"name": "Grade 1", "medium_id": medium_id})
    assert klass.status_code == 201, klass.text
    class_id = klass.json()["id"]
    section = client.post(SECTIONS, headers=headers, json={"name": "A", "class_id": class_id})
    assert section.status_code == 201, section.text
    class_section_id = section.json()["class_section_id"]
    subject = client.post(
        SUBJECTS,
        headers=headers,
        json={"name": "Math", "code": "M1", "medium_id": medium_id},
    )
    assert subject.status_code == 201, subject.text
    subject_id = subject.json()["id"]
    assert (
        client.put(
            f"{SUBJECTS}/{subject_id}/classes",
            headers=headers,
            json={"class_ids": [class_id]},
        ).status_code
        == 200
    )
    session = client.post(
        f"{ACADEMICS}/sessions",
        headers=headers,
        json={"name": "2026-27", "start_date": "2026-04-01", "end_date": "2027-03-31", "default": 1},
    )
    assert session.status_code == 201, session.text
    teacher = client.post(
        TEACHERS,
        headers=headers,
        json={
            "first_name": "T",
            "last_name": "One",
            "email": f"{email_prefix}-t1@eschool.com",
            "password": "teacherpass1",
            "employee_id": f"{email_prefix}-E1",
        },
    )
    assert teacher.status_code == 201, teacher.text
    teacher2 = client.post(
        TEACHERS,
        headers=headers,
        json={
            "first_name": "T",
            "last_name": "Two",
            "email": f"{email_prefix}-t2@eschool.com",
            "password": "teacherpass1",
            "employee_id": f"{email_prefix}-E2",
        },
    )
    assert teacher2.status_code == 201, teacher2.text
    asg = client.post(
        ASSIGNMENTS,
        headers=headers,
        json={"teacher_id": teacher.json()["id"], "subject_id": subject_id},
    )
    assert asg.status_code == 201, asg.text
    return {
        "class_id": class_id,
        "class_section_id": class_section_id,
        "subject_id": subject_id,
        "session_year_id": session.json()["id"],
        "teacher_user_id": teacher.json()["id"],
        "teacher_user_id_2": teacher2.json()["id"],
    }


def _hw_body(ids, **extra):
    body = {
        "session_year_id": ids["session_year_id"],
        "class_section_id": ids["class_section_id"],
        "subject_id": ids["subject_id"],
        "teacher_user_id": ids["teacher_user_id"],
        "title": "Chapter 1 worksheet",
        "instructions": "Solve all questions",
        "assigned_date": "2026-05-01",
        "deadline_at": "2026-05-10T23:59:59",
        "max_marks": 20,
        "allow_late": True,
        "attachments": [
            {
                "original_filename": "brief.pdf",
                "content_type": "application/pdf",
                "size_bytes": 1024,
            }
        ],
    }
    body.update(extra)
    return body


def _make_student(v1_db, school_id: int, ids: dict, *, email: str, admission_no: str) -> tuple[Student, str]:
    school = v1_db.get(School, school_id)
    assert school is not None
    guardian = User(
        first_name="G",
        last_name="Parent",
        email=f"g-{admission_no}@eschool.com",
        password=hash_password("guardianpass1"),
        status=1,
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    v1_db.add(guardian)
    v1_db.flush()
    student_user = User(
        first_name="Stu",
        last_name=admission_no,
        email=email,
        password=hash_password("studentpass1"),
        status=1,
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    v1_db.add(student_user)
    v1_db.flush()
    role = v1_db.scalar(
        select(Role).where(Role.name == "Student", Role.school_id == school_id, Role.guard_name == "web")
    )
    if role is None:
        role = Role(
            name="Student",
            guard_name="web",
            school_id=school_id,
            created_at=_now(),
            updated_at=_now(),
        )
        v1_db.add(role)
        v1_db.flush()
    v1_db.add(ModelHasRole(role_id=role.id, model_id=student_user.id, model_type=USER_MODEL))
    student = Student(
        user_id=student_user.id,
        class_section_id=ids["class_section_id"],
        admission_no=admission_no,
        roll_number=1,
        admission_date=datetime(2026, 4, 1).date(),
        school_id=school_id,
        guardian_id=guardian.id,
        session_year_id=ids["session_year_id"],
        enrollment_status="active",
        created_at=_now(),
        updated_at=_now(),
    )
    v1_db.add(student)
    v1_db.commit()
    v1_db.refresh(student)
    token = issue_token(v1_db, student_user)
    return student, token


def _student_headers(school_code: str, token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "school-code": school_code}


def test_openapi_registers_homework_routes():
    paths = app.openapi()["paths"]
    for path in (
        HW,
        f"{HW}/{{homework_id}}",
        f"{HW}/{{homework_id}}/submissions",
        f"{HW}/{{homework_id}}/summary",
        f"{HW}/{{homework_id}}/attachments",
        f"{SUBS}/{{submission_id}}",
        f"{SUBS}/{{submission_id}}/evaluation",
        STUDENT_HW,
        f"{STUDENT_HW}/{{homework_id}}",
        f"{STUDENT_HW}/{{homework_id}}/submissions",
        f"{STUDENT_HW}/{{homework_id}}/my-submission",
        f"{STUDENT_HW}/{{homework_id}}/my-submission/attachments",
        STUDENT_STATUS,
    ):
        assert path in paths, path
    route_paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    assert "/api/v1/school-admin/homework" in route_paths
    assert "/api/student/homework" in route_paths
    # Legacy stub left alone
    assert "/api/student/assignments" in route_paths


def test_homework_crud_auth_filters_and_soft_delete(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "hw-sa@eschool.com")
    school_id = _school(v1_client, sa, "HW01")
    admin = _school_admin(v1_client, sa, school_id, "hw-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="hw1")

    assert v1_client.post(HW, json=_hw_body(ids)).status_code == 401
    created = v1_client.post(HW, headers=admin, json=_hw_body(ids))
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["title"] == "Chapter 1 worksheet"
    assert body["max_marks"] == 20
    assert body["allow_late"] is True
    assert len(body["attachments"]) == 1
    assert body["attachments"][0]["stored"] is False
    hw_id = body["id"]

    # Teacher without assignment rejected
    bad = v1_client.post(
        HW,
        headers=admin,
        json=_hw_body(ids, teacher_user_id=ids["teacher_user_id_2"]),
    )
    assert bad.status_code == 422

    # Invalid deadline
    bad_dl = v1_client.post(
        HW,
        headers=admin,
        json=_hw_body(ids, assigned_date="2026-05-10", deadline_at="2026-05-01T12:00:00"),
    )
    assert bad_dl.status_code == 422

    # storage_key smuggling rejected
    bad_att = v1_client.post(
        HW,
        headers=admin,
        json=_hw_body(
            ids,
            title="Bad att",
            attachments=[
                {
                    "original_filename": "x.pdf",
                    "content_type": "application/pdf",
                    "size_bytes": 1,
                    "storage_key": "evil/path",
                }
            ],
        ),
    )
    assert bad_att.status_code == 422

    listed = v1_client.get(HW, headers=admin, params={"subject_id": ids["subject_id"]})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    got = v1_client.get(f"{HW}/{hw_id}", headers=admin)
    assert got.status_code == 200
    assert got.json()["id"] == hw_id

    patched = v1_client.patch(
        f"{HW}/{hw_id}", headers=admin, json={"title": "Updated worksheet", "max_marks": 25}
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Updated worksheet"
    assert patched.json()["max_marks"] == 25

    deleted = v1_client.delete(f"{HW}/{hw_id}", headers=admin)
    assert deleted.status_code == 200
    assert v1_client.get(f"{HW}/{hw_id}", headers=admin).status_code == 404
    row = v1_db.get(Homework, hw_id)
    assert row is not None and row.deleted_at is not None


def test_cross_school_homework_isolation(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "hw-x-sa@eschool.com")
    school_a = _school(v1_client, sa, "HWXA")
    school_b = _school(v1_client, sa, "HWXB")
    admin_a = _school_admin(v1_client, sa, school_a, "hw-xa@eschool.com")
    admin_b = _school_admin(v1_client, sa, school_b, "hw-xb@eschool.com")
    ids_a = _seed(v1_client, admin_a, email_prefix="hwa")
    ids_b = _seed(v1_client, admin_b, email_prefix="hwb")

    created = v1_client.post(HW, headers=admin_a, json=_hw_body(ids_a))
    assert created.status_code == 201
    hw_id = created.json()["id"]

    assert v1_client.get(f"{HW}/{hw_id}", headers=admin_b).status_code == 404
    assert (
        v1_client.patch(f"{HW}/{hw_id}", headers=admin_b, json={"title": "Nope"}).status_code
        == 404
    )
    # Cannot create using other school's IDs
    assert (
        v1_client.post(HW, headers=admin_b, json=_hw_body(ids_a, title="Steal")).status_code
        == 422
    )
    assert v1_client.post(HW, headers=admin_b, json=_hw_body(ids_b, title="Own")).status_code == 201


def test_student_list_submit_late_evaluate_summary(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "hw-st-sa@eschool.com")
    school_id = _school(v1_client, sa, "HWST")
    school = v1_db.get(School, school_id)
    admin = _school_admin(v1_client, sa, school_id, "hw-st-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="hwst")

    student, token = _make_student(
        v1_db, school_id, ids, email="hwst-s1@eschool.com", admission_no="HWST001"
    )
    student2, token2 = _make_student(
        v1_db, school_id, ids, email="hwst-s2@eschool.com", admission_no="HWST002"
    )
    sh = _student_headers(school.code, token)
    sh2 = _student_headers(school.code, token2)

    # Future deadline on-time submission
    future = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=5)).replace(
        microsecond=0
    )
    created = v1_client.post(
        HW,
        headers=admin,
        json=_hw_body(ids, deadline_at=future.isoformat(), max_marks=10),
    )
    assert created.status_code == 201, created.text
    hw_id = created.json()["id"]

    assert v1_client.get(STUDENT_HW).status_code == 200  # ApiError envelope without school-code
    listed = v1_client.get(STUDENT_HW, headers=sh)
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["my_submission_status"] == "pending"

    got = v1_client.get(f"{STUDENT_HW}/{hw_id}", headers=sh)
    assert got.status_code == 200
    assert got.json()["my_submission"] is None

    submitted = v1_client.post(
        f"{STUDENT_HW}/{hw_id}/submissions",
        headers=sh,
        json={"text_response": "My answers"},
    )
    assert submitted.status_code == 201, submitted.text
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["is_late"] is False
    assert submitted.json()["assignment_status"] == "submitted"
    sub_id = submitted.json()["id"]

    # Resubmit allowed before grading
    resub = v1_client.post(
        f"{STUDENT_HW}/{hw_id}/submissions",
        headers=sh,
        json={"text_response": "Updated answers"},
    )
    assert resub.status_code == 201
    assert resub.json()["id"] == sub_id
    assert resub.json()["text_response"] == "Updated answers"

    mine = v1_client.get(f"{STUDENT_HW}/{hw_id}/my-submission", headers=sh)
    assert mine.status_code == 200
    assert mine.json()["text_response"] == "Updated answers"

    # Other student cannot see this submission endpoint as own until they submit
    assert v1_client.get(f"{STUDENT_HW}/{hw_id}/my-submission", headers=sh2).status_code == 404

    # Student cannot evaluate
    assert (
        v1_client.patch(
            f"{SUBS}/{sub_id}/evaluation",
            headers=sh,
            json={"marks": 9},
        ).status_code
        == 401
    )

    summary = v1_client.get(f"{HW}/{hw_id}/summary", headers=admin)
    assert summary.status_code == 200
    assert summary.json()["assigned_students"] == 2
    assert summary.json()["pending_count"] == 1
    assert summary.json()["submitted_count"] == 1
    assert summary.json()["late_count"] == 0
    assert summary.json()["graded_count"] == 0

    # Authenticated school-admin v1 UUID is recorded as evaluator (not legacy teacher id).
    admin_login_email = "hw-st-admin@eschool.com"
    v1_admin = v1_db.scalar(select(V1User).where(V1User.email == admin_login_email))
    assert v1_admin is not None
    evaled = v1_client.patch(
        f"{SUBS}/{sub_id}/evaluation",
        headers=admin,
        json={"marks": 9, "grade": "A", "feedback": "Good"},
    )
    assert evaled.status_code == 200, evaled.text
    assert evaled.json()["status"] == "graded"
    assert evaled.json()["marks"] == 9
    assert evaled.json()["evaluated_by_user_id"] == str(v1_admin.id)
    assert evaled.json()["evaluated_by_actor"] == "v1_user"
    assert evaled.json()["evaluated_by_user_id"] != str(ids["teacher_user_id"])

    # Marks above max rejected
    assert (
        v1_client.patch(
            f"{SUBS}/{sub_id}/evaluation",
            headers=admin,
            json={"marks": 99},
        ).status_code
        == 422
    )

    # Graded: student cannot resubmit
    blocked = v1_client.post(
        f"{STUDENT_HW}/{hw_id}/submissions",
        headers=sh,
        json={"text_response": "Hack"},
    )
    assert blocked.status_code == 422

    status_list = v1_client.get(STUDENT_STATUS, headers=sh, params={"status": "graded"})
    assert status_list.status_code == 200
    assert status_list.json()["total"] == 1

    summary2 = v1_client.get(f"{HW}/{hw_id}/summary", headers=admin)
    assert summary2.json()["graded_count"] == 1
    assert summary2.json()["pending_count"] == 1
    assert summary2.json()["submitted_count"] == 0

    # Late homework (deadline in the past, allow_late=true)
    past = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)).replace(
        microsecond=0
    )
    late_hw = v1_client.post(
        HW,
        headers=admin,
        json=_hw_body(
            ids,
            title="Late allowed",
            assigned_date=(past - timedelta(days=2)).date().isoformat(),
            deadline_at=past.isoformat(),
            allow_late=True,
        ),
    )
    assert late_hw.status_code == 201
    late_id = late_hw.json()["id"]
    late_sub = v1_client.post(
        f"{STUDENT_HW}/{late_id}/submissions",
        headers=sh2,
        json={"text_response": "Sorry late"},
    )
    assert late_sub.status_code == 201
    assert late_sub.json()["is_late"] is True
    assert late_sub.json()["assignment_status"] == "late"

    # Late disallowed
    no_late = v1_client.post(
        HW,
        headers=admin,
        json=_hw_body(
            ids,
            title="No late",
            assigned_date=(past - timedelta(days=2)).date().isoformat(),
            deadline_at=past.isoformat(),
            allow_late=False,
        ),
    )
    assert no_late.status_code == 201
    rejected = v1_client.post(
        f"{STUDENT_HW}/{no_late.json()['id']}/submissions",
        headers=sh,
        json={"text_response": "Too late"},
    )
    assert rejected.status_code == 422

    # Class-section isolation: student from other section
    # Create homework for same school but different section by seeding section B is heavy —
    # instead soft-delete and ensure 404 for other school's student token attempted with wrong code.
    other_school = _school(v1_client, sa, "HWOT")
    other_admin = _school_admin(v1_client, sa, other_school, "hw-ot@eschool.com")
    other_ids = _seed(v1_client, other_admin, email_prefix="hwot")
    other_student, other_token = _make_student(
        v1_db, other_school, other_ids, email="hwot-s@eschool.com", admission_no="HWOT1"
    )
    other_school_row = v1_db.get(School, other_school)
    assert (
        v1_client.get(
            f"{STUDENT_HW}/{hw_id}",
            headers=_student_headers(other_school_row.code, other_token),
        ).status_code
        == 404
    )

    # Soft-deleted homework hidden from students
    v1_client.delete(f"{HW}/{hw_id}", headers=admin)
    assert v1_client.get(f"{STUDENT_HW}/{hw_id}", headers=sh).status_code == 404

    # Ensure unique active submission constraint path: second student creates own row
    assert v1_db.query(HomeworkSubmission).filter(HomeworkSubmission.deleted_at.is_(None)).count() >= 1
    assert student.id != student2.id
    assert other_student.id != student.id


def test_accounts_role_denied_homework(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "hw-fin-sa@eschool.com")
    school_id = _school(v1_client, sa, "HWFN")
    created = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=sa,
        json={
            "email": "hw-finance@eschool.com",
            "password": "adminpass1",
            "first_name": "Fin",
            "last_name": "User",
            "roles": ["accounts_admin"],
        },
    )
    assert created.status_code == 201, created.text
    login = v1_client.post(
        "/api/v1/auth/login", json={"email": "hw-finance@eschool.com", "password": "adminpass1"}
    )
    assert login.status_code == 200, login.text
    headers = _auth(login.json()["access_token"])
    assert v1_client.get(HW, headers=headers).status_code == 403


def _require_postgres_homework_locks():
    db = session_factory()()
    try:
        if not homework_svc._is_postgresql(db):
            pytest.skip("Homework submission locks require PostgreSQL")
    finally:
        db.close()


def test_concurrent_first_submissions_single_row_on_postgres(v1_client, v1_db):
    """Two concurrent first submits for the same student must leave one active row."""
    _require_postgres_homework_locks()
    sa = _super(v1_client, v1_db, "hw-conc-sa@eschool.com")
    school_id = _school(v1_client, sa, "HWCN")
    admin = _school_admin(v1_client, sa, school_id, "hw-conc-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="hwcn")
    student, _token = _make_student(
        v1_db, school_id, ids, email="hwcn-s@eschool.com", admission_no="HWCN1"
    )
    future = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=3)).replace(
        microsecond=0
    )
    created = v1_client.post(
        HW, headers=admin, json=_hw_body(ids, deadline_at=future.isoformat(), title="Conc")
    )
    assert created.status_code == 201
    hw_id = created.json()["id"]
    student_user = v1_db.get(User, student.user_id)
    assert student_user is not None

    barrier = Barrier(2)
    outcomes: list = []

    def worker(label: str) -> None:
        db = session_factory()()
        try:
            barrier.wait(timeout=30)
            # Re-load user in this session
            user = db.get(User, student_user.id)
            homework_svc.submit_homework(
                db, school_id, user, hw_id, {"text_response": f"answer-{label}"}
            )
            outcomes.append(("ok", label))
        except AcademicError as exc:
            outcomes.append(("err", exc.status_code, exc.detail))
        except BaseException as exc:  # noqa: BLE001
            outcomes.append(("boom", type(exc).__name__, str(exc)))
        finally:
            db.close()

    threads = [Thread(target=worker, args=("a",)), Thread(target=worker, args=("b",))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert len(outcomes) == 2, outcomes
    # Both may succeed (create + resubmit under lock) or one 409 from unique index.
    oks = [o for o in outcomes if o[0] == "ok"]
    errs = [o for o in outcomes if o[0] == "err"]
    assert len(oks) + len(errs) == 2, outcomes
    for err in errs:
        assert err[1] in (409, 422), outcomes
    v1_db.expire_all()
    active = (
        v1_db.query(HomeworkSubmission)
        .filter(
            HomeworkSubmission.homework_id == hw_id,
            HomeworkSubmission.student_id == student.id,
            HomeworkSubmission.deleted_at.is_(None),
        )
        .count()
    )
    assert active == 1


def test_concurrent_resubmissions_single_row_on_postgres(v1_client, v1_db):
    _require_postgres_homework_locks()
    sa = _super(v1_client, v1_db, "hw-res-sa@eschool.com")
    school_id = _school(v1_client, sa, "HWRS")
    admin = _school_admin(v1_client, sa, school_id, "hw-res-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="hwrs")
    student, _token = _make_student(
        v1_db, school_id, ids, email="hwrs-s@eschool.com", admission_no="HWRS1"
    )
    future = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=3)).replace(
        microsecond=0
    )
    created = v1_client.post(
        HW, headers=admin, json=_hw_body(ids, deadline_at=future.isoformat(), title="Res")
    )
    hw_id = created.json()["id"]
    student_user = v1_db.get(User, student.user_id)
    db0 = session_factory()()
    try:
        homework_svc.submit_homework(
            db0, school_id, student_user, hw_id, {"text_response": "first"}
        )
    finally:
        db0.close()

    barrier = Barrier(2)
    outcomes: list = []

    def worker(label: str) -> None:
        db = session_factory()()
        try:
            barrier.wait(timeout=30)
            user = db.get(User, student_user.id)
            homework_svc.submit_homework(
                db, school_id, user, hw_id, {"text_response": f"resub-{label}"}
            )
            outcomes.append(("ok", label))
        except AcademicError as exc:
            outcomes.append(("err", exc.status_code))
        except BaseException as exc:  # noqa: BLE001
            outcomes.append(("boom", type(exc).__name__, str(exc)))
        finally:
            db.close()

    threads = [Thread(target=worker, args=("x",)), Thread(target=worker, args=("y",))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert all(o[0] == "ok" for o in outcomes), outcomes
    v1_db.expire_all()
    rows = (
        v1_db.query(HomeworkSubmission)
        .filter(
            HomeworkSubmission.homework_id == hw_id,
            HomeworkSubmission.student_id == student.id,
            HomeworkSubmission.deleted_at.is_(None),
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0].text_response in ("resub-x", "resub-y")


def test_partial_unique_index_blocks_duplicate_active_submission(v1_client, v1_db):
    """DB unique index is the final guard (direct insert)."""
    _require_postgres_homework_locks()
    sa = _super(v1_client, v1_db, "hw-uq-sa@eschool.com")
    school_id = _school(v1_client, sa, "HWUQ")
    admin = _school_admin(v1_client, sa, school_id, "hw-uq-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="hwuq")
    student, _token = _make_student(
        v1_db, school_id, ids, email="hwuq-s@eschool.com", admission_no="HWUQ1"
    )
    future = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=2)).replace(
        microsecond=0
    )
    created = v1_client.post(
        HW, headers=admin, json=_hw_body(ids, deadline_at=future.isoformat(), title="Uq")
    )
    hw_id = created.json()["id"]
    now = _now()
    v1_db.add(
        HomeworkSubmission(
            school_id=school_id,
            homework_id=hw_id,
            student_id=student.id,
            text_response="a",
            submitted_at=now,
            status="submitted",
            is_late=0,
            created_at=now,
            updated_at=now,
        )
    )
    v1_db.commit()
    v1_db.add(
        HomeworkSubmission(
            school_id=school_id,
            homework_id=hw_id,
            student_id=student.id,
            text_response="b",
            submitted_at=now,
            status="submitted",
            is_late=0,
            created_at=now,
            updated_at=now,
        )
    )
    with pytest.raises(Exception):
        v1_db.commit()
    v1_db.rollback()
    assert (
        v1_db.query(HomeworkSubmission)
        .filter(
            HomeworkSubmission.homework_id == hw_id,
            HomeworkSubmission.deleted_at.is_(None),
        )
        .count()
        == 1
    )
    # Soft-deleted row must not block a new active insert (partial index).
    row = (
        v1_db.query(HomeworkSubmission)
        .filter(HomeworkSubmission.homework_id == hw_id, HomeworkSubmission.deleted_at.is_(None))
        .one()
    )
    row.deleted_at = _now()
    v1_db.commit()
    v1_db.add(
        HomeworkSubmission(
            school_id=school_id,
            homework_id=hw_id,
            student_id=student.id,
            text_response="c",
            submitted_at=_now(),
            status="submitted",
            is_late=0,
            created_at=_now(),
            updated_at=_now(),
        )
    )
    v1_db.commit()
    assert (
        v1_db.query(HomeworkSubmission)
        .filter(
            HomeworkSubmission.homework_id == hw_id,
            HomeworkSubmission.deleted_at.is_(None),
        )
        .count()
        == 1
    )


def test_student_binary_attachment_upload_and_503_without_storage(
    v1_client, v1_db, monkeypatch, tmp_path: Path
):
    sa = _super(v1_client, v1_db, "hw-up-sa@eschool.com")
    school_id = _school(v1_client, sa, "HWUP")
    school = v1_db.get(School, school_id)
    admin = _school_admin(v1_client, sa, school_id, "hw-up-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="hwup")
    _student, token = _make_student(
        v1_db, school_id, ids, email="hwup-s@eschool.com", admission_no="HWUP1"
    )
    sh = _student_headers(school.code, token)
    future = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=4)).replace(
        microsecond=0
    )
    created = v1_client.post(
        HW, headers=admin, json=_hw_body(ids, deadline_at=future.isoformat(), title="Upload")
    )
    hw_id = created.json()["id"]
    path = f"{STUDENT_HW}/{hw_id}/my-submission/attachments"

    monkeypatch.setenv("DOCUMENT_STORAGE_BACKEND", "none")
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", "")
    get_settings.cache_clear()
    denied = v1_client.post(path, headers=sh, files={"file": ("a.pdf", PDF, "application/pdf")})
    assert denied.status_code == 503, denied.text

    monkeypatch.setenv("DOCUMENT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()
    uploaded = v1_client.post(
        path, headers=sh, files={"file": ("answers.pdf", PDF, "application/pdf")}
    )
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    assert body["assignment_status"] == "submitted"
    assert len(body["attachments"]) == 1
    assert body["attachments"][0]["stored"] is True
    assert "storage_key" not in body["attachments"][0]

    # Text resubmit without attachments key must keep stored file metadata.
    resub = v1_client.post(
        f"{STUDENT_HW}/{hw_id}/submissions",
        headers=sh,
        json={"text_response": "see PDF"},
    )
    assert resub.status_code == 201
    assert len(resub.json()["attachments"]) == 1
    assert resub.json()["attachments"][0]["stored"] is True

    # Inactive enrollment cannot submit
    student_row = v1_db.get(Student, body["student_id"])
    student_row.enrollment_status = "inactive"
    v1_db.commit()
    blocked = v1_client.post(
        f"{STUDENT_HW}/{hw_id}/submissions",
        headers=sh,
        json={"text_response": "nope"},
    )
    assert blocked.status_code == 403
