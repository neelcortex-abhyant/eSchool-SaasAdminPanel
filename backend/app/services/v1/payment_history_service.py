"""Read-only payment history. Listing does not change payment, bill, or subscription rows."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tables import (
    PAYMENT_STATUS_AUTHORIZED,
    PAYMENT_STATUS_CAPTURED,
    PAYMENT_STATUS_CREATED,
    PAYMENT_STATUS_FAILED,
    PAYMENT_STATUS_REFUNDED,
    PaymentTransaction,
    School,
)
from app.services.v1.payment_verification_service import payment_status_name


VALID_STATUSES = frozenset(
    {
        PAYMENT_STATUS_CREATED,
        PAYMENT_STATUS_AUTHORIZED,
        PAYMENT_STATUS_CAPTURED,
        PAYMENT_STATUS_FAILED,
        PAYMENT_STATUS_REFUNDED,
    }
)


class PaymentHistoryError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def list_payments(
    db: Session,
    *,
    school_id: int | None = None,
    status: int | list[int] | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[PaymentTransaction], int]:
    if from_date is not None and to_date is not None and from_date > to_date:
        raise PaymentHistoryError("from_date must be on or before to_date", status_code=422)
    filters = _filters(school_id=school_id, status=status, from_date=from_date, to_date=to_date)
    total = int(db.scalar(select(func.count()).select_from(PaymentTransaction).where(*filters)) or 0)
    rows = list(
        db.scalars(
            select(PaymentTransaction)
            .where(*filters)
            .order_by(PaymentTransaction.created_at.desc().nulls_last(), PaymentTransaction.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return rows, total


def summarize_payments(
    db: Session,
    *,
    currency: str,
    school_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict:
    """Count payments by status and total captured paise, in one SQL aggregate.

    Only rows in ``currency`` are counted, so amounts are never mixed across
    currencies. Read-only.
    """
    if from_date is not None and to_date is not None and from_date > to_date:
        raise PaymentHistoryError("from_date must be on or before to_date", status_code=422)
    filters = _filters(school_id=school_id, status=None, from_date=from_date, to_date=to_date)
    filters.append(PaymentTransaction.currency == currency)

    def _count(*statuses: int):
        return func.count().filter(PaymentTransaction.status.in_(statuses))

    row = db.execute(
        select(
            func.coalesce(
                func.sum(PaymentTransaction.amount_paise).filter(
                    PaymentTransaction.status == PAYMENT_STATUS_CAPTURED
                ),
                0,
            ),
            _count(PAYMENT_STATUS_CAPTURED),
            _count(PAYMENT_STATUS_CREATED, PAYMENT_STATUS_AUTHORIZED),
            _count(PAYMENT_STATUS_FAILED),
            _count(PAYMENT_STATUS_REFUNDED),
            func.count(),
        ).where(*filters)
    ).one()
    paise = int(row[0] or 0)
    return {
        "currency": currency,
        "successful_amount_paise": paise,
        "successful_amount": paise / 100,
        "successful_count": int(row[1] or 0),
        "pending_count": int(row[2] or 0),
        "failed_count": int(row[3] or 0),
        "refunded_count": int(row[4] or 0),
        "total_count": int(row[5] or 0),
    }


def get_payment(db: Session, payment_id: int) -> PaymentTransaction:
    row = db.get(PaymentTransaction, payment_id)
    if row is None:
        raise PaymentHistoryError("Payment not found", status_code=404)
    return row


def require_school(db: Session, school_id: int) -> School:
    school = db.get(School, school_id)
    if school is None or school.deleted_at is not None:
        raise PaymentHistoryError("School not found", status_code=404)
    return school


def _filters(
    *,
    school_id: int | None,
    status: int | list[int] | None,
    from_date: date | None,
    to_date: date | None,
) -> list:
    filters = []
    if school_id is not None:
        filters.append(PaymentTransaction.school_id == school_id)
    if status is not None:
        statuses = [status] if isinstance(status, int) else list(status)
        if statuses:
            if any(value not in VALID_STATUSES for value in statuses):
                raise PaymentHistoryError("status must be from 0 through 4", status_code=422)
            filters.append(PaymentTransaction.status.in_(statuses))
    if from_date is not None:
        filters.append(PaymentTransaction.created_at >= datetime.combine(from_date, time.min))
    if to_date is not None:
        filters.append(PaymentTransaction.created_at < datetime.combine(to_date + timedelta(days=1), time.min))
    return filters


def serialize_payments(db: Session, rows: list[PaymentTransaction]) -> list:
    """Serialize rows with their invoice ids in one query."""
    from app.services.v1.invoice_service import invoice_ids_for_payments

    invoices = invoice_ids_for_payments(db, [row.id for row in rows])
    return [serialize_payment(row, invoice_id=invoices.get(row.id)) for row in rows]


def serialize_payment(row: PaymentTransaction, *, invoice_id: int | None = None):
    from app.schemas.v1.payments import PaymentTransactionResponse

    return PaymentTransactionResponse(
        id=row.id,
        school_id=row.school_id,
        bill_id=row.bill_id,
        gateway="razorpay",
        order_id=row.gateway_order_id,
        payment_id=row.gateway_payment_id,
        amount=int(row.amount_paise),
        currency=row.currency,
        status=payment_status_name(row.status),
        invoice_id=invoice_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
