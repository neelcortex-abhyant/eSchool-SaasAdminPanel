"""Offline tests for School Admin document storage (no Neon, no Postgres).

Storage unit tests use an isolated tmp_path. Route tests run the real FastAPI app
against an in-memory SQLite copy of the ORM schema, overriding only the DB session
and the School Admin auth dependency (school_id is switched per request).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import central_db
from app.api.v1 import school_admin
from app.core.config import get_settings
from app.main import app
from app.models.tables import Base, HomeworkSubmission, PersonDocument, School
from app.services.v1 import document_storage as store
from app.services.v1 import person_documents
from app.services.v1 import school_homework
from app.services.v1.school_academics import AcademicError

TEACHERS = "/api/v1/school-admin/teachers"
STAFF = "/api/v1/school-admin/staff"
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 64 + b"\xff\xd9"
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _set_storage(monkeypatch, backend: str, path: str) -> None:
    monkeypatch.setenv("DOCUMENT_STORAGE_BACKEND", backend)
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", path)
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def storage_dir(monkeypatch, tmp_path) -> Path:
    root = tmp_path / "private-docs"
    _set_storage(monkeypatch, "local", str(root))
    return root


def _stored_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file()]


# --- configuration ---------------------------------------------------------


def test_missing_configuration_returns_clear_503(monkeypatch):
    _set_storage(monkeypatch, "none", "")
    with pytest.raises(AcademicError) as exc:
        store.require_storage()
    assert exc.value.status_code == 503
    assert exc.value.detail == store.NOT_CONFIGURED_DETAIL
    assert "DOCUMENT_STORAGE_BACKEND=local" in exc.value.detail


def test_local_backend_without_path_names_the_missing_variable(monkeypatch):
    _set_storage(monkeypatch, "local", "  ")
    assert store.storage_config_error() == (
        "DOCUMENT_STORAGE_PATH is required when DOCUMENT_STORAGE_BACKEND=local."
    )


def test_unsupported_backend_is_rejected(monkeypatch, tmp_path):
    _set_storage(monkeypatch, "s3", str(tmp_path))
    reason = store.storage_config_error()
    assert reason is not None and "not supported" in reason


def test_quoted_and_mixed_case_values_are_accepted(monkeypatch, tmp_path):
    _set_storage(monkeypatch, ' "Local" ', f'"{tmp_path / "docs"}"')
    assert store.storage_configured()
    storage = store.get_storage()
    assert storage.root == (tmp_path / "docs").resolve()


@pytest.mark.parametrize("public_dir", ["public", "static", "www", "public_html", "htdocs"])
def test_public_web_root_is_rejected(monkeypatch, tmp_path, public_dir):
    _set_storage(monkeypatch, "local", str(tmp_path / public_dir / "documents"))
    reason = store.storage_config_error()
    assert reason == "DOCUMENT_STORAGE_PATH must not be inside a public web root."
    with pytest.raises(AcademicError) as exc:
        store.get_storage()
    assert exc.value.status_code == 503
    assert not (tmp_path / public_dir).exists()


def test_filesystem_root_is_rejected(monkeypatch):
    _set_storage(monkeypatch, "local", os.path.abspath(os.sep))
    assert store.storage_config_error() == "DOCUMENT_STORAGE_PATH must not be a filesystem root."


# --- local backend ---------------------------------------------------------


def test_local_storage_roundtrip_in_isolated_directory(storage_dir):
    storage = store.get_storage()
    assert storage_dir.is_dir()
    key = storage.build_key(7, 42, "pdf")
    assert key.startswith("7/42/") and key.endswith(".pdf")
    storage.put(key, PDF)
    assert storage.get(key) == PDF
    # Atomic write leaves no temp files behind.
    assert [p.name for p in _stored_files(storage_dir)] == [Path(key).name]
    if os.name != "nt":
        assert (storage_dir.stat().st_mode & 0o777) == 0o700
        assert ((storage_dir / key).stat().st_mode & 0o777) == 0o600
    storage.delete(key)
    assert _stored_files(storage_dir) == []


@pytest.mark.parametrize(
    "key", ["../escape.pdf", "1/../../escape.pdf", "C:/Windows/x.pdf", "1/2/a\x00.pdf", ""]
)
def test_unsafe_storage_keys_are_rejected(storage_dir, key):
    storage = store.get_storage()
    with pytest.raises(AcademicError) as exc:
        storage.put(key, PDF)
    assert exc.value.status_code == 422
    assert not (storage_dir.parent / "escape.pdf").exists()


def test_build_key_rejects_unknown_extension(storage_dir):
    with pytest.raises(AcademicError):
        store.get_storage().build_key(1, 1, "php")


def test_write_failure_is_503_without_leaking_paths(storage_dir, monkeypatch):
    storage = store.get_storage()

    def boom(*_args, **_kwargs):
        raise OSError(28, "No space left on device", str(storage_dir))

    monkeypatch.setattr(store.os, "replace", boom)
    with pytest.raises(AcademicError) as exc:
        storage.put(storage.build_key(1, 1, "png"), PNG)
    assert exc.value.status_code == 503
    assert exc.value.detail == store.UNAVAILABLE_DETAIL
    assert str(storage_dir) not in exc.value.detail
    assert _stored_files(storage_dir) == []


def test_missing_file_is_404(storage_dir):
    with pytest.raises(AcademicError) as exc:
        store.get_storage().get("1/1/" + "0" * 32 + ".pdf")
    assert exc.value.status_code == 404
    assert exc.value.detail == "Document file not found"


# --- route tests (real app, SQLite session) --------------------------------


@pytest.fixture()
def api():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _pg_shims(conn, _record):
        conn.create_function(
            "btrim", 1, lambda s: s.strip() if isinstance(s, str) else s, deterministic=True
        )

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    seed = Session()
    # SQLite ignores the Postgres partial-index WHERE, so blank-able unique columns get values.
    seed.add_all(
        [
            School(id=sid, name=f"School {sid}", code=f"S{sid}", support_email=f"s{sid}@eschool.com", domain=f"s{sid}.eschool.com")
            for sid in (1, 2)
        ]
    )
    seed.commit()
    seed.close()

    current = {"school_id": 1}

    def _db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    def _auth():
        return SimpleNamespace(user=SimpleNamespace(school_id=current["school_id"]))

    app.dependency_overrides[central_db] = _db
    app.dependency_overrides[school_admin.require_teachers] = _auth
    app.dependency_overrides[school_admin.require_staff] = _auth
    client = TestClient(app)

    def as_school(school_id: int) -> TestClient:
        current["school_id"] = school_id
        return client

    yield SimpleNamespace(client=client, as_school=as_school, Session=Session)
    app.dependency_overrides.clear()
    engine.dispose()


def _create_teacher(api, school_id: int = 1, suffix: str = "a") -> int:
    res = api.as_school(school_id).post(
        TEACHERS,
        json={
            "first_name": "Asha",
            "last_name": "Rao",
            "email": f"teacher-{suffix}@eschool.com",
            "password": "teacherpass1",
            "employee_id": f"T-{suffix}",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _upload(api, teacher_id: int, name: str, data: bytes, mime: str, title: str = "", category: str = "other"):
    return api.client.post(
        f"{TEACHERS}/{teacher_id}/documents",
        files={"file": (name, data, mime)},
        data={"title": title, "category": category},
    )


def test_teacher_created_even_when_storage_unconfigured(api, monkeypatch):
    _set_storage(monkeypatch, "none", "")
    teacher_id = _create_teacher(api)
    res = _upload(api, teacher_id, "schoolsaathi image.png", PNG, "image/png")
    assert res.status_code == 503
    assert res.json()["detail"] == store.NOT_CONFIGURED_DETAIL
    photo = api.client.post(f"{TEACHERS}/{teacher_id}/photo", files={"file": ("p.png", PNG, "image/png")})
    assert photo.status_code == 503
    profile = api.client.get(f"{TEACHERS}/{teacher_id}")
    assert profile.status_code == 200
    assert profile.json()["documents"] == []
    assert profile.json()["photo_url"] is None


@pytest.mark.parametrize(
    "name,data,mime,content_type",
    [
        ("scan.jpg", JPEG, "image/jpeg", "image/jpeg"),
        ("scan.jpeg", JPEG, "image/jpeg", "image/jpeg"),
        ("schoolsaathi image.png", PNG, "image/png", "image/png"),
        ("degree.pdf", PDF, "application/pdf", "application/pdf"),
    ],
)
def test_supported_document_types_upload_and_download(api, storage_dir, name, data, mime, content_type):
    teacher_id = _create_teacher(api)
    res = _upload(api, teacher_id, name, data, mime, title="Certificate", category="certificate")
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["content_type"] == content_type
    assert body["file_name"] == name
    assert body["url"] == f"{TEACHERS}/{teacher_id}/documents/{body['id']}/download"
    assert "storage_key" not in body and str(storage_dir) not in res.text

    with api.Session() as db:
        row = db.get(PersonDocument, body["id"])
        assert row.school_id == 1 and row.owner_user_id == teacher_id
        assert row.storage_key.startswith(f"1/{teacher_id}/")
        assert name not in row.storage_key  # generated key, not the client filename
        assert (storage_dir / row.storage_key).read_bytes() == data

    got = api.client.get(body["url"])
    assert got.status_code == 200
    assert got.content == data
    assert got.headers["content-type"].startswith(content_type)
    assert got.headers["x-content-type-options"] == "nosniff"
    assert got.headers["content-disposition"].startswith("attachment;")


def test_profile_photo_jpeg_and_png(api, storage_dir):
    teacher_id = _create_teacher(api)
    first = api.client.post(f"{TEACHERS}/{teacher_id}/photo", files={"file": ("me.jpg", JPEG, "image/jpeg")})
    assert first.status_code == 201, first.text
    assert first.json() == {"photo_url": f"{TEACHERS}/{teacher_id}/photo"}
    second = api.client.post(f"{TEACHERS}/{teacher_id}/photo", files={"file": ("me.png", PNG, "image/png")})
    assert second.status_code == 201
    got = api.client.get(f"{TEACHERS}/{teacher_id}/photo")
    assert got.status_code == 200 and got.content == PNG
    assert got.headers["cache-control"] == "private, no-store"
    # Replacing the photo removes the previous file.
    assert len(_stored_files(storage_dir)) == 1
    profile = api.client.get(f"{TEACHERS}/{teacher_id}").json()
    assert profile["photo_url"] == f"{TEACHERS}/{teacher_id}/photo"
    assert profile["documents"] == []  # photos are not listed as documents

    pdf_photo = api.client.post(f"{TEACHERS}/{teacher_id}/photo", files={"file": ("x.pdf", PDF, "application/pdf")})
    assert pdf_photo.status_code == 415


def test_rejects_unsupported_spoofed_and_oversized_files(api, storage_dir):
    teacher_id = _create_teacher(api)
    assert _upload(api, teacher_id, "notes.txt", b"plain text", "text/plain").status_code == 415
    assert _upload(api, teacher_id, "fake.pdf", b"MZ\x90\x00 not a pdf", "application/pdf").status_code == 415
    big_image = PNG + b"\x00" * (2 * 1024 * 1024)
    assert _upload(api, teacher_id, "big.png", big_image, "image/png").status_code == 413
    big_pdf = PDF + b"\x00" * (5 * 1024 * 1024)
    assert _upload(api, teacher_id, "big.pdf", big_pdf, "application/pdf").status_code == 413
    huge_pdf = PDF + b"\x00" * (11 * 1024 * 1024)
    assert _upload(api, teacher_id, "huge.pdf", huge_pdf, "application/pdf").status_code == 413
    assert _stored_files(storage_dir) == []
    with api.Session() as db:
        assert db.query(PersonDocument).count() == 0


def test_multiple_attachments_persist_on_profile_after_refresh(api, storage_dir):
    teacher_id = _create_teacher(api)
    uploads = [
        ("resume.pdf", PDF, "application/pdf", "Resume", "resume"),
        ("aadhaar.jpg", JPEG, "image/jpeg", "Aadhaar", "id_proof"),
        ("bed.png", PNG, "image/png", "B.Ed certificate", "certificate"),
    ]
    ids = []
    for name, data, mime, title, category in uploads:
        res = _upload(api, teacher_id, name, data, mime, title=title, category=category)
        assert res.status_code == 201, res.text
        ids.append(res.json()["id"])
    api.client.post(f"{TEACHERS}/{teacher_id}/photo", files={"file": ("me.png", PNG, "image/png")})

    # A new client simulates a page refresh / later login; data comes only from storage + DB.
    fresh = TestClient(app)
    profile = fresh.get(f"{TEACHERS}/{teacher_id}")
    assert profile.status_code == 200
    docs = profile.json()["documents"]
    assert [d["id"] for d in docs] == sorted(ids, reverse=True)
    assert {d["title"] for d in docs} == {"Resume", "Aadhaar", "B.Ed certificate"}
    assert all("storage_key" not in d for d in docs)
    listed = fresh.get(f"{TEACHERS}/{teacher_id}/documents").json()
    assert listed["total"] == 4  # list endpoint also includes the profile photo row
    for doc in docs:
        assert fresh.get(doc["url"]).status_code == 200


def test_document_limit_rejects_eleventh_without_orphan_file(api, storage_dir):
    teacher_id = _create_teacher(api)
    for i in range(10):
        assert _upload(api, teacher_id, f"d{i}.pdf", PDF, "application/pdf").status_code == 201
    res = _upload(api, teacher_id, "d10.pdf", PDF, "application/pdf")
    assert res.status_code == 422
    assert len(_stored_files(storage_dir)) == 10


def test_other_school_cannot_upload_list_or_download(api, storage_dir):
    teacher_a = _create_teacher(api, 1, "a")
    doc = _upload(api, teacher_a, "cv.pdf", PDF, "application/pdf").json()
    api.client.post(f"{TEACHERS}/{teacher_a}/photo", files={"file": ("me.png", PNG, "image/png")})
    files_before = len(_stored_files(storage_dir))

    other = api.as_school(2)
    assert _upload(api, teacher_a, "evil.pdf", PDF, "application/pdf").status_code == 404
    assert other.get(f"{TEACHERS}/{teacher_a}/documents").status_code == 404
    assert other.get(doc["url"]).status_code == 404
    assert other.get(f"{TEACHERS}/{teacher_a}/documents/{doc['id']}").status_code == 404
    assert other.delete(f"{TEACHERS}/{teacher_a}/documents/{doc['id']}").status_code == 404
    assert other.get(f"{TEACHERS}/{teacher_a}/photo").status_code == 404
    assert other.get(f"{TEACHERS}/{teacher_a}").status_code == 404
    assert len(_stored_files(storage_dir)) == files_before

    # A school-B teacher cannot be used to reach school A's document id either.
    teacher_b = _create_teacher(api, 2, "b")
    assert other.get(f"{TEACHERS}/{teacher_b}/documents/{doc['id']}/download").status_code == 404


def test_unauthenticated_requests_are_rejected(api, storage_dir):
    teacher_id = _create_teacher(api)
    del app.dependency_overrides[school_admin.require_teachers]
    res = api.client.post(
        f"{TEACHERS}/{teacher_id}/documents", files={"file": ("cv.pdf", PDF, "application/pdf")}
    )
    assert res.status_code == 401
    assert api.client.get(f"{TEACHERS}/{teacher_id}/documents").status_code == 401
    assert _stored_files(storage_dir) == []


def test_missing_file_on_disk_reports_404(api, storage_dir):
    teacher_id = _create_teacher(api)
    doc = _upload(api, teacher_id, "cv.pdf", PDF, "application/pdf").json()
    for path in _stored_files(storage_dir):
        path.unlink()  # e.g. ephemeral disk wiped by a redeploy
    res = api.client.get(doc["url"])
    assert res.status_code == 404
    assert res.json()["detail"] == "Document file not found"


def test_storage_write_error_is_reported_and_nothing_persisted(api, storage_dir, monkeypatch):
    teacher_id = _create_teacher(api)

    def boom(*_args, **_kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(store.os, "replace", boom)
    res = _upload(api, teacher_id, "cv.pdf", PDF, "application/pdf")
    assert res.status_code == 503
    assert res.json()["detail"] == store.UNAVAILABLE_DETAIL
    with api.Session() as db:
        assert db.query(PersonDocument).count() == 0
    assert _stored_files(storage_dir) == []


def test_metadata_failure_removes_written_file(api, storage_dir, monkeypatch):
    teacher_id = _create_teacher(api)

    def fail_commit(_db):
        raise AcademicError(409, "A record with these details already exists")

    monkeypatch.setattr(person_documents, "_commit", fail_commit)
    res = _upload(api, teacher_id, "cv.pdf", PDF, "application/pdf")
    assert res.status_code == 409
    assert _stored_files(storage_dir) == []
    with api.Session() as db:
        assert db.query(PersonDocument).count() == 0


def test_non_ascii_filename_downloads(api, storage_dir):
    teacher_id = _create_teacher(api)
    doc = _upload(api, teacher_id, "प्रमाणपत्र.pdf", PDF, "application/pdf").json()
    res = api.client.get(doc["url"])
    assert res.status_code == 200
    assert "filename*=UTF-8''" in res.headers["content-disposition"]


def test_staff_profile_includes_documents(api, storage_dir):
    res = api.client.post(
        STAFF,
        json={
            "first_name": "Ravi",
            "last_name": "K",
            "email": "staff@eschool.com",
            "password": "staffpass12",
            "employee_id": "S-1",
        },
    )
    assert res.status_code == 201, res.text
    staff_id = res.json()["id"]
    up = api.client.post(
        f"{STAFF}/{staff_id}/documents",
        files={"file": ("id.png", PNG, "image/png")},
        data={"title": "ID", "category": "id_proof"},
    )
    assert up.status_code == 201, up.text
    profile = api.client.get(f"{STAFF}/{staff_id}").json()
    assert [d["id"] for d in profile["documents"]] == [up.json()["id"]]
    assert profile["documents"][0]["url"].startswith(f"{STAFF}/{staff_id}/documents/")


# --- homework uploads: checks happen before the file is written ------------


def _full_attachments() -> str:
    return json.dumps(
        [
            {"original_filename": f"a{i}.pdf", "content_type": "application/pdf", "size_bytes": 1, "storage_key": f"1/1/{i:032x}.pdf"}
            for i in range(school_homework.MAX_ATTACHMENTS)
        ]
    )


def test_homework_attachment_limit_does_not_orphan_file(storage_dir, monkeypatch):
    hw = SimpleNamespace(teacher_user_id=5, attachments_json=_full_attachments())
    monkeypatch.setattr(school_homework, "_active_homework", lambda *_a: hw)
    with pytest.raises(AcademicError) as exc:
        school_homework.append_stored_attachment_to_homework(
            None, 1, 9, file_bytes=PDF, claimed_filename="brief.pdf"  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 422
    assert _stored_files(storage_dir) == []


def test_graded_submission_upload_does_not_orphan_file(api, storage_dir, monkeypatch):
    now = datetime.utcnow()
    hw = SimpleNamespace(
        id=3, school_id=1, class_section_id=1, session_year_id=1,
        deadline_at=now + timedelta(days=1), allow_late=0, teacher_user_id=5,
    )
    student = SimpleNamespace(id=4, user_id=8, class_section_id=1, session_year_id=1)
    monkeypatch.setattr(school_homework, "_active_homework", lambda *_a: hw)
    monkeypatch.setattr(school_homework, "_student_for_user", lambda *_a: student)
    with api.Session() as db:
        db.add(
            HomeworkSubmission(
                school_id=1, homework_id=3, student_id=4, submitted_at=now,
                status=school_homework.SUBMISSION_STATUS_GRADED, is_late=0,
                created_at=now, updated_at=now,
            )
        )
        db.commit()
        with pytest.raises(AcademicError) as exc:
            school_homework.append_stored_attachment_to_submission(
                db, 1, SimpleNamespace(id=8), 3, file_bytes=PDF, claimed_filename="answer.pdf"  # type: ignore[arg-type]
            )
    assert exc.value.status_code == 422
    assert _stored_files(storage_dir) == []
