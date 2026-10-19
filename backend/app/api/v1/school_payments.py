"""School payment history and invoices. Mounted at /api/v1/schools/{school_id}/payments and /invoices."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, assert_school_scope
from app.api.v1.payments import require_payment_initiator
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.api.v1.super_admin.invoices import invoice_pdf_response, invoice_response
from app.schemas.v1.invoices import SubscriptionInvoiceListResponse, SubscriptionInvoiceResponse
from app.schemas.v1.payments import PaymentTransactionListResponse
from app.services.v1.invoice_service import InvoiceAccessError, get_invoice, list_invoices
from app.services.v1.payment_history_service import PaymentHistoryError, list_payments, require_school, serialize_payments

router = APIRouter(prefix="/schools", tags=["v1-school-payments"])


@router.get("/{school_id}/payments", response_model=PaymentTransactionListResponse)
def list_school_payments(
    school_id: int,
    auth: Annotated[AuthContext, Depends(require_payment_initiator)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: list[int] | None = Query(
        default=None,
        alias="status",
        description="Repeat to match any of several statuses, e.g. status=0&status=1.",
    ),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
) -> PaymentTransactionListResponse:
    if auth.user.role != ROLE_SUPER_ADMIN:
        assert_school_scope(auth, school_id)
    try:
        require_school(db, school_id)
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
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return PaymentTransactionListResponse(
        items=serialize_payments(db, rows),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{school_id}/invoices", response_model=SubscriptionInvoiceListResponse)
def list_school_invoices(
    school_id: int,
    auth: Annotated[AuthContext, Depends(require_payment_initiator)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    bill_id: int | None = Query(default=None, ge=1),
    subscription_id: int | None = Query(default=None, ge=1),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
) -> SubscriptionInvoiceListResponse:
    if auth.user.role != ROLE_SUPER_ADMIN:
        assert_school_scope(auth, school_id)
    try:
        require_school(db, school_id)
        rows, total = list_invoices(
            db,
            school_id=school_id,
            bill_id=bill_id,
            subscription_id=subscription_id,
            from_date=from_date,
            to_date=to_date,
            page=page,
            page_size=page_size,
        )
    except (PaymentHistoryError, InvoiceAccessError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return SubscriptionInvoiceListResponse(
        items=[invoice_response(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{school_id}/invoices/{invoice_id}", response_model=SubscriptionInvoiceResponse)
def get_school_invoice(
    school_id: int,
    invoice_id: int,
    auth: Annotated[AuthContext, Depends(require_payment_initiator)],
    db: Annotated[Session, Depends(central_db)],
) -> SubscriptionInvoiceResponse:
    if auth.user.role != ROLE_SUPER_ADMIN:
        assert_school_scope(auth, school_id)
    try:
        require_school(db, school_id)
        row = get_invoice(db, invoice_id, school_id=school_id)
    except (PaymentHistoryError, InvoiceAccessError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return invoice_response(row)


@router.get("/{school_id}/invoices/{invoice_id}/pdf")
def download_school_invoice(
    school_id: int,
    invoice_id: int,
    auth: Annotated[AuthContext, Depends(require_payment_initiator)],
    db: Annotated[Session, Depends(central_db)],
) -> Response:
    if auth.user.role != ROLE_SUPER_ADMIN:
        assert_school_scope(auth, school_id)
    try:
        require_school(db, school_id)
        row = get_invoice(db, invoice_id, school_id=school_id)
    except (PaymentHistoryError, InvoiceAccessError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return invoice_pdf_response(row)
