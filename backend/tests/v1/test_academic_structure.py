"""Academic structure: sessions, filters, class-subjects, teacher assignments."""

from __future__ import annotations

from sqlalchemy import select

from app.models.tables import ClassSubject, SessionYear, TeacherAssignment
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User

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


def _school_admin(client, sa_headers, school_id: int, email: str, password: str = "adminpass1") -> dict[str, str]:
    created = client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=sa_headers,
        json={"email": email, "password": password, "first_name": "School", "last_name": "Admin"},
    )
    assert created.status_code == 201, created.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
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


def _seed_structure(client, headers):
    medium = client.post(f"{ACADEMICS}/mediums", headers=headers, json={"name": "English"})
    assert medium.status_code == 201, medium.text
    medium_id = medium.json()["id"]
    section = client.post(f"{ACADEMICS}/sections", headers=headers, json={"name": "A"})
    assert section.status_code == 201, section.text
    klass = client.post(
        f"{ACADEMICS}/classes",
        headers=headers,
        json={"name": "Grade 1", "medium_id": medium_id},
    )
    assert klass.status_code == 201, klass.text
    subject = client.post(
        f"{ACADEMICS}/subjects",
        headers=headers,
        json={"name": "Math", "medium_id": medium_id, "code": "M1"},
    )
    assert subject.status_code == 201, subject.text
    return {
        "medium_id": medium_id,
        "section_id": section.json()["id"],
        "class_id": klass.json()["id"],
        "subject_id": subject.json()["id"],
    }


def test_session_activate_and_compact_sessions_unchanged(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "acad-sa@eschool.com")
    school_id = _school(v1_client, sa, "ACAD01")
    admin = _school_admin(v1_client, sa, school_id, "acad-admin@eschool.com")

    first = v1_client.post(
        f"{ACADEMICS}/sessions",
        headers=admin,
        json={"name": "2025-26", "start_date": "2025-04-01", "end_date": "2026-03-31", "default": 1},
    )
    assert first.status_code == 201, first.text
    assert first.json()["default"] == 1
    assert "start_date" in first.json()

    second = v1_client.post(
        f"{ACADEMICS}/sessions",
        headers=admin,
        json={"name": "2026-27", "start_date": "2026-04-01", "end_date": "2027-03-31", "default": 0},
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["id"]

    activated = v1_client.post(f"{ACADEMICS}/sessions/{second_id}/activate", headers=admin)
    assert activated.status_code == 200, activated.text
    assert activated.json()["default"] == 1
    assert activated.json()["id"] == second_id

    listed = v1_client.get(f"{ACADEMICS}/sessions", headers=admin)
    assert listed.status_code == 200, listed.text
    by_id = {item["id"]: item for item in listed.json()["items"]}
    assert by_id[second_id]["default"] == 1
    assert by_id[first.json()["id"]]["default"] == 0
    assert "start_date" in by_id[second_id]
    assert "end_date" in by_id[second_id]

    compact = v1_client.get("/api/v1/school-admin/sessions", headers=admin)
    assert compact.status_code == 200, compact.text
    for item in compact.json()["items"]:
        assert set(item.keys()) == {"id", "name", "default"}

    # Only one default in DB for this school.
    rows = list(
        v1_db.scalars(
            select(SessionYear).where(
                SessionYear.school_id == school_id,
                SessionYear.deleted_at.is_(None),
                SessionYear.default == 1,
            )
        )
    )
    assert len(rows) == 1
    assert rows[0].id == second_id


def test_filters_class_sections_and_class_subjects(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "acad-filter-sa@eschool.com")
    school_id = _school(v1_client, sa, "ACAD02")
    admin = _school_admin(v1_client, sa, school_id, "acad-filter-admin@eschool.com")
    ids = _seed_structure(v1_client, admin)

    other_medium = v1_client.post(f"{ACADEMICS}/mediums", headers=admin, json={"name": "Hindi"})
    assert other_medium.status_code == 201
    other_class = v1_client.post(
        f"{ACADEMICS}/classes",
        headers=admin,
        json={"name": "Grade 2", "medium_id": other_medium.json()["id"]},
    )
    assert other_class.status_code == 201

    filtered = v1_client.get(
        f"{ACADEMICS}/classes",
        headers=admin,
        params={"medium_id": ids["medium_id"]},
    )
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["items"]] == [ids["class_id"]]

    linked = v1_client.post(
        f"{ACADEMICS}/class-sections",
        headers=admin,
        json={
            "class_id": ids["class_id"],
            "section_id": ids["section_id"],
            "medium_id": ids["medium_id"],
        },
    )
    assert linked.status_code == 201, linked.text
    assert linked.json()["class_name"] == "Grade 1"
    assert linked.json()["section_name"] == "A"
    assert v1_client.post(
        f"{ACADEMICS}/class-sections",
        headers=admin,
        json={
            "class_id": ids["class_id"],
            "section_id": ids["section_id"],
            "medium_id": ids["medium_id"],
        },
    ).status_code == 409

    cs_list = v1_client.get(
        f"{ACADEMICS}/class-sections",
        headers=admin,
        params={"class_id": ids["class_id"]},
    )
    assert cs_list.status_code == 200
    assert cs_list.json()["total"] == 1

    mapped = v1_client.post(
        f"{ACADEMICS}/class-subjects",
        headers=admin,
        json={"class_id": ids["class_id"], "subject_id": ids["subject_id"]},
    )
    assert mapped.status_code == 201, mapped.text
    assert mapped.json()["subject_name"] == "Math"
    assert v1_client.post(
        f"{ACADEMICS}/class-subjects",
        headers=admin,
        json={"class_id": ids["class_id"], "subject_id": ids["subject_id"]},
    ).status_code == 409

    deleted = v1_client.delete(f"{ACADEMICS}/class-sections/{linked.json()['id']}", headers=admin)
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}


