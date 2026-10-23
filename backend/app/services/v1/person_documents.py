"""Teacher/staff private document metadata and upload orchestration."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.tables import PersonDocument, User
from app.services.v1 import document_storage as store
from app.services.v1.school_academics import AcademicError, _commit, _envelope, _now, _page
from app.services.v1.school_staff import _owned_non_teaching_staff
from app.services.v1.school_teachers import _owned_teacher


def _doc_item(row: PersonDocument) -> dict:
    """Public metadata — never includes storage_key or filesystem paths."""
    return {
        "id": row.id,
        "owner_user_id": row.owner_user_id,
        "category": row.category,
        "content_type": row.content_type,
        "size_bytes": row.size_bytes,
        "original_filename": row.original_filename,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _photo_api_path(kind: str, owner_user_id: int) -> str:
    """Authenticated retrieval path stored in User.image (not a public URL)."""
    if kind == "teacher":
        return f"/api/v1/school-admin/teachers/{owner_user_id}/photo"
    return f"/api/v1/school-admin/staff/{owner_user_id}/photo"


def _resolve_owner(db: Session, school_id: int, kind: str, owner_user_id: int) -> User:
    if kind == "teacher":
        user, _staff = _owned_teacher(db, school_id, owner_user_id)
        return user
    if kind == "staff":
        user, _staff = _owned_non_teaching_staff(db, school_id, owner_user_id)
        return user
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
        raise AcademicError(404, "Document not found")
    return row


def list_documents(
    db: Session,
    school_id: int,
    kind: str,
    owner_user_id: int,
    *,
    page: int,
    page_size: int,
    category: str | None,
) -> dict:
    _resolve_owner(db, school_id, kind, owner_user_id)
    page, page_size = _page(page, page_size)
    query = db.query(PersonDocument).filter(
        PersonDocument.school_id == school_id,
        PersonDocument.owner_user_id == owner_user_id,
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
    return _envelope([_doc_item(row) for row in rows], total, page, page_size)


def get_document(
    db: Session, school_id: int, kind: str, owner_user_id: int, document_id: int
) -> dict:
    _resolve_owner(db, school_id, kind, owner_user_id)
    return _doc_item(_owned_document(db, school_id, owner_user_id, document_id))


def upload_document(
    db: Session,
    school_id: int,
    kind: str,
    owner_user_id: int,
    *,
    category: str,
    data: bytes,
    filename: str | None,
) -> dict:
    user = _resolve_owner(db, school_id, kind, owner_user_id)
    content_type, ext, safe_name = store.validate_upload(
        data, category=category, claimed_filename=filename
    )
    storage = store.get_storage()
    key = storage.build_key(school_id, owner_user_id, ext)
    cat = category.strip().lower()
    prior: list[PersonDocument] = []
    if cat == "profile_photo":
        prior = (
            db.query(PersonDocument)
            .filter(
                PersonDocument.school_id == school_id,
                PersonDocument.owner_user_id == owner_user_id,
                PersonDocument.category == "profile_photo",
                PersonDocument.deleted_at.is_(None),
            )
            .all()
        )
    storage.put(key, data)
    row = PersonDocument(
        school_id=school_id,
        owner_user_id=owner_user_id,
        category=cat,
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
        user.image = _photo_api_path(kind, owner_user_id)
        user.updated_at = _now()
    _commit(db)
    for old in prior:
        try:
            storage.delete(old.storage_key)
        except AcademicError:
            pass
    db.refresh(row)
    return _doc_item(row)


def download_document(
    db: Session, school_id: int, kind: str, owner_user_id: int, document_id: int
) -> tuple[bytes, str, str | None]:
    _resolve_owner(db, school_id, kind, owner_user_id)
    row = _owned_document(db, school_id, owner_user_id, document_id)
    data = store.get_storage().get(row.storage_key)
    return data, row.content_type, row.original_filename


def delete_document(
    db: Session, school_id: int, kind: str, owner_user_id: int, document_id: int
) -> dict:
    user = _resolve_owner(db, school_id, kind, owner_user_id)
    row = _owned_document(db, school_id, owner_user_id, document_id)
    key = row.storage_key
    was_photo = row.category == "profile_photo"
    row.deleted_at = _now()
    row.updated_at = _now()
    photo_suffix = f"/{owner_user_id}/photo"
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
    db: Session, school_id: int, kind: str, owner_user_id: int
) -> tuple[bytes, str]:
    _resolve_owner(db, school_id, kind, owner_user_id)
    row = (
        db.query(PersonDocument)
        .filter(
            PersonDocument.school_id == school_id,
            PersonDocument.owner_user_id == owner_user_id,
            PersonDocument.category == "profile_photo",
            PersonDocument.deleted_at.is_(None),
        )
        .order_by(PersonDocument.id.desc())
        .first()
    )
    if row is None:
        raise AcademicError(404, "Profile photo not found")
    data = store.get_storage().get(row.storage_key)
    return data, row.content_type
