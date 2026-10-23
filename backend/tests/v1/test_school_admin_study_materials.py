"""Module 4: study materials upload, list, download, isolation."""

from __future__ import annotations

from pathlib import Path

from fastapi.routing import APIRoute
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.main import app
from app.models.tables import (
    USER_MODEL,
    ModelHasRole,
    Role,
    School,
    Student,
    StudyMaterial,
    User,
)
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User as V1User
from app.services.mobile_auth import issue_token
from app.services.v1.school_academics import _now

MATERIALS = "/api/v1/school-admin/study-materials"
UPLOAD = f"{MATERIALS}/upload"
TEACHERS = "/api/v1/school-admin/teachers"
ASSIGNMENTS = "/api/v1/school-admin/teacher-assignments"
CLASSES = "/api/v1/school-admin/classes"
SECTIONS = "/api/v1/school-admin/sections"
SUBJECTS = "/api/v1/school-admin/subjects"
ACADEMICS = "/api/v1/school-admin/academics"
STUDENT_SM = "/api/student/study-materials"

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)
# Minimal OLE DOC header
DOC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64


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


def _seed(client, headers, *, email_prefix: str = "sm"):
    medium = client.post(f"{ACADEMICS}/mediums", headers=headers, json={"name": "English"})
    assert medium.status_code == 201
    medium_id = medium.json()["id"]
    klass = client.post(CLASSES, headers=headers, json={"name": "Grade 1", "medium_id": medium_id})
    assert klass.status_code == 201
    class_id = klass.json()["id"]
    section = client.post(SECTIONS, headers=headers, json={"name": "A", "class_id": class_id})
    assert section.status_code == 201
    class_section_id = section.json()["class_section_id"]
    subject = client.post(
        SUBJECTS, headers=headers, json={"name": "Science", "code": "SCI", "medium_id": medium_id}
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
            "email": f"{email_prefix}-t1@eschool.com",
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
    return {
        "class_section_id": class_section_id,
        "subject_id": subject_id,
        "session_year_id": session.json()["id"],
        "teacher_user_id": teacher.json()["id"],
        "teacher_user_id_2": teacher2.json()["id"],
    }


def _make_student(v1_db, school_id: int, ids: dict, *, email: str, admission_no: str):
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
    student_user = User(
        first_name="S",
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
        admission_date=date(2026, 4, 1),
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
    return student, issue_token(v1_db, student_user)


def _student_headers(code: str, token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "school-code": code}


def test_openapi_registers_study_material_routes():
    paths = app.openapi()["paths"]
    for path in (
        MATERIALS,
        f"{MATERIALS}/upload",
        f"{MATERIALS}/{{material_id}}",
        f"{MATERIALS}/{{material_id}}/download",
        f"{MATERIALS}/{{material_id}}/file",
        STUDENT_SM,
        f"{STUDENT_SM}/{{material_id}}",
        f"{STUDENT_SM}/{{material_id}}/download",
    ):
        assert path in paths, path
    assert "/api/student/assignments" in {
        r.path for r in app.routes if isinstance(r, APIRoute)
    }


def test_video_link_and_reference_crud_filters_soft_delete(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "sm-sa@eschool.com")
    school_id = _school(v1_client, sa, "SM01")
    admin = _school_admin(v1_client, sa, school_id, "sm-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="sm1")

    # JSON file type rejected
    assert (
        v1_client.post(
            MATERIALS,
            headers=admin,
            json={
                **ids,
                "resource_type": "file",
                "title": "Nope",
            },
        ).status_code
        == 422
    )

    created = v1_client.post(
        MATERIALS,
        headers=admin,
        json={
            "session_year_id": ids["session_year_id"],
            "class_section_id": ids["class_section_id"],
            "subject_id": ids["subject_id"],
            "teacher_user_id": ids["teacher_user_id"],
            "resource_type": "video_link",
            "title": "Intro video",
            "chapter": "Ch1",
            "topic": "Basics",
            "external_url": "https://www.youtube.com/watch?v=abc123",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["resource_type"] == "video_link"
    assert body["external_url"].startswith("https://")
    assert "storage_key" not in body
    mid = body["id"]

    # Bad URLs
    for url in (
        "http://example.com/x",
        "https://localhost/x",
        "https://127.0.0.1/x",
        "javascript:alert(1)",
        "file:///etc/passwd",
    ):
        bad = v1_client.post(
            MATERIALS,
            headers=admin,
            json={
                "session_year_id": ids["session_year_id"],
                "class_section_id": ids["class_section_id"],
                "subject_id": ids["subject_id"],
                "teacher_user_id": ids["teacher_user_id"],
                "resource_type": "document_reference",
                "title": "Bad",
                "external_url": url,
            },
        )
        assert bad.status_code == 422, url

    ref = v1_client.post(
        MATERIALS,
        headers=admin,
        json={
            "session_year_id": ids["session_year_id"],
            "class_section_id": ids["class_section_id"],
            "subject_id": ids["subject_id"],
            "teacher_user_id": ids["teacher_user_id"],
            "resource_type": "document_reference",
            "title": "External worksheet",
            "chapter": "Ch1",
            "external_url": "https://docs.example.com/worksheet.pdf",
        },
    )
    assert ref.status_code == 201

    # Unassigned teacher
    assert (
        v1_client.post(
            MATERIALS,
            headers=admin,
            json={
                "session_year_id": ids["session_year_id"],
                "class_section_id": ids["class_section_id"],
                "subject_id": ids["subject_id"],
                "teacher_user_id": ids["teacher_user_id_2"],
                "resource_type": "video_link",
                "title": "X",
                "external_url": "https://www.youtube.com/watch?v=x",
            },
        ).status_code
        == 422
    )

    listed = v1_client.get(
        MATERIALS, headers=admin, params={"chapter": "Ch1", "resource_type": "video_link", "q": "Intro"}
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    patched = v1_client.patch(
        f"{MATERIALS}/{mid}", headers=admin, json={"title": "Updated video", "topic": "Advanced"}
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Updated video"
    assert patched.json()["topic"] == "Advanced"

    # Client cannot set storage_key
    assert (
        v1_client.patch(
            f"{MATERIALS}/{mid}",
            headers=admin,
            json={"storage_key": "evil"},
        ).status_code
        == 422
    )

    deleted = v1_client.delete(f"{MATERIALS}/{mid}", headers=admin)
    assert deleted.status_code == 200
    assert v1_client.get(f"{MATERIALS}/{mid}", headers=admin).status_code == 404
    assert v1_db.get(StudyMaterial, mid).deleted_at is not None


def test_file_upload_download_requires_storage_and_rejects_bad_types(
    v1_client, v1_db, monkeypatch, tmp_path: Path
):
    sa = _super(v1_client, v1_db, "sm-up-sa@eschool.com")
    school_id = _school(v1_client, sa, "SMUP")
    admin = _school_admin(v1_client, sa, school_id, "sm-up-admin@eschool.com")
    ids = _seed(v1_client, admin, email_prefix="smup")

    form = {
        "session_year_id": str(ids["session_year_id"]),
        "class_section_id": str(ids["class_section_id"]),
        "subject_id": str(ids["subject_id"]),
        "teacher_user_id": str(ids["teacher_user_id"]),
        "title": "Notes PDF",
        "chapter": "Ch2",
        "topic": "Photosynthesis",
    }

    monkeypatch.setenv("DOCUMENT_STORAGE_BACKEND", "none")
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", "")
    get_settings.cache_clear()
    denied = v1_client.post(
        UPLOAD, headers=admin, data=form, files={"file": ("n.pdf", PDF, "application/pdf")}
    )
    assert denied.status_code == 503, denied.text

    monkeypatch.setenv("DOCUMENT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()

    # Malformed content
    bad = v1_client.post(
        UPLOAD, headers=admin, data=form, files={"file": ("x.exe", b"MZ\x90\x00", "application/pdf")}
    )
    assert bad.status_code == 422

    # Oversized (patch limit low)
    monkeypatch.setenv("DOCUMENT_MAX_FILE_BYTES", "10")
    get_settings.cache_clear()
    big = v1_client.post(
        UPLOAD, headers=admin, data=form, files={"file": ("big.pdf", PDF, "application/pdf")}
    )
    assert big.status_code == 422
    monkeypatch.setenv("DOCUMENT_MAX_FILE_BYTES", "10485760")
    get_settings.cache_clear()

    uploaded = v1_client.post(
        UPLOAD, headers=admin, data=form, files={"file": ("notes.pdf", PDF, "application/pdf")}
    )
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    assert body["resource_type"] == "file"
    assert body["has_file"] is True
    assert body["content_type"] == "application/pdf"
    assert "storage_key" not in body
    mid = body["id"]

    # DOC magic
    doc_up = v1_client.post(
        UPLOAD,
        headers=admin,
        data={**form, "title": "Word notes"},
        files={"file": ("a.doc", DOC, "application/msword")},
    )
    assert doc_up.status_code == 201, doc_up.text

    png_up = v1_client.post(
        UPLOAD,
        headers=admin,
        data={**form, "title": "Diagram"},
        files={"file": ("d.png", PNG, "image/png")},
    )
    assert png_up.status_code == 201

    dl = v1_client.get(f"{MATERIALS}/{mid}/download", headers=admin)
    assert dl.status_code == 200
    assert dl.content.startswith(b"%PDF")
    assert dl.headers.get("x-content-type-options") == "nosniff"
    assert "attachment" in dl.headers.get("content-disposition", "")

    # Replace file
    replaced = v1_client.post(
        f"{MATERIALS}/{mid}/file",
        headers=admin,
        files={"file": ("notes2.pdf", PDF + b"\n", "application/pdf")},
    )
    assert replaced.status_code == 200
    assert replaced.json()["has_file"] is True

    # Soft-delete hides download
    assert v1_client.delete(f"{MATERIALS}/{mid}", headers=admin).status_code == 200
    assert v1_client.get(f"{MATERIALS}/{mid}/download", headers=admin).status_code == 404


def test_student_isolation_and_download(v1_client, v1_db, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("DOCUMENT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()

    sa = _super(v1_client, v1_db, "sm-st-sa@eschool.com")
    school_a = _school(v1_client, sa, "SMSA")
    school_b = _school(v1_client, sa, "SMSB")
    admin_a = _school_admin(v1_client, sa, school_a, "sm-sta@eschool.com")
    admin_b = _school_admin(v1_client, sa, school_b, "sm-stb@eschool.com")
    ids_a = _seed(v1_client, admin_a, email_prefix="smsa")
    ids_b = _seed(v1_client, admin_b, email_prefix="smsb")
    school_row_a = v1_db.get(School, school_a)
    school_row_b = v1_db.get(School, school_b)

    student_a, token_a = _make_student(
        v1_db, school_a, ids_a, email="smsa-s@eschool.com", admission_no="SMSA1"
    )
    _student_b, token_b = _make_student(
        v1_db, school_b, ids_b, email="smsb-s@eschool.com", admission_no="SMSB1"
    )
    sh_a = _student_headers(school_row_a.code, token_a)
    sh_b = _student_headers(school_row_b.code, token_b)

    video = v1_client.post(
        MATERIALS,
        headers=admin_a,
        json={
            "session_year_id": ids_a["session_year_id"],
            "class_section_id": ids_a["class_section_id"],
            "subject_id": ids_a["subject_id"],
            "teacher_user_id": ids_a["teacher_user_id"],
            "resource_type": "video_link",
            "title": "School A video",
            "external_url": "https://www.youtube.com/watch?v=schoola",
        },
    )
    assert video.status_code == 201
    vid_id = video.json()["id"]

    form = {
        "session_year_id": str(ids_a["session_year_id"]),
        "class_section_id": str(ids_a["class_section_id"]),
        "subject_id": str(ids_a["subject_id"]),
        "teacher_user_id": str(ids_a["teacher_user_id"]),
        "title": "School A PDF",
    }
    file_mat = v1_client.post(
        UPLOAD, headers=admin_a, data=form, files={"file": ("a.pdf", PDF, "application/pdf")}
    )
    assert file_mat.status_code == 201
    file_id = file_mat.json()["id"]

    listed = v1_client.get(STUDENT_SM, headers=sh_a)
    assert listed.status_code == 200
    assert listed.json()["total"] == 2

    got = v1_client.get(f"{STUDENT_SM}/{vid_id}", headers=sh_a)
    assert got.status_code == 200
    assert got.json()["external_url"].startswith("https://")

    # Cross-school student sees nothing / 404
    assert v1_client.get(STUDENT_SM, headers=sh_b).json()["total"] == 0
    assert v1_client.get(f"{STUDENT_SM}/{vid_id}", headers=sh_b).status_code == 404
    assert v1_client.get(f"{STUDENT_SM}/{file_id}/download", headers=sh_b).status_code == 404

    # Own school download
    dl = v1_client.get(f"{STUDENT_SM}/{file_id}/download", headers=sh_a)
    assert dl.status_code == 200
    assert dl.content.startswith(b"%PDF")

    # Video download rejected
    assert v1_client.get(f"{STUDENT_SM}/{vid_id}/download", headers=sh_a).status_code == 422

    # Soft-deleted not downloadable
    v1_client.delete(f"{MATERIALS}/{file_id}", headers=admin_a)
    assert v1_client.get(f"{STUDENT_SM}/{file_id}/download", headers=sh_a).status_code == 404
    assert v1_client.get(STUDENT_SM, headers=sh_a).json()["total"] == 1

    # Inactive enrollment
    student_a.enrollment_status = "inactive"
    v1_db.commit()
    assert v1_client.get(STUDENT_SM, headers=sh_a).status_code == 403

    # Cross-school admin isolation
    assert v1_client.get(f"{MATERIALS}/{vid_id}", headers=admin_b).status_code == 404
