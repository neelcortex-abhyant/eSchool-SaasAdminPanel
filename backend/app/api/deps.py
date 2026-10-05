from __future__ import annotations

from collections.abc import Generator
from typing import Optional, Tuple

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.database import session_factory
from app.core.responses import VALIDATION_ERROR, fail
from app.core.security import read_session
from app.models.tables import School, User
from app.services.mobile_auth import find_school, find_token_user


class ApiError(Exception):
    """Raised by dependencies to return a Laravel-shaped JSON envelope (HTTP 200)."""

    def __init__(self, payload: dict):
        self.payload = payload


def central_db() -> Generator[Session, None, None]:
    """Shared Neon session (formerly the central MySQL database)."""
    db = session_factory()()
    try:
        yield db
    finally:
        db.close()


def open_named_db(_database_name: str | None = None) -> Session:
    """Compatibility shim.

    Historically opened a per-school MySQL database named ``database_name``.
    All schools now share one Neon database; isolation is via ``school_id``.
    Callers must still filter by school. The argument is ignored.
    """
    return session_factory()()


def school_is_ready(school: School | None) -> bool:
    return school is not None and school.deleted_at is None and school.installed == 1


def assert_user_in_school(user: User, school: School) -> bool:
    """Prevent cross-school access when the user is school-scoped."""
    if user.school_id is None:
        return True
    return user.school_id == school.id


def admin_context(
    request: Request,
    central: Session = Depends(central_db),
) -> Tuple[Session, User, Optional[int]]:
    token = request.cookies.get("eschool_session")
    payload = read_session(token) if token else None
    if not payload:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Unauthenticated")
    # Single Neon DB: always use the shared session. Cookie `db` is legacy metadata only.
    db = central
    user = db.get(User, payload.get("uid"))
    if user is None or user.deleted_at is not None:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Unauthenticated")
    # If the cookie carries a school code, enforce school_id match for school admins.
    code = payload.get("code")
    if code:
        school = find_school(db, code)
        if school is None or not assert_user_in_school(user, school):
            from fastapi import HTTPException

            raise HTTPException(status_code=401, detail="Unauthenticated")
        if user.school_id is not None and user.school_id != school.id:
            from fastapi import HTTPException

            raise HTTPException(status_code=403, detail="Cross-school access denied")
    request.state.admin_db_owned = False
    request.state.admin_db = db
    return db, user, user.school_id


def close_admin_db(request: Request) -> None:
    db = getattr(request.state, "admin_db", None)
    if getattr(request.state, "admin_db_owned", False) and db is not None:
        db.close()


def school_code_header(school_code: Optional[str] = Header(default=None, alias="school-code")) -> Optional[str]:
    return school_code


def _bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return authorization.strip()


def require_tenant_user(
    school_code: Optional[str] = Header(default=None, alias="school-code"),
    authorization: Optional[str] = Header(default=None),
    central: Session = Depends(central_db),
) -> Generator[Tuple[Session, User, School], None, None]:
    """Resolve school-code + Bearer token to (db, user, school) on the shared Neon DB."""
    if not school_code:
        raise ApiError(fail("School Code is Required", code=VALIDATION_ERROR))
    school = find_school(central, school_code)
    if not school_is_ready(school):
        raise ApiError(fail("Invalid school code", code=VALIDATION_ERROR))
    assert school is not None
    # Same Neon session; do not open a second physical database.
    db = central
    user = find_token_user(db, _bearer(authorization))
    if user is None or user.deleted_at is not None:
        raise ApiError(fail("Unauthenticated.", code=401))
    if not assert_user_in_school(user, school):
        raise ApiError(fail("Unauthenticated.", code=401))
    yield db, user, school
