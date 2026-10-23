"""Module 6: offline exams, schedules, marks, audits, results."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.core.security import hash_password
from app.main import app
from app.models.tables import USER_MODEL, ModelHasRole, Role, School, Student, User
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User as V1User
from app.services.mobile_auth import issue_token
from app.services.v1.school_academics import _now
from app.services.v1 import school_offline_exams as offline_svc

OE = "/api/v1/school-admin/offline-exams"
SCH = "/api/v1/school-admin/offline-exam-schedules"
TEACHERS = "/api/v1/school-admin/teachers"
ASSIGNMENTS = "/api/v1/school-admin/teacher-assignments"
CLASSES = "/api/v1/school-admin/classes"
SECTIONS = "/api/v1/school-admin/sections"
SUBJECTS = "/api/v1/school-admin/subjects"
ACADEMICS = "/api/v1/school-admin/academics"
STUDENT_OE = "/api/student/offline-exams"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _super(client, v1_db, email: str) -> dict[str, str]:
    created = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "secret123", "first_name": "A", "last_name": "B"},
    )
    assert created.status_code == 201, created.text
    user = v1_db.scalar(select(V1User).where(V1User.email == email))
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200
    return _auth(login.json()["access_token"])


def _school_admin(client, sa_headers, school_id: int, email: str, *, roles=None) -> dict[str, str]:
    payload = {
        "email": email,
        "password": "adminpass1",
        "first_name": "School",
        "last_name": "Admin",
    }
    if roles is not None:
        payload["roles"] = roles
    created = client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=sa_headers,
        json=payload,
    )
    assert created.status_code == 201, created.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "adminpass1"})
    assert login.status_code == 200
    return _auth(login.json()["access_token"])


def _school(client, sa_headers, code: str) -> int:
    school = client.post(
        "/api/v1/super-admin/schools",
        headers=sa_headers,
        json={"name": f"School {code}", "code": code},
    )
    assert school.status_code == 201
    return school.json()["id"]


def _seed(client, headers, *, email_prefix: str = "oe"):
    medium = client.post(f"{ACADEMICS}/mediums", headers=headers, json={"name": "English"})
    assert medium.status_code == 201
    medium_id = medium.json()["id"]
    klass = client.post(CLASSES, headers=headers, json={"name": "Grade 1", "medium_id": medium_id})
    assert klass.status_code == 201
    class_id = klass.json()["id"]
    section = client.post(SECTIONS, headers=headers, json={"name": "A", "class_id": class_id})
    assert section.status_code == 201
    subject = client.post(
        SUBJECTS, headers=headers, json={"name": "Math", "code": "M", "medium_id": medium_id}
    )
    assert subject.status_code == 201
    subject_id = subject.json()["id"]
    assert (
        client.put(
            f"{SUBJECTS}/{subject_id}/classes", headers=headers, json={"class_ids": [class_id]}
        ).status_code
        == 200
    )
    subject2 = client.post(
        SUBJECTS, headers=headers, json={"name": "Science", "code": "S", "medium_id": medium_id}
    )
    assert subject2.status_code == 201
    sid2 = subject2.json()["id"]
    assert (
        client.put(
            f"{SUBJECTS}/{sid2}/classes", headers=headers, json={"class_ids": [class_id]}
        ).status_code
        == 200
    )
    session = client.post(
        f"{ACADEMICS}/sessions",
        headers=headers,
        json={"name": "2026-27", "start_date": "2026-04-01", "end_date": "2027-03-31", "default": 1},
    )
    assert session.status_code == 201
    teacher = client.post(
        TEACHERS,
        headers=headers,
        json={
            "first_name": "T",
            "last_name": "One",
            "email": f"{email_prefix}-t@eschool.com",
            "password": "teacherpass1",
            "employee_id": f"{email_prefix}-E1",
        },
    )
    assert teacher.status_code == 201
    for sid in (subject_id, sid2):
        asg = client.post(
            ASSIGNMENTS,
            headers=headers,
            json={"teacher_id": teacher.json()["id"], "subject_id": sid},
        )
        assert asg.status_code == 201
    return {
        "class_section_id": section.json()["class_section_id"],
        "subject_id": subject_id,
        "subject_id_2": sid2,
        "session_year_id": session.json()["id"],
        "teacher_user_id": teacher.json()["id"],
    }


def _make_student(v1_db, school_id, ids, *, email, admission_no):
    guardian = User(
        first_name="G",
        last_name="P",
        email=f"g-{admission_no}@eschool.com",
        password=hash_password("x"),
        status=1,
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    v1_db.add(guardian)
    v1_db.flush()
    su = User(
        first_name="S",
        last_name=admission_no,
        email=email,
        password=hash_password("studentpass1"),
        status=1,
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    v1_db.add(su)
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
    v1_db.add(ModelHasRole(role_id=role.id, model_id=su.id, model_type=USER_MODEL))
    st = Student(
        user_id=su.id,
        class_section_id=ids["class_section_id"],
        admission_no=admission_no,
        roll_number=1,
        admission_date=date(2026, 4, 1),
        school_id=school_id,
        guardian_id=guardian.id,
        session_year_id=ids["session_year_id"],
        enrollment_status="active",
        created_at=_now(),
        updated_at=_now(),
    )
    v1_db.add(st)
    v1_db.commit()
    v1_db.refresh(st)
    return st, issue_token(v1_db, su), guardian


def test_openapi_registers_offline_exam_routes():
    paths = app.openapi()["paths"]
    for path in (
        OE,
        f"{OE}/{{exam_id}}",
        f"{OE}/{{exam_id}}/schedules",
        f"{OE}/{{exam_id}}/process-results",
        f"{OE}/{{exam_id}}/results",
        f"{OE}/{{exam_id}}/results/summary",
        SCH,
        f"{SCH}/{{schedule_id}}",
        f"{SCH}/{{schedule_id}}/marks",
        f"{SCH}/{{schedule_id}}/marks/bulk",
        STUDENT_OE,
        f"{STUDENT_OE}/{{exam_id}}/result",
        "/api/parent/offline-exams/{exam_id}/children/{student_id}/result",
    ):
        assert path in paths, path


def test_offline_exam_marks_results_publication_and_audit(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "oe-sa@eschool.com")
    school_id = _school(v1_client, sa, "OE01")
    admin = _school_admin(v1_client, sa, school_id, "oe-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="oe1")
    student, token, guardian = _make_student(
        v1_db, school_id, ids, email="oe1-s@eschool.com", admission_no="OE1001"
    )
    school = v1_db.get(School, school_id)
    sh = {"Authorization": f"Bearer {token}", "school-code": school.code}

    created = v1_client.post(
        OE,
        headers=admin,
        json={
            "name": "Mid Term",
            "session_year_id": ids["session_year_id"],
            "class_section_id": ids["class_section_id"],
            "exam_type": "term",
            "exam_date": "2026-09-01",
        },
    )
    assert created.status_code == 201, created.text
    exam_id = created.json()["id"]
    assert created.json()["publish"] is False

    # Invalid passing > max
    bad_sch = v1_client.post(
        f"{OE}/{exam_id}/schedules",
        headers=admin,
        json={
            "subject_id": ids["subject_id"],
            "teacher_user_id": ids["teacher_user_id"],
            "exam_date": "2026-09-10",
            "start_time": "09:00",
            "end_time": "11:00",
            "max_marks": 50,
            "passing_marks": 60,
        },
    )
    assert bad_sch.status_code == 422

    sch1 = v1_client.post(
        f"{OE}/{exam_id}/schedules",
        headers=admin,
        json={
            "subject_id": ids["subject_id"],
            "teacher_user_id": ids["teacher_user_id"],
            "exam_date": "2026-09-10",
            "start_time": "09:00",
            "end_time": "11:00",
            "max_marks": 50,
            "passing_marks": 20,
        },
    )
    assert sch1.status_code == 201, sch1.text
    sid1 = sch1.json()["id"]

    # Conflict same CS overlapping time
    conflict = v1_client.post(
        f"{OE}/{exam_id}/schedules",
        headers=admin,
        json={
            "subject_id": ids["subject_id_2"],
            "teacher_user_id": ids["teacher_user_id"],
            "exam_date": "2026-09-10",
            "start_time": "10:00",
            "end_time": "12:00",
            "max_marks": 50,
            "passing_marks": 20,
        },
    )
    assert conflict.status_code == 409

    sch2 = v1_client.post(
        f"{OE}/{exam_id}/schedules",
        headers=admin,
        json={
            "subject_id": ids["subject_id_2"],
            "teacher_user_id": ids["teacher_user_id"],
            "exam_date": "2026-09-11",
            "start_time": "09:00",
            "end_time": "11:00",
            "max_marks": 50,
            "passing_marks": 20,
        },
    )
    assert sch2.status_code == 201
    sid2 = sch2.json()["id"]

    # Invalid marks
    assert (
        v1_client.post(
            f"{SCH}/{sid1}/marks",
            headers=admin,
            json={"student_id": student.id, "marks_obtained": 99, "status": "present"},
        ).status_code
        == 422
    )

    m1 = v1_client.post(
        f"{SCH}/{sid1}/marks",
        headers=admin,
        json={"student_id": student.id, "marks_obtained": 40, "status": "present"},
    )
    assert m1.status_code == 201, m1.text
    mark_id = m1.json()["id"]

    bulk = v1_client.post(
        f"{SCH}/{sid2}/marks/bulk",
        headers=admin,
        json={"items": [{"student_id": student.id, "marks_obtained": 15, "status": "present"}]},
    )
    assert bulk.status_code == 200
    assert bulk.json()["created"] == 1

    # Bad bulk all-or-nothing
    bad_bulk = v1_client.post(
        f"{SCH}/{sid2}/marks/bulk",
        headers=admin,
        json={
            "items": [
                {"student_id": student.id, "marks_obtained": 10, "status": "present"},
                {"student_id": 999999, "marks_obtained": 10, "status": "present"},
            ]
        },
    )
    assert bad_bulk.status_code == 422

    processed = v1_client.post(f"{OE}/{exam_id}/process-results", headers=admin)
    assert processed.status_code == 200, processed.text
    assert processed.json()["processed_students"] == 1
    # Idempotent
    processed2 = v1_client.post(f"{OE}/{exam_id}/process-results", headers=admin)
    assert processed2.status_code == 200
    assert processed2.json()["processed_students"] == 1

    results = v1_client.get(f"{OE}/{exam_id}/results", headers=admin)
    assert results.status_code == 200
    assert results.json()["total"] == 1
    row = results.json()["items"][0]
    assert row["total_obtained"] == 55.0
    assert row["total_max_marks"] == 100.0
    assert row["percentage"] == 55.0
    assert row["passed"] is False  # science 15 < 20

    # Student cannot see until publish
    assert v1_client.get(f"{STUDENT_OE}/{exam_id}/result", headers=sh).status_code == 404

    assert (
        v1_client.patch(f"{OE}/{exam_id}", headers=admin, json={"publish": True}).status_code
        == 200
    )
    mine = v1_client.get(f"{STUDENT_OE}/{exam_id}/result", headers=sh)
    assert mine.status_code == 200
    assert mine.json()["percentage"] == 55.0

    # Correction blocked while published
    assert (
        v1_client.post(
            f"{SCH}/{sid2}/marks",
            headers=admin,
            json={
                "student_id": student.id,
                "marks_obtained": 30,
                "status": "present",
                "reason": "recheck",
            },
        ).status_code
        == 422
    )

    # Unpublish then correct with reason + audit
    assert (
        v1_client.patch(f"{OE}/{exam_id}", headers=admin, json={"publish": False}).status_code
        == 200
    )
    corr = v1_client.post(
        f"{SCH}/{sid2}/marks",
        headers=admin,
        json={
            "student_id": student.id,
            "marks_obtained": 30,
            "status": "present",
            "reason": "Recheck paper",
        },
    )
    assert corr.status_code == 201
    audits = v1_client.get(f"/api/v1/school-admin/offline-exam-marks/{mark_id}/audits", headers=admin)
    # audit is on sid2 mark; fetch mark id from list
    marks = v1_client.get(
        "/api/v1/school-admin/offline-exam-marks",
        headers=admin,
        params={"schedule_id": sid2},
    )
    mid2 = marks.json()["items"][0]["id"]
    audits = v1_client.get(f"/api/v1/school-admin/offline-exam-marks/{mid2}/audits", headers=admin)
    assert audits.status_code == 200
    assert len(audits.json()) >= 1
    assert audits.json()[0]["reason"] == "Recheck paper"

    # Reprocess + publish
    assert v1_client.post(f"{OE}/{exam_id}/process-results", headers=admin).status_code == 200
    assert (
        v1_client.patch(f"{OE}/{exam_id}", headers=admin, json={"publish": True}).status_code
        == 200
    )
    mine2 = v1_client.get(f"{STUDENT_OE}/{exam_id}/result", headers=sh)
    assert mine2.json()["total_obtained"] == 70.0
    assert mine2.json()["passed"] is True

    summary = v1_client.get(f"{OE}/{exam_id}/results/summary", headers=admin)
    assert summary.json()["enrolled_students"] == 1
    assert summary.json()["passed_count"] == 1

    # Cross-school
    school_b = _school(v1_client, sa, "OE02")
    admin_b = _school_admin(v1_client, sa, school_b, "oe-b@eschool.com")
    assert v1_client.get(f"{OE}/{exam_id}", headers=admin_b).status_code == 404

    # Accounts denied
    accounts = _school_admin(
        v1_client, sa, school_id, "oe-acc@eschool.com", roles=["accounts_admin"]
    )
    assert v1_client.get(OE, headers=accounts).status_code == 403

    # Parent access via guardian token
    g_role = v1_db.scalar(
        select(Role).where(Role.name == "Guardian", Role.school_id == school_id, Role.guard_name == "web")
    )
    if g_role is None:
        g_role = Role(
            name="Guardian",
            guard_name="web",
            school_id=school_id,
            created_at=_now(),
            updated_at=_now(),
        )
        v1_db.add(g_role)
        v1_db.flush()
    v1_db.add(ModelHasRole(role_id=g_role.id, model_id=guardian.id, model_type=USER_MODEL))
    v1_db.commit()
    g_token = issue_token(v1_db, guardian)
    parent = v1_client.get(
        f"/api/parent/offline-exams/{exam_id}/children/{student.id}/result",
        headers={"Authorization": f"Bearer {g_token}", "school-code": school.code},
    )
    assert parent.status_code == 200, parent.text
    assert parent.json()["passed"] is True

    assert offline_svc._round_pct(1, 3) == 33.33
