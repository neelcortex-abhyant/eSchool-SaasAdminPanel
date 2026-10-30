"""Module 3: private teacher/staff document upload, list, download."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.models.tables import PersonDocument
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User as V1User

TEACHERS = "/api/v1/school-admin/teachers"
# 1x1 PNG
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


def _enable_storage(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("DOCUMENT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()


def test_upload_requires_configured_storage(v1_client, v1_db, monkeypatch):
    monkeypatch.setenv("DOCUMENT_STORAGE_BACKEND", "none")
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", "")
    get_settings.cache_clear()

    sa = _super(v1_client, v1_db, "doc-sa0@eschool.com")
    school_id = _school(v1_client, sa, "DOC0")
    admin = _school_admin(v1_client, sa, school_id, "doc-admin0@eschool.com")
    teacher = v1_client.post(
        TEACHERS,
        headers=admin,
        json={
            "first_name": "T",
            "last_name": "D",
            "email": "doc-t0@eschool.com",
            "password": "teacherpass1",
            "employee_id": "DOC0-T",
        },
    )
    assert teacher.status_code == 201
    res = v1_client.post(
        f"{TEACHERS}/{teacher.json()['id']}/documents",
        headers=admin,
        files={"file": ("x.pdf", PDF, "application/pdf")},
        data={"category": "resume"},
    )
    assert res.status_code == 503


def test_teacher_document_upload_list_download_and_isolation(
    v1_client, v1_db, monkeypatch, tmp_path
):
    _enable_storage(monkeypatch, tmp_path)
    sa = _super(v1_client, v1_db, "doc-sa1@eschool.com")
    school_a = _school(v1_client, sa, "DOCA")
    school_b = _school(v1_client, sa, "DOCB")
    admin_a = _school_admin(v1_client, sa, school_a, "doc-aa@eschool.com")
    admin_b = _school_admin(v1_client, sa, school_b, "doc-ab@eschool.com")

    teacher = v1_client.post(
        TEACHERS,
        headers=admin_a,
        json={
            "first_name": "T",
            "last_name": "D",
            "email": "doc-t1@eschool.com",
            "password": "teacherpass1",
            "employee_id": "DOC1-T",
        },
    )
    assert teacher.status_code == 201
    teacher_id = teacher.json()["id"]

    bad = v1_client.post(
        f"{TEACHERS}/{teacher_id}/documents",
        headers=admin_a,
        files={"file": ("x.txt", b"not-a-real-type", "text/plain")},
        data={"category": "other"},
    )
    # People upload contract: unsupported magic bytes → 415 (not 422).
    assert bad.status_code == 415

    uploaded = v1_client.post(
        f"{TEACHERS}/{teacher_id}/documents",
        headers=admin_a,
        files={"file": ("cv.pdf", PDF, "application/pdf")},
        data={"category": "resume"},
    )
    assert uploaded.status_code == 201, uploaded.text
    meta = uploaded.json()
    assert meta["category"] == "resume"
    assert meta["content_type"] == "application/pdf"
    assert meta["original_filename"] == "cv.pdf"
    assert "storage_key" not in meta
    document_id = meta["id"]

    listed = v1_client.get(f"{TEACHERS}/{teacher_id}/documents", headers=admin_a)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    downloaded = v1_client.get(
        f"{TEACHERS}/{teacher_id}/documents/{document_id}/download", headers=admin_a
    )
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF")
    assert downloaded.headers["content-type"].startswith("application/pdf")

    assert (
        v1_client.get(
            f"{TEACHERS}/{teacher_id}/documents/{document_id}/download", headers=admin_b
        ).status_code
        == 404
    )

    row = v1_db.get(PersonDocument, document_id)
    assert row is not None
    assert row.school_id == school_a
    assert (tmp_path / row.storage_key).is_file()

    photo = v1_client.post(
        f"{TEACHERS}/{teacher_id}/photo",
        headers=admin_a,
        files={"file": ("face.png", PNG, "image/png")},
    )
    assert photo.status_code == 201, photo.text
    got_photo = v1_client.get(f"{TEACHERS}/{teacher_id}/photo", headers=admin_a)
    assert got_photo.status_code == 200
    assert got_photo.content.startswith(b"\x89PNG")

    deleted = v1_client.delete(
        f"{TEACHERS}/{teacher_id}/documents/{document_id}", headers=admin_a
    )
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
    assert (
        v1_client.get(
            f"{TEACHERS}/{teacher_id}/documents/{document_id}", headers=admin_a
        ).status_code
        == 404
    )


def test_teacher_profile_lists_persisted_documents(v1_client, v1_db, monkeypatch, tmp_path):
    _enable_storage(monkeypatch, tmp_path)
    sa = _super(v1_client, v1_db, "doc-sa2@eschool.com")
    school_id = _school(v1_client, sa, "DOCP")
    admin = _school_admin(v1_client, sa, school_id, "doc-ap@eschool.com")
    teacher = v1_client.post(
        TEACHERS,
        headers=admin,
        json={
            "first_name": "T",
            "last_name": "P",
            "email": "doc-tp@eschool.com",
            "password": "teacherpass1",
            "employee_id": "DOCP-T",
        },
    )
    assert teacher.status_code == 201
    teacher_id = teacher.json()["id"]
    ids = []
    for name, data, mime in (("cv.pdf", PDF, "application/pdf"), ("id.png", PNG, "image/png")):
        res = v1_client.post(
            f"{TEACHERS}/{teacher_id}/documents",
            headers=admin,
            files={"file": (name, data, mime)},
            data={"category": "other", "title": name},
        )
        assert res.status_code == 201, res.text
        ids.append(res.json()["id"])
    photo = v1_client.post(
        f"{TEACHERS}/{teacher_id}/photo",
        headers=admin,
        files={"file": ("face.png", PNG, "image/png")},
    )
    assert photo.status_code == 201

    profile = v1_client.get(f"{TEACHERS}/{teacher_id}", headers=admin)
    assert profile.status_code == 200
    body = profile.json()
    assert body["photo_url"] == f"{TEACHERS}/{teacher_id}/photo"
    assert [d["id"] for d in body["documents"]] == sorted(ids, reverse=True)
    assert all("storage_key" not in d for d in body["documents"])
