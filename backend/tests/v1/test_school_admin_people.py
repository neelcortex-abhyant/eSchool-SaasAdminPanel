"""People API: students, parents, guardians (contract routes under /school-admin)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi.routing import APIRoute
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.main import app
from app.models.tables import Student, StudentGuardian, User
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User as V1User

STUDENTS = "/api/v1/school-admin/students"
PARENTS = "/api/v1/school-admin/parents"
ACADEMICS = "/api/v1/school-admin/academics"

# 1x1 PNG + minimal PDF for upload limit / MIME tests
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)
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


def _session_and_section(client, headers: dict, v1_db) -> tuple[int, int]:
    from app.core.v1_database import get_v1_session_factory
    from app.models.tables import ClassSection, SchoolClass, Section, SessionYear
    from app.core.security import utcnow

    # Prefer API session create when available.
    sess = client.post(
        f"{ACADEMICS}/sessions",
        headers=headers,
        json={
            "name": "2026-27",
            "start_date": "2026-04-01",
            "end_date": "2027-03-31",
            "default": 1,
        },
    )
    assert sess.status_code in (200, 201), sess.text
    session_year_id = sess.json()["id"]

    medium = client.post(f"{ACADEMICS}/mediums", headers=headers, json={"name": "English"})
    assert medium.status_code in (200, 201), medium.text
    medium_id = medium.json()["id"]

    klass = client.post(
        f"{ACADEMICS}/classes",
        headers=headers,
        json={"name": "Class 5", "medium_id": medium_id},
    )
    assert klass.status_code in (200, 201), klass.text
    class_id = klass.json()["id"]

    section = client.post(f"{ACADEMICS}/sections", headers=headers, json={"name": "A"})
    assert section.status_code in (200, 201), section.text
    section_id = section.json()["id"]

    cs = client.post(
        f"{ACADEMICS}/class-sections",
        headers=headers,
        json={"class_id": class_id, "section_id": section_id, "medium_id": medium_id},
    )
    if cs.status_code not in (200, 201):
        # Fallback: insert ClassSection directly if API shape differs.
        db = get_v1_session_factory()()
        try:
            # Resolve school from session year.
            sy = db.get(SessionYear, session_year_id)
            assert sy is not None
            row = ClassSection(
                class_id=class_id,
                section_id=section_id,
                medium_id=medium_id,
                school_id=sy.school_id,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return session_year_id, row.id
        finally:
            db.close()
    return session_year_id, cs.json()["id"]


def _enable_storage(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DOCUMENT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()


def _student_body(
    session_year_id: int,
    class_section_id: int,
    *,
    first_name: str = "Riya",
    last_name: str = "Sharma",
    admission_no: str | None = None,
    roll_number: int | None = None,
    email: str | None = None,
    guardian_email: str = "guardian.people@example.com",
    guardian_mobile: str = "9830111101",
    include_email_key: bool = False,
) -> dict:
    dob = (date.today() - timedelta(days=10 * 365)).isoformat()
    body: dict = {
        "first_name": first_name,
        "last_name": last_name,
        "dob": dob,
        "gender": "female",
        "admission_date": date.today().isoformat(),
        "session_year_id": session_year_id,
        "class_section_id": class_section_id,
        "current_address": "12 Lake View",
        "guardian": {
            "first_name": "Rajesh",
            "last_name": last_name,
            "email": guardian_email,
            "mobile": guardian_mobile,
            "relationship": "Father",
        },
    }
    if admission_no is not None:
        body["admission_no"] = admission_no
    if roll_number is not None:
        body["roll_number"] = roll_number
    if include_email_key or email is not None:
        body["email"] = email
    return body


def test_openapi_registers_people_student_parent_routes():
    paths = app.openapi()["paths"]
    for path in (
        STUDENTS,
        f"{STUDENTS}/{{student_id}}",
        f"{STUDENTS}/{{student_id}}/status",
        f"{STUDENTS}/{{student_id}}/guardians",
        f"{STUDENTS}/{{student_id}}/documents",
        PARENTS,
        f"{PARENTS}/{{parent_id}}",
        f"{PARENTS}/{{parent_id}}/status",
        "/api/v1/school-admin/teachers/departments",
        "/api/v1/school-admin/staff/departments",
    ):
        assert path in paths, path
    # Academics catch-all remains (students via /academics/{resource}).
    assert any("/academics/{resource}" in p or "/academics/" in p for p in paths)
    route_paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    assert "/api/v1/school-admin/students" in route_paths
    assert "/api/v1/school-admin/parents" in route_paths
    assert f"{STUDENTS}/{{student_id}}/documents" in route_paths
    assert any("/academics" in p for p in route_paths)


def test_student_admission_guardian_link_and_parent_profile(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "people-sa@example.com")
    school_id = _school(v1_client, sa, "PPL1")
    headers = _school_admin(v1_client, sa, school_id, "people-admin@example.com")
    session_year_id, class_section_id = _session_and_section(v1_client, headers, v1_db)

    dob = (date.today() - timedelta(days=10 * 365)).isoformat()
    created = v1_client.post(
        STUDENTS,
        headers=headers,
        json={
            "first_name": "Riya",
            "last_name": "Sharma",
            "dob": dob,
            "gender": "female",
            "admission_date": date.today().isoformat(),
            "session_year_id": session_year_id,
            "class_section_id": class_section_id,
            "current_address": "12 Lake View",
            "guardian": {
                "first_name": "Rajesh",
                "last_name": "Sharma",
                "email": "rajesh.people@example.com",
                "mobile": "9830111137",
                "relationship": "Father",
            },
        },
    )
    assert created.status_code == 201, created.text
    profile = created.json()
    assert profile["admission_no"].startswith("ADM")
    assert profile["guardians"] and profile["guardians"][0]["is_primary"] is True
    student_id = profile["id"]
    parent_id = profile["guardians"][0]["parent_id"]

    # Legacy guardian_id synced.
    row = v1_db.get(Student, student_id)
    assert row is not None
    assert row.guardian_id == parent_id

    # Academics list still works.
    acad = v1_client.get(f"{ACADEMICS}/students", headers=headers)
    assert acad.status_code == 200, acad.text

    # Link second guardian via parent create + link.
    parent2 = v1_client.post(
        PARENTS,
        headers=headers,
        json={
            "first_name": "Anita",
            "last_name": "Sharma",
            "email": "anita.people@example.com",
            "mobile": "9830111138",
            "status": 1,
            "students": [],
        },
    )
    assert parent2.status_code == 201, parent2.text
    p2_id = parent2.json()["id"]

    linked = v1_client.post(
        f"{STUDENTS}/{student_id}/guardians",
        headers=headers,
        json={"parent_id": p2_id, "relationship": "Mother", "is_primary": True},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["guardians"][0]["parent_id"] == p2_id
    assert linked.json()["guardians"][0]["is_primary"] is True

    # Cannot remove last remaining after unlinking one.
    unlink = v1_client.delete(
        f"{STUDENTS}/{student_id}/guardians/{parent_id}",
        headers=headers,
    )
    assert unlink.status_code == 200, unlink.text

    only = v1_client.delete(
        f"{STUDENTS}/{student_id}/guardians/{p2_id}",
        headers=headers,
    )
    assert only.status_code == 409, only.text

    # Parent profile shows children.
    parent_profile = v1_client.get(f"{PARENTS}/{p2_id}", headers=headers)
    assert parent_profile.status_code == 200, parent_profile.text
    kids = parent_profile.json()["children"]
    assert any(c["student_id"] == student_id for c in kids)

    # Status deactivates user.
    status = v1_client.patch(
        f"{STUDENTS}/{student_id}/status",
        headers=headers,
        json={"status": 0},
    )
    assert status.status_code == 200, status.text
    assert status.json()["status"] == 0
    user = v1_db.get(User, row.user_id)
    assert user is not None and user.status == 0


def test_school_id_forbidden_on_student_body(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "people-sa2@example.com")
    school_id = _school(v1_client, sa, "PPL2")
    headers = _school_admin(v1_client, sa, school_id, "people-admin2@example.com")
    bad = v1_client.post(
        STUDENTS,
        headers=headers,
        json={
            "school_id": 999,
            "first_name": "X",
            "last_name": "Y",
            "dob": "2015-01-01",
            "gender": "male",
            "admission_date": "2026-01-01",
            "session_year_id": 1,
            "class_section_id": 1,
            "current_address": "Addr",
            "guardian": {
                "first_name": "P",
                "last_name": "Q",
                "email": "pq@example.com",
                "mobile": "9000000000",
                "relationship": "Father",
            },
        },
    )
    assert bad.status_code == 422


def test_omitted_student_email_returns_null_and_stores_placeholder(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "people-email-sa@example.com")
    school_id = _school(v1_client, sa, "PPLE")
    headers = _school_admin(v1_client, sa, school_id, "people-email-admin@example.com")
    session_year_id, class_section_id = _session_and_section(v1_client, headers, v1_db)

    created = v1_client.post(
        STUDENTS,
        headers=headers,
        json=_student_body(
            session_year_id,
            class_section_id,
            guardian_email="email-g@example.com",
            guardian_mobile="9830111201",
        ),
    )
    assert created.status_code == 201, created.text
    profile = created.json()
    assert profile["email"] is None
    student = v1_db.get(Student, profile["id"])
    assert student is not None
    user = v1_db.get(User, student.user_id)
    assert user is not None
    assert user.email
    assert ".eschool.internal" in user.email or user.email.endswith(".internal")


def test_cross_school_student_isolation(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "people-xsa@example.com")
    school_a = _school(v1_client, sa, "PPLA")
    school_b = _school(v1_client, sa, "PPLB")
    admin_a = _school_admin(v1_client, sa, school_a, "people-xa@example.com")
    admin_b = _school_admin(v1_client, sa, school_b, "people-xb@example.com")
    sy_a, cs_a = _session_and_section(v1_client, admin_a, v1_db)

    created = v1_client.post(
        STUDENTS,
        headers=admin_a,
        json=_student_body(
            sy_a,
            cs_a,
            guardian_email="xa-g@example.com",
            guardian_mobile="9830111301",
        ),
    )
    assert created.status_code == 201, created.text
    student_id = created.json()["id"]
    parent_id = created.json()["guardians"][0]["parent_id"]

    assert v1_client.get(f"{STUDENTS}/{student_id}", headers=admin_b).status_code == 404
    assert v1_client.get(f"{PARENTS}/{parent_id}", headers=admin_b).status_code == 404
    assert (
        v1_client.patch(
            f"{STUDENTS}/{student_id}/status",
            headers=admin_b,
            json={"status": 0},
        ).status_code
        == 404
    )


def test_duplicate_admission_and_roll_numbers(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "people-dup-sa@example.com")
    school_id = _school(v1_client, sa, "PPLD")
    headers = _school_admin(v1_client, sa, school_id, "people-dup-admin@example.com")
    session_year_id, class_section_id = _session_and_section(v1_client, headers, v1_db)

    first = v1_client.post(
        STUDENTS,
        headers=headers,
        json=_student_body(
            session_year_id,
            class_section_id,
            admission_no="ADM-DUP-1",
            roll_number=7,
            guardian_email="dup-g1@example.com",
            guardian_mobile="9830111401",
        ),
    )
    assert first.status_code == 201, first.text

    dup_adm = v1_client.post(
        STUDENTS,
        headers=headers,
        json=_student_body(
            session_year_id,
            class_section_id,
            first_name="Other",
            admission_no="ADM-DUP-1",
            roll_number=8,
            guardian_email="dup-g2@example.com",
            guardian_mobile="9830111402",
        ),
    )
    assert dup_adm.status_code == 409, dup_adm.text

    dup_roll = v1_client.post(
        STUDENTS,
        headers=headers,
        json=_student_body(
            session_year_id,
            class_section_id,
            first_name="Third",
            admission_no="ADM-DUP-2",
            roll_number=7,
            guardian_email="dup-g3@example.com",
            guardian_mobile="9830111403",
        ),
    )
    assert dup_roll.status_code == 409, dup_roll.text


def test_maximum_four_guardians(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "people-g4-sa@example.com")
    school_id = _school(v1_client, sa, "PPLG")
    headers = _school_admin(v1_client, sa, school_id, "people-g4-admin@example.com")
    session_year_id, class_section_id = _session_and_section(v1_client, headers, v1_db)

    created = v1_client.post(
        STUDENTS,
        headers=headers,
        json=_student_body(
            session_year_id,
            class_section_id,
            guardian_email="g4-0@example.com",
            guardian_mobile="9830111500",
        ),
    )
    assert created.status_code == 201, created.text
    student_id = created.json()["id"]

    for i in range(1, 4):
        parent = v1_client.post(
            PARENTS,
            headers=headers,
            json={
                "first_name": f"G{i}",
                "last_name": "Extra",
                "email": f"g4-{i}@example.com",
                "mobile": f"983011150{i}",
                "status": 1,
                "students": [],
            },
        )
        assert parent.status_code == 201, parent.text
        linked = v1_client.post(
            f"{STUDENTS}/{student_id}/guardians",
            headers=headers,
            json={
                "parent_id": parent.json()["id"],
                "relationship": "Guardian",
                "is_primary": False,
            },
        )
        assert linked.status_code == 200, linked.text

    assert len(v1_client.get(f"{STUDENTS}/{student_id}", headers=headers).json()["guardians"]) == 4

    overflow_parent = v1_client.post(
        PARENTS,
        headers=headers,
        json={
            "first_name": "Too",
            "last_name": "Many",
            "email": "g4-overflow@example.com",
            "mobile": "9830111599",
            "status": 1,
            "students": [],
        },
    )
    assert overflow_parent.status_code == 201, overflow_parent.text
    blocked = v1_client.post(
        f"{STUDENTS}/{student_id}/guardians",
        headers=headers,
        json={
            "parent_id": overflow_parent.json()["id"],
            "relationship": "Guardian",
            "is_primary": False,
        },
    )
    assert blocked.status_code == 409, blocked.text


def test_student_document_list_mime_and_size_limits(
    v1_client, v1_db, monkeypatch, tmp_path
):
    _enable_storage(monkeypatch, tmp_path)
    sa = _super(v1_client, v1_db, "people-doc-sa@example.com")
    school_id = _school(v1_client, sa, "PPLDOC")
    headers = _school_admin(v1_client, sa, school_id, "people-doc-admin@example.com")
    session_year_id, class_section_id = _session_and_section(v1_client, headers, v1_db)

    created = v1_client.post(
        STUDENTS,
        headers=headers,
        json=_student_body(
            session_year_id,
            class_section_id,
            guardian_email="doc-g@example.com",
            guardian_mobile="9830111601",
        ),
    )
    assert created.status_code == 201, created.text
    student_id = created.json()["id"]

    bad_mime = v1_client.post(
        f"{STUDENTS}/{student_id}/documents",
        headers=headers,
        files={"file": ("notes.txt", b"plain-text-not-allowed", "text/plain")},
        data={"category": "other", "title": "Notes"},
    )
    assert bad_mime.status_code == 415, bad_mime.text

    too_big_image = v1_client.post(
        f"{STUDENTS}/{student_id}/documents",
        headers=headers,
        files={
            "file": (
                "big.png",
                PNG + b"\x00" * (2 * 1024 * 1024 + 1),
                "image/png",
            )
        },
        data={"category": "other", "title": "Big"},
    )
    assert too_big_image.status_code == 413, too_big_image.text

    too_big_pdf = v1_client.post(
        f"{STUDENTS}/{student_id}/documents",
        headers=headers,
        files={
            "file": (
                "big.pdf",
                PDF + b"\x00" * (5 * 1024 * 1024 + 1),
                "application/pdf",
            )
        },
        data={"category": "other", "title": "BigPdf"},
    )
    assert too_big_pdf.status_code == 413, too_big_pdf.text

    uploaded = v1_client.post(
        f"{STUDENTS}/{student_id}/documents",
        headers=headers,
        files={"file": ("id.pdf", PDF, "application/pdf")},
        data={"category": "id_proof", "title": "ID Card"},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["title"] == "ID Card"
    assert "storage_key" not in uploaded.json()

    listed = v1_client.get(f"{STUDENTS}/{student_id}/documents", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == uploaded.json()["id"]


def test_deactivated_parent_login_rejected(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "people-deact-sa@example.com")
    school_code = "PPLDE"
    school_id = _school(v1_client, sa, school_code)
    headers = _school_admin(v1_client, sa, school_id, "people-deact-admin@example.com")
    session_year_id, class_section_id = _session_and_section(v1_client, headers, v1_db)

    guardian_email = "deact-parent@example.com"
    created = v1_client.post(
        STUDENTS,
        headers=headers,
        json=_student_body(
            session_year_id,
            class_section_id,
            guardian_email=guardian_email,
            guardian_mobile="9830111701",
        ),
    )
    assert created.status_code == 201, created.text
    parent_id = created.json()["guardians"][0]["parent_id"]

    parent = v1_db.get(User, parent_id)
    assert parent is not None
    parent.password = hash_password("parentpass1")
    v1_db.commit()

    ok = v1_client.post(
        "/api/parent/login",
        data={
            "email": guardian_email,
            "password": "parentpass1",
            "school_code": school_code,
        },
    )
    assert ok.json()["error"] is False, ok.text
    assert ok.json().get("token")

    deactivated = v1_client.patch(
        f"{PARENTS}/{parent_id}/status",
        headers=headers,
        json={"status": 0},
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["status"] == 0

    denied = v1_client.post(
        "/api/parent/login",
        data={
            "email": guardian_email,
            "password": "parentpass1",
            "school_code": school_code,
        },
    )
    body = denied.json()
    assert body["error"] is True
    assert body["code"] == 116
    assert "deactivated" in body["message"].lower()
    assert "token" not in body or not body.get("token")
