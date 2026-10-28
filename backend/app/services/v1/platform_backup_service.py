"""Super Admin platform backup / restore job metadata.

Blocker: full ``pg_dump`` against Neon is not wired. When storage is configured we
write an encrypted metadata-only artifact and set ``status=metadata_only``.
Restore never drops or reloads the live database — it only records a restore request
when ``ALLOW_BACKUP_RESTORE`` is true and confirmation == ``RESTORE``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.tables import PlatformBackup
from app.models.v1.user import User
from app.services.v1 import audit_service
from app.services.v1.school_academics import AcademicError, _commit, _envelope, _now, _page
from app.services.v1 import school_secrets_crypto as secrets_crypto


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _item(row: PlatformBackup) -> dict:
    """Metadata only — never include dump bytes."""
    return {
        "id": row.id,
        "created_by": row.created_by,
        "status": row.status,
        "size_bytes": row.size_bytes,
        "checksum": row.checksum,
        "storage_uri": row.storage_uri,
        "error_message": row.error_message,
        "expires_at": _iso(row.expires_at),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def create_backup(db: Session, actor: User) -> dict:
    settings = get_settings()
    if not settings.backup_storage_configured:
        raise AcademicError(503, "Backup storage is not configured")

    now = _now()
    retention = max(1, int(settings.backup_retention_days or 30))
    expires_at = now + timedelta(days=retention)

    row = PlatformBackup(
        created_by=str(actor.id),
        status="pending",
        expires_at=expires_at,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    _commit(db)
    db.refresh(row)

    storage_root = Path(settings.backup_storage_path.strip())
    try:
        storage_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        row.status = "failed"
        row.error_message = "Could not create backup storage directory"
        row.updated_at = _now()
        _commit(db)
        raise AcademicError(503, "Backup storage is not writable") from exc

    # Metadata-only artifact: not a real pg_dump. Full dump blocked pending ops approval.
    meta = {
        "note": "logical backup metadata only",
        "created_at": now.isoformat(),
        "backup_id": row.id,
        "blocker": "full pg_dump against Neon is not wired",
    }
    plain = (
        "-- eSchool platform backup metadata (not a database dump)\n"
        + json.dumps(meta, separators=(",", ":"))
        + "\n"
    )
    try:
        # Prefer Fernet when school secrets key is set; otherwise write plaintext
        # bytes still marked metadata_only (never claim a successful dump).
        if settings.school_secrets_configured:
            payload = secrets_crypto.encrypt_secret(plain).encode("ascii")
            suffix = ".enc"
        else:
            payload = plain.encode("utf-8")
            suffix = ".meta"
        path = storage_root / f"platform_backup_{row.id}{suffix}"
        path.write_bytes(payload)
        checksum = hashlib.sha256(payload).hexdigest()
        row.status = "metadata_only"
        row.size_bytes = len(payload)
        row.checksum = checksum
        row.storage_uri = str(path)
        row.error_message = (
            "Full pg_dump is not wired; metadata-only artifact written. "
            "Ops approval required before enabling real Neon dumps."
        )
        row.updated_at = _now()
        _commit(db)
    except AcademicError:
        row.status = "failed"
        row.error_message = "Failed to encrypt backup metadata"
        row.updated_at = _now()
        _commit(db)
        raise
    except OSError as exc:
        row.status = "failed"
        row.error_message = "Failed to write backup artifact"
        row.updated_at = _now()
        _commit(db)
        raise AcademicError(503, "Failed to write backup artifact") from exc

    db.refresh(row)
    audit_service.record_audit(
        db,
        actor=actor,
        action="backup.create",
        entity_type="platform_backup",
        entity_id=row.id,
        metadata={"status": row.status, "checksum": row.checksum},
    )
    return _item(row)


def list_backups(db: Session, *, page: int = 1, page_size: int = 20) -> dict:
    page, page_size = _page(page, page_size)
    base = select(PlatformBackup)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.order_by(PlatformBackup.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return _envelope([_item(r) for r in rows], total, page, page_size)


def get_backup(db: Session, backup_id: int) -> dict:
    row = db.get(PlatformBackup, backup_id)
    if row is None:
        raise AcademicError(404, "Backup not found")
    return _item(row)


def request_restore(db: Session, actor: User, backup_id: int, confirmation: str) -> dict:
    settings = get_settings()
    if not settings.allow_backup_restore:
        raise AcademicError(403, "Backup restore is disabled")
    if (confirmation or "").strip() != "RESTORE":
        raise AcademicError(422, 'confirmation must be exactly "RESTORE"')

    row = db.get(PlatformBackup, backup_id)
    if row is None:
        raise AcademicError(404, "Backup not found")
    now = _now()
    if row.expires_at is not None and row.expires_at < now:
        raise AcademicError(422, "Backup has expired and cannot be restored")

    # Safe no-op: record restore request only — never drop/restore Neon.
    row.status = "restored_requested"
    row.updated_at = now
    _commit(db)
    db.refresh(row)
    audit_service.record_audit(
        db,
        actor=actor,
        action="backup.restore_requested",
        entity_type="platform_backup",
        entity_id=row.id,
        metadata={"status": row.status, "confirmation": "RESTORE"},
    )
    return {
        **_item(row),
        "message": (
            "Restore request recorded. No database drop/restore was performed. "
            "Full Neon restore remains blocked pending ops approval."
        ),
    }
