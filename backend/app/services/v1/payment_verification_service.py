"""Checkout verification and Razorpay webhook processing.

A bill is marked paid only when the gateway reports the payment captured:
either a signed payment.captured webhook, or a verify call whose gateway
fetch returns status captured with the order's amount and currency. The
checkout callback alone moves a payment to authorized and does not pay.

Capture marks the matching bill paid once and issues one invoice. It does not
renew or activate the subscription. Renewal already extends the term and
creates the pending bill before payment, so capture must not extend that term
again. A capture on a cancelled or deleted bill does not pay that bill or
issue an invoice. It is recorded for a manual refund.

A full refund (refund.processed) moves a captured payment to refunded. The
bill, subscription, and invoice are not changed. A partial refund is recorded
only.

A lost order-create response can still leave a remote order with no local row.
This phase does not close that gap.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from razorpay.errors import SignatureVerificationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.tables import (
    PAYMENT_STATUS_AUTHORIZED,
    PAYMENT_STATUS_CAPTURED,
    PAYMENT_STATUS_CREATED,
    PAYMENT_STATUS_FAILED,
    PAYMENT_STATUS_REFUNDED,
    PaymentTransaction,
    PaymentWebhookEvent,
    SubscriptionBill,
)
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User
from app.services.v1 import audit_service
from app.services.v1.payment_order_service import PaymentCaller, PaymentOrderError
from app.services.v1.subscription_service import BILL_STATUS_CANCELLED, BILL_STATUS_PAID

PAYMENT_STATUS_NAMES = {
    PAYMENT_STATUS_CREATED: "created",
    PAYMENT_STATUS_AUTHORIZED: "authorized",
    PAYMENT_STATUS_CAPTURED: "captured",
    PAYMENT_STATUS_FAILED: "failed",
    PAYMENT_STATUS_REFUNDED: "refunded",
}

# Webhook event outcomes stored on payment_webhook_events.outcome.
OUTCOME_APPLIED = "applied"
OUTCOME_IGNORED = "ignored"
OUTCOME_STALE = "stale"
OUTCOME_AMOUNT_MISMATCH = "amount_mismatch"
OUTCOME_PAYMENT_CONFLICT = "payment_conflict"
OUTCOME_BILL_NOT_PAYABLE = "bill_not_payable"
OUTCOME_PARTIAL_REFUND = "partial_refund"
OUTCOME_UNKNOWN_PAYMENT = "unknown_payment"

_TERMINAL = frozenset({PAYMENT_STATUS_CAPTURED, PAYMENT_STATUS_REFUNDED})
_EVENT_TARGETS = {
    "payment.captured": PAYMENT_STATUS_CAPTURED,
    "payment.failed": PAYMENT_STATUS_FAILED,
    "payment.authorized": PAYMENT_STATUS_AUTHORIZED,
    "payment.pending": None,
}
_REFUND_EVENTS = frozenset({"refund.processed"})
_REMOTE_TARGETS = {
    "captured": PAYMENT_STATUS_CAPTURED,
    "authorized": PAYMENT_STATUS_AUTHORIZED,
    "failed": PAYMENT_STATUS_FAILED,
}
_MAX_WEBHOOK_BYTES = 262144


def payment_status_name(status: int) -> str:
    return PAYMENT_STATUS_NAMES.get(status, "created")


class PaymentFetcher(Protocol):
    def fetch_payment(self, payment_id: str) -> dict | None:
        """Return the gateway payment entity, or None when the gateway cannot be reached."""


@dataclass(frozen=True)
class WebhookOutcome:
    status_code: int
    detail: str = "Webhook received"


@dataclass(frozen=True)
class _ParsedEvent:
    event_id: str
    event_type: str
    kind: str
    order_id: str | None = None
    payment_id: str | None = None
    amount: int | None = None
    currency: str | None = None
    amount_refunded: int | None = None


def verify_checkout_payment(
    db: Session,
    *,
    caller: PaymentCaller,
    actor: User | None,
    order_id: str,
    payment_id: str,
    signature: str,
    settings: Settings,
    fetcher: PaymentFetcher | None = None,
) -> PaymentTransaction:
    """Bind a signed payment id to the local order and apply the gateway state.

    The checkout signature proves the payment belongs to the order. The
    gateway fetch supplies the amount, currency, and status. A captured
    payment marks the bill paid once and issues one invoice. When the gateway
    cannot be reached, the payment is authorized and the webhook finishes it.
    """
    from app.services.v1.razorpay_client import validate_razorpay_credentials, verify_checkout_signature

    if not _visible_id(order_id, 64) or not _visible_id(payment_id, 64) or not signature:
        raise PaymentOrderError("Payment signature is invalid", status_code=400)
    key_id, key_secret = validate_razorpay_credentials(settings)
    found = db.scalar(select(PaymentTransaction).where(PaymentTransaction.gateway_order_id == order_id))
    if found is None:
        raise PaymentOrderError("Payment not found", status_code=404)
    if caller.role != ROLE_SUPER_ADMIN and caller.school_id != found.school_id:
        db.rollback()
        raise PaymentOrderError("Forbidden", status_code=403)
    try:
        verify_checkout_signature(
            key_id=key_id,
            key_secret=key_secret,
            order_id=order_id,
            payment_id=payment_id,
            signature=signature,
        )
    except SignatureVerificationError:
        db.rollback()
        raise PaymentOrderError("Payment signature is invalid", status_code=400) from None
    except Exception:
        db.rollback()
        raise PaymentOrderError("Payment signature is invalid", status_code=400) from None
    db.rollback()

    remote = _fetch_remote(fetcher if fetcher is not None else _build_fetcher(settings), payment_id)

    row = db.scalar(
        select(PaymentTransaction)
        .where(PaymentTransaction.gateway_order_id == order_id)
        .with_for_update()
    )
    if row is None:
        db.rollback()
        raise PaymentOrderError("Payment not found", status_code=404)
    target = PAYMENT_STATUS_AUTHORIZED
    if remote is not None:
        if not _remote_matches(remote, row, order_id, payment_id):
            audit_service.record_audit(
                db,
                actor=actor,
                action="payment.verify_mismatch",
                entity_type="payment_transaction",
                entity_id=row.id,
                school_id=row.school_id,
                metadata=_remote_metadata(remote, payment_id),
                commit=False,
            )
            _commit_or_raise(db)
            raise PaymentOrderError("Payment does not match the order", status_code=409)
        target = _REMOTE_TARGETS.get(str(remote.get("status") or ""), PAYMENT_STATUS_AUTHORIZED)

    try:
        binding = _bind_payment_id(db, row, payment_id, target)
    except _PaymentConflict:
        db.rollback()
        raise PaymentOrderError("Payment is linked to a different transaction", status_code=409) from None
    if binding == _STALE:
        db.rollback()
        raise PaymentOrderError("Payment is linked to a different transaction", status_code=409)
    changed = binding == _BOUND
    changed = _transition(row, target, rebound=changed) or changed
    settled = False
    if row.status == PAYMENT_STATUS_CAPTURED and target == PAYMENT_STATUS_CAPTURED:
        settled = _settle_capture(db, row, actor=actor) != _SETTLE_NONE
    if not changed and not settled:
        existing_id = row.id
        db.rollback()
        reloaded = db.get(PaymentTransaction, existing_id)
        if reloaded is None:
            raise PaymentOrderError("Payment not found", status_code=404)
        return reloaded
    if changed:
        row.updated_at = _utcnow()
        audit_service.record_audit(
            db,
            actor=actor,
            action="payment.verify",
            entity_type="payment_transaction",
            entity_id=row.id,
            school_id=row.school_id,
            metadata={"status": row.status, "order_id": row.gateway_order_id},
            commit=False,
        )
    _commit_or_raise(db)
    try:
        db.refresh(row)
    except Exception:
        return row
    return row


def process_razorpay_webhook(
    db: Session,
    *,
    raw_body: bytes,
    signature: str,
    event_id: str,
    settings: Settings,
) -> WebhookOutcome:
    """Apply one signed webhook. Invalid signatures do not write."""
    from app.services.v1.razorpay_client import verify_webhook_signature, webhook_secret

    if len(raw_body) > _MAX_WEBHOOK_BYTES:
        raise PaymentOrderError("Webhook event is invalid", status_code=400)
    secret = webhook_secret(settings)
    if not signature or not _visible_id(event_id, 128):
        raise PaymentOrderError("Webhook signature is invalid", status_code=400)
    try:
        verify_webhook_signature(body=raw_body, signature=signature, secret=secret)
    except SignatureVerificationError:
        raise PaymentOrderError("Webhook signature is invalid", status_code=400) from None
    except Exception:
        raise PaymentOrderError("Webhook signature is invalid", status_code=400) from None
    event = _parse_event(raw_body, event_id)
    try:
        return _apply_event(db, event)
    except PaymentOrderError:
        raise
    except IntegrityError:
        db.rollback()
        if _find_event(db, event.event_id) is not None:
            return WebhookOutcome(200)
        raise PaymentOrderError("Payment could not be recorded", status_code=500) from None
    except Exception:
        db.rollback()
        raise PaymentOrderError("Payment could not be recorded", status_code=500) from None


def _apply_event(db: Session, event: _ParsedEvent) -> WebhookOutcome:
    if _find_event(db, event.event_id) is not None:
        db.rollback()
        return WebhookOutcome(200)
    if event.kind == "other":
        _add_event(db, event, None, OUTCOME_IGNORED)
        db.commit()
        return WebhookOutcome(200)
    if event.kind == "refund":
        return _apply_refund(db, event)
    row = db.scalar(
        select(PaymentTransaction)
        .where(PaymentTransaction.gateway_order_id == event.order_id)
        .with_for_update()
    )
    if row is None:
        db.rollback()
        raise PaymentOrderError("Payment order is not available yet", status_code=503)
    if event.amount != row.amount_paise or event.currency != row.currency:
        _record_problem(db, row, event, "payment.mismatch", OUTCOME_AMOUNT_MISMATCH)
        db.commit()
        return WebhookOutcome(200)
    target = _EVENT_TARGETS[event.event_type]
    row_id = row.id
    try:
        binding = _bind_payment_id(db, row, event.payment_id, target)
    except _PaymentConflict:
        db.rollback()
        conflict_row = db.get(PaymentTransaction, row_id)
        if conflict_row is not None:
            _record_problem(db, conflict_row, event, "payment.conflict", OUTCOME_PAYMENT_CONFLICT, link=False)
        else:
            _add_event(db, event, None, OUTCOME_PAYMENT_CONFLICT)
        db.commit()
        return WebhookOutcome(409, "Payment is linked to a different transaction")
    if binding == _STALE:
        _add_event(db, event, row.id, OUTCOME_STALE)
        db.commit()
        return WebhookOutcome(200)
    changed = _transition(row, target, rebound=binding == _BOUND)
    outcome = OUTCOME_APPLIED if changed or binding == _BOUND else OUTCOME_STALE
    if target == PAYMENT_STATUS_CAPTURED and row.status == PAYMENT_STATUS_CAPTURED:
        settle = _settle_capture(db, row, actor=None)
        if settle == _SETTLE_REFUSED:
            outcome = OUTCOME_BILL_NOT_PAYABLE
        elif settle == _SETTLE_DONE:
            outcome = OUTCOME_APPLIED
    if changed:
        row.updated_at = _utcnow()
    _add_event(db, event, row.id, outcome)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return WebhookOutcome(200)


def _apply_refund(db: Session, event: _ParsedEvent) -> WebhookOutcome:
    row = db.scalar(
        select(PaymentTransaction)
        .where(PaymentTransaction.gateway_payment_id == event.payment_id)
        .with_for_update()
    )
    if row is None:
        _add_event(db, event, None, OUTCOME_UNKNOWN_PAYMENT)
        db.commit()
        return WebhookOutcome(200)
    if event.currency != row.currency:
        _record_problem(db, row, event, "payment.mismatch", OUTCOME_AMOUNT_MISMATCH)
        db.commit()
        return WebhookOutcome(200)
    if row.status != PAYMENT_STATUS_CAPTURED:
        _add_event(db, event, row.id, OUTCOME_STALE)
        db.commit()
        return WebhookOutcome(200)
    refunded = event.amount_refunded if event.amount_refunded is not None else event.amount
    if refunded is None or refunded < row.amount_paise:
        _record_problem(db, row, event, "payment.partial_refund", OUTCOME_PARTIAL_REFUND)
        db.commit()
        return WebhookOutcome(200)
    row.status = PAYMENT_STATUS_REFUNDED
    row.updated_at = _utcnow()
    audit_service.record_audit(
        db,
        actor=None,
        action="payment.refunded",
        entity_type="payment_transaction",
        entity_id=row.id,
        school_id=row.school_id,
        metadata={"bill_id": row.bill_id, "amount_paise": refunded},
        commit=False,
    )
    _add_event(db, event, row.id, OUTCOME_APPLIED)
    db.commit()
    return WebhookOutcome(200)


_SETTLE_NONE = "none"
_SETTLE_DONE = "done"
_SETTLE_REFUSED = "refused"


def _settle_capture(db: Session, row: PaymentTransaction, *, actor: User | None) -> str:
    """Mark the bill paid once and issue one invoice. Does not commit.

    Returns done when a bill or invoice row was written, none when both
    already existed, and refused when the bill is cancelled or missing.
    """
    from app.services.v1.invoice_service import find_invoice_for_payment, issue_invoice_for_captured_payment

    bill = db.scalar(
        select(SubscriptionBill).where(SubscriptionBill.id == row.bill_id).with_for_update()
    )
    if (
        bill is None
        or bill.deleted_at is not None
        or bill.school_id != row.school_id
        or bill.status == BILL_STATUS_CANCELLED
    ):
        audit_service.record_audit(
            db,
            actor=actor,
            action="payment.captured_unpayable_bill",
            entity_type="payment_transaction",
            entity_id=row.id,
            school_id=row.school_id,
            metadata={
                "bill_id": row.bill_id,
                "bill_status": None if bill is None else bill.status,
                "refund_required": True,
            },
            commit=False,
        )
        return _SETTLE_REFUSED
    wrote = False
    if bill.status != BILL_STATUS_PAID:
        bill.status = BILL_STATUS_PAID
        bill.updated_at = _utcnow()
        audit_service.record_audit(
            db,
            actor=actor,
            action="bill.status",
            entity_type="subscription_bill",
            entity_id=bill.id,
            school_id=bill.school_id,
            metadata={"status": bill.status, "payment_transaction_id": row.id},
            commit=False,
        )
        wrote = True
    if find_invoice_for_payment(db, row.id) is None:
        wrote = issue_invoice_for_captured_payment(db, row) is not None or wrote
    return _SETTLE_DONE if wrote else _SETTLE_NONE


def _transition(row: PaymentTransaction, target: int | None, *, rebound: bool) -> bool:
    """Apply the next status. A failed order moves to authorized only for a new payment id."""
    if target == PAYMENT_STATUS_AUTHORIZED and row.status == PAYMENT_STATUS_FAILED and not rebound:
        return False
    updated = _next_status(row.status, target)
    if updated is None or updated == row.status:
        return False
    row.status = updated
    return True


def _next_status(current: int, target: int | None) -> int | None:
    """Return the status to store. None keeps the current status."""
    if target is None or current == target:
        return current
    if current in _TERMINAL:
        return None
    if target == PAYMENT_STATUS_CAPTURED:
        return PAYMENT_STATUS_CAPTURED
    if target == PAYMENT_STATUS_FAILED:
        return PAYMENT_STATUS_FAILED
    if target == PAYMENT_STATUS_AUTHORIZED and current in (PAYMENT_STATUS_CREATED, PAYMENT_STATUS_FAILED):
        return PAYMENT_STATUS_AUTHORIZED
    return None


class _PaymentConflict(Exception):
    pass


_SAME = "same"
_BOUND = "bound"
_STALE = "stale"


def _bind_payment_id(db: Session, row: PaymentTransaction, payment_id: str, target: int | None) -> str:
    """Attach the gateway payment id to the order row.

    A Razorpay order accepts a new attempt after a failed one, so a failed
    row takes the new id. An authorized row takes a new id only on capture.
    Another id on a captured or refunded row is a conflict for a capture and
    stale for any other event. An id owned by another row is a conflict.
    """
    if row.gateway_payment_id == payment_id:
        return _SAME
    owner = db.scalar(
        select(PaymentTransaction.id).where(
            PaymentTransaction.gateway_payment_id == payment_id,
            PaymentTransaction.id != row.id,
        )
    )
    if owner is not None:
        raise _PaymentConflict
    replaceable = row.gateway_payment_id is None or row.status in (PAYMENT_STATUS_CREATED, PAYMENT_STATUS_FAILED)
    if not replaceable and target == PAYMENT_STATUS_CAPTURED and row.status == PAYMENT_STATUS_AUTHORIZED:
        replaceable = True
    if not replaceable:
        if target == PAYMENT_STATUS_CAPTURED:
            raise _PaymentConflict
        return _STALE
    row.gateway_payment_id = payment_id
    row.updated_at = _utcnow()
    return _BOUND


def _build_fetcher(settings: Settings) -> PaymentFetcher:
    from app.services.v1.razorpay_client import RazorpayPaymentFetcher, validate_razorpay_credentials

    key_id, key_secret = validate_razorpay_credentials(settings)
    return RazorpayPaymentFetcher(key_id, key_secret)


def _fetch_remote(fetcher: PaymentFetcher, payment_id: str) -> dict | None:
    try:
        remote = fetcher.fetch_payment(payment_id)
    except Exception:
        return None
    return remote if isinstance(remote, dict) else None


def _remote_matches(remote: dict, row: PaymentTransaction, order_id: str, payment_id: str) -> bool:
    amount = remote.get("amount")
    return (
        remote.get("id") == payment_id
        and remote.get("order_id") == order_id
        and type(amount) is int
        and amount == row.amount_paise
        and remote.get("currency") == row.currency
    )


def _remote_metadata(remote: dict, payment_id: str) -> dict:
    amount = remote.get("amount")
    return {
        "payment_id": payment_id,
        "remote_order_id": str(remote.get("order_id") or "")[:64],
        "remote_amount": amount if type(amount) is int else None,
        "remote_currency": str(remote.get("currency") or "")[:3],
        "remote_status": str(remote.get("status") or "")[:32],
    }


def _record_problem(
    db: Session,
    row: PaymentTransaction,
    event: _ParsedEvent,
    action: str,
    outcome: str,
    *,
    link: bool = True,
) -> None:
    audit_service.record_audit(
        db,
        actor=None,
        action=action,
        entity_type="payment_transaction",
        entity_id=row.id,
        school_id=row.school_id,
        metadata={
            "event_id": event.event_id,
            "event_type": event.event_type,
            "payment_id": event.payment_id,
            "amount_paise": event.amount,
            "currency": event.currency,
            "expected_amount_paise": int(row.amount_paise),
            "expected_currency": row.currency,
        },
        commit=False,
    )
    _add_event(db, event, row.id if link else None, outcome)


def _commit_or_raise(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise PaymentOrderError("Payment is linked to a different transaction", status_code=409) from None
    except Exception:
        db.rollback()
        raise PaymentOrderError("Payment could not be recorded", status_code=500) from None


def _parse_event(raw_body: bytes, event_id: str) -> _ParsedEvent:
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise PaymentOrderError("Webhook event is invalid", status_code=400) from None
    if not isinstance(payload, dict):
        raise PaymentOrderError("Webhook event is invalid", status_code=400)
    event_type = payload.get("event")
    if not isinstance(event_type, str) or not _visible_id(event_type, 64):
        raise PaymentOrderError("Webhook event is invalid", status_code=400)
    if event_type in _REFUND_EVENTS:
        return _parse_refund(payload, event_id, event_type)
    if event_type not in _EVENT_TARGETS:
        return _ParsedEvent(event_id, event_type, "other")
    entity = _entity(payload, "payment")
    if entity is None:
        raise PaymentOrderError("Webhook event is invalid", status_code=400)
    order_id = entity.get("order_id")
    payment_id = entity.get("id")
    currency = entity.get("currency")
    amount = entity.get("amount")
    if (
        not _visible_id(order_id if isinstance(order_id, str) else "", 64)
        or not _visible_id(payment_id if isinstance(payment_id, str) else "", 64)
        or not _currency_code(currency)
        or type(amount) is not int
        or amount < 0
    ):
        raise PaymentOrderError("Webhook event is invalid", status_code=400)
    return _ParsedEvent(event_id, event_type, "payment", order_id, payment_id, amount, currency)


def _parse_refund(payload: dict, event_id: str, event_type: str) -> _ParsedEvent:
    refund = _entity(payload, "refund")
    if refund is None:
        raise PaymentOrderError("Webhook event is invalid", status_code=400)
    payment_id = refund.get("payment_id")
    amount = refund.get("amount")
    currency = refund.get("currency")
    if (
        not _visible_id(payment_id if isinstance(payment_id, str) else "", 64)
        or not _currency_code(currency)
        or type(amount) is not int
        or amount < 0
    ):
        raise PaymentOrderError("Webhook event is invalid", status_code=400)
    order_id = None
    amount_refunded = None
    payment = _entity(payload, "payment")
    if payment is not None:
        if isinstance(payment.get("order_id"), str) and _visible_id(payment["order_id"], 64):
            order_id = payment["order_id"]
        if type(payment.get("amount_refunded")) is int and payment["amount_refunded"] >= 0:
            amount_refunded = payment["amount_refunded"]
    return _ParsedEvent(event_id, event_type, "refund", order_id, payment_id, amount, currency, amount_refunded)


def _entity(payload: dict, name: str) -> dict | None:
    body = payload.get("payload")
    if not isinstance(body, dict):
        return None
    wrapper = body.get(name)
    if not isinstance(wrapper, dict):
        return None
    entity = wrapper.get("entity")
    if not isinstance(entity, dict):
        return None
    return entity


def _currency_code(value: object) -> bool:
    return isinstance(value, str) and len(value) == 3 and value.isascii() and value.isalpha() and value.isupper()


def _add_event(db: Session, event: _ParsedEvent, payment_transaction_id: int | None, outcome: str) -> None:
    db.add(
        PaymentWebhookEvent(
            provider="razorpay",
            event_id=event.event_id,
            event_type=event.event_type,
            payment_transaction_id=payment_transaction_id,
            gateway_order_id=event.order_id,
            gateway_payment_id=event.payment_id,
            amount_paise=event.amount,
            currency=event.currency,
            outcome=outcome,
            created_at=_utcnow(),
        )
    )


def _find_event(db: Session, event_id: str) -> PaymentWebhookEvent | None:
    return db.scalar(
        select(PaymentWebhookEvent).where(
            PaymentWebhookEvent.provider == "razorpay",
            PaymentWebhookEvent.event_id == event_id,
        )
    )


def _visible_id(value: str, limit: int) -> bool:
    return bool(value) and len(value) <= limit and all(33 <= ord(char) <= 126 for char in value)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
