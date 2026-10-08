"""Super Admin school subscriptions + bills — /api/v1/super-admin/schools/{id}/subscriptions."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_super_admin
from app.schemas.v1.subscriptions import (
    SubscriptionBillCreateRequest,
    SubscriptionBillListResponse,
    SubscriptionBillResponse,
    SubscriptionBillStatusRequest,
    SubscriptionCreateRequest,
    SubscriptionListResponse,
    SubscriptionResponse,
    SubscriptionStatusRequest,
    SubscriptionUpdateRequest,
)
from app.services.v1 import audit_service, subscription_service

router = APIRouter(prefix="/schools/{school_id}/subscriptions", tags=["v1-super-admin-subscriptions"])


def _http(exc: subscription_service.SubscriptionServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def create_subscription(
    school_id: int,
    body: SubscriptionCreateRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SubscriptionResponse:
    try:
        sub = subscription_service.create_subscription(
            db,
            school_id,
            package_id=body.package_id,
            start_date=body.start_date,
            end_date=body.end_date,
            cycle=body.cycle,
            auto_renew=body.auto_renew,
            status=body.status,
        )
    except subscription_service.SubscriptionServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="subscription.create", entity_type="subscription",
        entity_id=sub.id, school_id=school_id, metadata={"package_id": sub.package_id, "status": sub.status},
    )
    return SubscriptionResponse.model_validate(sub)


@router.get("", response_model=SubscriptionListResponse)
def list_subscriptions(
    school_id: int,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: int | None = Query(default=None, alias="status"),
) -> SubscriptionListResponse:
    try:
        rows, total = subscription_service.list_subscriptions(
            db,
            school_id,
            page=page,
            page_size=page_size,
            status=status_filter,
        )
    except subscription_service.SubscriptionServiceError as exc:
        raise _http(exc) from exc
    return SubscriptionListResponse(
        items=[SubscriptionResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
def get_subscription(
    school_id: int,
    subscription_id: int,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SubscriptionResponse:
    try:
        sub = subscription_service.get_subscription(db, school_id, subscription_id)
    except subscription_service.SubscriptionServiceError as exc:
        raise _http(exc) from exc
    return SubscriptionResponse.model_validate(sub)


@router.patch("/{subscription_id}", response_model=SubscriptionResponse)
def patch_subscription(
    school_id: int,
    subscription_id: int,
    body: SubscriptionUpdateRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SubscriptionResponse:
    try:
        sub = subscription_service.update_subscription(
            db,
            school_id,
            subscription_id,
            package_id=body.package_id,
            start_date=body.start_date,
            end_date=body.end_date,
            cycle=body.cycle,
            auto_renew=body.auto_renew,
        )
    except subscription_service.SubscriptionServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="subscription.update", entity_type="subscription",
        entity_id=sub.id, school_id=school_id, metadata={"package_id": sub.package_id},
    )
    return SubscriptionResponse.model_validate(sub)


@router.patch("/{subscription_id}/status", response_model=SubscriptionResponse)
def patch_subscription_status(
    school_id: int,
    subscription_id: int,
    body: SubscriptionStatusRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SubscriptionResponse:
    try:
        sub = subscription_service.set_subscription_status(
            db, school_id, subscription_id, status=body.status
        )
    except subscription_service.SubscriptionServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="subscription.status", entity_type="subscription",
        entity_id=sub.id, school_id=school_id, metadata={"status": sub.status},
    )
    return SubscriptionResponse.model_validate(sub)


@router.post(
    "/{subscription_id}/bills",
    response_model=SubscriptionBillResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_bill(
    school_id: int,
    subscription_id: int,
    body: SubscriptionBillCreateRequest,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SubscriptionBillResponse:
    try:
        bill = subscription_service.create_bill(
            db,
            school_id,
            subscription_id,
            period_start=body.period_start,
            period_end=body.period_end,
            amount=body.amount,
            due_date=body.due_date,
            description=body.description,
            status=body.status,
        )
    except subscription_service.SubscriptionServiceError as exc:
        raise _http(exc) from exc
    return SubscriptionBillResponse.model_validate(bill)


@router.get("/{subscription_id}/bills", response_model=SubscriptionBillListResponse)
def list_bills(
    school_id: int,
    subscription_id: int,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: int | None = Query(default=None, alias="status"),
) -> SubscriptionBillListResponse:
    try:
        rows, total = subscription_service.list_bills(
            db,
            school_id,
            subscription_id,
            page=page,
            page_size=page_size,
            status=status_filter,
        )
    except subscription_service.SubscriptionServiceError as exc:
        raise _http(exc) from exc
    return SubscriptionBillListResponse(
        items=[SubscriptionBillResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{subscription_id}/bills/{bill_id}", response_model=SubscriptionBillResponse)
def get_bill(
    school_id: int,
    subscription_id: int,
    bill_id: int,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SubscriptionBillResponse:
    try:
        bill = subscription_service.get_bill(db, school_id, subscription_id, bill_id)
    except subscription_service.SubscriptionServiceError as exc:
        raise _http(exc) from exc
    return SubscriptionBillResponse.model_validate(bill)


@router.patch(
    "/{subscription_id}/bills/{bill_id}/status",
    response_model=SubscriptionBillResponse,
)
def patch_bill_status(
    school_id: int,
    subscription_id: int,
    bill_id: int,
    body: SubscriptionBillStatusRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SubscriptionBillResponse:
    try:
        bill = subscription_service.set_bill_status(
            db, school_id, subscription_id, bill_id, status=body.status
        )
    except subscription_service.SubscriptionServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="bill.status", entity_type="subscription_bill",
        entity_id=bill.id, school_id=school_id, metadata={"status": bill.status, "amount": bill.amount},
    )
    return SubscriptionBillResponse.model_validate(bill)
