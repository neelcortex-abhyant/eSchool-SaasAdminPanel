"""Fernet encrypt/decrypt for school integration secrets.

Never log plaintext. When SCHOOL_SECRETS_KEY is missing/invalid, raise 503.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.services.v1.school_academics import AcademicError


def _fernet() -> Fernet:
    settings = get_settings()
    if not settings.school_secrets_configured:
        raise AcademicError(503, "School secrets encryption is not configured")
    key = settings.school_secrets_key.get_secret_value().strip().encode("utf-8")
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    """Return Fernet ciphertext as ascii text. Never logs plaintext."""
    if plaintext is None:
        raise AcademicError(422, "Secret value is required")
    token = _fernet().encrypt(str(plaintext).encode("utf-8"))
    return token.decode("ascii")


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt Fernet ciphertext. Raises 503 if key missing; 422 if token invalid."""
    if not ciphertext:
        raise AcademicError(422, "Secret is not configured")
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise AcademicError(422, "Secret could not be decrypted") from exc
