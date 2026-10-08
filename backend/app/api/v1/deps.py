from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.v1_database import get_v1_db
from app.models.v1.roles import ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN
from app.models.v1.session import AuthSession
from app.models.v1.user import STATUS_ACTIVE, User
from app.services.v1 import auth_service

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: User
    session: AuthSession


def get_current_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_v1_db)],
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        user, session = auth_service.resolve_user_from_token(db, credentials.credentials)
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return AuthContext(user=user, session=session)


def get_current_user(auth: Annotated[AuthContext, Depends(get_current_auth)]) -> User:
    return auth.user


def require_super_admin(auth: Annotated[AuthContext, Depends(get_current_auth)]) -> AuthContext:
    """Allow only v1 users with role=super_admin. Unauthenticated → 401 via get_current_auth."""
    if auth.user.role != ROLE_SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return auth


def require_school_admin(auth: Annotated[AuthContext, Depends(get_current_auth)]) -> AuthContext:
    """Allow only active school_admin with a bound school_id."""
    if auth.user.role != ROLE_SCHOOL_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if auth.user.status != STATUS_ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")
    if auth.user.school_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No school assigned")
    return auth


def assert_school_scope(auth: AuthContext, school_id: int) -> None:
    """Deny access when authenticated school_admin targets another school.

    Super Admin bypasses. Never trusts client-supplied school_id as identity —
    compares path/resource school_id to server-side auth.user.school_id.
    """
    if auth.user.role == ROLE_SUPER_ADMIN:
        return
    if auth.user.role != ROLE_SCHOOL_ADMIN or auth.user.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
