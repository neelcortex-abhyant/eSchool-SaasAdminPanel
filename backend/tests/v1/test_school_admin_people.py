"""School Admin people APIs: isolation, conflicts, guardian rules, uploads.

Contract: docs/PEOPLE_API_CONTRACT.md.
School B's admin must never read or reference school A's records.
"""

from __future__ import annotations

import io
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.tables import StudentGuardian, User as LegacyUser
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User

ACAD = "/api/v1/school-admin/academics"
SA = "/api/v1/school-admin"


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ok(res, status: int = 200):
    assert res.status_code == status, res.text
    return res.json()


def _field(res, *loc: str | int) -> str:
    """The 422 message for one body field."""
    assert res.status_code == 422, res.text
    for item in res.json()["detail"]:
        if item["loc"] == ["body", *loc]:
            return item["msg"]
    raise AssertionError(f"no error for {loc}: {res.text}")


def _super_admin(client, db) -> dict[str, str]:
    email = "people-sa@eschool.com"
    _ok(client.post("/api/v1/auth/signup", json={"email": email, "password": "secret123", "first_name": "S", "last_name": "A"}), 201)
    user = db.scalar(select(User).where(User.email == email))
    user.role = ROLE_SUPER_ADMIN
    db.commit()
    return _h(_ok(client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"}))["access_token"])


def _school_admin(client, sa, code: str) -> dict[str, str]:
    school = _ok(
        client.post(
            "/api/v1/super-admin/schools",
            headers=sa,
            json={"name": f"School {code}", "address": "1", "support_phone": "1", "support_email": f"{code.lower()}@eschool.com", "code": code},
        ),
        201,
    )
    email = f"admin@{code.lower()}.edu"
    _ok(
        client.post(
            f"/api/v1/super-admin/schools/{school['id']}/admins",
            headers=sa,
            json={"email": email, "password": "adminpass1", "first_name": "A", "last_name": "B"},
        ),
        201,
    )
    token = _ok(client.post("/api/v1/auth/login", json={"email": email, "password": "adminpass1"}))["access_token"]
    return {"headers": _h(token), "school_id": school["id"], "code": code}


def _structure(client, headers) -> SimpleNamespace:
    """Medium, session, class and section through the existing academics routes."""
    medium = _ok(client.post(f"{ACAD}/mediums", headers=headers, json={"name": "English"}), 201)
    session = _ok(
        client.post(f"{ACAD}/sessions", headers=headers, json={"name": "2026-27", "start_date": "2026-04-01", "end_date": "2027-03-31", "default": 1}),
        201,
    )
    school_class = _ok(client.post(f"{ACAD}/classes", headers=headers, json={"name": "Class 5", "medium_id": medium["id"]}), 201)
    section_row = _ok(client.post(f"{ACAD}/sections", headers=headers, json={"name": "A"}), 201)
    section = _ok(
        client.post(f"{ACAD}/class-sections", headers=headers, json={"class_id": school_class["id"], "section_id": section_row["id"], "medium_id": medium["id"]}),
        201,
    )
    return SimpleNamespace(medium=medium, session=session, school_class=school_class, section=section)


def _employee(client, headers, kind: str, email: str, **extra) -> dict:
    body = {
        "first_name": "Rahul", "last_name": "Mehta", "email": email, "mobile": "9710205406",
        "department": "Mathematics", "designation": "Teacher", "joining_date": "2016-06-01",
        "employment_type": "Permanent", "qualification": "M.Sc", "status": 1,
    }
    body.update(extra)
    return _ok(client.post(f"{SA}/{kind}", headers=headers, json=body), 201)


def _student_body(world, **extra) -> dict:
    body = {
        "first_name": "Riya", "last_name": "Sharma", "dob": "2016-12-05", "gender": "female",
        "admission_date": "2026-10-21", "session_year_id": world.session["id"], "class_section_id": world.section["id"],
        "roll_number": None, "email": None, "mobile": None, "current_address": "12 Lake View Road", "status": 1,
        "guardian": {"first_name": "Rajesh", "last_name": "Sharma", "email": "rajesh@example.com", "mobile": "98301 11137", "relationship": "Father"},
    }
    body.update(extra)
    return body


@pytest.fixture()
def world(v1_client, v1_db, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("FILE_STORAGE_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    sa = _super_admin(v1_client, v1_db)
    a = _school_admin(v1_client, sa, "PEOA01")
    b = _school_admin(v1_client, sa, "PEOB01")
    a_world = _structure(v1_client, a["headers"])
    b_world = _structure(v1_client, b["headers"])
    return SimpleNamespace(client=v1_client, db=v1_db, a=a, b=b, A=a_world, B=b_world, ha=a["headers"], hb=b["headers"])


def test_student_admission_conflicts_and_isolation(world):
    c, ha, A = world.client, world.ha, world.A
    student = _ok(c.post(f"{SA}/students", headers=ha, json=_student_body(A)), 201)
    assert student["admission_no"] == "ADM20260001"
    assert student["class_name"] == "Class 5" and student["section_name"] == "A" and student["session_name"] == "2026-27"
    assert student["guardian_name"] == "Rajesh Sharma" and student["guardians"][0]["is_primary"] is True
    assert student["email"] is None and student["documents"] == []

    second = _ok(c.post(f"{SA}/students", headers=ha, json=_student_body(A, first_name="Aarav", roll_number=3, guardian={"parent_id": student["guardians"][0]["parent_id"], "relationship": "Father"})), 201)
    assert second["admission_no"] == "ADM20260002"
    res = c.post(f"{SA}/students", headers=ha, json=_student_body(A, admission_no="ADM20260001", guardian={"parent_id": student["guardians"][0]["parent_id"], "relationship": "Father"}))
    assert res.status_code == 409 and res.json()["detail"] == "Admission number ADM20260001 is already used by Riya Sharma"
    res = c.post(f"{SA}/students", headers=ha, json=_student_body(A, roll_number=3, guardian={"parent_id": student["guardians"][0]["parent_id"], "relationship": "Mother"}))
    assert res.status_code == 409 and "Roll number 3 is already used by Aarav Sharma" in res.json()["detail"]
    res = c.post(f"{SA}/students", headers=ha, json=_student_body(A, guardian={"first_name": "R", "last_name": "S", "email": "RAJESH@example.com", "mobile": "1112223334", "relationship": "Father"}))
    assert res.status_code == 409 and res.json()["detail"].startswith("Rajesh Sharma is already registered")
    res = c.post(f"{SA}/students", headers=ha, json=_student_body(A, guardian={"first_name": "R", "last_name": "S", "email": "new@example.com", "mobile": "98301-11137", "relationship": "Father"}))
    assert res.status_code == 409  # same mobile digits

    # Validation keeps nested paths, so the guardian email error isn't shown on the student email field.
    res = c.post(f"{SA}/students", headers=ha, json=_student_body(A, dob=(date.today() + timedelta(days=1)).isoformat(), gender="x", guardian={"first_name": "", "last_name": "S", "email": "bad", "mobile": "12", "relationship": "Uncle"}))
    assert _field(res, "dob") == "Date of birth can't be in the future"
    assert _field(res, "gender") == "Choose a gender"
    assert _field(res, "guardian", "email") == "Enter a valid email address"
    assert _field(res, "guardian", "mobile")
    assert _field(res, "guardian", "first_name") == "First name is required"
    assert _field(res, "guardian", "relationship") == "Choose the relationship"
    assert c.post(f"{SA}/students", headers=ha, json={**_student_body(A), "school_id": world.b["school_id"]}).status_code == 422

    # School B: 404 on A's student, 422 when referencing A's ids.
    assert c.get(f"{SA}/students/{student['id']}", headers=world.hb).status_code == 404
    assert c.patch(f"{SA}/students/{student['id']}/status", headers=world.hb, json={"status": 0}).status_code == 404
    res = c.post(f"{SA}/students", headers=world.hb, json=_student_body(A, guardian={"parent_id": student["guardians"][0]["parent_id"], "relationship": "Father"}))
    assert _field(res, "session_year_id") and _field(res, "class_section_id") and _field(res, "guardian", "parent_id")
    assert _ok(c.get(f"{SA}/students", headers=world.hb))["total"] == 0

    # Filters and sorting
    listing = _ok(c.get(f"{SA}/students", headers=ha, params={"sort": "admission_no", "order": "desc"}))
    assert [row["admission_no"] for row in listing["items"]] == ["ADM20260002", "ADM20260001"]
    assert _ok(c.get(f"{SA}/students", headers=ha, params={"q": "aarav"}))["total"] == 1
    assert _ok(c.get(f"{SA}/students", headers=ha, params={"class_id": A.school_class["id"]}))["total"] == 2
    assert _ok(c.get(f"{SA}/students", headers=ha, params={"parent_id": student["guardians"][0]["parent_id"]}))["total"] == 2

    # Update needs admission_no.
    body = {k: v for k, v in _student_body(A, first_name="Riya K").items() if k != "guardian"}
    assert _field(c.patch(f"{SA}/students/{student['id']}", headers=ha, json=body), "admission_no") == "Admission number is required"
    updated = _ok(c.patch(f"{SA}/students/{student['id']}", headers=ha, json={**body, "admission_no": "ADM20260001", "email": "riya@example.com"}))
    assert updated["name"] == "Riya K Sharma" and updated["email"] == "riya@example.com"


def test_student_status_blocks_sign_in(world):
    c, ha = world.client, world.ha
    from app.core.security import hash_password

    student = _ok(c.post(f"{SA}/students", headers=ha, json=_student_body(world.A)), 201)
    teacher = _employee(c, ha, "teachers", "login@a.edu")
    db = world.db
    for row in db.scalars(select(LegacyUser).where(LegacyUser.school_id == world.a["school_id"])):
        row.password = hash_password("secret1")
    db.commit()
    login = {"gr_number": student["admission_no"], "password": "secret1", "school_code": "PEOA01"}
    assert c.post("/api/student/login", data=login).json()["error"] is False
    teacher_login = {"email": "login@a.edu", "password": "secret1", "school_code": "PEOA01"}
    assert c.post("/api/teacher/login", data=teacher_login).json()["error"] is False

    assert _ok(c.patch(f"{SA}/students/{student['id']}/status", headers=ha, json={"status": 0}))["status"] == 0
    assert c.post("/api/student/login", data=login).json()["error"] is True
    _ok(c.patch(f"{SA}/teachers/{teacher['id']}/status", headers=ha, json={"status": 0}))
    assert c.post("/api/teacher/login", data=teacher_login).json()["error"] is True
    parent_id = student["guardians"][0]["parent_id"]
    assert _ok(c.patch(f"{SA}/parents/{parent_id}/status", headers=ha, json={"status": 0}))["status"] == 0
    assert c.post("/api/parent/login", data={"email": "rajesh@example.com", "password": "secret1", "school_code": "PEOA01"}).json()["error"] is True


def test_guardian_link_rules(world):
    c, ha = world.client, world.ha
    student = _ok(c.post(f"{SA}/students", headers=ha, json=_student_body(world.A)), 201)
    first_parent = student["guardians"][0]["parent_id"]
    parents = [
        _ok(c.post(f"{SA}/parents", headers=ha, json={"first_name": f"P{i}", "last_name": "X", "email": f"p{i}@example.com", "mobile": f"90000000{i}0", "status": 1, "students": []}), 201)
        for i in range(4)
    ]
    assert c.post(f"{SA}/students/{student['id']}/guardians", headers=ha, json={"parent_id": first_parent, "relationship": "Father"}).status_code == 409
    profile = _ok(c.post(f"{SA}/students/{student['id']}/guardians", headers=ha, json={"parent_id": parents[0]["id"], "relationship": "Mother", "is_primary": True}))
    primary = [g for g in profile["guardians"] if g["is_primary"]]
    assert [g["parent_id"] for g in primary] == [parents[0]["id"]] and profile["guardian_name"] == "P0 X"
    for parent in parents[1:3]:
        _ok(c.post(f"{SA}/students/{student['id']}/guardians", headers=ha, json={"parent_id": parent["id"], "relationship": "Other"}))
    full = c.post(f"{SA}/students/{student['id']}/guardians", headers=ha, json={"parent_id": parents[3]["id"], "relationship": "Other"})
    assert full.status_code == 409 and "already has 4 guardians" in full.json()["detail"]
    b_parent = _ok(c.post(f"{SA}/parents", headers=world.hb, json={"first_name": "B", "last_name": "P", "email": "b@example.com", "mobile": "9111111111", "status": 1, "students": []}), 201)
    assert _field(c.post(f"{SA}/students/{student['id']}/guardians", headers=ha, json={"parent_id": b_parent["id"], "relationship": "Other"}), "parent_id")

    # Removing the primary promotes another; the last one can't be removed.
    profile = _ok(c.delete(f"{SA}/students/{student['id']}/guardians/{parents[0]['id']}", headers=ha))
    assert sum(g["is_primary"] for g in profile["guardians"]) == 1
    remaining = [g["parent_id"] for g in profile["guardians"]]
    for parent_id in remaining[:-1]:
        profile = _ok(c.delete(f"{SA}/students/{student['id']}/guardians/{parent_id}", headers=ha))
        assert sum(g["is_primary"] for g in profile["guardians"]) == 1
    last = c.delete(f"{SA}/students/{student['id']}/guardians/{remaining[-1]}", headers=ha)
    assert last.status_code == 409
    assert last.json()["detail"] == "Riya Sharma must keep at least one parent or guardian. Link another one first."
    assert c.delete(f"{SA}/students/{student['id']}/guardians/{remaining[-1]}", headers=world.hb).status_code == 404
    links = world.db.scalars(select(StudentGuardian).where(StudentGuardian.student_id == student["id"])).all()
    assert len(links) == 1 and links[0].is_primary


def test_parents_filters_conflicts_and_children(world):
    c, ha = world.client, world.ha
    student = _ok(c.post(f"{SA}/students", headers=ha, json=_student_body(world.A)), 201)
    _employee(c, ha, "teachers", "teacher@a.edu")
    by_email = _ok(c.get(f"{SA}/parents", headers=ha, params={"email": "RAJESH@example.com"}))
    assert by_email["total"] == 1 and by_email["items"][0]["children"][0]["student_id"] == student["id"]
    assert _ok(c.get(f"{SA}/parents", headers=ha, params={"mobile": "+91-9830111137"}))["total"] == 0  # digits must match exactly
    assert _ok(c.get(f"{SA}/parents", headers=ha, params={"mobile": "9830 111 137"}))["total"] == 1

    base = {"first_name": "Sita", "last_name": "Rao", "email": "sita@example.com", "mobile": "9000000001", "status": 1}
    res = c.post(f"{SA}/parents", headers=ha, json={**base, "mobile": "98301-11137", "students": []})
    assert res.status_code == 409 and res.json()["detail"].startswith("Rajesh Sharma already has the phone number")
    res = c.post(f"{SA}/parents", headers=ha, json={**base, "email": "teacher@a.edu", "students": []})
    assert res.status_code == 409 and res.json()["detail"] == "teacher@a.edu is already used by a teacher or staff member in this school"
    b_student = _ok(c.post(f"{SA}/students", headers=world.hb, json=_student_body(world.B, guardian={"first_name": "Q", "last_name": "Q", "email": "q@example.com", "mobile": "9222222222", "relationship": "Father"})), 201)
    res = c.post(f"{SA}/parents", headers=ha, json={**base, "students": [{"student_id": b_student["id"], "relationship": "Mother"}]})
    assert _field(res, "students", 0, "student_id") == "Choose a student from this school"
    res = c.post(f"{SA}/parents", headers=ha, json={**base, "students": [{"student_id": student["id"], "relationship": "Mother"}] * 2})
    assert _field(res, "students") == "Each student can be linked once"

    sita = _ok(c.post(f"{SA}/parents", headers=ha, json={**base, "students": [{"student_id": student["id"], "relationship": "Mother"}]}), 201)
    assert sita["children"][0]["is_primary"] is False
    assert c.get(f"{SA}/parents/{sita['id']}", headers=world.hb).status_code == 404
    teacher_id = _ok(c.get(f"{SA}/teachers", headers=ha))["items"][0]["id"]
    assert c.get(f"{SA}/parents/{teacher_id}", headers=ha).status_code == 404
    updated = _ok(c.patch(f"{SA}/parents/{sita['id']}", headers=ha, json={**base, "occupation": "Doctor"}))
    assert updated["occupation"] == "Doctor" and len(updated["children"]) == 1


# ---------- teachers and staff ----------


def test_teachers_and_staff(world):
    c, ha = world.client, world.ha
    t1 = _employee(c, ha, "teachers", "t1@a.edu")
    t2 = _employee(c, ha, "teachers", "t2@a.edu", department="Science")
    s1 = _employee(c, ha, "staff", "s1@a.edu", qualification=None, department="Office", designation="Clerk")
    assert (t1["employee_code"], t2["employee_code"], s1["employee_code"]) == ("TCH0001", "TCH0002", "STF0001")
    assert _employee(c, world.hb, "teachers", "t1@b.edu")["employee_code"] == "TCH0001"  # codes are per school

    assert c.get(f"{SA}/staff/{t1['id']}", headers=ha).status_code == 404
    assert c.get(f"{SA}/teachers/{s1['id']}", headers=ha).status_code == 404
    assert c.get(f"{SA}/teachers/{t1['id']}", headers=world.hb).status_code == 404
    res = c.post(f"{SA}/teachers", headers=ha, json={"employee_code": "tch0001", "first_name": "X", "last_name": "Y", "email": "x@a.edu", "mobile": "9999999999", "department": "M", "designation": "T", "joining_date": "2020-01-01", "employment_type": "Contract", "qualification": "B.Ed", "status": 1})
    assert res.status_code == 409 and res.json()["detail"] == "Employee ID tch0001 is already used by Rahul Mehta"
    res = c.post(f"{SA}/staff", headers=ha, json={"first_name": "X", "last_name": "Y", "email": "T1@a.edu", "mobile": "9999999999", "department": "M", "designation": "T", "joining_date": "2020-01-01", "employment_type": "Contract", "status": 1})
    assert res.status_code == 409 and "already used by a teacher or staff member" in res.json()["detail"]
    res = c.post(f"{SA}/teachers", headers=ha, json={"first_name": "X", "last_name": "Y", "email": "z@a.edu", "mobile": "9999999999", "department": "M", "designation": "T", "joining_date": "2020-01-01", "employment_type": "Temp", "dob": (date.today() - timedelta(days=365 * 10)).isoformat(), "status": 1})
    assert _field(res, "qualification") == "Qualification is required for teachers"
    assert _field(res, "employment_type") == "Choose the employment type"
    assert _field(res, "dob") == "Employees must be at least 18 years old"

    assert _ok(c.get(f"{SA}/teachers/departments", headers=ha)) == {"items": ["Mathematics", "Science"]}
    assert _ok(c.get(f"{SA}/staff/departments", headers=ha)) == {"items": ["Office"]}
    assert _ok(c.get(f"{SA}/teachers", headers=ha, params={"department": "science"}))["total"] == 1
    assert _ok(c.get(f"{SA}/teachers", headers=ha, params={"q": "TCH0002"}))["total"] == 1
    body = {k: t1[k] for k in ("first_name", "last_name", "email", "mobile", "department", "designation", "joining_date", "employment_type")}
    assert _field(c.patch(f"{SA}/teachers/{t1['id']}", headers=ha, json={**body, "qualification": "M.Sc", "status": 1}), "employee_code") == "Employee ID is required"
    updated = _ok(c.patch(f"{SA}/teachers/{t1['id']}", headers=ha, json={**body, "employee_code": "TCH0100", "designation": "HOD", "qualification": "PhD", "status": 1}))
    assert updated["employee_code"] == "TCH0100" and updated["designation"] == "HOD" and updated["qualification"] == "PhD"


# ---------- uploads ----------


def _png(size=(4, 4)) -> bytes:
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", size, (200, 10, 10)).save(out, format="PNG")
    return out.getvalue()


PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def test_uploads_are_checked_signed_and_isolated(world):
    c, ha = world.client, world.ha
    student = _ok(c.post(f"{SA}/students", headers=ha, json=_student_body(world.A)), 201)
    url = f"{SA}/students/{student['id']}"

    fake = c.post(f"{url}/documents", headers=ha, files={"file": ("report.pdf", b"<html><script>alert(1)</script>", "application/pdf")}, data={"title": "Report"})
    assert fake.status_code == 415 and fake.json()["detail"] == "Only PDF, JPG and PNG files are allowed"
    big = c.post(f"{url}/documents", headers=ha, files={"file": ("big.pdf", PDF + b"0" * (5 * 1024 * 1024), "application/pdf")})
    assert big.status_code == 413
    webp_doc = c.post(f"{url}/documents", headers=ha, files={"file": ("x.webp", b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp")})
    assert webp_doc.status_code == 415

    doc = _ok(c.post(f"{url}/documents", headers=ha, files={"file": ("../../birth.pdf", PDF, "text/plain")}, data={"title": "Birth certificate"}), 201)
    assert doc["content_type"] == "application/pdf" and doc["file_name"] == "birth.pdf" and doc["size"] == len(PDF)
    download = c.get(doc["url"])
    assert download.status_code == 200 and download.content == PDF
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["content-type"] == "application/pdf"
    assert c.get(doc["url"] + "x").status_code == 404
    assert _ok(c.get(url, headers=ha))["documents"][0]["id"] == doc["id"]

    photo = c.post(f"{url}/photo", headers=ha, files={"file": ("me.pdf", PDF, "image/png")})
    assert photo.status_code == 415
    photo = _ok(c.post(f"{url}/photo", headers=ha, files={"file": ("me.png", _png(), "application/pdf")}))
    image = c.get(photo["photo_url"])
    assert image.status_code == 200 and image.headers["content-type"] == "image/png" and image.content.startswith(b"\x89PNG")
    assert _ok(c.get(f"{SA}/students", headers=ha))["items"][0]["photo_url"]

    # School B can't upload to, list or delete A's files.
    assert c.post(f"{url}/documents", headers=world.hb, files={"file": ("a.pdf", PDF, "application/pdf")}).status_code == 404
    assert c.delete(f"{url}/documents/{doc['id']}", headers=world.hb).status_code == 404
    b_teacher = _employee(c, world.hb, "teachers", "t@b.edu")
    assert c.delete(f"{SA}/teachers/{b_teacher['id']}/documents/{doc['id']}", headers=world.hb).status_code == 404

    for i in range(9):
        _ok(c.post(f"{url}/documents", headers=ha, files={"file": (f"d{i}.pdf", PDF, "application/pdf")}), 201)
    eleventh = c.post(f"{url}/documents", headers=ha, files={"file": ("d.pdf", PDF, "application/pdf")})
    assert eleventh.status_code == 409
    assert _ok(c.delete(f"{url}/documents/{doc['id']}", headers=ha)) == {"deleted": True}
    assert c.get(doc["url"]).status_code == 404  # the stored file is gone too

    teacher = _employee(c, ha, "teachers", "t@a.edu")
    tdoc = _ok(c.post(f"{SA}/teachers/{teacher['id']}/documents", headers=ha, files={"file": ("cv.png", _png(), "image/png")}, data={"title": "CV"}), 201)
    assert _ok(c.get(f"{SA}/teachers/{teacher['id']}", headers=ha))["documents"][0]["id"] == tdoc["id"]
    assert c.delete(f"{SA}/staff/{teacher['id']}/documents/{tdoc['id']}", headers=ha).status_code == 404
