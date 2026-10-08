"""Super Admin reports — /api/v1/super-admin/reports/..."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_super_admin
from app.schemas.v1.reports import (
    BillReportItem,
    BillReportResponse,
    SchoolReportItem,
    SchoolReportResponse,
    SubscriptionReportItem,
    SubscriptionReportResponse,
)
from app.services.v1 import report_service

router = APIRouter(prefix="/reports", tags=["v1-super-admin-reports"])


def _http(exc: report_service.ReportServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/schools", response_model=SchoolReportResponse)
def report_schools(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    status_filter: int | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> SchoolReportResponse:
    try:
        items, total = report_service.report_schools(
            db, status=status_filter, page=page, page_size=page_size
        )
    except report_service.ReportServiceError as exc:
        raise _http(exc) from exc
    return SchoolReportResponse(
        items=[SchoolReportItem.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/subscriptions", response_model=SubscriptionReportResponse)
def report_subscriptions(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    status_filter: int | None = Query(default=None, alias="status"),
    package_id: int | None = Query(default=None, ge=1),
    school_id: int | None = Query(default=None, ge=1),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> SubscriptionReportResponse:
    try:
        items, total = report_service.report_subscriptions(
            db,
            status=status_filter,
            package_id=package_id,
            school_id=school_id,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
        )
    except report_service.ReportServiceError as exc:
        raise _http(exc) from exc
    return SubscriptionReportResponse(
        items=[SubscriptionReportItem.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/bills", response_model=BillReportResponse)
def report_bills(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    status_filter: int | None = Query(default=None, alias="status"),
    school_id: int | None = Query(default=None, ge=1),
    subscription_id: int | None = Query(default=None, ge=1),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> BillReportResponse:
    try:
        items, amount_sum, total = report_service.report_bills(
            db,
            status=status_filter,
            school_id=school_id,
            subscription_id=subscription_id,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
        )
    except report_service.ReportServiceError as exc:
        raise _http(exc) from exc
    return BillReportResponse(
        items=[BillReportItem.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        amount_sum=amount_sum,
    )
