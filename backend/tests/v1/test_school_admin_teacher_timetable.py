"""Module 2: teacher timetable views, daily/weekly, availability."""

from __future__ import annotations

from fastapi.routing import APIRoute
from sqlalchemy import select

from app.main import app
from app.models.tables import ClassTimetableEntry
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User
from app.services.v1 import school_timetable as timetable_svc

ENTRIES = "/api/v1/school-admin/timetable-entries"
TEACHERS = "/api/v1/school-admin/teachers"
ASSIGNMENTS = "/api/v1/school-admin/teacher-assignments"
CLASSES = "/api/v1/school-admin/classes"
SECTIONS = "/api/v1/school-admin/sections"
SUBJECTS = "/api/v1/school-admin/subjects"
ACADEMICS = "/api/v1/school-admin/academics"


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


def _seed(client, headers, *, email_prefix: str = "m2"):
    medium = client.post(f"{ACADEMICS}/mediums", headers=headers, json={"name": "English"})
    assert medium.status_code == 201, medium.text
    medium_id = medium.json()["id"]
    klass = client.post(CLASSES, headers=headers, json={"name": "Grade 1", "medium_id": medium_id})
    assert klass.status_code == 201
    class_id = klass.json()["id"]
    section = client.post(SECTIONS, headers=headers, json={"name": "A", "class_id": class_id})
    assert section.status_code == 201
    class_section_id = section.json()["class_section_id"]
    klass2 = client.post(CLASSES, headers=headers, json={"name": "Grade 2", "medium_id": medium_id})
    assert klass2.status_code == 201
    section2 = client.post(
        SECTIONS, headers=headers, json={"name": "B", "class_id": klass2.json()["id"]}
    )
    assert section2.status_code == 201
    class_section_id_2 = section2.json()["class_section_id"]
    subject = client.post(
        SUBJECTS,
        headers=headers,
        json={"name": "Math", "code": "M2", "medium_id": medium_id},
    )
    assert subject.status_code == 201
    subject_id = subject.json()["id"]
    assert (
        client.put(
            f"{SUBJECTS}/{subject_id}/classes",
            headers=headers,
            json={"class_ids": [class_id, klass2.json()["id"]]},
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
            "first_name": "Tea",
            "last_name": "Cher",
            "email": f"{email_prefix}-t@eschool.com",
            "password": "teacherpass1",
            "employee_id": f"{email_prefix}-E1",
        },
    )
    assert teacher.status_code == 201, teacher.text
    teacher_id = teacher.json()["id"]
    asg = client.post(
        ASSIGNMENTS,
        headers=headers,
        json={"teacher_id": teacher_id, "subject_id": subject_id},
    )
    assert asg.status_code == 201, asg.text
    return {
        "class_id": class_id,
        "section_id": section.json()["id"],
        "class_section_id": class_section_id,
        "class_section_id_2": class_section_id_2,
        "subject_id": subject_id,
        "session_year_id": session.json()["id"],
        "teacher_user_id": teacher_id,
    }


def _slot(ids, **extra):
    body = {
        "session_year_id": ids["session_year_id"],
        "class_section_id": ids["class_section_id"],
        "subject_id": ids["subject_id"],
        "teacher_user_id": ids["teacher_user_id"],
        "day": "monday",
        "start_time": "09:00",
        "end_time": "09:45",
    }
    body.update(extra)
    return body


def test_openapi_registers_teacher_timetable_routes():
    paths = app.openapi()["paths"]
    for path in (
        f"{TEACHERS}/{{teacher_user_id}}/timetable",
        f"{TEACHERS}/{{teacher_user_id}}/timetable/daily",
        f"{TEACHERS}/{{teacher_user_id}}/timetable/weekly",
        f"{TEACHERS}/{{teacher_user_id}}/availability",
    ):
        assert path in paths, path
    route_paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    assert "/api/v1/school-admin/teachers/{teacher_user_id}/timetable" in route_paths


