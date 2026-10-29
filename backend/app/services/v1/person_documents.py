"""Private person document metadata and upload orchestration.

Supports teacher, staff, and student owners. Storage keys never leave the server;
clients receive authenticated download paths (``url``) rather than public bucket URLs.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.tables import PersonDocument, User
from app.services.v1 import document_storage as store
from app.services.v1.school_academics import AcademicError, _commit, _envelope, _now, _page
from app.services.v1.school_people import document_public_item, resolve_student_owner_user_id
from app.services.v1.school_staff import _owned_non_teaching_staff
from app.services.v1.school_teachers import _owned_teacher

# People API contract limits (tighter than study-material defaults).
PEOPLE_MAX_IMAGE_BYTES = 2 * 1024 * 1024
PEOPLE_MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_DOCUMENTS_PER_OWNER = 10


def _photo_api_path(kind: str, route_owner_id: int) -> str:
    """Authenticated retrieval path stored in User.image (not a public URL)."""
    if kind == "teacher":
        return f"/api/v1/school-admin/teachers/{route_owner_id}/photo"
    if kind == "staff":
        return f"/api/v1/school-admin/staff/{route_owner_id}/photo"
    return f"/api/v1/school-admin/students/{route_owner_id}/photo"


def _resolve_owner(
    db: Session, school_id: int, kind: str, route_owner_id: int
) -> tuple[User, int]:
    """Return (user, route_owner_id). route_owner_id is student.id or users.id."""
    if kind == "teacher":
        user, _staff = _owned_teacher(db, school_id, route_owner_id)
        return user, route_owner_id
    if kind == "staff":
        user, _staff = _owned_non_teaching_staff(db, school_id, route_owner_id)
        return user, route_owner_id
    if kind == "student":
        user_id = resolve_student_owner_user_id(db, school_id, route_owner_id)
        user = db.get(User, user_id)
        if user is None or user.school_id != school_id or user.deleted_at is not None:
            raise AcademicError(404, "Record not found")
        return user, route_owner_id
    raise AcademicError(422, "Invalid owner kind")


def _owned_document(
    db: Session, school_id: int, owner_user_id: int, document_id: int
) -> PersonDocument:
    row = db.get(PersonDocument, document_id)
    if (
        row is None
        or row.school_id != school_id
        or row.owner_user_id != owner_user_id
        or row.deleted_at is not None
    ):
        raise AcademicError(404, "Record not found")
    return row


def _validate_people_upload(
    data: bytes, *, category: str, claimed_filename: str | None, title: str | None
) -> tuple[str, str, str | None, str | None]:
    cat = (category or "").strip().lower()
    if cat not in store.DOC_CATEGORIES:
        raise AcademicError(
            422,
            "category must be one of: other, resume, id_proof, certificate, profile_photo",
        )
    try:
        content_type, ext = store._detect_type(data)
    except AcademicError as exc:
        # Contract uses 415 for wrong magic bytes.
        raise AcademicError(415, "Only PDF, JPG and PNG files are allowed") from exc

    if content_type in store.IMAGE_TYPES:
        if len(data) > PEOPLE_MAX_IMAGE_BYTES:
            raise AcademicError(413, "Image exceeds maximum allowed size of 2 MB")
    else:
        if len(data) > PEOPLE_MAX_FILE_BYTES:
            raise AcademicError(413, "File exceeds maximum allowed size of 5 MB")

    if cat in store.PHOTO_CATEGORIES and content_type not in store.IMAGE_TYPES:
        raise AcademicError(415, "profile_photo must be an image (JPEG, PNG, or WebP)")
    # Contract documents: PDF, JPEG, PNG (WebP allowed for photos only).
    if cat not in store.PHOTO_CATEGORIES and content_type == "image/webp":
        raise AcademicError(415, "Only PDF, JPG and PNG files are allowed")

    safe_name = store.sanitize_filename(claimed_filename)
    clean_title = None
    if title is not None and str(title).strip():
        clean_title = str(title).strip()[:120]
    return content_type, ext, safe_name, clean_title


def list_documents(
    db: Session,
    school_id: int,
    kind: str,
    route_owner_id: int,
    *,
    page: int,
    page_size: int,
    category: str | None,
) -> dict:
    user, route_id = _resolve_owner(db, school_id, kind, route_owner_id)
    page, page_size = _page(page, page_size)
    query = db.query(PersonDocument).filter(
        PersonDocument.school_id == school_id,
        PersonDocument.owner_user_id == user.id,
        PersonDocument.deleted_at.is_(None),
    )
    if category is not None and str(category).strip():
        cat = str(category).strip().lower()
        if cat not in store.DOC_CATEGORIES:
            raise AcademicError(422, "Invalid document category filter")
        query = query.filter(PersonDocument.category == cat)
    total = query.count()
    rows = (
        query.order_by(PersonDocument.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        document_public_item(row, owner_kind=kind, route_owner_id=route_id) for row in rows
    ]
    return _envelope(items, total, page, page_size)


def get_document(
    db: Session, school_id: int, kind: str, route_owner_id: int, document_id: int
) -> dict:
    user, route_id = _resolve_owner(db, school_id, kind, route_owner_id)
    row = _owned_document(db, school_id, user.id, document_id)
    return document_public_item(row, owner_kind=kind, route_owner_id=route_id)


def upload_document(
    db: Session,
    school_id: int,
    kind: str,
    route_owner_id: int,
    *,
    category: str,
    data: bytes,
    filename: str | None,
    title: str | None = None,
) -> dict:
    user, route_id = _resolve_owner(db, school_id, kind, route_owner_id)
    content_type, ext, safe_name, clean_title = _validate_people_upload(
        data, category=category, claimed_filename=filename, title=title
    )
    storage = store.get_storage()
    key = storage.build_key(school_id, user.id, ext)
    cat = category.strip().lower()
    prior: list[PersonDocument] = []
    if cat == "profile_photo":
        prior = (
            db.query(PersonDocument)
            .filter(
                PersonDocument.school_id == school_id,
                PersonDocument.owner_user_id == user.id,
                PersonDocument.category == "profile_photo",
                PersonDocument.deleted_at.is_(None),
            )
            .all()
        )
    else:
        doc_count = (
            db.query(PersonDocument)
            .filter(
                PersonDocument.school_id == school_id,
                PersonDocument.owner_user_id == user.id,
                PersonDocument.deleted_at.is_(None),
                PersonDocument.category != "profile_photo",
            )
            .count()
        )
        if doc_count >= MAX_DOCUMENTS_PER_OWNER:
            raise AcademicError(422, "A record may have at most 10 documents")

    storage.put(key, data)
    try:
        row = PersonDocument(
            school_id=school_id,
            owner_user_id=user.id,
            category=cat,
            title=clean_title or safe_name,
            storage_key=key,
            content_type=content_type,
            size_bytes=len(data),
            original_filename=safe_name,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(row)
        for old in prior:
            old.deleted_at = _now()
            old.updated_at = _now()
        if cat == "profile_photo":
            user.image = _photo_api_path(kind, route_id)
            user.updated_at = _now()
        _commit(db)
    except Exception:
        # Metadata was not saved: roll back and remove the file so it is not orphaned.
        db.rollback()
        store.discard(storage, key)
        raise
    for old in prior:
        store.discard(storage, old.storage_key)
    db.refresh(row)
    return document_public_item(row, owner_kind=kind, route_owner_id=route_id)


def download_document(
    db: Session, school_id: int, kind: str, route_owner_id: int, document_id: int
) -> tuple[bytes, str, str | None]:
    user, _route_id = _resolve_owner(db, school_id, kind, route_owner_id)
    row = _owned_document(db, school_id, user.id, document_id)
    data = store.get_storage().get(row.storage_key)
    return data, row.content_type, row.original_filename


def delete_document(
    db: Session, school_id: int, kind: str, route_owner_id: int, document_id: int
) -> dict:
    user, route_id = _resolve_owner(db, school_id, kind, route_owner_id)
    row = _owned_document(db, school_id, user.id, document_id)
    key = row.storage_key
    was_photo = row.category == "profile_photo"
    row.deleted_at = _now()
    row.updated_at = _now()
    photo_suffix = f"/{route_id}/photo"
    if was_photo and user.image and str(user.image).endswith(photo_suffix):
        user.image = None
        user.updated_at = _now()
    _commit(db)
    try:
        store.get_storage().delete(key)
    except AcademicError:
        pass
    return {"deleted": True}


def get_profile_photo_bytes(
    db: Session, school_id: int, kind: str, route_owner_id: int
) -> tuple[bytes, str]:
    user, _route_id = _resolve_owner(db, school_id, kind, route_owner_id)
    row = (
        db.query(PersonDocument)
        .filter(
            PersonDocument.school_id == school_id,
            PersonDocument.owner_user_id == user.id,
            PersonDocument.category == "profile_photo",
            PersonDocument.deleted_at.is_(None),
        )
        .order_by(PersonDocument.id.desc())
        .first()
    )
    if row is None:
        raise AcademicError(404, "Record not found")
    data = store.get_storage().get(row.storage_key)
    return data, row.content_type


def upload_photo(
    db: Session,
    school_id: int,
    kind: str,
    route_owner_id: int,
    *,
    data: bytes,
    filename: str | None,
) -> dict:
    """Contract-shaped photo upload → ``{ photo_url }``."""
    item = upload_document(
        db,
        school_id,
        kind,
        route_owner_id,
        category="profile_photo",
        data=data,
        filename=filename,
        title="Profile photo",
    )
    user, route_id = _resolve_owner(db, school_id, kind, route_owner_id)
    return {"photo_url": user.image or _photo_api_path(kind, route_id), "document": item}
