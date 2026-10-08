from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_super_admin
from app.api.v1.super_admin import addons as addons_routes
from app.api.v1.super_admin import audit_logs as audit_logs_routes
from app.api.v1.super_admin import notifications as notifications_routes
from app.api.v1.super_admin import plans as plans_routes
from app.api.v1.super_admin import reports as reports_routes
from app.api.v1.super_admin import school_addons as school_addons_routes
from app.api.v1.super_admin import schools as schools_routes
from app.api.v1.super_admin import settings as settings_routes
from app.api.v1.super_admin import subscriptions as subscriptions_routes
from app.core.v1_database import get_v1_db
from app.schemas.v1.auth import AuthTokenResponse, LoginRequest, SignupRequest
from app.schemas.v1.dashboard import SuperAdminDashboardResponse
from app.schemas.v1.users import UserResponse
from app.services.v1 import auth_service
from app.services.v1.dashboard_service import platform_dashboard

router = APIRouter(prefix="/super-admin", tags=["v1-super-admin"])
router.include_router(schools_routes.router)
router.include_router(plans_routes.router)
router.include_router(subscriptions_routes.router)
router.include_router(addons_routes.router)
router.include_router(school_addons_routes.router)
router.include_router(reports_routes.router)
router.include_router(settings_routes.router)
router.include_router(audit_logs_routes.router)
router.include_router(notifications_routes.router)


def _token_response(issued: auth_service.IssuedSession) -> AuthTokenResponse:
    return AuthTokenResponse(
        access_token=issued.plain_token,
        token_type="bearer",
        expires_at=issued.expires_at,
        user=UserResponse.model_validate(issued.user),
    )


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: SignupRequest,
    db: Annotated[Session, Depends(get_v1_db)],
) -> AuthTokenResponse:
    """Bootstrap / gated Super Admin registration (reuses v1 user + session)."""
    try:
        issued = auth_service.register_super_admin(
            db,
            email=body.email,
            password=body.password,
            first_name=body.first_name,
            last_name=body.last_name,
            mobile=body.mobile,
        )
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _token_response(issued)


@router.post("/login", response_model=AuthTokenResponse)
def login(
    body: LoginRequest,
    db: Annotated[Session, Depends(get_v1_db)],
) -> AuthTokenResponse:
    """Super Admin login — credentials + role=super_admin required."""
    try:
        issued = auth_service.login_super_admin(db, email=body.email, password=body.password)
    except auth_service.AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _token_response(issued)


@router.get("/me", response_model=UserResponse)
def me(auth: Annotated[AuthContext, Depends(require_super_admin)]) -> UserResponse:
    """Super Admin profile — same UserResponse shape as /auth/me, role-gated."""
    return UserResponse.model_validate(auth.user)


@router.get("/dashboard", response_model=SuperAdminDashboardResponse)
def dashboard(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SuperAdminDashboardResponse:
    """Platform dashboard counts from existing School/Package/v1_users models."""
    return SuperAdminDashboardResponse(**platform_dashboard(db))


@router.get("/ping")
def ping(auth: Annotated[AuthContext, Depends(require_super_admin)]) -> dict[str, str]:
    """Auth probe for Super Admin."""
    return {"status": "ok", "role": auth.user.role}