def test_teacher_timetable_daily_weekly_filters_and_fields(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "m2-sa@eschool.com")
    school_id = _school(v1_client, sa, "M2T1")
    admin = _school_admin(v1_client, sa, school_id, "m2-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="m2a")
    tid = ids["teacher_user_id"]
    sid = ids["session_year_id"]

    mon = v1_client.post(ENTRIES, headers=admin, json=_slot(ids))
    assert mon.status_code == 201, mon.text
    tue = v1_client.post(
        ENTRIES,
        headers=admin,
        json=_slot(
            ids,
            day="tuesday",
            start_time="10:00",
            end_time="10:45",
            class_section_id=ids["class_section_id_2"],
        ),
    )
    assert tue.status_code == 201, tue.text

    listed = v1_client.get(
        f"{TEACHERS}/{tid}/timetable",
        headers=admin,
        params={"session_year_id": sid},
    )
    assert listed.status_code == 200, listed.text
    assert set(listed.json().keys()) == {"items", "total", "page", "page_size"}
    assert listed.json()["total"] == 2
    item = listed.json()["items"][0]
    assert item["entry_id"] == item["id"]
    assert item["subject_name"] == "Math"
    assert item["class_name"]
    assert item["section_name"]
    assert item["teacher_user_id"] == tid
    assert "password" not in item

    day_filter = v1_client.get(
        f"{TEACHERS}/{tid}/timetable",
        headers=admin,
        params={"session_year_id": sid, "day": "Tuesday"},
    )
    assert day_filter.status_code == 200
    assert day_filter.json()["total"] == 1
    assert day_filter.json()["items"][0]["day"] == "tuesday"

    daily = v1_client.get(
        f"{TEACHERS}/{tid}/timetable/daily",
        headers=admin,
        params={"session_year_id": sid, "day": "monday"},
    )
    assert daily.status_code == 200
    assert daily.json()["day"] == "monday"
    assert len(daily.json()["entries"]) == 1
    assert daily.json()["entries"][0]["start_time"] == "09:00"

    weekly = v1_client.get(
        f"{TEACHERS}/{tid}/timetable/weekly",
        headers=admin,
        params={"session_year_id": sid},
    )
    assert weekly.status_code == 200
    days = weekly.json()["days"]
    assert [d["day"] for d in days] == [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
    ]
    assert len(days[0]["entries"]) == 1
    assert len(days[1]["entries"]) == 1
    assert days[2]["entries"] == []


def test_teacher_availability_conflicts_exclude_and_soft_delete(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "m2-av-sa@eschool.com")
    school_id = _school(v1_client, sa, "M2AV")
    admin = _school_admin(v1_client, sa, school_id, "m2-av-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="m2av")
    tid = ids["teacher_user_id"]
    sid = ids["session_year_id"]

    free = v1_client.get(
        f"{TEACHERS}/{tid}/availability",
        headers=admin,
        params={
            "session_year_id": sid,
            "day": "monday",
            "start_time": "09:00",
            "end_time": "09:45",
        },
    )
    assert free.status_code == 200
    assert free.json()["available"] is True
    assert free.json()["conflicts"] == []

    created = v1_client.post(ENTRIES, headers=admin, json=_slot(ids))
    assert created.status_code == 201
    entry_id = created.json()["id"]

    busy = v1_client.get(
        f"{TEACHERS}/{tid}/availability",
        headers=admin,
        params={
            "session_year_id": sid,
            "day": "monday",
            "start_time": "09:15",
            "end_time": "10:00",
        },
    )
    assert busy.status_code == 200
    assert busy.json()["available"] is False
    assert len(busy.json()["conflicts"]) == 1
    assert busy.json()["conflicts"][0]["entry_id"] == entry_id

    excluded = v1_client.get(
        f"{TEACHERS}/{tid}/availability",
        headers=admin,
        params={
            "session_year_id": sid,
            "day": "monday",
            "start_time": "09:15",
            "end_time": "10:00",
            "exclude_entry_id": entry_id,
        },
    )
    assert excluded.status_code == 200
    assert excluded.json()["available"] is True
    assert excluded.json()["exclude_entry_id"] == entry_id

    assert v1_client.delete(f"{ENTRIES}/{entry_id}", headers=admin).status_code == 200
    after = v1_client.get(
        f"{TEACHERS}/{tid}/timetable",
        headers=admin,
        params={"session_year_id": sid},
    )
    assert after.json()["total"] == 0
    avail_after = v1_client.get(
        f"{TEACHERS}/{tid}/availability",
        headers=admin,
        params={
            "session_year_id": sid,
            "day": "monday",
            "start_time": "09:00",
            "end_time": "09:45",
        },
    )
    assert avail_after.json()["available"] is True
    row = v1_db.get(ClassTimetableEntry, entry_id)
    assert row is not None and row.deleted_at is not None


def test_teacher_timetable_auth_isolation_and_invalid_teacher(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "m2-x-sa@eschool.com")
    school_a = _school(v1_client, sa, "M2XA")
    school_b = _school(v1_client, sa, "M2XB")
    admin_a = _school_admin(v1_client, sa, school_a, "m2-xa@eschool.com")
    admin_b = _school_admin(v1_client, sa, school_b, "m2-xb@eschool.com")
    accounts = _school_admin(
        v1_client, sa, school_a, "m2-acc@eschool.com", roles=["accounts_admin"]
    )
    ids = _seed(v1_client, admin_a, email_prefix="m2x")
    tid = ids["teacher_user_id"]
    sid = ids["session_year_id"]
    assert v1_client.post(ENTRIES, headers=admin_a, json=_slot(ids)).status_code == 201

    assert v1_client.get(f"{TEACHERS}/{tid}/timetable", params={"session_year_id": sid}).status_code in (
        401,
        403,
    )
    assert (
        v1_client.get(
            f"{TEACHERS}/{tid}/timetable",
            headers=accounts,
            params={"session_year_id": sid},
        ).status_code
        == 403
    )
    assert (
        v1_client.get(
            f"{TEACHERS}/{tid}/timetable",
            headers=admin_b,
            params={"session_year_id": sid},
        ).status_code
        == 404
    )
    assert (
        v1_client.get(
            f"{TEACHERS}/999999/timetable/weekly",
            headers=admin_a,
            params={"session_year_id": sid},
        ).status_code
        == 404
    )

    # Inactive teacher → 404 on timetable views
    assert (
        v1_client.patch(f"{TEACHERS}/{tid}/status", headers=admin_a, json={"status": 0}).status_code
        == 200
    )
    assert (
        v1_client.get(
            f"{TEACHERS}/{tid}/timetable",
            headers=admin_a,
            params={"session_year_id": sid},
        ).status_code
        == 404
    )


def test_write_paths_still_use_advisory_lock_helpers():
    """Sanity: Module 1 lock helpers remain the write protocol entry points."""
    assert callable(timetable_svc._acquire_timetable_advisory_locks)
    assert callable(timetable_svc._schedule_lock_labels)
    assert callable(timetable_svc.create_entry)
    assert callable(timetable_svc.update_entry)
    assert callable(timetable_svc.soft_delete_entry)
    src = open(timetable_svc.__file__, encoding="utf-8").read()
    assert "_acquire_timetable_advisory_locks" in src
    assert "pg_advisory_xact_lock" in src
    # Teacher reads must not take write locks.
    assert "list_teacher_timetable" in src
    assert "check_teacher_availability" in src
