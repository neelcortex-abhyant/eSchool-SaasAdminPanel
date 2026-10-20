from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.auth import login_with_limits
from app.api.v1.deps import AuthContext, require_super_admin
from app.api.v1.super_admin import addons as addons_routes
from app.api.v1.super_admin import audit_logs as audit_logs_routes
from app.api.v1.super_admin import notifications as notifications_routes
from app.api.v1.super_admin import plans as plans_routes
from app.api.v1.super_admin import reports as reports_routes
from app.api.v1.super_admin import school_addons as school_addons_routes
from app.api.v1.super_admin import school_admins as school_admins_routes
from app.api.v1.super_admin import schools as schools_routes
from app.api.v1.super_admin import settings as settings_routes
from app.api.v1.super_admin import subscriptions as subscriptions_routes
from app.api.v1.super_admin import invoices as invoice_routes
from app.api.v1.super_admin import payments as payment_routes
from app.core.v1_database import get_v1_db
from app.schemas.v1.auth import AuthTokenResponse, LoginRequest, SignupRequest
from app.schemas.v1.dashboard import (
    DashboardStatsResponse,
    RecentActivitiesResponse,
    RecentSchoolsResponse,
    RegistrationAnalyticsResponse,
    SchoolStatusResponse,
    SubscriptionDistributionResponse,
    SuperAdminDashboardResponse,
)
from app.schemas.v1.users import UserResponse
from app.services.v1 import auth_service
from app.services.v1.dashboard_service import (
    dashboard_stats,
    platform_dashboard,
    recent_activities,
    recent_schools,
    registration_analytics,
    school_status_distribution,
    subscription_distribution,
)

router = APIRouter(prefix="/super-admin", tags=["v1-super-admin"])
router.include_router(schools_routes.router)
router.include_router(school_admins_routes.router)
router.include_router(plans_routes.router)
router.include_router(subscriptions_routes.router)
router.include_router(subscriptions_routes.platform_router)
router.include_router(payment_routes.router)
router.include_router(invoice_routes.router)
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
    request: Request,
    db: Annotated[Session, Depends(get_v1_db)],
) -> AuthTokenResponse:
    """Super Admin login — credentials + role=super_admin required. Shares the login rate limits."""
    issued = login_with_limits(
        request, body.email, lambda: auth_service.login_super_admin(db, email=body.email, password=body.password)
    )
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


@router.get("/dashboard/stats", response_model=DashboardStatsResponse)
def dashboard_statistics(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> DashboardStatsResponse:
    """Platform counts. Does not change GET /dashboard."""
    return DashboardStatsResponse(**dashboard_stats(db))


@router.get("/dashboard/recent-schools", response_model=RecentSchoolsResponse)
def dashboard_recent_schools(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> RecentSchoolsResponse:
    """Newest non-deleted schools. Does not change GET /dashboard or /dashboard/stats."""
    return RecentSchoolsResponse(**recent_schools(db, limit=limit))


@router.get("/dashboard/registrations", response_model=RegistrationAnalyticsResponse)
def dashboard_registrations(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    year: Annotated[int, Query(ge=2000, le=2100)],
) -> RegistrationAnalyticsResponse:
    """Monthly school registrations for one calendar year."""
    return RegistrationAnalyticsResponse(**registration_analytics(db, year=year))


@router.get("/dashboard/school-status", response_model=SchoolStatusResponse)
def dashboard_school_status(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolStatusResponse:
    """Active and inactive school counts. Same rules as dashboard stats."""
    return SchoolStatusResponse(**school_status_distribution(db))


@router.get("/dashboard/subscriptions", response_model=SubscriptionDistributionResponse)
def dashboard_subscriptions(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SubscriptionDistributionResponse:
    """Plan distribution for non-deleted schools. Does not change other dashboard routes."""
    return SubscriptionDistributionResponse(**subscription_distribution(db))


@router.get("/dashboard/recent-activities", response_model=RecentActivitiesResponse)
def dashboard_recent_activities(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> RecentActivitiesResponse:
    """Newest audit activities. Does not change other dashboard routes."""
    return RecentActivitiesResponse(**recent_activities(db, limit=limit))


@router.get("/ping")
def ping(auth: Annotated[AuthContext, Depends(require_super_admin)]) -> dict[str, str]:
    """Auth probe for Super Admin."""
    return {"status": "ok", "role": auth.user.role}
