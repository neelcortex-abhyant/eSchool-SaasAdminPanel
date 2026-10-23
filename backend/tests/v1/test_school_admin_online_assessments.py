"""Module 5: online MCQ assessments, attempts, evaluation, answer-key secrecy."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Barrier, Thread

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import select

from app.core.database import session_factory
from app.core.security import hash_password
from app.main import app
from app.models.tables import (
    USER_MODEL,
    ModelHasRole,
    OnlineAssessmentAttempt,
    Role,
    School,
    Student,
    User,
)
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User as V1User
from app.services.mobile_auth import issue_token
from app.services.v1 import school_online_assessments as oa_svc
from app.services.v1.school_academics import AcademicError, _now

OA = "/api/v1/school-admin/online-assessments"
TEACHERS = "/api/v1/school-admin/teachers"
ASSIGNMENTS = "/api/v1/school-admin/teacher-assignments"
CLASSES = "/api/v1/school-admin/classes"
SECTIONS = "/api/v1/school-admin/sections"
SUBJECTS = "/api/v1/school-admin/subjects"
ACADEMICS = "/api/v1/school-admin/academics"
STUDENT_OA = "/api/student/online-assessments"
STUDENT_ATT = "/api/student/online-assessment-attempts"


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


def _seed(client, headers, *, email_prefix: str = "oa"):
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
    asg = client.post(
        ASSIGNMENTS,
        headers=headers,
        json={"teacher_id": teacher.json()["id"], "subject_id": subject_id},
    )
    assert asg.status_code == 201
    return {
        "class_section_id": section.json()["class_section_id"],
        "subject_id": subject_id,
        "session_year_id": session.json()["id"],
        "teacher_user_id": teacher.json()["id"],
    }


def _window(**extra):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    body = {
        "available_from": (now - timedelta(hours=1)).isoformat(),
        "available_until": (now + timedelta(days=1)).isoformat(),
        "duration_minutes": 30,
        "total_marks": 2,
        "passing_marks": 1,
        "title": "Unit Test",
    }
    body.update(extra)
    return body


def _mcq(text="Q1", marks=1.0, correct=0):
    choices = [
        {"choice_text": "A", "is_correct": correct == 0},
        {"choice_text": "B", "is_correct": correct == 1},
    ]
    return {"question_text": text, "marks": marks, "choices": choices, "topic": "Algebra"}


def _make_student(v1_db, school_id, ids, *, email, admission_no):
    from datetime import date

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


def _sh(code, token):
    return {"Authorization": f"Bearer {token}", "school-code": code}


def test_openapi_registers_online_assessment_routes():
    paths = app.openapi()["paths"]
    for path in (
        OA,
        f"{OA}/{{assessment_id}}",
        f"{OA}/{{assessment_id}}/questions",
        f"{OA}/{{assessment_id}}/questions/import",
        f"{OA}/{{assessment_id}}/attempts",
        STUDENT_OA,
        f"{STUDENT_OA}/{{assessment_id}}/attempts",
        f"{STUDENT_ATT}/{{attempt_id}}",
        f"{STUDENT_ATT}/{{attempt_id}}/answers",
        f"{STUDENT_ATT}/{{attempt_id}}/submit",
    ):
        assert path in paths, path
    assert "/api/student/get-online-exam-list" in {
        r.path for r in app.routes if isinstance(r, APIRoute)
    }


def test_exam_crud_publish_validation_and_answer_key_secrecy(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "oa-sa@eschool.com")
    school_id = _school(v1_client, sa, "OA01")
    admin = _school_admin(v1_client, sa, school_id, "oa-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="oa1")

    # Invalid marks
    bad = v1_client.post(
        OA,
        headers=admin,
        json={
            **ids,
            **_window(total_marks=5, passing_marks=10),
        },
    )
    assert bad.status_code == 422

    created = v1_client.post(OA, headers=admin, json={**ids, **_window()})
    assert created.status_code == 201, created.text
    aid = created.json()["id"]
    assert created.json()["status"] == "draft"

    # Publish without questions fails
    assert (
        v1_client.patch(f"{OA}/{aid}", headers=admin, json={"status": "published"}).status_code
        == 422
    )

    q1 = v1_client.post(f"{OA}/{aid}/questions", headers=admin, json=_mcq("Two plus two?", 1, 1))
    assert q1.status_code == 201, q1.text
    assert q1.json()["choices"][1]["is_correct"] is True
    q2 = v1_client.post(f"{OA}/{aid}/questions", headers=admin, json=_mcq("Three?", 1, 0))
    assert q2.status_code == 201

    pub = v1_client.patch(f"{OA}/{aid}", headers=admin, json={"status": "published"})
    assert pub.status_code == 200
    assert pub.json()["status"] == "published"

    student, token = _make_student(
        v1_db, school_id, ids, email="oa1-s@eschool.com", admission_no="OA1001"
    )
    school = v1_db.get(School, school_id)
    sh = _sh(school.code, token)

    start = v1_client.post(f"{STUDENT_OA}/{aid}/attempts", headers=sh)
    assert start.status_code == 201, start.text
    attempt = start.json()
    assert attempt["status"] == "in_progress"
    assert "score" not in attempt or attempt.get("score") is None
    for q in attempt["questions"]:
        for c in q["choices"]:
            assert "is_correct" not in c

    # Duplicate start
    assert v1_client.post(f"{STUDENT_OA}/{aid}/attempts", headers=sh).status_code == 409

    correct_b = q1.json()["choices"][1]["id"]
    wrong_a = q2.json()["choices"][0]["id"]
    # Wait - q2 correct is index 0 (A). Student picks wrong for q2 = index 1
    wrong_b = q2.json()["choices"][1]["id"]
    saved = v1_client.post(
        f"{STUDENT_ATT}/{attempt['id']}/answers",
        headers=sh,
        json={
            "answers": [
                {"question_id": q1.json()["id"], "choice_id": correct_b},
                {"question_id": q2.json()["id"], "choice_id": wrong_b},
            ]
        },
    )
    assert saved.status_code == 200, saved.text

    # Idempotent autosave
    saved2 = v1_client.post(
        f"{STUDENT_ATT}/{attempt['id']}/answers",
        headers=sh,
        json={
            "answers": [
                {"question_id": q1.json()["id"], "choice_id": correct_b},
            ]
        },
    )
    assert saved2.status_code == 200

    submitted = v1_client.post(f"{STUDENT_ATT}/{attempt['id']}/submit", headers=sh)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "evaluated"
    # Results not published → no score leak
    assert "score" not in submitted.json() or submitted.json().get("score") is None

    # Publish results
    assert (
        v1_client.patch(f"{OA}/{aid}", headers=admin, json={"results_published": True}).status_code
        == 200
    )
    result = v1_client.get(f"{STUDENT_ATT}/{attempt['id']}", headers=sh)
    assert result.status_code == 200
    assert result.json()["score"] == 1.0
    assert result.json()["percentage"] == 50.0
    assert result.json()["passed"] is True  # passing_marks=1
    # Correct keys visible after publication
    assert any(
        "is_correct" in c for q in result.json().get("questions", []) for c in q.get("choices", [])
    )

    # Post-submit modification blocked
    assert (
        v1_client.post(
            f"{STUDENT_ATT}/{attempt['id']}/answers",
            headers=sh,
            json={"answers": [{"question_id": q1.json()["id"], "choice_id": wrong_a}]},
        ).status_code
        == 422
    )

    # Soft-delete exam
    assert v1_client.delete(f"{OA}/{aid}", headers=admin).status_code == 200
    assert v1_client.get(STUDENT_OA, headers=sh).json()["total"] == 0


def test_cross_school_and_accounts_denied(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "oa-x-sa@eschool.com")
    school_a = _school(v1_client, sa, "OAXA")
    school_b = _school(v1_client, sa, "OAXB")
    admin_a = _school_admin(v1_client, sa, school_a, "oa-xa@eschool.com")
    admin_b = _school_admin(v1_client, sa, school_b, "oa-xb@eschool.com")
    ids_a = _seed(v1_client, admin_a, email_prefix="oaxa")
    created = v1_client.post(OA, headers=admin_a, json={**ids_a, **_window()})
    assert created.status_code == 201
    aid = created.json()["id"]
    assert v1_client.get(f"{OA}/{aid}", headers=admin_b).status_code == 404

    accounts = _school_admin(
        v1_client, sa, school_a, "oa-acc@eschool.com", roles=["accounts_admin"]
    )
    assert v1_client.get(OA, headers=accounts).status_code == 403


def test_bulk_import_all_or_nothing_and_concurrent_start(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "oa-imp-sa@eschool.com")
    school_id = _school(v1_client, sa, "OAIM")
    admin = _school_admin(v1_client, sa, school_id, "oa-imp-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="oaim")
    created = v1_client.post(
        OA, headers=admin, json={**ids, **_window(total_marks=2, passing_marks=1)}
    )
    aid = created.json()["id"]

    # Bad import — no questions created
    bad = v1_client.post(
        f"{OA}/{aid}/questions/import",
        headers=admin,
        json={
            "items": [
                _mcq("Good", 1, 0),
                {"question_text": "Bad", "marks": 1, "choices": [{"choice_text": "Only one"}]},
            ]
        },
    )
    assert bad.status_code == 422
    detail = v1_client.get(f"{OA}/{aid}", headers=admin).json()
    assert detail["questions"] == []

    ok = v1_client.post(
        f"{OA}/{aid}/questions/import",
        headers=admin,
        json={"items": [_mcq("Q1", 1, 0), _mcq("Q2", 1, 1)]},
    )
    assert ok.status_code == 201
    assert ok.json()["created"] == 2
    assert (
        v1_client.patch(f"{OA}/{aid}", headers=admin, json={"status": "published"}).status_code
        == 200
    )

    student, _token = _make_student(
        v1_db, school_id, ids, email="oaim-s@eschool.com", admission_no="OAIM1"
    )
    student_user = v1_db.get(User, student.user_id)

    db_check = session_factory()()
    try:
        if not oa_svc._is_postgresql(db_check):
            pytest.skip("Concurrent attempt lock requires PostgreSQL")
    finally:
        db_check.close()

    barrier = Barrier(2)
    outcomes: list = []

    def worker() -> None:
        db = session_factory()()
        try:
            barrier.wait(timeout=30)
            user = db.get(User, student_user.id)
            oa_svc.start_attempt(db, school_id, user, aid)
            outcomes.append("ok")
        except AcademicError as exc:
            outcomes.append(("err", exc.status_code))
        except BaseException as exc:  # noqa: BLE001
            outcomes.append(("boom", type(exc).__name__))
        finally:
            db.close()

    threads = [Thread(target=worker), Thread(target=worker)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert outcomes.count("ok") == 1, outcomes
    errs = [o for o in outcomes if isinstance(o, tuple) and o[0] == "err"]
    assert len(errs) == 1 and errs[0][1] == 409, outcomes
    v1_db.expire_all()
    assert (
        v1_db.query(OnlineAssessmentAttempt)
        .filter(
            OnlineAssessmentAttempt.assessment_id == aid,
            OnlineAssessmentAttempt.deleted_at.is_(None),
        )
        .count()
        == 1
    )


def test_percentage_rounding_helper():
    assert oa_svc._round_pct(1, 3) == 33.33
    assert oa_svc._round_pct(2, 3) == 66.67
    assert oa_svc._round_pct(1, 2) == 50.0
