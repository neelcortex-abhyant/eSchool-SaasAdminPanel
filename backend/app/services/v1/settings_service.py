"""Platform settings via existing system_settings table (Phase 8)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import SystemSetting

# Readable + writable non-secret platform keys.
PUBLIC_SETTING_KEYS = frozenset(
    {
        "app_name",
        "support_email",
        "support_phone",
        "currency",
        "timezone",
        "web_maintenance",
        "frontend_url",
        "default_language",
        "tagline",
    }
)

# Writable only — never returned in plaintext on GET.
SECRET_SETTING_KEYS = frozenset(
    {
        "smtp_password",
        "payment_secret_key",
        "firebase_private_key",
        "webhook_secret",
    }
)

ALLOWED_SETTING_KEYS = PUBLIC_SETTING_KEYS | SECRET_SETTING_KEYS


class SettingsServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def get_platform_settings(db: Session) -> dict:
    rows = list(db.scalars(select(SystemSetting).where(SystemSetting.name.in_(ALLOWED_SETTING_KEYS))))
    by_name = {r.name: r for r in rows}
    settings: dict[str, dict] = {}
    for key in sorted(ALLOWED_SETTING_KEYS):
        row = by_name.get(key)
        if key in SECRET_SETTING_KEYS:
            settings[key] = {
                "value": None,
                "secret": True,
                "configured": bool(row and row.data),
                "type": row.type if row else "secret",
            }
        else:
            settings[key] = {
                "value": row.data if row else None,
                "secret": False,
                "configured": row is not None,
                "type": row.type if row else "string",
            }
    return {"settings": settings}


def update_platform_settings(db: Session, updates: dict[str, str | None]) -> dict:
    if not updates:
        raise SettingsServiceError("No settings provided", status_code=422)
    unknown = set(updates) - ALLOWED_SETTING_KEYS
    if unknown:
        raise SettingsServiceError(
            f"Unknown or disallowed setting keys: {', '.join(sorted(unknown))}",
            status_code=422,
        )

    changed: list[str] = []
    for key, value in updates.items():
        if value is None:
            continue
        text = str(value)[:255]
        row = db.scalar(select(SystemSetting).where(SystemSetting.name == key))
        setting_type = "secret" if key in SECRET_SETTING_KEYS else "string"
        if row is None:
            db.add(SystemSetting(name=key, data=text, type=setting_type))
        else:
            row.data = text
            row.type = setting_type
        changed.append(key)
    if not changed:
        raise SettingsServiceError("No settings provided", status_code=422)
    db.commit()
    result = get_platform_settings(db)
    result["updated_keys"] = changed
    return result
