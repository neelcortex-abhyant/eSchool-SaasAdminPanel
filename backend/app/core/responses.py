"""Response envelopes used by the existing mobile API."""
from __future__ import annotations

SUCCESS = 200
INVALID_LOGIN = 101
VALIDATION_ERROR = 102
EXCEPTION_ERROR = 103
INVALID_PASSWORD = 109
INVALID_USER_DETAILS = 110
INACTIVE_CHILD = 115
INACTIVATED_USER = 116


def ok(message: str, data=None, code: int = SUCCESS, **extra) -> dict:
    body = {"error": False, "message": message, "data": data, "code": code}
    body.update(extra)
    return body


def fail(message: str, data=None, code: int = EXCEPTION_ERROR, details: str = "") -> dict:
    return {
        "error": True,
        "message": message,
        "data": data,
        "code": code,
        "details": details,
    }
