"""Super Admin school subscriptions + bills — /api/v1/super-admin/schools/{id}/subscriptions."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_super_admin
from app.schemas.v1.subscriptions import (
    SubscriptionBillCreateRequest,
    SubscriptionBillListResponse,
    SubscriptionBillResponse,
    SubscriptionBillStatusRequest,
    PlatformSubscriptionListResponse,
    PlatformSubscriptionResponse,
    SubscriptionCreateRequest,
    SubscriptionExpireResponse,
    SubscriptionListResponse,
    SubscriptionRenewalListResponse,
    SubscriptionRenewalResponse,
    SubscriptionResponse,
    SubscriptionStatusRequest,
    SubscriptionUpdateRequest,
)
from app.services.v1 import audit_service, subscription_service

router = APIRouter(prefix="/schools/{school_id}/subscriptions", tags=["v1-super-admin-subscriptions"])
platform_router = APIRouter(prefix="/subscriptions", tags=["v1-super-admin-subscriptions"])


def _http(exc: subscription_service.SubscriptionServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _audited(db: Session, detail: str, work, audit):
    """Run work uncommitted, then commit it with the audit row."""
    try:
        result = work()
    except subscription_service.SubscriptionServiceError as exc:
        db.rollback()
        raise _http(exc) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail=detail) from None
    try:
        audit(result)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail=detail) from None
    return result


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def create_subscription(
    school_id: int,
    body: SubscriptionCreateRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SubscriptionResponse:
    sub = _audited(
        db,
        "Subscription could not be recorded",
        lambda: subscription_service.create_subscription(
            db,
            school_id,
            package_id=body.package_id,
            start_date=body.start_date,
            end_date=body.end_date,
            cycle=body.cycle,
            auto_renew=body.auto_renew,
            status=body.status,
            commit=False,
        ),
        lambda created: audit_service.record_audit(
            db,
            actor=auth.user,
            action="subscription.create",
            entity_type="subscription",
            entity_id=created.id,
            school_id=school_id,
            metadata={"package_id": created.package_id, "status": created.status},
        ),
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
    sub = _audited(
        db,
        "Subscription could not be recorded",
        lambda: subscription_service.update_subscription(
            db,
            school_id,
            subscription_id,
            package_id=body.package_id,
            start_date=body.start_date,
            end_date=body.end_date,
            cycle=body.cycle,
            auto_renew=body.auto_renew,
            commit=False,
        ),
        lambda updated: audit_service.record_audit(
            db,
            actor=auth.user,
            action="subscription.update",
            entity_type="subscription",
            entity_id=updated.id,
            school_id=school_id,
            metadata={"package_id": updated.package_id},
        ),
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
    sub = _audited(
        db,
        "Subscription could not be recorded",
        lambda: subscription_service.set_subscription_status(
            db, school_id, subscription_id, status=body.status, commit=False
        ),
        lambda updated: audit_service.record_audit(
            db,
            actor=auth.user,
            action="subscription.status",
            entity_type="subscription",
            entity_id=updated.id,
            school_id=school_id,
            metadata={"status": updated.status},
        ),
    )
    return SubscriptionResponse.model_validate(sub)


@router.post("/{subscription_id}/renew", response_model=SubscriptionResponse)
def renew_subscription(
    school_id: int,
    subscription_id: int,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SubscriptionResponse:
    try:
        sub = subscription_service.renew_subscription(
            db, school_id, subscription_id, commit=False
        )
    except subscription_service.SubscriptionServiceError as exc:
        raise _http(exc) from exc
    try:
        # record_audit commits this session, including the uncommitted renewal.
        audit_service.record_audit(
            db,
            actor=auth.user,
            action="subscription.renew",
            entity_type="subscription",
            entity_id=sub.id,
            school_id=school_id,
            metadata={
                "package_id": sub.package_id,
                "cycle": sub.cycle,
                "start_date": sub.start_date.isoformat(),
                "end_date": sub.end_date.isoformat(),
                "status": sub.status,
            },
        )
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Renewal could not be recorded") from None
    return SubscriptionResponse.model_validate(sub)


@router.get("/{subscription_id}/renewals", response_model=SubscriptionRenewalListResponse)
def list_renewals(
    school_id: int,
    subscription_id: int,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> SubscriptionRenewalListResponse:
    try:
        rows, total = subscription_service.list_renewals(
            db,
            school_id,
            subscription_id,
            page=page,
            page_size=page_size,
        )
    except subscription_service.SubscriptionServiceError as exc:
        raise _http(exc) from exc
    return SubscriptionRenewalListResponse(
        items=[SubscriptionRenewalResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@platform_router.get("", response_model=PlatformSubscriptionListResponse)
def list_platform_subscriptions(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, description="Case-insensitive partial match on school name."),
    status_filter: int | None = Query(default=None, alias="status", ge=0, le=3),
    package_id: int | None = Query(default=None, ge=1),
    school_id: int | None = Query(default=None, ge=1),
    sort: Literal["end_date", "-end_date", "created_at", "-created_at"] = Query(
        default="end_date",
        description="end_date, -end_date, created_at, or -created_at. Default is end_date, then id.",
    ),
) -> PlatformSubscriptionListResponse:
    try:
        rows, total = subscription_service.list_platform_subscriptions(
            db,
            page=page,
            page_size=page_size,
            q=q,
            status=status_filter,
            package_id=package_id,
            school_id=school_id,
            sort=sort,
        )
    except subscription_service.SubscriptionServiceError as exc:
        raise _http(exc) from exc
    items = []
    for sub, school_name, plan_name in rows:
        payload = SubscriptionResponse.model_validate(sub).model_dump()
        payload["school_name"] = school_name
        payload["plan_name"] = plan_name
        items.append(PlatformSubscriptionResponse.model_validate(payload))
    return PlatformSubscriptionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@platform_router.post("/expire-due", response_model=SubscriptionExpireResponse)
def expire_due_subscriptions(
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SubscriptionExpireResponse:
    """Expire active subscriptions whose end date is before today's UTC date.

    No scheduler calls this. An external cron can invoke it. School activation
    is not changed.
    """
    try:
        expired = subscription_service.expire_due_subscriptions(db, commit=False)
        if expired:
            audit_service.record_audit(
                db,
                actor=auth.user,
                action="subscription.expire",
                entity_type="subscription",
                entity_id=None,
                school_id=None,
                metadata={"expired": expired},
            )
        else:
            db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Subscriptions could not be expired") from None
    return SubscriptionExpireResponse(expired=expired)


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
    bill = _audited(
        db,
        "Bill status could not be recorded",
        lambda: subscription_service.set_bill_status(
            db, school_id, subscription_id, bill_id, status=body.status, commit=False
        ),
        lambda updated: audit_service.record_audit(
            db,
            actor=auth.user,
            action="bill.status",
            entity_type="subscription_bill",
            entity_id=updated.id,
            school_id=school_id,
            metadata={"status": updated.status, "amount": updated.amount},
        ),
    )
    return SubscriptionBillResponse.model_validate(bill)
