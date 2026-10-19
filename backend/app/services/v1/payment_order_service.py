"""Create a Razorpay order for an existing subscription bill.

The charge amount comes from the bill. This service does not mark the bill
paid and does not activate or renew a subscription.

Idempotency: the caller supplies a key of 1 to 64 visible characters. The same
school and key, with the same bill, amount, and currency, returns the stored
row and does not call Razorpay again. A different bill, amount, or currency
for that key is rejected.

One order per bill: a bill has at most one transaction that is not refunded.
A request with a new key for a bill that already has a created or failed
order returns that order, because a Razorpay order accepts a new attempt
after a failed one. An authorized or captured order is a 409. A second
remote order is never opened while the first can still be paid.

Concurrency: the request takes a transaction advisory lock on the school and
idempotency key, then locks the bill, before calling Razorpay. The bill lock
serializes requests with different keys. The unique (school_id,
idempotency_key), gateway order id, and partial bill_id index are the backstop.

Lost gateway response: Razorpay's order API does not accept this idempotency
key, and the SDK retry is left off. If the gateway accepts an order and the
response or the local commit is lost, no payment row is stored. The error says
the order may already exist. A retry can create another remote order because
there is no local row to reuse. This service does not claim the remote order
was absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.tables import (
    PAYMENT_STATUS_AUTHORIZED,
    PAYMENT_STATUS_CAPTURED,
    PAYMENT_STATUS_CREATED,
    PAYMENT_STATUS_FAILED,
    PAYMENT_STATUS_REFUNDED,
    PaymentTransaction,
    School,
    Subscription,
    SubscriptionBill,
)
from app.models.v1.roles import ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN
from app.services.v1.plan_service import normalize_money
from app.services.v1.subscription_service import (
    BILL_STATUS_OVERDUE,
    BILL_STATUS_PENDING,
)

MIN_CHARGE_PAISE = 100
PAYABLE_BILL_STATUSES = frozenset({BILL_STATUS_PENDING, BILL_STATUS_OVERDUE})
# A Razorpay order accepts a new attempt after a failed payment.
REUSABLE_ORDER_STATUSES = frozenset({PAYMENT_STATUS_CREATED, PAYMENT_STATUS_FAILED})


class PaymentOrderError(Exception):
    def __init__(self, detail: str, status_code: int = 400, *, outcome_unknown: bool = False):
        self.detail = detail
        self.status_code = status_code
        self.outcome_unknown = outcome_unknown
        super().__init__(detail)


@dataclass(frozen=True)
class PaymentCaller:
    """Authenticated caller. School admins are limited to their own school."""

    role: str
    school_id: int | None = None


class OrderGateway(Protocol):
    def create_order(
        self,
        *,
        amount_paise: int,
        currency: str,
        receipt: str,
        notes: dict[str, str],
    ) -> dict:
        """Return the gateway order payload, including id, amount, and currency."""


def rupees_to_paise(amount: float) -> int:
    """Convert rupees to integer paise. Reject zero, negatives, and out-of-range amounts."""
    try:
        money = normalize_money(amount)
    except ValueError:
        raise ValueError("must be from 0.01 through 9999999999.99") from None
    if money <= 0:
        raise ValueError("must be positive")
    return int((money * 100).to_integral_value())


def create_payment_order(
    db: Session,
    bill_id: int,
    *,
    caller: PaymentCaller,
    idempotency_key: str | None,
    settings: Settings | None = None,
    gateway: OrderGateway | None = None,
) -> PaymentTransaction:
    """Create or reuse a gateway order for one bill. The bill status is not changed."""
    key = _clean_idempotency_key(idempotency_key)
    active_settings = settings if settings is not None else get_settings()
    currency = _currency(active_settings)
    bill, subscription = _load_bill_graph(db, bill_id)
    _authorize(caller, bill.school_id)
    _require_payable(bill)
    paise = _charge_paise(bill.amount)

    _lock_request(db, bill.school_id, key)
    locked = _lock_bill(db, bill.id, subscription.id)
    try:
        _require_payable(locked)
        paise = _charge_paise(locked.amount)
        existing = _existing_order(db, locked.school_id, key)
        if existing is not None:
            _require_same_request(existing, locked, paise, currency)
            existing_id = existing.id
            db.rollback()
            reloaded = db.get(PaymentTransaction, existing_id)
            if reloaded is None:
                raise PaymentOrderError("Payment order could not be reloaded", status_code=500)
            return reloaded
        open_order = _open_bill_order(db, locked.id)
        if open_order is not None:
            _require_reusable(open_order, locked, paise, currency)
            open_id = open_order.id
            db.rollback()
            reloaded = db.get(PaymentTransaction, open_id)
            if reloaded is None:
                raise PaymentOrderError("Payment order could not be reloaded", status_code=500)
            return reloaded

        active_gateway = gateway if gateway is not None else _build_gateway(active_settings)
        payload = active_gateway.create_order(
            amount_paise=paise,
            currency=currency,
            receipt=f"bill-{locked.id}"[:40],
            notes={
                "bill_id": str(locked.id),
                "school_id": str(locked.school_id),
                "subscription_id": str(locked.subscription_id),
            },
        )
        order_id, returned_amount, returned_currency = _validated_payload(payload)
        if returned_amount != paise or returned_currency != currency:
            raise PaymentOrderError(
                "Payment gateway response did not match the bill. The order may already exist.",
                status_code=502,
                outcome_unknown=True,
            )
    except PaymentOrderError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise PaymentOrderError(
            "Payment gateway did not confirm the order. It may already exist.",
            status_code=504,
            outcome_unknown=True,
        ) from exc

    saved_bill_id = locked.id
    saved_school_id = locked.school_id
    now = _utcnow()
    row = PaymentTransaction(
        bill_id=saved_bill_id,
        school_id=saved_school_id,
        gateway_order_id=order_id,
        gateway_payment_id=None,
        idempotency_key=key,
        amount_paise=paise,
        currency=currency,
        status=PAYMENT_STATUS_CREATED,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        winner = _existing_order(db, saved_school_id, key) or _open_bill_order(db, saved_bill_id)
        if (
            winner is not None
            and winner.status in REUSABLE_ORDER_STATUSES
            and _matches_values(winner, saved_bill_id, saved_school_id, paise, currency)
        ):
            return winner
        raise PaymentOrderError(
            "The order could not be recorded. It may already exist at the gateway.",
            status_code=500,
            outcome_unknown=True,
        ) from exc
    except Exception as exc:
        db.rollback()
        raise PaymentOrderError(
            "The order could not be recorded. It may already exist at the gateway.",
            status_code=500,
            outcome_unknown=True,
        ) from exc
    try:
        db.refresh(row)
    except Exception:
        return row
    return row


def _build_gateway(settings: Settings) -> OrderGateway:
    from app.services.v1.razorpay_client import RazorpayOrderGateway, validate_razorpay_credentials

    key_id, key_secret = validate_razorpay_credentials(settings)
    return RazorpayOrderGateway(key_id, key_secret)


def _currency(settings: Settings) -> str:
    from app.services.v1.razorpay_client import charge_currency

    return charge_currency(settings)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clean_idempotency_key(value: str | None) -> str:
    if value is None:
        raise PaymentOrderError("Idempotency key is required", status_code=422)
    key = value.strip()
    if not key or len(key) > 64 or any(ord(char) < 33 or ord(char) > 126 for char in key):
        raise PaymentOrderError(
            "Idempotency key must be 1 to 64 visible characters",
            status_code=422,
        )
    return key


def _authorize(caller: PaymentCaller, school_id: int) -> None:
    if caller.role == ROLE_SUPER_ADMIN:
        return
    if caller.role == ROLE_SCHOOL_ADMIN and caller.school_id == school_id:
        return
    raise PaymentOrderError("Forbidden", status_code=403)


def _load_bill_graph(db: Session, bill_id: int) -> tuple[SubscriptionBill, Subscription]:
    bill = db.get(SubscriptionBill, bill_id)
    if bill is None or bill.deleted_at is not None:
        raise PaymentOrderError("Bill not found", status_code=404)
    subscription = db.get(Subscription, bill.subscription_id)
    school = db.get(School, bill.school_id)
    if (
        subscription is None
        or subscription.deleted_at is not None
        or subscription.school_id != bill.school_id
        or school is None
        or school.deleted_at is not None
    ):
        raise PaymentOrderError("Subscription not found", status_code=404)
    return bill, subscription


def _lock_request(db: Session, school_id: int, idempotency_key: str) -> None:
    db.execute(
        text("SELECT pg_advisory_xact_lock(:school_id, hashtext(:idempotency_key))"),
        {"school_id": school_id, "idempotency_key": idempotency_key},
    )


def _lock_bill(db: Session, bill_id: int, subscription_id: int) -> SubscriptionBill:
    locked = db.scalar(
        select(SubscriptionBill).where(SubscriptionBill.id == bill_id).with_for_update()
    )
    if locked is None or locked.deleted_at is not None:
        db.rollback()
        raise PaymentOrderError("Bill not found", status_code=404)
    if locked.subscription_id != subscription_id:
        db.rollback()
        raise PaymentOrderError("Subscription not found", status_code=404)
    subscription = db.get(Subscription, locked.subscription_id)
    if (
        subscription is None
        or subscription.deleted_at is not None
        or subscription.school_id != locked.school_id
    ):
        db.rollback()
        raise PaymentOrderError("Subscription not found", status_code=404)
    return locked


def _require_payable(bill: SubscriptionBill) -> None:
    if bill.status not in PAYABLE_BILL_STATUSES:
        raise PaymentOrderError("Bill is not payable", status_code=422)


def _charge_paise(amount: float) -> int:
    try:
        paise = rupees_to_paise(amount)
    except ValueError:
        raise PaymentOrderError(
            "Bill amount must be from 0.01 through 9999999999.99",
            status_code=422,
        ) from None
    if paise < MIN_CHARGE_PAISE:
        raise PaymentOrderError("Bill amount is below the minimum charge of 1.00 INR", status_code=422)
    return paise


def _existing_order(db: Session, school_id: int, idempotency_key: str) -> PaymentTransaction | None:
    return db.scalar(
        select(PaymentTransaction).where(
            PaymentTransaction.school_id == school_id,
            PaymentTransaction.idempotency_key == idempotency_key,
        )
    )


def _open_bill_order(db: Session, bill_id: int) -> PaymentTransaction | None:
    """Return the bill's transaction that is not refunded. The partial index allows one."""
    return db.scalar(
        select(PaymentTransaction)
        .where(
            PaymentTransaction.bill_id == bill_id,
            PaymentTransaction.status != PAYMENT_STATUS_REFUNDED,
        )
        .order_by(PaymentTransaction.id)
        .limit(1)
    )


