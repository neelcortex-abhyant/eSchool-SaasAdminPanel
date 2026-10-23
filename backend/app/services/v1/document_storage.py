"""Private document storage backends for teacher/staff uploads.

Default backend is ``none`` (not configured). Local private directory is supported
when ``DOCUMENT_STORAGE_BACKEND=local`` and ``DOCUMENT_STORAGE_PATH`` is set.
No S3/GCS/Azure provider is implemented in this repository.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.services.v1.school_academics import AcademicError

IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})
DOCUMENT_TYPES = frozenset({"application/pdf"})
# Office documents for study materials only (not person_documents categories).
OFFICE_DOCUMENT_TYPES = frozenset(
    {
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)
ALLOWED_TYPES = IMAGE_TYPES | DOCUMENT_TYPES
STUDY_MATERIAL_TYPES = ALLOWED_TYPES | OFFICE_DOCUMENT_TYPES
DOC_CATEGORIES = frozenset(
    {"other", "resume", "id_proof", "certificate", "profile_photo"}
)
PHOTO_CATEGORIES = frozenset({"profile_photo"})


def storage_configured() -> bool:
    return get_settings().document_storage_configured


def require_storage() -> None:
    if not storage_configured():
        raise AcademicError(
            503,
            "Document storage is not configured. Set DOCUMENT_STORAGE_BACKEND=local "
            "and DOCUMENT_STORAGE_PATH to a private directory (not a public web root).",
        )


def _detect_type(data: bytes) -> tuple[str, str]:
    if not data:
        raise AcademicError(422, "Empty file is not allowed")
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if data.startswith(b"%PDF"):
        return "application/pdf", "pdf"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    raise AcademicError(422, "Unsupported file type. Allowed: JPEG, PNG, WebP, PDF")


def _detect_office_type(data: bytes) -> tuple[str, str] | None:
    """Magic-byte detection for DOC/DOCX used by study materials."""
    if data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "application/msword", "doc"
    # DOCX is a ZIP; require PK header and a word/ path hint in the first chunk.
    if data.startswith(b"PK") and b"word/" in data[:8192]:
        return (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "docx",
        )
    return None


def detect_study_material_type(data: bytes) -> tuple[str, str]:
    """Return (content_type, extension) for study-material uploads."""
    try:
        return _detect_type(data)
    except AcademicError:
        office = _detect_office_type(data)
        if office is not None:
            return office
        raise AcademicError(
            422,
            "Unsupported file type. Allowed: JPEG, PNG, WebP, PDF, DOC, DOCX",
        ) from None


def validate_study_material_upload(
    data: bytes, *, claimed_filename: str | None
) -> tuple[str, str, str | None]:
    """Validate study-material binary; enforces size limits from settings."""
    content_type, ext = detect_study_material_type(data)
    settings = get_settings()
    if content_type in IMAGE_TYPES:
        if len(data) > settings.document_max_image_bytes:
            raise AcademicError(422, "Image exceeds maximum allowed size")
    else:
        if len(data) > settings.document_max_file_bytes:
            raise AcademicError(422, "File exceeds maximum allowed size")
    return content_type, ext, sanitize_filename(claimed_filename)


def sanitize_filename(name: str | None) -> str | None:
    if not name:
        return None
    base = Path(name).name.strip()
    if not base:
        return None
    base = re.sub(r"[^\w.\- ]+", "_", base, flags=re.UNICODE)
    return base[:255] or None


def validate_upload(
    data: bytes, *, category: str, claimed_filename: str | None
) -> tuple[str, str, str | None]:
    """Return (content_type, extension, sanitized_filename)."""
    cat = (category or "").strip().lower()
    if cat not in DOC_CATEGORIES:
        raise AcademicError(
            422,
            "category must be one of: other, resume, id_proof, certificate, profile_photo",
        )
    content_type, ext = _detect_type(data)
    settings = get_settings()
    if content_type in IMAGE_TYPES:
        if len(data) > settings.document_max_image_bytes:
            raise AcademicError(422, "Image exceeds maximum allowed size")
    else:
        if len(data) > settings.document_max_file_bytes:
            raise AcademicError(422, "File exceeds maximum allowed size")
    if cat in PHOTO_CATEGORIES and content_type not in IMAGE_TYPES:
        raise AcademicError(422, "profile_photo must be an image (JPEG, PNG, or WebP)")
    if cat == "resume" and content_type not in DOCUMENT_TYPES and content_type not in IMAGE_TYPES:
        raise AcademicError(422, "Unsupported file type for resume")
    return content_type, ext, sanitize_filename(claimed_filename)


class LocalDocumentStorage:
    """Writes under a private root. Keys are opaque relative paths."""

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def build_key(self, school_id: int, owner_user_id: int, ext: str) -> str:
        return f"{school_id}/{owner_user_id}/{uuid.uuid4().hex}.{ext}"

    def put(self, key: str, data: bytes) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.is_file():
            raise AcademicError(404, "Document file not found")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.is_file():
            path.unlink()

    def _resolve(self, key: str) -> Path:
        cleaned = key.replace("\\", "/").lstrip("/")
        if ".." in cleaned.split("/"):
            raise AcademicError(422, "Invalid storage key")
        path = (self.root / cleaned).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise AcademicError(422, "Invalid storage key") from exc
        return path


def get_storage() -> LocalDocumentStorage:
    require_storage()
    settings = get_settings()
    backend = (settings.document_storage_backend or "").strip().lower()
    if backend != "local":
        raise AcademicError(503, "Document storage backend is not available")
    return LocalDocumentStorage(settings.document_storage_path)
