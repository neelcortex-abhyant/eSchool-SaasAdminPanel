"""POST /api/v1/payments/initiate.

Creates a Razorpay order through create_payment_order. The response is the
same direct JSON shape as the other v1 routes. It includes the public key id
and omits the key secret and webhook secret.

A captured payment for the bill is returned again only when the same
idempotency key is reused. A new key does not open another order: it gets
the bill's created or failed order back, and an authorized or captured
order is a 409.

POST /verify checks the checkout signature and reads the payment from
Razorpay. Only a gateway status of captured, with the order's amount and
currency, marks the bill paid. POST /webhook/razorpay is the other path to
the same result. See docs/PAYMENTS_API.md.

A lost gateway response can still leave a remote order without a local row.
Razorpay's order API does not accept this idempotency key, and storing a
recovery record would need a schema change. This route does not add that
workaround, and local idempotency does not by itself prevent a second remote
order after a lost response.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, assert_school_scope, get_current_auth, require_school_admin
from app.core.config import get_settings
from app.models.tables import PAYMENT_STATUS_CAPTURED, PaymentTransaction, SubscriptionBill
from app.models.v1.roles import ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN
from app.schemas.v1.payments import (
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
    WebhookReceiptResponse,
)
from app.services.v1.payment_order_service import PaymentCaller, PaymentOrderError, create_payment_order
from app.services.v1.payment_verification_service import (
    payment_status_name,
    process_razorpay_webhook,
    verify_checkout_payment,
)

router = APIRouter(prefix="/payments", tags=["v1-payments"])


def require_payment_initiator(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    db: Annotated[Session, Depends(central_db)],
) -> AuthContext:
    """Super Admin, or a school admin whose school is active and installed."""
    if auth.user.role == ROLE_SUPER_ADMIN:
        return auth
    if auth.user.role == ROLE_SCHOOL_ADMIN:
        return require_school_admin(auth, db)
    raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/initiate", response_model=PaymentInitiateResponse)
def initiate_payment(
    body: PaymentInitiateRequest,
    auth: Annotated[AuthContext, Depends(require_payment_initiator)],
    db: Annotated[Session, Depends(central_db)],
) -> PaymentInitiateResponse:
    if auth.user.role != ROLE_SUPER_ADMIN:
        assert_school_scope(auth, body.school_id)
    bill = db.get(SubscriptionBill, body.bill_id)
    if bill is None or bill.deleted_at is not None or bill.school_id != body.school_id:
        raise HTTPException(status_code=404, detail="Bill not found")
    if bill.subscription_id != body.subscription_id:
        raise HTTPException(status_code=404, detail="Subscription not found")
    _reject_new_order_after_capture(db, bill, body.idempotency_key)
    try:
        row = create_payment_order(
            db,
            bill.id,
            caller=PaymentCaller(role=auth.user.role, school_id=auth.user.school_id),
            idempotency_key=body.idempotency_key,
            settings=get_settings(),
        )
    except PaymentOrderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    key_id = (get_settings().razorpay_key_id or "").strip()
    if not key_id:
        raise HTTPException(status_code=503, detail="Payment configuration is missing")
    return PaymentInitiateResponse(
        order_id=row.gateway_order_id,
        amount=int(row.amount_paise),
        currency=row.currency,
        gateway="razorpay",
        key_id=key_id,
        status=payment_status_name(row.status),
    )


@router.post("/verify", response_model=PaymentVerifyResponse)
def verify_payment(
    body: PaymentVerifyRequest,
    auth: Annotated[AuthContext, Depends(require_payment_initiator)],
    db: Annotated[Session, Depends(central_db)],
) -> PaymentVerifyResponse:
    try:
        row = verify_checkout_payment(
            db,
            caller=PaymentCaller(role=auth.user.role, school_id=auth.user.school_id),
            actor=auth.user,
            order_id=body.razorpay_order_id,
            payment_id=body.razorpay_payment_id,
            signature=body.razorpay_signature,
            settings=get_settings(),
        )
    except PaymentOrderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return PaymentVerifyResponse(
        order_id=row.gateway_order_id,
        payment_id=row.gateway_payment_id or body.razorpay_payment_id,
        amount=int(row.amount_paise),
        currency=row.currency,
        status=payment_status_name(row.status),
    )


@router.post("/webhook/razorpay", response_model=WebhookReceiptResponse)
async def razorpay_webhook(
    request: Request,
    db: Annotated[Session, Depends(central_db)],
) -> WebhookReceiptResponse:
    raw_body = await request.body()
    try:
        outcome = process_razorpay_webhook(
            db,
            raw_body=raw_body,
            signature=request.headers.get("x-razorpay-signature", ""),
            event_id=request.headers.get("x-razorpay-event-id", ""),
            settings=get_settings(),
        )
    except PaymentOrderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    if outcome.status_code != 200:
        raise HTTPException(status_code=outcome.status_code, detail=outcome.detail)
    return WebhookReceiptResponse(received=True)


def _reject_new_order_after_capture(db: Session, bill: SubscriptionBill, idempotency_key: str) -> None:
    captured = db.scalar(
        select(PaymentTransaction).where(
            PaymentTransaction.bill_id == bill.id,
            PaymentTransaction.school_id == bill.school_id,
            PaymentTransaction.status == PAYMENT_STATUS_CAPTURED,
        )
    )
    if captured is None or captured.idempotency_key == idempotency_key.strip():
        return
    raise HTTPException(status_code=409, detail="Bill already has a captured payment")