def _require_reusable(
    existing: PaymentTransaction,
    bill: SubscriptionBill,
    paise: int,
    currency: str,
) -> None:
    if existing.status == PAYMENT_STATUS_CAPTURED:
        raise PaymentOrderError("Bill already has a captured payment", status_code=409)
    if existing.status == PAYMENT_STATUS_AUTHORIZED:
        raise PaymentOrderError("A payment for this bill is awaiting capture", status_code=409)
    if not _matches(existing, bill, paise, currency):
        raise PaymentOrderError("The bill's open order does not match the bill", status_code=409)


def _matches(existing: PaymentTransaction, bill: SubscriptionBill, paise: int, currency: str) -> bool:
    return _matches_values(existing, bill.id, bill.school_id, paise, currency)


def _matches_values(
    existing: PaymentTransaction,
    bill_id: int,
    school_id: int,
    paise: int,
    currency: str,
) -> bool:
    return (
        existing.bill_id == bill_id
        and existing.school_id == school_id
        and existing.amount_paise == paise
        and existing.currency == currency
    )


def _require_same_request(
    existing: PaymentTransaction,
    bill: SubscriptionBill,
    paise: int,
    currency: str,
) -> None:
    if not _matches(existing, bill, paise, currency):
        raise PaymentOrderError("Idempotency key does not match this payment", status_code=409)


def _validated_payload(payload: object) -> tuple[str, int, str]:
    if not isinstance(payload, dict):
        raise PaymentOrderError(
            "Payment gateway did not confirm the order. It may already exist.",
            status_code=504,
            outcome_unknown=True,
        )
    order_id = str(payload.get("id") or "")
    if not order_id or len(order_id) > 64 or any(ord(char) < 33 or ord(char) > 126 for char in order_id):
        raise PaymentOrderError(
            "Payment gateway did not confirm the order. It may already exist.",
            status_code=504,
            outcome_unknown=True,
        )
    try:
        amount = int(payload.get("amount"))
    except (TypeError, ValueError):
        amount = -1
    currency = str(payload.get("currency") or "")
    return order_id, amount, currency
