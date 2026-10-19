"""Issue a subscription receipt when a payment is captured.

Issued rows are immutable. A price, school, or plan correction must be a new
credit note that references invoice_number. Do not update these columns.
Refunds do not rewrite the receipt.

No GST rate, GSTIN, seller address, or tax-invoice wording is stored. Tax
columns remain null until a tax configuration exists. Null means tax is not
configured, not that the sale is exempt or zero-rated.

Invoice numbers are SUB-YYYY-NNNNNN. The year counter row is locked with
FOR UPDATE. The payment transaction id is unique, so a repeated capture
returns the existing receipt.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.tables import (
    PAYMENT_STATUS_CAPTURED,
    Package,
    PaymentTransaction,
    School,
    Subscription,
    SubscriptionBill,
    SubscriptionInvoice,
    SubscriptionInvoiceCounter,
)


class InvoiceAccessError(Exception):
    def __init__(self, detail: str, status_code: int = 404):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def issue_invoice_for_captured_payment(db: Session, payment: PaymentTransaction) -> SubscriptionInvoice | None:
    """Insert one receipt for a captured payment. Does not commit."""
    if payment.status != PAYMENT_STATUS_CAPTURED or not payment.gateway_payment_id:
        return None
    existing = db.scalar(
        select(SubscriptionInvoice)
        .where(SubscriptionInvoice.payment_transaction_id == payment.id)
        .with_for_update()
    )
    if existing is not None:
        return existing
    snapshot = _snapshot(db, payment)
    if snapshot is None:
        return None
    issued_at = _utcnow()
    invoice = SubscriptionInvoice(
        invoice_number=_allocate_invoice_number(db, issued_at),
        issued_at=issued_at,
        payment_transaction_id=payment.id,
        gateway="razorpay",
        gateway_order_id=payment.gateway_order_id,
        gateway_payment_id=payment.gateway_payment_id,
        currency=payment.currency,
        amount_paise=int(payment.amount_paise),
        tax_label=None,
        tax_rate_percent=None,
        tax_amount_paise=None,
        total_amount_paise=int(payment.amount_paise),
        **snapshot,
    )
    try:
        with db.begin_nested():
            db.add(invoice)
            db.flush()
    except IntegrityError:
        found = db.scalar(
            select(SubscriptionInvoice).where(SubscriptionInvoice.payment_transaction_id == payment.id)
        )
        if found is None:
            raise
        return found
    return invoice


def find_invoice_for_payment(db: Session, payment_transaction_id: int) -> SubscriptionInvoice | None:
    return db.scalar(
        select(SubscriptionInvoice).where(SubscriptionInvoice.payment_transaction_id == payment_transaction_id)
    )


def invoice_ids_for_payments(db: Session, payment_transaction_ids: list[int]) -> dict[int, int]:
    """Map payment transaction id to invoice id for the given payments."""
    if not payment_transaction_ids:
        return {}
    rows = db.execute(
        select(SubscriptionInvoice.payment_transaction_id, SubscriptionInvoice.id).where(
            SubscriptionInvoice.payment_transaction_id.in_(payment_transaction_ids)
        )
    ).all()
    return {int(payment_id): int(invoice_id) for payment_id, invoice_id in rows}


def get_invoice(db: Session, invoice_id: int, *, school_id: int | None = None) -> SubscriptionInvoice:
    row = db.get(SubscriptionInvoice, invoice_id)
    if row is None or (school_id is not None and row.school_id != school_id):
        raise InvoiceAccessError("Invoice not found", status_code=404)
    return row


def list_invoices(
    db: Session,
    *,
    school_id: int | None = None,
    bill_id: int | None = None,
    subscription_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[SubscriptionInvoice], int]:
    """List issued invoices, newest first. Dates filter issued_at (UTC, inclusive days)."""
    if from_date is not None and to_date is not None and from_date > to_date:
        raise InvoiceAccessError("from_date must be on or before to_date", status_code=422)
    filters = []
    if school_id is not None:
        filters.append(SubscriptionInvoice.school_id == school_id)
    if bill_id is not None:
        filters.append(SubscriptionInvoice.bill_id == bill_id)
    if subscription_id is not None:
        filters.append(SubscriptionInvoice.subscription_id == subscription_id)
    if from_date is not None:
        filters.append(SubscriptionInvoice.issued_at >= datetime.combine(from_date, time.min))
    if to_date is not None:
        filters.append(SubscriptionInvoice.issued_at < datetime.combine(to_date + timedelta(days=1), time.min))
    total = int(db.scalar(select(func.count()).select_from(SubscriptionInvoice).where(*filters)) or 0)
    rows = list(
        db.scalars(
            select(SubscriptionInvoice)
            .where(*filters)
            .order_by(SubscriptionInvoice.issued_at.desc(), SubscriptionInvoice.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return rows, total


def _snapshot(db: Session, payment: PaymentTransaction) -> dict | None:
    bill = db.get(SubscriptionBill, payment.bill_id)
    school = db.get(School, payment.school_id)
    if (
        bill is None
        or school is None
        or bill.deleted_at is not None
        or school.deleted_at is not None
        or bill.school_id != payment.school_id
    ):
        return None
    subscription = db.get(Subscription, bill.subscription_id)
    if subscription is None or subscription.deleted_at is not None or subscription.school_id != payment.school_id:
        return None
    plan = db.get(Package, subscription.package_id)
    if plan is None:
        return None
    return {
        "bill_id": bill.id,
        "school_id": school.id,
        "subscription_id": subscription.id,
        "package_id": plan.id,
        "school_name": school.name or "",
        "school_address": school.address or "",
        "school_email": school.support_email or "",
        "school_phone": school.support_phone or "",
        "plan_name": plan.name or "",
        "plan_description": plan.description,
        "cycle": subscription.cycle,
        "period_start": bill.period_start,
        "period_end": bill.period_end,
    }


def _allocate_invoice_number(db: Session, issued_at: datetime) -> str:
    year = issued_at.year
    counter = db.scalar(
        select(SubscriptionInvoiceCounter)
        .where(SubscriptionInvoiceCounter.year == year)
        .with_for_update()
    )
    if counter is None:
        counter = SubscriptionInvoiceCounter(year=year, last_value=0)
        try:
            with db.begin_nested():
                db.add(counter)
                db.flush()
        except IntegrityError:
            counter = db.scalar(
                select(SubscriptionInvoiceCounter)
                .where(SubscriptionInvoiceCounter.year == year)
                .with_for_update()
            )
            if counter is None:
                raise
    counter.last_value += 1
    db.flush()
    return f"SUB-{year}-{counter.last_value:06d}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
