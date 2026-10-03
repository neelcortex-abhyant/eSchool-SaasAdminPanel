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
    db = session_factory()()
    try:
        yield db
    finally:
        db.close()


def open_named_db(database_name: str) -> Session:
    return session_factory(database_name)()


def admin_context(
    request: Request,
    central: Session = Depends(central_db),
) -> Tuple[Session, User, Optional[int]]:
    token = request.cookies.get("eschool_session")
    payload = read_session(token) if token else None
    if not payload:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Unauthenticated")
    database_name = payload.get("db")
    db = open_named_db(database_name) if database_name else central
    user = db.get(User, payload.get("uid"))
    if user is None or user.deleted_at is not None:
        if database_name:
            db.close()
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Unauthenticated")
    request.state.admin_db_owned = bool(database_name)
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
    """Resolve school-code + Bearer token to (school_db, user, school)."""
    if not school_code:
        raise ApiError(fail("School Code is Required", code=VALIDATION_ERROR))
    school = find_school(central, school_code)
    if school is None or not school.database_name:
        raise ApiError(fail("Invalid school code", code=VALIDATION_ERROR))
    db = open_named_db(school.database_name)
    try:
        user = find_token_user(db, _bearer(authorization))
        if user is None or user.deleted_at is not None:
            raise ApiError(fail("Unauthenticated.", code=401))
        yield db, user, school
    finally:
        db.close()
