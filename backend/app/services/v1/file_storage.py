"""Private file storage for people photos and documents.

Files are stored under random keys and never served from a public path. A
caller gets a short-lived signed token (itsdangerous, keyed by session_secret)
and downloads through GET /api/v1/files/{token}.

Only the local disk backend exists today. An S3 backend needs save/read/delete
plus a signed_url that returns a presigned GET; callers use get_storage() only.
"""

from __future__ import annotations

import io
import secrets
from pathlib import Path

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import get_settings

PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
DOCUMENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}
PHOTO_MAX_BYTES = 2 * 1024 * 1024
DOCUMENT_MAX_BYTES = 5 * 1024 * 1024
DOCUMENTS_PER_RECORD = 10

# Served inline; anything else is sent as an attachment.
INLINE_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
EXTENSIONS = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

_SALT = "people-file-download"


class StorageError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def sniff_type(data: bytes) -> str | None:
    """Content type from the file's leading bytes. The name and header are ignored."""
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def reencode_image(data: bytes, content_type: str) -> bytes:
    """Decode and save the image again, dropping EXIF and anything appended to it.

    Without Pillow the bytes are kept as uploaded (the type was already sniffed).
    """
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - Pillow is optional
        return data
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            if image.width * image.height > 40_000_000:
                raise StorageError(413, "The image is too large")
            fmt = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}[content_type]
            if fmt == "JPEG" and image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            out = io.BytesIO()
            # A fresh save writes no EXIF, ICC or text chunks unless passed in.
            image.save(out, format=fmt)
            return out.getvalue()
    except StorageError:
        raise
    except Exception as exc:
        raise StorageError(415, "The image could not be read. Upload a JPG, PNG or WebP file.") from exc


def new_key(content_type: str) -> str:
    return f"{secrets.token_hex(2)}/{secrets.token_urlsafe(24)}.{EXTENSIONS.get(content_type, 'bin')}"


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise StorageError(404, "File not found")
        return path

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise StorageError(404, "File not found")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            path.unlink()


def get_storage() -> LocalStorage:
    settings = get_settings()
    if settings.file_storage_backend != "local":
        raise RuntimeError(f"Unsupported file_storage_backend: {settings.file_storage_backend}")
    root = Path(settings.file_storage_dir) if settings.file_storage_dir else Path(__file__).resolve().parents[3] / "var" / "uploads"
    return LocalStorage(root)


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().session_secret, salt=_SALT)


def sign(key: str, content_type: str, file_name: str) -> str:
    return _serializer().dumps({"k": key, "t": content_type, "n": file_name})


def unsign(token: str) -> dict:
    try:
        data = _serializer().loads(token, max_age=get_settings().file_url_ttl_seconds)
    except SignatureExpired as exc:
        raise StorageError(410, "This link has expired") from exc
    except BadSignature as exc:
        raise StorageError(404, "File not found") from exc
    if not isinstance(data, dict) or not isinstance(data.get("k"), str):
        raise StorageError(404, "File not found")
    return data