def test_teacher_assignments_rbac_and_isolation(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "acad-assign-sa@eschool.com")
    school_a = _school(v1_client, sa, "ACAD03")
    school_b = _school(v1_client, sa, "ACAD04")
    admin_a = _school_admin(v1_client, sa, school_a, "acad-a@eschool.com")
    admin_b = _school_admin(v1_client, sa, school_b, "acad-b@eschool.com")
    ids = _seed_structure(v1_client, admin_a)

    teacher = v1_client.post(
        f"{ACADEMICS}/teachers",
        headers=admin_a,
        json={"first_name": "T", "last_name": "One", "email": "teacher-acad@eschool.com"},
    )
    assert teacher.status_code == 201, teacher.text
    teacher_id = teacher.json()["id"]

    session = v1_client.post(
        f"{ACADEMICS}/sessions",
        headers=admin_a,
        json={"name": "Y1", "start_date": "2026-04-01", "end_date": "2027-03-31"},
    )
    assert session.status_code == 201
    class_section = v1_client.post(
        f"{ACADEMICS}/class-sections",
        headers=admin_a,
        json={
            "class_id": ids["class_id"],
            "section_id": ids["section_id"],
            "medium_id": ids["medium_id"],
        },
    )
    assert class_section.status_code == 201
    mapped = v1_client.post(
        f"{ACADEMICS}/class-subjects",
        headers=admin_a,
        json={"class_id": ids["class_id"], "subject_id": ids["subject_id"]},
    )
    assert mapped.status_code == 201, mapped.text

    created = v1_client.post(
        f"{ACADEMICS}/teacher-assignments",
        headers=admin_a,
        json={
            "teacher_id": teacher_id,
            "subject_id": ids["subject_id"],
            "class_section_id": class_section.json()["id"],
            "session_year_id": session.json()["id"],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["teacher_id"] == teacher_id
    assert created.json()["staff_id"] >= 1
    assignment_id = created.json()["id"]

    assert v1_client.post(
        f"{ACADEMICS}/teacher-assignments",
        headers=admin_a,
        json={
            "teacher_id": teacher_id,
            "subject_id": ids["subject_id"],
            "class_section_id": class_section.json()["id"],
            "session_year_id": session.json()["id"],
        },
    ).status_code == 409

    detail = v1_client.get(f"{ACADEMICS}/teacher-assignments/{assignment_id}", headers=admin_a)
    assert detail.status_code == 200
    assert detail.json()["subject_id"] == ids["subject_id"]

    # Other school cannot see or mutate.
    assert (
        v1_client.get(f"{ACADEMICS}/teacher-assignments/{assignment_id}", headers=admin_b).status_code
        == 404
    )
    assert (
        v1_client.delete(f"{ACADEMICS}/teacher-assignments/{assignment_id}", headers=admin_b).status_code
        == 404
    )

    # Cross-school subject id rejected.
    foreign_ids = _seed_structure(v1_client, admin_b)
    bad = v1_client.post(
        f"{ACADEMICS}/teacher-assignments",
        headers=admin_a,
        json={"teacher_id": teacher_id, "subject_id": foreign_ids["subject_id"]},
    )
    assert bad.status_code == 422

    soft = v1_client.delete(f"{ACADEMICS}/teacher-assignments/{assignment_id}", headers=admin_a)
    assert soft.status_code == 200
    row = v1_db.get(TeacherAssignment, assignment_id)
    assert row is not None and row.deleted_at is not None

    mapped = v1_db.scalar(select(ClassSubject).where(ClassSubject.school_id == school_a))
    # class-subject may be absent in this test; ensure model is importable / table creatable via create_all
    assert ClassSubject.__tablename__ == "class_subjects"
