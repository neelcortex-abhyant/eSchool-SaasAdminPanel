"""Super Admin payment reads. Mounted at /api/v1/super-admin/payments."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_super_admin
from app.schemas.v1.payments import PaymentTransactionListResponse, PaymentTransactionResponse
from app.services.v1.payment_history_service import (
    PaymentHistoryError,
    get_payment,
    list_payments,
    serialize_payments,
)

router = APIRouter(prefix="/payments", tags=["v1-super-admin-payments"])


def _http(exc: PaymentHistoryError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("", response_model=PaymentTransactionListResponse)
def list_admin_payments(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    school_id: int | None = Query(default=None, ge=1),
    status_filter: int | None = Query(default=None, alias="status", ge=0, le=4),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
) -> PaymentTransactionListResponse:
    try:
        rows, total = list_payments(
            db,
            school_id=school_id,
            status=status_filter,
            from_date=from_date,
            to_date=to_date,
            page=page,
            page_size=page_size,
        )
    except PaymentHistoryError as exc:
        raise _http(exc) from exc
    return PaymentTransactionListResponse(
        items=serialize_payments(db, rows),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{payment_id}", response_model=PaymentTransactionResponse)
def get_admin_payment(
    payment_id: int,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> PaymentTransactionResponse:
    try:
        row = get_payment(db, payment_id)
    except PaymentHistoryError as exc:
        raise _http(exc) from exc
    return serialize_payments(db, [row])[0]
