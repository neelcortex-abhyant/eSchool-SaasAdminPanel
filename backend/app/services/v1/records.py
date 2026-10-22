"""Helpers shared by the School Admin academics and people services.

Errors follow the v1 shapes: 404 {"detail": "Record not found"}, 409 with a
sentence the UI shows as is, and 422 as a FastAPI-style list whose loc names
the body field, so the UI can place each message next to its field.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Union

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

PAGE_SIZE_MAX = 50
NOT_FOUND = "Record not found"

Loc = Union[str, tuple]


class RecordError(Exception):
    def __init__(self, status_code: int, detail) -> None:
        self.status_code = status_code
        self.detail = detail


def _loc(field: Loc) -> list:
    parts = field if isinstance(field, tuple) else tuple(str(field).split("."))
    return ["body", *[int(p) if isinstance(p, str) and p.isdigit() else p for p in parts]]


class FieldErrors:
    """Collects 422 messages so a form gets every problem at once. First message per field wins."""

    def __init__(self) -> None:
        self._items: dict[tuple, str] = {}

    def add(self, field: Loc, message: str) -> None:
        key = tuple(_loc(field))
        self._items.setdefault(key, message)

    def has(self, field: Loc) -> bool:
        return tuple(_loc(field)) in self._items

    def __bool__(self) -> bool:
        return bool(self._items)

    def raise_if_any(self) -> None:
        if self._items:
            raise RecordError(
                422,
                [{"loc": list(loc), "msg": msg, "type": "value_error"} for loc, msg in self._items.items()],
            )


def invalid(field: Loc, message: str):
    errors = FieldErrors()
    errors.add(field, message)
    errors.raise_if_any()


def not_found():
    raise RecordError(404, NOT_FOUND)


def conflict(message: str):
    raise RecordError(409, message)


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def today() -> date:
    return date.today()


def clean(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def optional(value) -> str | None:
    text = clean(value)
    return text or None


def paging(page: int, page_size: int) -> tuple[int, int]:
    return max(page, 1), page_size if 1 <= page_size <= PAGE_SIZE_MAX else 20


def envelope(items: list, total: int, page: int, page_size: int) -> dict:
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def status_filter(status: str | None) -> int | None:
    return int(status) if status in ("0", "1") else None


def as_status(value) -> int:
    return 0 if value in (0, "0") else 1


def commit(db: Session, message: str = "A record with these details already exists") -> None:
    """Commit, turning a unique-index race into 409 after the service's own checks passed."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RecordError(409, message) from exc


def lock(db: Session, name: str, school_id: int) -> None:
    """Serialize a per-school sequence (admission numbers, employee codes) for this transaction."""
    from sqlalchemy import text

    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"{name}:{school_id}"})


def years_between(start: date, end: date) -> int:
    years = end.year - start.year
    if (end.month, end.day) < (start.month, start.day):
        years -= 1
    return years
