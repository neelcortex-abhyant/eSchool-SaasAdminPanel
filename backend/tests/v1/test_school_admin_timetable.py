"""Module 1: class timetable CRUD, weekly view, conflicts, isolation."""

from __future__ import annotations

from threading import Barrier, Thread

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import select

from app.core.database import session_factory
from app.main import app
from app.models.tables import ClassTimetableEntry
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User
from app.services.v1.school_academics import AcademicError
from app.services.v1 import school_timetable as timetable_svc

ENTRIES = "/api/v1/school-admin/timetable-entries"
WEEKLY = "/api/v1/school-admin/timetable/weekly"
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


def _seed(client, headers, *, email_prefix: str = "tt"):
    medium = client.post(f"{ACADEMICS}/mediums", headers=headers, json={"name": "English"})
    assert medium.status_code == 201, medium.text
    medium_id = medium.json()["id"]
    klass = client.post(CLASSES, headers=headers, json={"name": "Grade 1", "medium_id": medium_id})
    assert klass.status_code == 201, klass.text
    class_id = klass.json()["id"]
    section = client.post(SECTIONS, headers=headers, json={"name": "A", "class_id": class_id})
    assert section.status_code == 201, section.text
    section_id = section.json()["id"]
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
        json={"name": "Math", "code": "M1", "medium_id": medium_id},
    )
    assert subject.status_code == 201, subject.text
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
    # Broad assignments (any class-section / session) for timetable eligibility.
    for tid in (teacher.json()["id"], teacher2.json()["id"]):
        asg = client.post(
            ASSIGNMENTS,
            headers=headers,
            json={"teacher_id": tid, "subject_id": subject_id},
        )
        assert asg.status_code == 201, asg.text
    return {
        "medium_id": medium_id,
        "class_id": class_id,
        "section_id": section_id,
        "class_id_2": klass2.json()["id"],
        "section_id_2": section2.json()["id"],
        "class_section_id": class_section_id,
        "class_section_id_2": class_section_id_2,
        "subject_id": subject_id,
        "session_year_id": session.json()["id"],
        "teacher_user_id": teacher.json()["id"],
        "teacher_user_id_2": teacher2.json()["id"],
    }


def _entry_body(ids, **extra):
    body = {
        "session_year_id": ids["session_year_id"],
        "class_section_id": ids["class_section_id"],
        "subject_id": ids["subject_id"],
        "teacher_user_id": ids["teacher_user_id"],
        "day": "monday",
        "start_time": "09:00",
        "end_time": "09:45",
        "note": "Period 1",
    }
    body.update(extra)
    return body


def test_openapi_registers_timetable_routes():
    paths = app.openapi()["paths"]
    for path in (
        ENTRIES,
        f"{ENTRIES}/{{entry_id}}",
        WEEKLY,
    ):
        assert path in paths, path
    route_paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    assert "/api/v1/school-admin/timetable-entries" in route_paths
    assert "/api/v1/school-admin/timetable/weekly" in route_paths


