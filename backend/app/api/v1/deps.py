from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.core.v1_database import get_v1_db
from app.models.tables import School
from app.models.v1.roles import ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN
from app.models.v1.session import AuthSession
from app.models.v1.user import STATUS_ACTIVE, User
from app.services.v1 import auth_service, rbac
from app.services.v1.school_service import INSTALLED_YES, STATUS_ACTIVE as SCHOOL_STATUS_ACTIVE
from app.services.v1.subscription_access import subscription_expiry_blocks_access

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


def require_school_admin(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    db: Annotated[Session, Depends(central_db)],
) -> AuthContext:
    """Allow only an active school_admin bound to an active, installed school.

    Login keeps auth_service.assert_school_admin_login_allowed. That helper returns
    when status is 1, even if installed is 0, so it is not used for these routes.
    """
    if auth.user.role != ROLE_SCHOOL_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if auth.user.status != STATUS_ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")
    if auth.user.school_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No school assigned")
    school = db.get(School, auth.user.school_id)
    if (
        school is not None
        and school.deleted_at is None
        and school.status == SCHOOL_STATUS_ACTIVE
        and school.installed == INSTALLED_YES
    ):
        if subscription_expiry_blocks_access(auth.user.school_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Subscription access is not available",
            )
        return auth
    if (
        school is not None
        and school.deleted_at is None
        and school.status != SCHOOL_STATUS_ACTIVE
        and school.installed != INSTALLED_YES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This school is waiting for approval. You can sign in after it is activated.",
        )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="School access is suspended")


def assert_school_permission(auth: AuthContext, db: Session, permission: str) -> None:
    """Deny a school_admin whose roles do not grant `permission` (services/v1/rbac.py).

    Call after require_school_admin. Roles are read from the DB on every request,
    so a role change applies to existing sessions immediately.
    """
    if permission not in rbac.permissions_for(db, auth.user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def require_school_permission(permission: str):
    """Dependency: an active school_admin (require_school_admin) holding `permission`."""

    def dependency(
        auth: Annotated[AuthContext, Depends(require_school_admin)],
        db: Annotated[Session, Depends(central_db)],
    ) -> AuthContext:
        assert_school_permission(auth, db, permission)
        return auth

    return dependency


def assert_school_scope(auth: AuthContext, school_id: int) -> None:
    """Deny access when authenticated school_admin targets another school.

    Super Admin bypasses. Never trusts client-supplied school_id as identity —
    compares path/resource school_id to server-side auth.user.school_id.
    """
    if auth.user.role == ROLE_SUPER_ADMIN:
        return
    if auth.user.role != ROLE_SCHOOL_ADMIN or auth.user.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
