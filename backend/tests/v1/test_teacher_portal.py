"""Teacher portal APIs: PAT auth, assignment scope, homework/marks writes."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password, utcnow
from app.main import app
from app.models.tables import (
    USER_MODEL,
    ModelHasRole,
    OfflineExamMark,
    PersonalAccessToken,
    Role,
    School,
    Staff,
    Student,
    User,
)
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User as V1User
from app.services.mobile_auth import issue_token
from app.services.v1.school_academics import _now

TP = "/api/teacher"
HW_ADMIN = "/api/v1/school-admin/homework"
OE = "/api/v1/school-admin/offline-exams"
SCH_ADMIN = "/api/v1/school-admin/offline-exam-schedules"
TEACHERS = "/api/v1/school-admin/teachers"
STAFF = "/api/v1/school-admin/staff"
ASSIGNMENTS = "/api/v1/school-admin/teacher-assignments"
CLASSES = "/api/v1/school-admin/classes"
SECTIONS = "/api/v1/school-admin/sections"
SUBJECTS = "/api/v1/school-admin/subjects"
ACADEMICS = "/api/v1/school-admin/academics"
STUDENT_HW = "/api/student/homework"
OA_ADMIN = "/api/v1/school-admin/online-assessments"

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _th(code: str, token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "school-code": code}


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


def _seed(client, headers, *, email_prefix: str = "tp"):
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
    assert teacher2.status_code == 201
    asg = client.post(
        ASSIGNMENTS,
        headers=headers,
        json={"teacher_id": teacher.json()["id"], "subject_id": subject_id},
    )
    assert asg.status_code == 201
    # teacher2 assigned only to science
    asg2 = client.post(
        ASSIGNMENTS,
        headers=headers,
        json={"teacher_id": teacher2.json()["id"], "subject_id": sid2},
    )
    assert asg2.status_code == 201
    return {
        "class_section_id": section.json()["class_section_id"],
        "subject_id": subject_id,
        "subject_id_2": sid2,
        "session_year_id": session.json()["id"],
        "teacher_user_id": teacher.json()["id"],
        "teacher_user_id_2": teacher2.json()["id"],
        "teacher_email": f"{email_prefix}-t@eschool.com",
        "teacher2_email": f"{email_prefix}-t2@eschool.com",
    }


def _teacher_token(v1_db, school_id: int, teacher_user_id: int) -> str:
    user = v1_db.get(User, teacher_user_id)
    assert user is not None
    return issue_token(v1_db, user)


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
    return st, issue_token(v1_db, su)


def _unauthorized(resp) -> bool:
    """Mobile deps return Laravel envelope at HTTP 200."""
    if resp.status_code in (401, 403):
        return True
    body = resp.json()
    if isinstance(body, dict) and body.get("error") is True:
        return True
    msg = str(body.get("message") or "").lower()
    return "unauthorized" in msg or "unauthenticated" in msg


def test_openapi_registers_teacher_portal_routes():
    paths = app.openapi()["paths"]
    for path in (
        f"{TP}/me",
        f"{TP}/assignments",
        f"{TP}/timetable/daily",
        f"{TP}/timetable/weekly",
        f"{TP}/homework",
        f"{TP}/homework/{{homework_id}}",
        f"{TP}/homework/{{homework_id}}/submissions",
        f"{TP}/homework-submissions/{{submission_id}}/evaluation",
        f"{TP}/study-materials",
        f"{TP}/offline-exam-schedules",
        f"{TP}/offline-exam-schedules/{{schedule_id}}/marks",
        f"{TP}/online-assessments",
    ):
        assert path in paths, path


def test_teacher_homework_marks_scope_and_denials(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "tp-sa@eschool.com")
    school_id = _school(v1_client, sa, "TP01")
    school = v1_db.get(School, school_id)
    admin = _school_admin(v1_client, sa, school_id, "tp-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="tp1")
    t_token = _teacher_token(v1_db, school_id, ids["teacher_user_id"])
    t2_token = _teacher_token(v1_db, school_id, ids["teacher_user_id_2"])
    th = _th(school.code, t_token)
    th2 = _th(school.code, t2_token)

    me = v1_client.get(f"{TP}/me", headers=th)
    assert me.status_code == 200, me.text
    assert me.json()["teacher_user_id"] == ids["teacher_user_id"]

    asgs = v1_client.get(f"{TP}/assignments", headers=th)
    assert asgs.status_code == 200
    assert asgs.json()["total"] >= 1

    # Student token denied
    student, s_token = _make_student(
        v1_db, school_id, ids, email="tp1-s@eschool.com", admission_no="TP1001"
    )
    assert _unauthorized(v1_client.get(f"{TP}/me", headers=_th(school.code, s_token)))

    # Create homework as teacher — identity forced (client teacher_user_id ignored)
    future = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=5)).replace(
        microsecond=0
    )
    created = v1_client.post(
        f"{TP}/homework",
        headers=th,
        json={
            "session_year_id": ids["session_year_id"],
            "class_section_id": ids["class_section_id"],
            "subject_id": ids["subject_id"],
            "title": "Teacher HW",
            "instructions": "Do it",
            "assigned_date": "2026-05-01",
            "deadline_at": future.isoformat(),
            "max_marks": 10,
            "allow_late": True,
            "attachments": [],
            "teacher_user_id": ids["teacher_user_id_2"],  # forbidden extra → 422
        },
    )
    assert created.status_code == 422  # extra forbid

    created = v1_client.post(
        f"{TP}/homework",
        headers=th,
        json={
            "session_year_id": ids["session_year_id"],
            "class_section_id": ids["class_section_id"],
            "subject_id": ids["subject_id"],
            "title": "Teacher HW",
            "instructions": "Do it",
            "assigned_date": "2026-05-01",
            "deadline_at": future.isoformat(),
            "max_marks": 10,
            "allow_late": True,
            "attachments": [],
        },
    )
    assert created.status_code == 201, created.text
    hw_id = created.json()["id"]
    assert created.json()["teacher_user_id"] == ids["teacher_user_id"]

    # Unassigned subject rejected
    bad = v1_client.post(
        f"{TP}/homework",
        headers=th,
        json={
            "session_year_id": ids["session_year_id"],
            "class_section_id": ids["class_section_id"],
            "subject_id": ids["subject_id_2"],
            "title": "Science HW",
            "assigned_date": "2026-05-01",
            "deadline_at": future.isoformat(),
            "attachments": [],
        },
    )
    assert bad.status_code == 422

    # Other teacher cannot see/manage this homework
    assert v1_client.get(f"{TP}/homework/{hw_id}", headers=th2).status_code == 404

    # Student submits; teacher evaluates
    sh = _th(school.code, s_token)
    sub = v1_client.post(
        f"{STUDENT_HW}/{hw_id}/submissions",
        headers=sh,
        json={"text_response": "Answers"},
    )
    assert sub.status_code == 201, sub.text
    sub_id = sub.json()["id"]

    assert v1_client.get(f"{TP}/homework/{hw_id}/submissions", headers=th).status_code == 200
    evaled = v1_client.patch(
        f"{TP}/homework-submissions/{sub_id}/evaluation",
        headers=th,
        json={"marks": 8, "feedback": "OK"},
    )
    assert evaled.status_code == 200, evaled.text
    assert evaled.json()["status"] == "graded"
    assert evaled.json()["evaluated_by_user_id"] == f"teacher:{ids['teacher_user_id']}"
    assert evaled.json()["evaluated_by_actor"] == "teacher"

    # Other teacher cannot evaluate
    assert (
        v1_client.patch(
            f"{TP}/homework-submissions/{sub_id}/evaluation",
            headers=th2,
            json={"marks": 1},
        ).status_code
        == 404
    )

    # Study material for assigned subject
    mat = v1_client.post(
        f"{TP}/study-materials",
        headers=th,
        json={
            "session_year_id": ids["session_year_id"],
            "class_section_id": ids["class_section_id"],
            "subject_id": ids["subject_id"],
            "resource_type": "video_link",
            "title": "Intro video",
            "external_url": "https://example.com/v",
        },
    )
    assert mat.status_code == 201, mat.text
    assert mat.json()["teacher_user_id"] == ids["teacher_user_id"]

    # Offline marks
    exam = v1_client.post(
        OE,
        headers=admin,
        json={
            "name": "Unit Test",
            "session_year_id": ids["session_year_id"],
            "class_section_id": ids["class_section_id"],
            "exam_type": "unit",
            "exam_date": "2026-09-01",
        },
    )
    assert exam.status_code == 201, exam.text
    exam_id = exam.json()["id"]
    sch = v1_client.post(
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
    assert sch.status_code == 201, sch.text
    sid = sch.json()["id"]

    mark = v1_client.post(
        f"{TP}/offline-exam-schedules/{sid}/marks",
        headers=th,
        json={"student_id": student.id, "marks_obtained": 40, "status": "present"},
    )
    assert mark.status_code == 201, mark.text

    # Unassigned teacher cannot enter marks on this schedule
    assert (
        v1_client.post(
            f"{TP}/offline-exam-schedules/{sid}/marks",
            headers=th2,
            json={"student_id": student.id, "marks_obtained": 10, "status": "present"},
        ).status_code
        == 404
    )

    # Inactive employment denied
    staff = v1_db.scalar(
        select(Staff).where(
            Staff.user_id == ids["teacher_user_id"], Staff.school_id == school_id
        )
    )
    assert staff is not None
    staff.employment_status = "terminated"
    v1_db.commit()
    assert _unauthorized(v1_client.get(f"{TP}/me", headers=th))
    staff.employment_status = "active"
    v1_db.commit()

    # Cross-school denial
    school_b = _school(v1_client, sa, "TP02")
    school_b_row = v1_db.get(School, school_b)
    assert _unauthorized(v1_client.get(f"{TP}/me", headers=_th(school_b_row.code, t_token)))

    # School-admin homework path still works (regression)
    admin_hw = v1_client.post(
        HW_ADMIN,
        headers=admin,
        json={
            "session_year_id": ids["session_year_id"],
            "class_section_id": ids["class_section_id"],
            "subject_id": ids["subject_id"],
            "teacher_user_id": ids["teacher_user_id"],
            "title": "Admin HW",
            "instructions": "x",
            "assigned_date": "2026-05-01",
            "deadline_at": future.isoformat(),
            "max_marks": 5,
            "allow_late": True,
            "attachments": [],
        },
    )
    assert admin_hw.status_code == 201, admin_hw.text


def test_teacher_portal_negative_auth_and_resource_isolation(
    v1_client, v1_db, monkeypatch, tmp_path: Path
):
    sa = _super(v1_client, v1_db, "tp-neg-sa@eschool.com")
    school_id = _school(v1_client, sa, "TPNG")
    school = v1_db.get(School, school_id)
    admin = _school_admin(v1_client, sa, school_id, "tp-neg-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="tpng")
    t_token = _teacher_token(v1_db, school_id, ids["teacher_user_id"])
    t2_token = _teacher_token(v1_db, school_id, ids["teacher_user_id_2"])
    th = _th(school.code, t_token)
    th2 = _th(school.code, t2_token)
    student, _s_token = _make_student(
        v1_db, school_id, ids, email="tpng-s@eschool.com", admission_no="TPNG001"
    )

    # --- Staff/Driver without Teacher role ---
    staff_created = v1_client.post(
        STAFF,
        headers=admin,
        json={
            "first_name": "D",
            "last_name": "River",
            "email": "tpng-driver@eschool.com",
            "password": "driverpass1",
            "employee_id": "TPNG-DRV",
            "designation": "Driver",
        },
    )
    assert staff_created.status_code == 201, staff_created.text
    assert staff_created.json()["role"] != "Teacher"
    driver_user = v1_db.get(User, staff_created.json()["id"])
    driver_token = issue_token(v1_db, driver_user)
    assert _unauthorized(v1_client.get(f"{TP}/me", headers=_th(school.code, driver_token)))

    # --- School-admin JWT is not a teacher PAT ---
    assert _unauthorized(v1_client.get(f"{TP}/me", headers={**admin, "school-code": school.code}))

    # --- Expired teacher PAT ---
    expired_plain = issue_token(v1_db, v1_db.get(User, ids["teacher_user_id"]))
    token_id = int(expired_plain.split("|", 1)[0])
    pat = v1_db.get(PersonalAccessToken, token_id)
    assert pat is not None
    pat.expires_at = utcnow() - timedelta(hours=1)
    v1_db.commit()
    assert _unauthorized(v1_client.get(f"{TP}/me", headers=_th(school.code, expired_plain)))

    # --- Unassigned offline schedule: matching assignment alone is not enough ---
    exam = v1_client.post(
        OE,
        headers=admin,
        json={
            "name": "Unassigned Sched Exam",
            "session_year_id": ids["session_year_id"],
            "class_section_id": ids["class_section_id"],
            "exam_date": "2026-10-01",
        },
    )
    assert exam.status_code == 201, exam.text
    exam_id = exam.json()["id"]
    unassigned = v1_client.post(
        f"{OE}/{exam_id}/schedules",
        headers=admin,
        json={
            "subject_id": ids["subject_id"],
            # no teacher_user_id
            "exam_date": "2026-10-05",
            "start_time": "09:00",
            "end_time": "10:00",
            "max_marks": 40,
            "passing_marks": 16,
        },
    )
    assert unassigned.status_code == 201, unassigned.text
    unassigned_id = unassigned.json()["id"]
    assert unassigned.json().get("teacher_user_id") in (None, 0)

    before_unassigned = v1_db.query(OfflineExamMark).filter_by(schedule_id=unassigned_id).count()
    denied_unassigned = v1_client.post(
        f"{TP}/offline-exam-schedules/{unassigned_id}/marks",
        headers=th,
        json={"student_id": student.id, "marks_obtained": 30, "status": "present"},
    )
    assert denied_unassigned.status_code == 404
    assert v1_db.query(OfflineExamMark).filter_by(schedule_id=unassigned_id).count() == before_unassigned

    # School-admin can still enter marks on unassigned schedule
    admin_mark = v1_client.post(
        f"{SCH_ADMIN}/{unassigned_id}/marks",
        headers=admin,
        json={"student_id": student.id, "marks_obtained": 25, "status": "present"},
    )
    assert admin_mark.status_code == 201, admin_mark.text

    # Explicitly assigned schedule: authorized teacher still works
    assigned = v1_client.post(
        f"{OE}/{exam_id}/schedules",
        headers=admin,
        json={
            "subject_id": ids["subject_id_2"],
            "teacher_user_id": ids["teacher_user_id_2"],
            "exam_date": "2026-10-06",
            "start_time": "11:00",
            "end_time": "12:00",
            "max_marks": 40,
            "passing_marks": 16,
        },
    )
    assert assigned.status_code == 201, assigned.text
    assigned_id = assigned.json()["id"]
    ok_mark = v1_client.post(
        f"{TP}/offline-exam-schedules/{assigned_id}/marks",
        headers=th2,
        json={"student_id": student.id, "marks_obtained": 28, "status": "present"},
    )
    assert ok_mark.status_code == 201, ok_mark.text
    # Teacher without this schedule assignment cannot write
    assert (
        v1_client.post(
            f"{TP}/offline-exam-schedules/{assigned_id}/marks",
            headers=th,
            json={"student_id": student.id, "marks_obtained": 1, "status": "present"},
        ).status_code
        == 404
    )

    # --- Published results block teacher mark updates; no mutation ---
    assert v1_client.post(f"{OE}/{exam_id}/process-results", headers=admin).status_code == 200
    assert (
        v1_client.patch(f"{OE}/{exam_id}", headers=admin, json={"publish": True}).status_code
        == 200
    )
    published_attempt = v1_client.post(
        f"{TP}/offline-exam-schedules/{assigned_id}/marks",
        headers=th2,
        json={
            "student_id": student.id,
            "marks_obtained": 39,
            "status": "present",
            "reason": "should fail while published",
        },
    )
    assert published_attempt.status_code == 422
    marks_after = v1_client.get(
        f"{TP}/offline-exam-marks",
        headers=th2,
        params={"schedule_id": assigned_id},
    )
    assert marks_after.status_code == 200
    assert marks_after.json()["items"][0]["marks_obtained"] == 28.0

    # Unpublish so bulk test can run
    assert (
        v1_client.patch(f"{OE}/{exam_id}", headers=admin, json={"publish": False}).status_code
        == 200
    )

    # --- Bulk marks: valid + invalid → all-or-nothing ---
    count_before = v1_db.query(OfflineExamMark).filter_by(schedule_id=assigned_id).count()
    bulk = v1_client.post(
        f"{TP}/offline-exam-schedules/{assigned_id}/marks/bulk",
        headers=th2,
        json={
            "items": [
                {"student_id": student.id, "marks_obtained": 35, "status": "present"},
                {"student_id": 99999999, "marks_obtained": 10, "status": "present"},
            ]
        },
    )
    assert bulk.status_code == 422
    assert v1_db.query(OfflineExamMark).filter_by(schedule_id=assigned_id).count() == count_before
    still = v1_client.get(
        f"{TP}/offline-exam-marks", headers=th2, params={"schedule_id": assigned_id}
    )
    assert still.json()["items"][0]["marks_obtained"] == 28.0

    # --- Online assessment: Teacher A cannot read Teacher B's assessment/attempts ---
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    oa = v1_client.post(
        f"{TP}/online-assessments",
        headers=th,
        json={
            "session_year_id": ids["session_year_id"],
            "class_section_id": ids["class_section_id"],
            "subject_id": ids["subject_id"],
            "title": "OA for T1",
            "duration_minutes": 30,
            "total_marks": 2,
            "passing_marks": 1,
            "available_from": (now - timedelta(hours=1)).isoformat(),
            "available_until": (now + timedelta(days=1)).isoformat(),
        },
    )
    assert oa.status_code == 201, oa.text
    oa_id = oa.json()["id"]
    assert v1_client.get(f"{TP}/online-assessments/{oa_id}", headers=th2).status_code == 404
    assert (
        v1_client.get(f"{TP}/online-assessments/{oa_id}/attempts", headers=th2).status_code == 404
    )
    # Owner can still read
    assert v1_client.get(f"{TP}/online-assessments/{oa_id}", headers=th).status_code == 200

    # --- Study material download isolation ---
    monkeypatch.setenv("DOCUMENT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()
    uploaded = v1_client.post(
        f"{TP}/study-materials/upload",
        headers=th,
        data={
            "title": "T1 Notes",
            "session_year_id": str(ids["session_year_id"]),
            "class_section_id": str(ids["class_section_id"]),
            "subject_id": str(ids["subject_id"]),
        },
        files={"file": ("notes.pdf", PDF, "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    mid = uploaded.json()["id"]
    assert v1_client.get(f"{TP}/study-materials/{mid}/download", headers=th).status_code == 200
    assert v1_client.get(f"{TP}/study-materials/{mid}/download", headers=th2).status_code == 404
    get_settings.cache_clear()