def test_timetable_crud_list_filters_weekly_and_soft_delete(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "tt-sa@eschool.com")
    school_id = _school(v1_client, sa, "TT01")
    admin = _school_admin(v1_client, sa, school_id, "tt-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="tt1")

    created = v1_client.post(ENTRIES, headers=admin, json=_entry_body(ids))
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["day"] == "monday"
    assert body["start_time"] == "09:00"
    assert body["end_time"] == "09:45"
    assert body["subject_name"] == "Math"
    assert body["teacher_name"]
    assert "school_id" not in body
    entry_id = body["id"]

    second = v1_client.post(
        ENTRIES,
        headers=admin,
        json=_entry_body(
            ids,
            day="Tuesday",
            start_time="10:00",
            end_time="10:45",
            teacher_user_id=ids["teacher_user_id_2"],
            note=None,
        ),
    )
    assert second.status_code == 201, second.text

    listed = v1_client.get(ENTRIES, headers=admin, params={"session_year_id": ids["session_year_id"]})
    assert listed.status_code == 200
    assert set(listed.json().keys()) == {"items", "total", "page", "page_size"}
    assert listed.json()["total"] == 2
    assert listed.json()["items"][0]["day"] == "monday"

    filtered = v1_client.get(
        ENTRIES,
        headers=admin,
        params={"day": "tuesday", "class_section_id": ids["class_section_id"]},
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1

    paged = v1_client.get(ENTRIES, headers=admin, params={"page": 1, "page_size": 1})
    assert paged.status_code == 200
    assert len(paged.json()["items"]) == 1
    assert paged.json()["total"] == 2

    detail = v1_client.get(f"{ENTRIES}/{entry_id}", headers=admin)
    assert detail.status_code == 200
    assert detail.json()["id"] == entry_id

    updated = v1_client.patch(
        f"{ENTRIES}/{entry_id}",
        headers=admin,
        json={"note": "Updated", "end_time": "09:50"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["note"] == "Updated"
    assert updated.json()["end_time"] == "09:50"

    # Self-update without changing slot must not 409.
    same = v1_client.patch(
        f"{ENTRIES}/{entry_id}",
        headers=admin,
        json={"note": "Still ok"},
    )
    assert same.status_code == 200, same.text

    weekly = v1_client.get(
        WEEKLY,
        headers=admin,
        params={
            "session_year_id": ids["session_year_id"],
            "class_section_id": ids["class_section_id"],
        },
    )
    assert weekly.status_code == 200, weekly.text
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

    deleted = v1_client.delete(f"{ENTRIES}/{entry_id}", headers=admin)
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
    assert v1_client.get(f"{ENTRIES}/{entry_id}", headers=admin).status_code == 404
    listed_after = v1_client.get(ENTRIES, headers=admin)
    assert listed_after.json()["total"] == 1
    row = v1_db.get(ClassTimetableEntry, entry_id)
    assert row is not None and row.deleted_at is not None


def test_timetable_validation_and_conflicts(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "tt-c-sa@eschool.com")
    school_id = _school(v1_client, sa, "TTC1")
    admin = _school_admin(v1_client, sa, school_id, "tt-c-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="ttc")

    assert (
        v1_client.post(
            ENTRIES, headers=admin, json=_entry_body(ids, day="sunday")
        ).status_code
        == 422
    )
    assert (
        v1_client.post(
            ENTRIES,
            headers=admin,
            json=_entry_body(ids, start_time="10:00", end_time="09:00"),
        ).status_code
        == 422
    )
    assert (
        v1_client.post(
            ENTRIES,
            headers=admin,
            json=_entry_body(ids, session_year_id=999999),
        ).status_code
        == 422
    )
    assert (
        v1_client.post(
            ENTRIES,
            headers=admin,
            json=_entry_body(ids, class_section_id=999999),
        ).status_code
        == 422
    )
    assert (
        v1_client.post(
            ENTRIES,
            headers=admin,
            json=_entry_body(ids, teacher_user_id=ids["teacher_user_id_2"] + 5000),
        ).status_code
        == 422
    )

    first = v1_client.post(ENTRIES, headers=admin, json=_entry_body(ids))
    assert first.status_code == 201, first.text

    # Class-section overlap
    overlap = v1_client.post(
        ENTRIES,
        headers=admin,
        json=_entry_body(
            ids,
            teacher_user_id=ids["teacher_user_id_2"],
            start_time="09:30",
            end_time="10:15",
        ),
    )
    assert overlap.status_code == 409

    # Teacher overlap across class-sections
    teacher_clash = v1_client.post(
        ENTRIES,
        headers=admin,
        json=_entry_body(
            ids,
            class_section_id=ids["class_section_id_2"],
            start_time="09:15",
            end_time="10:00",
        ),
    )
    assert teacher_clash.status_code == 409

    # Non-overlapping same class OK
    ok = v1_client.post(
        ENTRIES,
        headers=admin,
        json=_entry_body(
            ids,
            start_time="11:00",
            end_time="11:45",
            teacher_user_id=ids["teacher_user_id_2"],
        ),
    )
    assert ok.status_code == 201, ok.text


def test_timetable_auth_permission_and_cross_school(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "tt-x-sa@eschool.com")
    school_a = _school(v1_client, sa, "TTXA")
    school_b = _school(v1_client, sa, "TTXB")
    admin_a = _school_admin(v1_client, sa, school_a, "tt-xa@eschool.com")
    admin_b = _school_admin(v1_client, sa, school_b, "tt-xb@eschool.com")
    accounts = _school_admin(
        v1_client, sa, school_a, "tt-acc@eschool.com", roles=["accounts_admin"]
    )
    ids = _seed(v1_client, admin_a, email_prefix="ttx")

    assert v1_client.get(ENTRIES).status_code in (401, 403)
    assert (
        v1_client.post(ENTRIES, headers=accounts, json=_entry_body(ids)).status_code == 403
    )

    created = v1_client.post(ENTRIES, headers=admin_a, json=_entry_body(ids))
    assert created.status_code == 201, created.text
    entry_id = created.json()["id"]

    assert v1_client.get(f"{ENTRIES}/{entry_id}", headers=admin_b).status_code == 404
    assert (
        v1_client.patch(
            f"{ENTRIES}/{entry_id}", headers=admin_b, json={"note": "x"}
        ).status_code
        == 404
    )
    assert v1_client.delete(f"{ENTRIES}/{entry_id}", headers=admin_b).status_code == 404


def _require_postgres_advisory_locks():
    db = session_factory()()
    try:
        if not timetable_svc._is_postgresql(db):
            pytest.skip("Timetable advisory locks require PostgreSQL")
    finally:
        db.close()


def _active_overlap_count(db, school_id: int, *, session_year_id: int, class_section_id: int, day: str) -> int:
    rows = (
        db.query(ClassTimetableEntry)
        .filter(
            ClassTimetableEntry.school_id == school_id,
            ClassTimetableEntry.session_year_id == session_year_id,
            ClassTimetableEntry.class_section_id == class_section_id,
            ClassTimetableEntry.day == day,
            ClassTimetableEntry.deleted_at.is_(None),
        )
        .all()
    )
    overlaps = 0
    for i, a in enumerate(rows):
        for b in rows[i + 1 :]:
            if a.start_time < b.end_time and a.end_time > b.start_time:
                overlaps += 1
    return overlaps


def test_concurrent_overlapping_creates_one_wins_on_postgres(v1_client, v1_db):
    """Independent sessions + barrier: empty-slot race must not leave overlaps."""
    _require_postgres_advisory_locks()
    sa = _super(v1_client, v1_db, "tt-conc-sa@eschool.com")
    school_id = _school(v1_client, sa, "TTCN")
    admin = _school_admin(v1_client, sa, school_id, "tt-conc-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="ttconc")
    body = _entry_body(ids, start_time="09:00", end_time="09:45")

    barrier = Barrier(2)
    outcomes: list[tuple] = []

    def worker(teacher_user_id: int) -> None:
        db = session_factory()()
        try:
            barrier.wait(timeout=30)
            payload = {**body, "teacher_user_id": teacher_user_id}
            item = timetable_svc.create_entry(db, school_id, payload)
            outcomes.append(("ok", item["id"]))
        except AcademicError as exc:
            outcomes.append(("err", exc.status_code, exc.detail))
        except BaseException as exc:  # noqa: BLE001
            outcomes.append(("boom", type(exc).__name__, str(exc)))
        finally:
            db.close()

    # Same class-section/day/time; different teachers → class-section conflict.
    threads = [
        Thread(target=worker, args=(ids["teacher_user_id"],)),
        Thread(target=worker, args=(ids["teacher_user_id_2"],)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert len(outcomes) == 2, outcomes
    oks = [o for o in outcomes if o[0] == "ok"]
    errs = [o for o in outcomes if o[0] == "err"]
    assert len(oks) == 1, outcomes
    assert len(errs) == 1 and errs[0][1] == 409, outcomes
    v1_db.expire_all()
    assert (
        _active_overlap_count(
            v1_db,
            school_id,
            session_year_id=ids["session_year_id"],
            class_section_id=ids["class_section_id"],
            day="monday",
        )
        == 0
    )
    assert (
        v1_db.query(ClassTimetableEntry)
        .filter(
            ClassTimetableEntry.school_id == school_id,
            ClassTimetableEntry.deleted_at.is_(None),
        )
        .count()
        == 1
    )


def test_concurrent_updates_into_same_slot_one_wins_on_postgres(v1_client, v1_db):
    _require_postgres_advisory_locks()
    sa = _super(v1_client, v1_db, "tt-updc-sa@eschool.com")
    school_id = _school(v1_client, sa, "TTUP")
    admin = _school_admin(v1_client, sa, school_id, "tt-updc-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="ttupdc")

    first = v1_client.post(
        ENTRIES,
        headers=admin,
        json=_entry_body(ids, start_time="09:00", end_time="09:45"),
    )
    second = v1_client.post(
        ENTRIES,
        headers=admin,
        json=_entry_body(
            ids,
            start_time="11:00",
            end_time="11:45",
            teacher_user_id=ids["teacher_user_id_2"],
        ),
    )
    assert first.status_code == 201 and second.status_code == 201, (first.text, second.text)
    id_a, id_b = first.json()["id"], second.json()["id"]

    barrier = Barrier(2)
    outcomes: list[tuple] = []

    def worker(entry_id: int) -> None:
        db = session_factory()()
        try:
            barrier.wait(timeout=30)
            item = timetable_svc.update_entry(
                db,
                school_id,
                entry_id,
                {"start_time": "10:00", "end_time": "10:45"},
            )
            outcomes.append(("ok", item["id"]))
        except AcademicError as exc:
            outcomes.append(("err", exc.status_code, exc.detail))
        except BaseException as exc:  # noqa: BLE001
            outcomes.append(("boom", type(exc).__name__, str(exc)))
        finally:
            db.close()

    threads = [Thread(target=worker, args=(id_a,)), Thread(target=worker, args=(id_b,))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert len(outcomes) == 2, outcomes
    oks = [o for o in outcomes if o[0] == "ok"]
    errs = [o for o in outcomes if o[0] == "err"]
    assert len(oks) == 1, outcomes
    assert len(errs) == 1 and errs[0][1] == 409, outcomes
    v1_db.expire_all()
    assert (
        _active_overlap_count(
            v1_db,
            school_id,
            session_year_id=ids["session_year_id"],
            class_section_id=ids["class_section_id"],
            day="monday",
        )
        == 0
    )
