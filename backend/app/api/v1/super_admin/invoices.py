"""Super Admin invoice reads. Mounted at /api/v1/super-admin/invoices."""

from __future__ import annotations

from typing import Annotated

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_super_admin
from app.schemas.v1.invoices import SubscriptionInvoiceListResponse, SubscriptionInvoiceResponse
from app.services.v1.invoice_pdf import invoice_filename, render_invoice_pdf
from app.services.v1.invoice_service import InvoiceAccessError, get_invoice, list_invoices

router = APIRouter(prefix="/invoices", tags=["v1-super-admin-invoices"])


def _http(exc: InvoiceAccessError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def invoice_response(row) -> SubscriptionInvoiceResponse:
    rate = None if row.tax_rate_percent is None else format(row.tax_rate_percent, "f")
    return SubscriptionInvoiceResponse(
        id=row.id,
        invoice_number=row.invoice_number,
        issued_at=row.issued_at,
        payment_transaction_id=row.payment_transaction_id,
        bill_id=row.bill_id,
        school_id=row.school_id,
        subscription_id=row.subscription_id,
        package_id=row.package_id,
        gateway=row.gateway,
        order_id=row.gateway_order_id,
        payment_id=row.gateway_payment_id,
        currency=row.currency,
        amount=int(row.amount_paise),
        tax_label=row.tax_label,
        tax_rate_percent=rate,
        tax_amount=None if row.tax_amount_paise is None else int(row.tax_amount_paise),
        total_amount=int(row.total_amount_paise),
        school_name=row.school_name,
        school_address=row.school_address,
        school_email=row.school_email,
        school_phone=row.school_phone,
        plan_name=row.plan_name,
        plan_description=row.plan_description,
        cycle=row.cycle,
        period_start=row.period_start,
        period_end=row.period_end,
    )


def invoice_pdf_response(row) -> Response:
    payload = render_invoice_pdf(row)
    filename = invoice_filename(row.invoice_number)
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("", response_model=SubscriptionInvoiceListResponse)
def list_admin_invoices(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    school_id: int | None = Query(default=None, ge=1),
    bill_id: int | None = Query(default=None, ge=1),
    subscription_id: int | None = Query(default=None, ge=1),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
) -> SubscriptionInvoiceListResponse:
    try:
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
    except InvoiceAccessError as exc:
        raise _http(exc) from exc
    return SubscriptionInvoiceListResponse(
        items=[invoice_response(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{invoice_id}", response_model=SubscriptionInvoiceResponse)
def get_admin_invoice(
    invoice_id: int,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SubscriptionInvoiceResponse:
    try:
        row = get_invoice(db, invoice_id)
    except InvoiceAccessError as exc:
        raise _http(exc) from exc
    return invoice_response(row)


@router.get("/{invoice_id}/pdf")
def download_admin_invoice(
    invoice_id: int,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> Response:
    try:
        row = get_invoice(db, invoice_id)
    except InvoiceAccessError as exc:
        raise _http(exc) from exc
    return invoice_pdf_response(row)
