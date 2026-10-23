"""Study material management (Module 4).

Resource types
--------------
- ``file``: binary stored via ``document_storage`` (requires local backend config).
- ``video_link`` / ``document_reference``: validated https URLs only; never fetched
  or stored as files. Client storage_key / filesystem paths are rejected.

Chapter/topic
-------------
No Neon LessonTopic ORM exists (catalog ``lesson_topics`` is unmapped). Optional
``chapter`` / ``topic`` free-text metadata is used instead.

Size limits
-----------
Reuse ``DOCUMENT_MAX_IMAGE_BYTES`` / ``DOCUMENT_MAX_FILE_BYTES`` settings
(defaults 5 MiB images / 10 MiB documents). Formats: JPEG, PNG, WebP, PDF, DOC, DOCX.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.tables import (
    ClassSection,
    SessionYear,
    Student,
    StudyMaterial,
    Subject,
    TeacherAssignment,
    User,
)
from app.services.v1.document_storage import (
    get_storage,
    sanitize_filename,
    storage_configured,
    validate_study_material_upload,
)
from app.services.v1.school_academics import (
    AcademicError,
    _assert_subject_mapped_to_class,
    _commit,
    _envelope,
    _now,
    _owned,
    _page,
    _same_school,
    _staff_for_teacher_user,
    _user_name,
)

RESOURCE_FILE = "file"
RESOURCE_VIDEO = "video_link"
RESOURCE_DOC_REF = "document_reference"
RESOURCE_TYPES = frozenset({RESOURCE_FILE, RESOURCE_VIDEO, RESOURCE_DOC_REF})
ENROLLED_STATUSES = frozenset({"admitted", "active"})

_WRITE_BLOCKLIST = frozenset(
    {
        "school_id",
        "id",
        "deleted_at",
        "created_at",
        "updated_at",
        "staff_id",
        "storage_key",
        "content_type",
        "size_bytes",
        "original_filename",
        "uploaded_by_v1_user_id",
    }
)


def sanitize_material_body(body: dict) -> dict:
    return {k: v for k, v in body.items() if k not in _WRITE_BLOCKLIST}


def _assert_teacher_assignment(
    db: Session,
    school_id: int,
    *,
    staff_id: int,
    subject_id: int,
    class_section_id: int,
    session_year_id: int,
) -> None:
    rows = (
        db.query(TeacherAssignment)
        .filter(
            TeacherAssignment.school_id == school_id,
            TeacherAssignment.staff_id == staff_id,
            TeacherAssignment.subject_id == subject_id,
            TeacherAssignment.deleted_at.is_(None),
            or_(
                TeacherAssignment.class_section_id.is_(None),
                TeacherAssignment.class_section_id == class_section_id,
            ),
            or_(
                TeacherAssignment.session_year_id.is_(None),
                TeacherAssignment.session_year_id == session_year_id,
            ),
        )
        .all()
    )
    if not rows:
        raise AcademicError(
            422,
            "Teacher has no active assignment for this subject and class/session scope",
        )


def _validate_external_url(raw: Any, *, field: str = "external_url") -> str:
    if raw is None or not str(raw).strip():
        raise AcademicError(422, f"{field} is required")
    url = str(raw).strip()
    if len(url) > 2048:
        raise AcademicError(422, f"{field} is too long")
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        raise AcademicError(422, f"{field} must be an https URL")
    if not parsed.netloc or parsed.username or parsed.password:
        raise AcademicError(422, f"{field} is not a valid https URL")
    host = parsed.hostname or ""
    if not host or host.lower() in {"localhost", "127.0.0.1", "::1"}:
        raise AcademicError(422, f"{field} host is not allowed")
    # Block literal private/link-local IPs in the hostname.
    try:
        addr = ipaddress.ip_address(host)
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
        ):
            raise AcademicError(422, f"{field} host is not allowed")
    except ValueError:
        # Hostname is not an IP — require a plausible DNS label.
        if not re.fullmatch(r"[A-Za-z0-9.-]+", host) or "." not in host:
            raise AcademicError(422, f"{field} host is not allowed") from None
    return url


def _material_item(db: Session, row: StudyMaterial) -> dict:
    teacher = db.get(User, row.teacher_user_id)
    subject = db.get(Subject, row.subject_id)
    data = {
        "id": row.id,
        "session_year_id": row.session_year_id,
        "class_section_id": row.class_section_id,
        "subject_id": row.subject_id,
        "subject_name": subject.name if subject else None,
        "teacher_user_id": row.teacher_user_id,
        "teacher_name": _user_name(teacher),
        "resource_type": row.resource_type,
        "title": row.title,
        "description": row.description,
        "chapter": row.chapter,
        "topic": row.topic,
        "content_type": row.content_type,
        "size_bytes": row.size_bytes,
        "original_filename": row.original_filename,
        "has_file": bool(row.storage_key) and row.resource_type == RESOURCE_FILE,
        "external_url": row.external_url
        if row.resource_type in (RESOURCE_VIDEO, RESOURCE_DOC_REF)
        else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    return data


def _active(db: Session, school_id: int, material_id: int) -> StudyMaterial:
    return _owned(db, StudyMaterial, material_id, school_id)


def _storage_key_refcount(db: Session, school_id: int, storage_key: str | None) -> int:
    if not storage_key:
        return 0
    return (
        db.query(StudyMaterial)
        .filter(
            StudyMaterial.school_id == school_id,
            StudyMaterial.storage_key == storage_key,
            StudyMaterial.deleted_at.is_(None),
        )
        .count()
    )


def _safe_delete_storage_key(db: Session, school_id: int, storage_key: str | None) -> None:
    """Delete physical file only when no active study material still references it."""
    if not storage_key or not storage_configured():
        return
    if _storage_key_refcount(db, school_id, storage_key) > 0:
        return
    try:
        get_storage().delete(storage_key)
    except AcademicError:
        # Missing file is non-fatal during cleanup.
        pass


def _student_for_user(db: Session, user: User, school_id: int) -> Student:
    student = (
        db.query(Student)
        .filter(
            Student.user_id == user.id,
            Student.school_id == school_id,
            Student.deleted_at.is_(None),
        )
        .first()
    )
    if student is None:
        raise AcademicError(404, "Student profile not found")
    if student.enrollment_status not in ENROLLED_STATUSES:
        raise AcademicError(403, "Student enrollment is not active")
    return student


def create_material(
    db: Session,
    school_id: int,
    body: dict,
    *,
    actor_v1_user_id: str | None,
    file_bytes: bytes | None = None,
    claimed_filename: str | None = None,
) -> dict:
    data = sanitize_material_body(body)
    resource_type = str(data.get("resource_type") or "").strip().lower()
    if resource_type not in RESOURCE_TYPES:
        raise AcademicError(
            422,
            "resource_type must be one of: file, video_link, document_reference",
        )

    session_year_id = int(data.get("session_year_id") or 0)
    class_section_id = int(data.get("class_section_id") or 0)
    subject_id = int(data.get("subject_id") or 0)
    teacher_user_id = int(data.get("teacher_user_id") or 0)
    if not all([session_year_id, class_section_id, subject_id, teacher_user_id]):
        raise AcademicError(
            422,
            "session_year_id, class_section_id, subject_id and teacher_user_id are required",
        )

    _same_school(db, SessionYear, session_year_id, school_id, "Session year")
    class_section = _same_school(db, ClassSection, class_section_id, school_id, "Class section")
    _same_school(db, Subject, subject_id, school_id, "Subject")
    _assert_subject_mapped_to_class(db, school_id, class_section.class_id, subject_id)
    staff = _staff_for_teacher_user(db, school_id, teacher_user_id)
    _assert_teacher_assignment(
        db,
        school_id,
        staff_id=staff.id,
        subject_id=subject_id,
        class_section_id=class_section_id,
        session_year_id=session_year_id,
    )

    title = str(data.get("title") or "").strip()
    if not title or len(title) > 255:
        raise AcademicError(422, "title is required and must be at most 255 characters")
    description = data.get("description")
    if description is not None:
        description = str(description)
        if len(description) > 20000:
            raise AcademicError(422, "description too long")
    chapter = data.get("chapter")
    if chapter is not None:
        chapter = str(chapter).strip()[:255] or None
    topic = data.get("topic")
    if topic is not None:
        topic = str(topic).strip()[:255] or None

    # Reject client-controlled storage fields even if smuggled past schema.
    for banned in ("storage_key", "path", "url", "file_path"):
        if banned in body:
            raise AcademicError(422, f"{banned} cannot be set by clients")

    storage_key = None
    content_type = None
    size_bytes = None
    original_filename = None
    external_url = None

    if resource_type == RESOURCE_FILE:
        if not storage_configured():
            raise AcademicError(
                503,
                "Document storage is not configured. Set DOCUMENT_STORAGE_BACKEND=local "
                "and DOCUMENT_STORAGE_PATH to a private directory (not a public web root).",
            )
        if not file_bytes:
            raise AcademicError(422, "file upload is required for resource_type=file")
        content_type, ext, original_filename = validate_study_material_upload(
            file_bytes, claimed_filename=claimed_filename
        )
        storage = get_storage()
        storage_key = storage.build_key(school_id, teacher_user_id, ext)
        storage.put(storage_key, file_bytes)
        size_bytes = len(file_bytes)
    else:
        external_url = _validate_external_url(data.get("external_url"))
        if file_bytes:
            raise AcademicError(422, "file upload is not allowed for link/reference resources")

    row = StudyMaterial(
        school_id=school_id,
        session_year_id=session_year_id,
        class_section_id=class_section_id,
        subject_id=subject_id,
        teacher_user_id=teacher_user_id,
        staff_id=staff.id,
        uploaded_by_v1_user_id=(str(actor_v1_user_id)[:36] if actor_v1_user_id else None),
        resource_type=resource_type,
        title=title,
        description=description,
        chapter=chapter,
        topic=topic,
        storage_key=storage_key,
        content_type=content_type,
        size_bytes=size_bytes,
        original_filename=original_filename,
        external_url=external_url,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _material_item(db, row)


def list_materials(
    db: Session,
    school_id: int,
    *,
    page: int,
    page_size: int,
    session_year_id: int | None = None,
    class_section_id: int | None = None,
    subject_id: int | None = None,
    resource_type: str | None = None,
    chapter: str | None = None,
    topic: str | None = None,
    teacher_user_id: int | None = None,
    q: str = "",
) -> dict:
    page, page_size = _page(page, page_size)
    query = db.query(StudyMaterial).filter(
        StudyMaterial.school_id == school_id,
        StudyMaterial.deleted_at.is_(None),
    )
    if session_year_id is not None:
        query = query.filter(StudyMaterial.session_year_id == session_year_id)
    if class_section_id is not None:
        query = query.filter(StudyMaterial.class_section_id == class_section_id)
    if subject_id is not None:
        query = query.filter(StudyMaterial.subject_id == subject_id)
    if teacher_user_id is not None:
        query = query.filter(StudyMaterial.teacher_user_id == teacher_user_id)
    if resource_type is not None:
        rt = resource_type.strip().lower()
        if rt not in RESOURCE_TYPES:
            raise AcademicError(422, "invalid resource_type filter")
        query = query.filter(StudyMaterial.resource_type == rt)
    if chapter and chapter.strip():
        query = query.filter(StudyMaterial.chapter.ilike(f"%{chapter.strip()}%"))
    if topic and topic.strip():
        query = query.filter(StudyMaterial.topic.ilike(f"%{topic.strip()}%"))
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                StudyMaterial.title.ilike(like),
                StudyMaterial.description.ilike(like),
                StudyMaterial.chapter.ilike(like),
                StudyMaterial.topic.ilike(like),
            )
        )
    total = query.count()
    rows = (
        query.order_by(StudyMaterial.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _envelope([_material_item(db, r) for r in rows], total, page, page_size)


def get_material(db: Session, school_id: int, material_id: int) -> dict:
    return _material_item(db, _active(db, school_id, material_id))


def update_material(
    db: Session,
    school_id: int,
    material_id: int,
    body: dict,
    *,
    actor_v1_user_id: str | None,
    file_bytes: bytes | None = None,
    claimed_filename: str | None = None,
) -> dict:
    row = _active(db, school_id, material_id)
    data = sanitize_material_body(body)

    session_year_id = row.session_year_id
    class_section_id = row.class_section_id
    subject_id = row.subject_id
    teacher_user_id = row.teacher_user_id

    if "session_year_id" in data and data["session_year_id"] is not None:
        session_year_id = int(data["session_year_id"])
        _same_school(db, SessionYear, session_year_id, school_id, "Session year")
    if "class_section_id" in data and data["class_section_id"] is not None:
        class_section_id = int(data["class_section_id"])
        _same_school(db, ClassSection, class_section_id, school_id, "Class section")
    if "subject_id" in data and data["subject_id"] is not None:
        subject_id = int(data["subject_id"])
        _same_school(db, Subject, subject_id, school_id, "Subject")
    if "teacher_user_id" in data and data["teacher_user_id"] is not None:
        teacher_user_id = int(data["teacher_user_id"])

    class_section = _same_school(db, ClassSection, class_section_id, school_id, "Class section")
    _assert_subject_mapped_to_class(db, school_id, class_section.class_id, subject_id)
    staff = _staff_for_teacher_user(db, school_id, teacher_user_id)
    _assert_teacher_assignment(
        db,
        school_id,
        staff_id=staff.id,
        subject_id=subject_id,
        class_section_id=class_section_id,
        session_year_id=session_year_id,
    )

    if "title" in data:
        title = str(data["title"] or "").strip()
        if not title or len(title) > 255:
            raise AcademicError(422, "title is required and must be at most 255 characters")
        row.title = title
    if "description" in data:
        description = data["description"]
        if description is not None:
            description = str(description)
            if len(description) > 20000:
                raise AcademicError(422, "description too long")
        row.description = description
    if "chapter" in data:
        chapter = data["chapter"]
        row.chapter = str(chapter).strip()[:255] if chapter is not None else None
        if row.chapter == "":
            row.chapter = None
    if "topic" in data:
        topic = data["topic"]
        row.topic = str(topic).strip()[:255] if topic is not None else None
        if row.topic == "":
            row.topic = None

    if "external_url" in data:
        if row.resource_type == RESOURCE_FILE:
            raise AcademicError(422, "external_url is not allowed for file resources")
        row.external_url = _validate_external_url(data["external_url"])

    old_key = row.storage_key
    if file_bytes is not None:
        if row.resource_type != RESOURCE_FILE:
            raise AcademicError(422, "file replacement is only allowed for file resources")
        if not storage_configured():
            raise AcademicError(
                503,
                "Document storage is not configured. Set DOCUMENT_STORAGE_BACKEND=local "
                "and DOCUMENT_STORAGE_PATH.",
            )
        content_type, ext, original_filename = validate_study_material_upload(
            file_bytes, claimed_filename=claimed_filename
        )
        storage = get_storage()
        new_key = storage.build_key(school_id, teacher_user_id, ext)
        storage.put(new_key, file_bytes)
        row.storage_key = new_key
        row.content_type = content_type
        row.size_bytes = len(file_bytes)
        row.original_filename = original_filename

    row.session_year_id = session_year_id
    row.class_section_id = class_section_id
    row.subject_id = subject_id
    row.teacher_user_id = teacher_user_id
    row.staff_id = staff.id
    if actor_v1_user_id:
        row.uploaded_by_v1_user_id = str(actor_v1_user_id)[:36]
    row.updated_at = _now()
    _commit(db)

    if file_bytes is not None and old_key and old_key != row.storage_key:
        _safe_delete_storage_key(db, school_id, old_key)

    db.refresh(row)
    return _material_item(db, row)


def soft_delete_material(db: Session, school_id: int, material_id: int) -> dict:
    row = _active(db, school_id, material_id)
    key = row.storage_key
    now = _now()
    row.deleted_at = now
    row.updated_at = now
    _commit(db)
    _safe_delete_storage_key(db, school_id, key)
    return {"id": material_id, "deleted": True}


def get_file_bytes(db: Session, school_id: int, material_id: int) -> tuple[bytes, str, str | None]:
    """Return (bytes, content_type, download_filename) for file resources."""
    row = _active(db, school_id, material_id)
    if row.resource_type != RESOURCE_FILE:
        raise AcademicError(422, "Material is not a downloadable file")
    if not row.storage_key:
        raise AcademicError(404, "Document file not found")
    if not storage_configured():
        raise AcademicError(
            503,
            "Document storage is not configured. Set DOCUMENT_STORAGE_BACKEND=local "
            "and DOCUMENT_STORAGE_PATH.",
        )
    data = get_storage().get(row.storage_key)
    filename = row.original_filename or sanitize_filename(f"material-{row.id}")
    content_type = row.content_type or "application/octet-stream"
    return data, content_type, filename


def list_student_materials(
    db: Session,
    school_id: int,
    user: User,
    *,
    page: int,
    page_size: int,
    subject_id: int | None = None,
    resource_type: str | None = None,
    chapter: str | None = None,
    topic: str | None = None,
    q: str = "",
) -> dict:
    student = _student_for_user(db, user, school_id)
    return list_materials(
        db,
        school_id,
        page=page,
        page_size=page_size,
        session_year_id=student.session_year_id,
        class_section_id=student.class_section_id,
        subject_id=subject_id,
        resource_type=resource_type,
        chapter=chapter,
        topic=topic,
        q=q,
    )


def get_student_material(db: Session, school_id: int, user: User, material_id: int) -> dict:
    student = _student_for_user(db, user, school_id)
    row = _active(db, school_id, material_id)
    if (
        row.class_section_id != student.class_section_id
        or row.session_year_id != student.session_year_id
    ):
        raise AcademicError(404, "Record not found")
    return _material_item(db, row)


def get_student_file_bytes(
    db: Session, school_id: int, user: User, material_id: int
) -> tuple[bytes, str, str | None]:
    student = _student_for_user(db, user, school_id)
    row = _active(db, school_id, material_id)
    if (
        row.class_section_id != student.class_section_id
        or row.session_year_id != student.session_year_id
    ):
        raise AcademicError(404, "Record not found")
    return get_file_bytes(db, school_id, material_id)
