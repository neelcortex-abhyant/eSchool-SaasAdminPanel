"""Private document storage backends for teacher/staff uploads.

Default backend is ``none`` (not configured). Local private directory is supported
when ``DOCUMENT_STORAGE_BACKEND=local`` and ``DOCUMENT_STORAGE_PATH`` is set.
No S3/GCS/Azure provider is implemented in this repository.

The local backend only survives restarts and redeploys when DOCUMENT_STORAGE_PATH
sits on a persistent volume (on Render: an attached persistent disk). Roots inside
a public web directory are rejected.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.services.v1.school_academics import AcademicError

logger = logging.getLogger("eschool.document_storage")

NOT_CONFIGURED_DETAIL = (
    "Document storage is not configured. Set DOCUMENT_STORAGE_BACKEND=local "
    "and DOCUMENT_STORAGE_PATH to a private directory (not a public web root)."
)
UNAVAILABLE_DETAIL = "Document storage is unavailable. Try again later."
SUPPORTED_BACKENDS = frozenset({"local"})
# Directory names that conventionally hold web-served files. A storage root at or
# under one of these could make private documents reachable without auth.
PUBLIC_DIR_NAMES = frozenset({"public", "public_html", "static", "htdocs", "www", "wwwroot"})
STORAGE_EXTENSIONS = frozenset({"jpg", "png", "webp", "pdf", "doc", "docx"})

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


def _clean_setting(value: str | None) -> str:
    # Dashboard values are sometimes pasted with surrounding quotes.
    return (value or "").strip().strip("'\"").strip()


def storage_config_error() -> str | None:
    """Client-safe reason storage cannot be used, or None when it is usable."""
    settings = get_settings()
    backend = _clean_setting(settings.document_storage_backend).lower()
    path = _clean_setting(settings.document_storage_path)
    if backend in ("", "none"):
        return NOT_CONFIGURED_DETAIL
    if backend not in SUPPORTED_BACKENDS:
        return "Document storage backend is not supported. Set DOCUMENT_STORAGE_BACKEND=local."
    if not path:
        return "DOCUMENT_STORAGE_PATH is required when DOCUMENT_STORAGE_BACKEND=local."
    return unsafe_root_reason(Path(path))


def unsafe_root_reason(raw: Path) -> str | None:
    """Reject storage roots that are a filesystem root or inside a public web root."""
    resolved = raw.expanduser().resolve()
    if resolved.parent == resolved:
        return "DOCUMENT_STORAGE_PATH must not be a filesystem root."
    if any(part.lower() in PUBLIC_DIR_NAMES for part in resolved.parts):
        return "DOCUMENT_STORAGE_PATH must not be inside a public web root."
    return None


def storage_configured() -> bool:
    return storage_config_error() is None


def require_storage() -> None:
    reason = storage_config_error()
    if reason is not None:
        raise AcademicError(503, reason)


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


def _restrict(path: Path, mode: int) -> None:
    # POSIX permissions only; Windows ACLs are left to the host.
    if os.name != "nt":
        os.chmod(path, mode)


class LocalDocumentStorage:
    """Writes under a private root. Keys are opaque relative paths.

    Filesystem errors surface as 503 with a fixed message; paths never reach clients.
    """

    def __init__(self, root: str) -> None:
        reason = unsafe_root_reason(Path(root))
        if reason is not None:
            raise AcademicError(503, reason)
        self.root = Path(root).expanduser().resolve()
        try:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            _restrict(self.root, 0o700)
        except OSError as exc:
            logger.error("document_storage_root_unusable errno=%s", exc.errno)
            raise AcademicError(503, UNAVAILABLE_DETAIL) from None

    def build_key(self, school_id: int, owner_user_id: int, ext: str) -> str:
        ext = (ext or "").lower()
        if ext not in STORAGE_EXTENSIONS:
            raise AcademicError(422, "Unsupported file type")
        return f"{int(school_id)}/{int(owner_user_id)}/{uuid.uuid4().hex}.{ext}"

    def put(self, key: str, data: bytes) -> None:
        path = self._resolve(key)
        tmp_name: str | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Write to a sibling temp file then rename, so readers never see partial files.
            fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".upload-")
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            _restrict(Path(tmp_name), 0o600)
            os.replace(tmp_name, path)
            tmp_name = None
        except OSError as exc:
            logger.error("document_storage_write_failed errno=%s", exc.errno)
            raise AcademicError(503, UNAVAILABLE_DETAIL) from None
        finally:
            if tmp_name is not None:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass

    def get(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.is_file():
            raise AcademicError(404, "Document file not found")
        try:
            return path.read_bytes()
        except OSError as exc:
            logger.error("document_storage_read_failed errno=%s", exc.errno)
            raise AcademicError(503, UNAVAILABLE_DETAIL) from None

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        try:
            if path.is_file():
                path.unlink()
        except OSError as exc:
            logger.warning("document_storage_delete_failed errno=%s", exc.errno)

    def _resolve(self, key: str) -> Path:
        cleaned = (key or "").replace("\\", "/").lstrip("/")
        parts = cleaned.split("/")
        if not cleaned or "\x00" in cleaned or ":" in cleaned or ".." in parts:
            raise AcademicError(422, "Invalid storage key")
        path = (self.root / cleaned).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise AcademicError(422, "Invalid storage key") from exc
        return path


def discard(storage: LocalDocumentStorage, key: str | None) -> None:
    """Best-effort removal of a just-written file when its metadata was not saved."""
    if not key:
        return
    try:
        storage.delete(key)
    except AcademicError:
        pass


def get_storage() -> LocalDocumentStorage:
    require_storage()
    return LocalDocumentStorage(_clean_setting(get_settings().document_storage_path))
