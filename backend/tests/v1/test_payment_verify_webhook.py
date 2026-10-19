"""Checkout verification and Razorpay webhooks. Signatures are local HMACs, not live API calls."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date, datetime, timezone

from pydantic import SecretStr
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.database import session_factory
from app.models.tables import (
    PAYMENT_STATUS_AUTHORIZED,
    PAYMENT_STATUS_CAPTURED,
    PAYMENT_STATUS_CREATED,
    PAYMENT_STATUS_FAILED,
    PAYMENT_STATUS_REFUNDED,
    AuditLog,
    Package,
    PaymentTransaction,
    PaymentWebhookEvent,
    School,
    Subscription,
    SubscriptionBill,
    SubscriptionInvoice,
    SubscriptionRenewal,
)
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User
from app.services.v1.subscription_service import (
    BILL_STATUS_CANCELLED,
    BILL_STATUS_PAID,
    BILL_STATUS_PENDING,
    SUB_STATUS_ACTIVE,
    SUB_STATUS_INACTIVE,
)


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        razorpay_currency="INR",
        razorpay_key_id="rzp_test_unit",
        razorpay_key_secret=SecretStr("unit-secret"),
        razorpay_webhook_secret=SecretStr("unit-webhook"),
    )


class FakeFetcher:
    """Stands in for the Razorpay payment fetch. Never calls the network."""

    def __init__(self):
        self.status: str | None = "authorized"
        self.amount = 249900
        self.currency = "INR"
        self.order_id: str | None = None
        self.calls: list[str] = []

    def fetch_payment(self, payment_id: str) -> dict | None:
        self.calls.append(payment_id)
        if self.status is None:
            return None
        return {
            "id": payment_id,
            "order_id": self.order_id or "order_test_1",
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status,
        }


def _patch(monkeypatch) -> FakeFetcher:
    fetcher = FakeFetcher()
    monkeypatch.setattr("app.api.v1.payments.get_settings", lambda: _settings())
    monkeypatch.setattr(
        "app.services.v1.payment_verification_service._build_fetcher",
        lambda _settings: fetcher,
    )
    return fetcher


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _super_headers(client, v1_db, email: str) -> dict[str, str]:
    created = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "secret123", "first_name": "Pay", "last_name": "Admin"},
    )
    assert created.status_code == 201, created.text
    user = v1_db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200, login.text
    return _auth(login.json()["access_token"])


def _school_admin_headers(client, super_headers, school_id: int, email: str) -> dict[str, str]:
    created = client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=super_headers,
        json={"email": email, "password": "adminpass1", "first_name": "School", "last_name": "Admin"},
    )
    assert created.status_code == 201, created.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "adminpass1"})
    assert login.status_code == 200, login.text
    return _auth(login.json()["access_token"])


def _school_bill(client, headers, code: str) -> dict:
    school = client.post("/api/v1/super-admin/schools", headers=headers, json={"name": "Pay School", "code": code})
    assert school.status_code == 201, school.text
    school_id = school.json()["id"]
    plan = client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": f"Plan {code}", "monthly_price": 10, "yearly_price": 100},
    )
    assert plan.status_code == 201, plan.text
    activated = client.patch(
        f"/api/v1/super-admin/plans/{plan.json()['id']}/status",
        headers=headers,
        json={"status": 1},
    )
    assert activated.status_code == 200, activated.text
    subscription = client.post(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions",
        headers=headers,
        json={
            "package_id": plan.json()["id"],
            "start_date": "2026-10-01",
            "end_date": "2026-11-01",
            "cycle": "monthly",
            "auto_renew": 1,
            "status": 1,
        },
    )
    assert subscription.status_code == 201, subscription.text
    subscription_id = subscription.json()["id"]
    end_date = subscription.json()["end_date"]
    bill = client.post(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions/{subscription_id}/bills",
        headers=headers,
        json={"period_start": "2026-10-01", "period_end": "2026-11-01", "amount": 2499, "status": 0},
    )
    assert bill.status_code == 201, bill.text
    return {
        "school_id": school_id,
        "subscription_id": subscription_id,
        "bill_id": bill.json()["id"],
        "end_date": end_date,
    }


def _insert_payment(ids: dict, *, order_id: str = "order_test_1", payment_id: str | None = None, status: int = 0) -> None:
    db = session_factory()()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(
            PaymentTransaction(
                bill_id=ids["bill_id"],
                school_id=ids["school_id"],
                gateway_order_id=order_id,
                gateway_payment_id=payment_id,
                idempotency_key=order_id,
                amount_paise=249900,
                currency="INR",
                status=status,
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
    finally:
        db.close()


def _checkout_signature(order_id: str, payment_id: str, secret: str = "unit-secret") -> str:
    message = f"{order_id}|{payment_id}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def _verify_body(order_id: str = "order_test_1", payment_id: str = "pay_test_1", *, secret: str = "unit-secret") -> dict:
    return {
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": _checkout_signature(order_id, payment_id, secret),
    }


def _webhook(event: str, *, order_id: str, payment_id: str, event_id: str, amount: int = 249900) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(
        {
            "event": event,
            "payload": {
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "order_id": order_id,
                        "amount": amount,
                        "currency": "INR",
                        "status": event.split(".", 1)[-1],
                    }
                }
            },
        },
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(b"unit-webhook", raw, hashlib.sha256).hexdigest()
    return raw, {
        "x-razorpay-signature": signature,
        "x-razorpay-event-id": event_id,
        "content-type": "application/json",
    }


def _orm_payment(*, code: str, sub_status: int = SUB_STATUS_ACTIVE, order_id: str = "order_orm_1") -> dict:
    db = session_factory()()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        school = School(name="Orm School", code=code, status=1, installed=1, created_at=now, updated_at=now)
        plan = Package(name=f"Orm {code}", monthly_price=10, yearly_price=100, status=1, created_at=now)
        db.add_all([school, plan])
        db.flush()
        subscription = Subscription(
            school_id=school.id,
            package_id=plan.id,
            status=sub_status,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 11, 1),
            cycle="monthly",
            auto_renew=1,
            created_at=now,
            updated_at=now,
        )
        db.add(subscription)
        db.flush()
        bill = SubscriptionBill(
            subscription_id=subscription.id,
            school_id=school.id,
            amount=2499,
            status=BILL_STATUS_PENDING,
            period_start=date(2026, 10, 1),
            period_end=date(2026, 11, 1),
            created_at=now,
            updated_at=now,
        )
        db.add(bill)
        db.flush()
        payment = PaymentTransaction(
            bill_id=bill.id,
            school_id=school.id,
            gateway_order_id=order_id,
            gateway_payment_id=None,
            idempotency_key=order_id,
            amount_paise=249900,
            currency="INR",
            status=PAYMENT_STATUS_CREATED,
            created_at=now,
            updated_at=now,
        )
        db.add(payment)
        db.commit()
        return {
            "school_id": school.id,
            "subscription_id": subscription.id,
            "bill_id": bill.id,
            "payment_id": payment.id,
            "end_date": "2026-11-01",
            "order_id": order_id,
        }
    finally:
        db.close()


def _state(bill_id: int) -> tuple[SubscriptionBill, Subscription, PaymentTransaction]:
    db = session_factory()()
    try:
        bill = db.get(SubscriptionBill, bill_id)
        assert bill is not None
        subscription = db.get(Subscription, bill.subscription_id)
        payment = db.scalar(select(PaymentTransaction).where(PaymentTransaction.bill_id == bill_id))
        assert subscription is not None and payment is not None
        db.expunge_all()
        return bill, subscription, payment
    finally:
        db.close()


def test_school_admin_verifies_a_signed_checkout(v1_client, v1_db, monkeypatch):
    _patch(monkeypatch)
    headers = _super_headers(v1_client, v1_db, "pay-verify-sa@eschool.com")
    ids = _school_bill(v1_client, headers, "PAYV01")
    _insert_payment(ids)
    admin = _school_admin_headers(v1_client, headers, ids["school_id"], "pay-verify-admin@eschool.com")
    response = v1_client.post("/api/v1/payments/verify", headers=admin, json=_verify_body())
    assert response.status_code == 200, response.text
    assert response.json() == {
        "order_id": "order_test_1",
        "payment_id": "pay_test_1",
        "amount": 249900,
        "currency": "INR",
        "status": "authorized",
    }
    assert "unit-secret" not in response.text
    assert "unit-webhook" not in response.text
    bill, subscription, payment = _state(ids["bill_id"])
    assert payment.status == PAYMENT_STATUS_AUTHORIZED
    assert bill.status == BILL_STATUS_PENDING
    assert subscription.status == SUB_STATUS_ACTIVE
    assert subscription.end_date.isoformat() == ids["end_date"]


def test_invalid_checkout_signature_is_rejected(v1_client, v1_db, monkeypatch):
    _patch(monkeypatch)
    headers = _super_headers(v1_client, v1_db, "pay-badsig-sa@eschool.com")
    ids = _school_bill(v1_client, headers, "PAYV02")
    _insert_payment(ids)
    body = _verify_body(secret="other-secret")
    response = v1_client.post("/api/v1/payments/verify", headers=headers, json=body)
    assert response.status_code == 400
    assert response.json()["detail"] == "Payment signature is invalid"
    assert "unit-secret" not in response.text
    _, _, payment = _state(ids["bill_id"])
    assert payment.status == PAYMENT_STATUS_CREATED
    assert payment.gateway_payment_id is None


def test_unknown_order_is_rejected(v1_client, v1_db, monkeypatch):
    _patch(monkeypatch)
    headers = _super_headers(v1_client, v1_db, "pay-missing-order-sa@eschool.com")
    response = v1_client.post(
        "/api/v1/payments/verify",
        headers=headers,
        json=_verify_body(order_id="order_missing"),
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found"


def test_school_admin_cannot_verify_another_school(v1_client, v1_db, monkeypatch):
    _patch(monkeypatch)
    headers = _super_headers(v1_client, v1_db, "pay-scope-sa@eschool.com")
    own = _school_bill(v1_client, headers, "PAYV03")
    other = _school_bill(v1_client, headers, "PAYV04")
    _insert_payment(other, order_id="order_other_school")
    admin = _school_admin_headers(v1_client, headers, own["school_id"], "pay-scope-admin@eschool.com")
    response = v1_client.post(
        "/api/v1/payments/verify",
        headers=admin,
        json=_verify_body(order_id="order_other_school"),
    )
    assert response.status_code == 403
    _, _, payment = _state(other["bill_id"])
    assert payment.status == PAYMENT_STATUS_CREATED
    assert payment.gateway_payment_id is None


def test_repeated_verification_does_not_pay_the_bill(v1_client, v1_db, monkeypatch):
    _patch(monkeypatch)
    headers = _super_headers(v1_client, v1_db, "pay-repeat-verify-sa@eschool.com")
    ids = _school_bill(v1_client, headers, "PAYV05")
    _insert_payment(ids)
    first = v1_client.post("/api/v1/payments/verify", headers=headers, json=_verify_body())
    second = v1_client.post("/api/v1/payments/verify", headers=headers, json=_verify_body())
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "authorized"
    bill, subscription, _payment = _state(ids["bill_id"])
    assert bill.status == BILL_STATUS_PENDING
    assert subscription.status == SUB_STATUS_ACTIVE
    db = session_factory()()
    try:
        audits = db.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "payment.verify")
        )
        renewals = db.scalar(select(func.count()).select_from(SubscriptionRenewal))
        assert audits == 1
        assert renewals == 0
    finally:
        db.close()


def test_captured_webhook_marks_the_bill_paid_once(v1_client, monkeypatch):
    _patch(monkeypatch)
    ids = _orm_payment(code="PAYW01")
    raw, headers = _webhook("payment.captured", order_id=ids["order_id"], payment_id="pay_cap_1", event_id="evt_cap_1")
    first = v1_client.post("/api/v1/payments/webhook/razorpay", content=raw, headers=headers)
    second_raw, second_headers = _webhook(
        "payment.captured", order_id=ids["order_id"], payment_id="pay_cap_1", event_id="evt_cap_2"
    )
    second = v1_client.post("/api/v1/payments/webhook/razorpay", content=second_raw, headers=second_headers)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json() == {"received": True}
    assert "unit-webhook" not in first.text
    assert "pay_cap_1" not in first.text
    bill, subscription, payment = _state(ids["bill_id"])
    assert payment.status == PAYMENT_STATUS_CAPTURED
    assert payment.gateway_payment_id == "pay_cap_1"
    assert bill.status == BILL_STATUS_PAID
    assert subscription.status == SUB_STATUS_ACTIVE
    assert subscription.end_date.isoformat() == ids["end_date"]
    db = session_factory()()
    try:
        paid_audits = db.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "bill.status")
        )
        renewals = db.scalar(select(func.count()).select_from(SubscriptionRenewal))
        assert paid_audits == 1
        assert renewals == 0
        stored = db.scalars(select(AuditLog.metadata_json)).all()
        assert all(item is None or "unit-webhook" not in item for item in stored)
    finally:
        db.close()


def test_invalid_webhook_signature_changes_nothing(v1_client, monkeypatch):
    _patch(monkeypatch)
    ids = _orm_payment(code="PAYW02")
    raw, headers = _webhook("payment.captured", order_id=ids["order_id"], payment_id="pay_bad", event_id="evt_bad")
    headers["x-razorpay-signature"] = "0" * 64
    response = v1_client.post("/api/v1/payments/webhook/razorpay", content=raw, headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "Webhook signature is invalid"
    assert "unit-webhook" not in response.text
    bill, _, payment = _state(ids["bill_id"])
    assert payment.status == PAYMENT_STATUS_CREATED
    assert bill.status == BILL_STATUS_PENDING
    db = session_factory()()
    try:
        assert db.scalar(select(func.count()).select_from(PaymentWebhookEvent)) == 0
    finally:
        db.close()


def test_duplicate_webhook_event_is_ignored(v1_client, monkeypatch):
    _patch(monkeypatch)
    ids = _orm_payment(code="PAYW03")
    raw, headers = _webhook("payment.captured", order_id=ids["order_id"], payment_id="pay_dup", event_id="evt_dup")
    assert v1_client.post("/api/v1/payments/webhook/razorpay", content=raw, headers=headers).status_code == 200
    again = v1_client.post("/api/v1/payments/webhook/razorpay", content=raw, headers=headers)
    assert again.status_code == 200
    db = session_factory()()
    try:
        assert db.scalar(select(func.count()).select_from(PaymentWebhookEvent)) == 1
        assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "bill.status")) == 1
    finally:
        db.close()


def test_failed_payment_does_not_activate_or_pay(v1_client, monkeypatch):
    _patch(monkeypatch)
    ids = _orm_payment(code="PAYW04", sub_status=SUB_STATUS_INACTIVE)
    raw, headers = _webhook("payment.failed", order_id=ids["order_id"], payment_id="pay_fail", event_id="evt_fail")
    response = v1_client.post("/api/v1/payments/webhook/razorpay", content=raw, headers=headers)
    assert response.status_code == 200, response.text
    bill, subscription, payment = _state(ids["bill_id"])
    assert payment.status == 3
    assert bill.status == BILL_STATUS_PENDING
    assert subscription.status == SUB_STATUS_INACTIVE
    db = session_factory()()
    try:
        assert db.scalar(select(func.count()).select_from(SubscriptionRenewal)) == 0
    finally:
        db.close()


def test_authorized_and_pending_events_do_not_pay(v1_client, monkeypatch):
    _patch(monkeypatch)
    ids = _orm_payment(code="PAYW05")
    authorized, authorized_headers = _webhook(
        "payment.authorized", order_id=ids["order_id"], payment_id="pay_auth", event_id="evt_auth"
    )
    pending, pending_headers = _webhook(
        "payment.pending", order_id=ids["order_id"], payment_id="pay_auth", event_id="evt_pending"
    )
    assert v1_client.post("/api/v1/payments/webhook/razorpay", content=authorized, headers=authorized_headers).status_code == 200
    assert v1_client.post("/api/v1/payments/webhook/razorpay", content=pending, headers=pending_headers).status_code == 200
    bill, subscription, payment = _state(ids["bill_id"])
    assert payment.status == PAYMENT_STATUS_AUTHORIZED
    assert bill.status == BILL_STATUS_PENDING
    assert subscription.status == SUB_STATUS_ACTIVE


def test_failed_event_after_capture_does_not_downgrade(v1_client, monkeypatch):
    _patch(monkeypatch)
    ids = _orm_payment(code="PAYW06")
    captured, captured_headers = _webhook(
        "payment.captured", order_id=ids["order_id"], payment_id="pay_order", event_id="evt_order_cap"
    )
    failed, failed_headers = _webhook(
        "payment.failed", order_id=ids["order_id"], payment_id="pay_order", event_id="evt_order_fail"
    )
    assert v1_client.post("/api/v1/payments/webhook/razorpay", content=captured, headers=captured_headers).status_code == 200
    assert v1_client.post("/api/v1/payments/webhook/razorpay", content=failed, headers=failed_headers).status_code == 200
    bill, subscription, payment = _state(ids["bill_id"])
    assert payment.status == PAYMENT_STATUS_CAPTURED
    assert bill.status == BILL_STATUS_PAID
    assert subscription.end_date.isoformat() == ids["end_date"]
    db = session_factory()()
    try:
        assert db.scalar(select(func.count()).select_from(SubscriptionRenewal)) == 0
        assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "bill.status")) == 1
    finally:
        db.close()


def test_payment_id_conflict_does_not_move_the_payment(v1_client, monkeypatch):
    _patch(monkeypatch)
    first = _orm_payment(code="PAYW07", order_id="order_conflict_1")
    second = _orm_payment(code="PAYW08", order_id="order_conflict_2")
    db = session_factory()()
    try:
        row = db.get(PaymentTransaction, first["payment_id"])
        assert row is not None
        row.gateway_payment_id = "pay_taken"
        db.commit()
    finally:
        db.close()
    raw, headers = _webhook(
        "payment.captured", order_id="order_conflict_2", payment_id="pay_taken", event_id="evt_conflict"
    )
    response = v1_client.post("/api/v1/payments/webhook/razorpay", content=raw, headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"] == "Payment is linked to a different transaction"
    _, _, second_payment = _state(second["bill_id"])
    _, _, first_payment = _state(first["bill_id"])
    assert second_payment.gateway_payment_id is None
    assert second_payment.status == PAYMENT_STATUS_CREATED
    assert first_payment.gateway_payment_id == "pay_taken"
    replay = v1_client.post("/api/v1/payments/webhook/razorpay", content=raw, headers=headers)
    assert replay.status_code == 200


def test_capture_after_failure_pays_the_bill_without_renewal(v1_client, monkeypatch):
    _patch(monkeypatch)
    ids = _orm_payment(code="PAYW09", sub_status=SUB_STATUS_INACTIVE)
    failed, failed_headers = _webhook(
        "payment.failed", order_id=ids["order_id"], payment_id="pay_late", event_id="evt_late_fail"
    )
    captured, captured_headers = _webhook(
        "payment.captured", order_id=ids["order_id"], payment_id="pay_late", event_id="evt_late_cap"
    )
    assert v1_client.post("/api/v1/payments/webhook/razorpay", content=failed, headers=failed_headers).status_code == 200
    assert v1_client.post("/api/v1/payments/webhook/razorpay", content=captured, headers=captured_headers).status_code == 200
    bill, subscription, payment = _state(ids["bill_id"])
    assert payment.status == PAYMENT_STATUS_CAPTURED
    assert bill.status == BILL_STATUS_PAID
    assert subscription.status == SUB_STATUS_INACTIVE
    db = session_factory()()
    try:
        assert db.scalar(select(func.count()).select_from(SubscriptionRenewal)) == 0
    finally:
        db.close()


def test_amount_mismatch_does_not_mark_the_bill_paid(v1_client, monkeypatch):
    _patch(monkeypatch)
    ids = _orm_payment(code="PAYW10")
    raw, headers = _webhook(
        "payment.captured",
        order_id=ids["order_id"],
        payment_id="pay_mismatch",
        event_id="evt_mismatch",
        amount=1,
    )
    response = v1_client.post("/api/v1/payments/webhook/razorpay", content=raw, headers=headers)
    assert response.status_code == 200, response.text
    bill, _, payment = _state(ids["bill_id"])
    assert payment.status == PAYMENT_STATUS_CREATED
    assert payment.gateway_payment_id is None
    assert bill.status == BILL_STATUS_PENDING



def _signed(payload: dict, event_id: str) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(b"unit-webhook", raw, hashlib.sha256).hexdigest()
    return raw, {
        "x-razorpay-signature": signature,
        "x-razorpay-event-id": event_id,
        "content-type": "application/json",
    }


def _refund(*, payment_id: str, event_id: str, amount: int, amount_refunded: int | None = None) -> tuple[bytes, dict[str, str]]:
    payment_entity: dict = {"id": payment_id, "amount": 249900, "currency": "INR", "status": "refunded"}
    if amount_refunded is not None:
        payment_entity["amount_refunded"] = amount_refunded
    return _signed(
        {
            "event": "refund.processed",
            "payload": {
                "refund": {"entity": {"id": f"rfnd_{event_id}", "payment_id": payment_id, "amount": amount, "currency": "INR"}},
                "payment": {"entity": payment_entity},
            },
        },
        event_id,
    )


def _post(client, raw: bytes, headers: dict[str, str]):
    return client.post("/api/v1/payments/webhook/razorpay", content=raw, headers=headers)


def _count(model, *where) -> int:
    db = session_factory()()
    try:
        return int(db.scalar(select(func.count()).select_from(model).where(*where)) or 0)
    finally:
        db.close()


def _event(event_id: str) -> PaymentWebhookEvent:
    db = session_factory()()
    try:
        row = db.scalar(select(PaymentWebhookEvent).where(PaymentWebhookEvent.event_id == event_id))
        assert row is not None
        db.expunge(row)
        return row
    finally:
        db.close()


def _set_bill_status(bill_id: int, status: int) -> None:
    db = session_factory()()
    try:
        bill = db.get(SubscriptionBill, bill_id)
        assert bill is not None
        bill.status = status
        db.commit()
    finally:
        db.close()


def test_verify_with_gateway_capture_pays_once_and_webhook_does_not_duplicate(v1_client, v1_db, monkeypatch):
    fetcher = _patch(monkeypatch)
    fetcher.status = "captured"
    fetcher.order_id = "order_orm_cap"
    headers = _super_headers(v1_client, v1_db, "pay-verify-capture-sa@eschool.com")
    ids = _orm_payment(code="PAYV10", order_id="order_orm_cap")
    body = _verify_body(order_id="order_orm_cap", payment_id="pay_verify_cap")
    first = v1_client.post("/api/v1/payments/verify", headers=headers, json=body)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "captured"
    second = v1_client.post("/api/v1/payments/verify", headers=headers, json=body)
    assert second.status_code == 200
    assert second.json()["status"] == "captured"
    raw, hook_headers = _webhook(
        "payment.captured", order_id="order_orm_cap", payment_id="pay_verify_cap", event_id="evt_verify_cap"
    )
    assert _post(v1_client, raw, hook_headers).status_code == 200
    bill, subscription, payment = _state(ids["bill_id"])
    assert payment.status == PAYMENT_STATUS_CAPTURED
    assert bill.status == BILL_STATUS_PAID
    assert subscription.end_date.isoformat() == ids["end_date"]
    assert _count(SubscriptionInvoice) == 1
    assert _count(AuditLog, AuditLog.action == "bill.status") == 1
    assert _count(AuditLog, AuditLog.action == "payment.verify") == 1
    assert _count(SubscriptionRenewal) == 0
    assert _event("evt_verify_cap").outcome == "stale"


def test_verify_rejects_a_gateway_amount_that_does_not_match(v1_client, v1_db, monkeypatch):
    fetcher = _patch(monkeypatch)
    fetcher.status = "captured"
    fetcher.amount = 100
    headers = _super_headers(v1_client, v1_db, "pay-verify-mismatch-sa@eschool.com")
    ids = _school_bill(v1_client, headers, "PAYV11")
    _insert_payment(ids)
    response = v1_client.post("/api/v1/payments/verify", headers=headers, json=_verify_body())
    assert response.status_code == 409
    assert response.json()["detail"] == "Payment does not match the order"
    bill, _, payment = _state(ids["bill_id"])
    assert payment.status == PAYMENT_STATUS_CREATED
    assert payment.gateway_payment_id is None
    assert bill.status == BILL_STATUS_PENDING
    assert _count(AuditLog, AuditLog.action == "payment.verify_mismatch") == 1
    assert _count(SubscriptionInvoice) == 0


def test_verify_without_gateway_response_stays_authorized(v1_client, v1_db, monkeypatch):
    fetcher = _patch(monkeypatch)
    fetcher.status = None
    headers = _super_headers(v1_client, v1_db, "pay-verify-offline-sa@eschool.com")
    ids = _school_bill(v1_client, headers, "PAYV12")
    _insert_payment(ids)
    response = v1_client.post("/api/v1/payments/verify", headers=headers, json=_verify_body())
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "authorized"
    assert fetcher.calls == ["pay_test_1"]
    bill, _, _ = _state(ids["bill_id"])
    assert bill.status == BILL_STATUS_PENDING


def test_capture_on_a_cancelled_bill_does_not_pay_or_invoice(v1_client, monkeypatch):
    _patch(monkeypatch)
    ids = _orm_payment(code="PAYW11", order_id="order_cancelled")
    _set_bill_status(ids["bill_id"], BILL_STATUS_CANCELLED)
    raw, headers = _webhook(
        "payment.captured", order_id="order_cancelled", payment_id="pay_cancelled", event_id="evt_cancelled"
    )
    assert _post(v1_client, raw, headers).status_code == 200
    bill, _, payment = _state(ids["bill_id"])
    assert payment.status == PAYMENT_STATUS_CAPTURED
    assert bill.status == BILL_STATUS_CANCELLED
    assert _count(SubscriptionInvoice) == 0
    assert _count(AuditLog, AuditLog.action == "payment.captured_unpayable_bill") == 1
    assert _event("evt_cancelled").outcome == "bill_not_payable"


def test_retry_after_failed_attempt_on_the_same_order_pays_once(v1_client, monkeypatch):
    _patch(monkeypatch)
    ids = _orm_payment(code="PAYW12", order_id="order_retry")
    failed, failed_headers = _webhook("payment.failed", order_id="order_retry", payment_id="pay_try_1", event_id="evt_try_1")
    captured, captured_headers = _webhook(
        "payment.captured", order_id="order_retry", payment_id="pay_try_2", event_id="evt_try_2"
    )
    late, late_headers = _webhook("payment.failed", order_id="order_retry", payment_id="pay_try_1", event_id="evt_try_1b")
    assert _post(v1_client, failed, failed_headers).status_code == 200
    assert _post(v1_client, captured, captured_headers).status_code == 200
    assert _post(v1_client, late, late_headers).status_code == 200
    bill, _, payment = _state(ids["bill_id"])
    assert payment.status == PAYMENT_STATUS_CAPTURED
    assert payment.gateway_payment_id == "pay_try_2"
    assert bill.status == BILL_STATUS_PAID
    assert _count(SubscriptionInvoice) == 1
    assert _event("evt_try_1b").outcome == "stale"


def test_full_refund_marks_payment_refunded_and_keeps_bill_and_invoice(v1_client, monkeypatch):
    _patch(monkeypatch)
    ids = _orm_payment(code="PAYW13", order_id="order_refund")
    raw, headers = _webhook("payment.captured", order_id="order_refund", payment_id="pay_refund", event_id="evt_ref_cap")
    assert _post(v1_client, raw, headers).status_code == 200
    partial, partial_headers = _refund(payment_id="pay_refund", event_id="evt_ref_part", amount=1000, amount_refunded=1000)
    assert _post(v1_client, partial, partial_headers).status_code == 200
    _, _, payment = _state(ids["bill_id"])
    assert payment.status == PAYMENT_STATUS_CAPTURED
    assert _event("evt_ref_part").outcome == "partial_refund"
    full, full_headers = _refund(payment_id="pay_refund", event_id="evt_ref_full", amount=248900, amount_refunded=249900)
    assert _post(v1_client, full, full_headers).status_code == 200
    assert _post(v1_client, full, full_headers).status_code == 200
    bill, subscription, payment = _state(ids["bill_id"])
    assert payment.status == PAYMENT_STATUS_REFUNDED
    assert bill.status == BILL_STATUS_PAID
    assert subscription.end_date.isoformat() == ids["end_date"]
    assert _count(SubscriptionInvoice) == 1
    assert _count(AuditLog, AuditLog.action == "payment.refunded") == 1
    unknown, unknown_headers = _refund(payment_id="pay_not_ours", event_id="evt_ref_unknown", amount=100)
    assert _post(v1_client, unknown, unknown_headers).status_code == 200
    assert _event("evt_ref_unknown").outcome == "unknown_payment"


def test_mismatch_and_unknown_events_record_diagnostics(v1_client, monkeypatch):
    _patch(monkeypatch)
    ids = _orm_payment(code="PAYW14", order_id="order_diag")
    raw, headers = _webhook(
        "payment.captured", order_id="order_diag", payment_id="pay_diag", event_id="evt_diag", amount=5
    )
    assert _post(v1_client, raw, headers).status_code == 200
    event = _event("evt_diag")
    assert event.outcome == "amount_mismatch"
    assert event.amount_paise == 5
    assert event.currency == "INR"
    assert event.gateway_order_id == "order_diag"
    assert event.gateway_payment_id == "pay_diag"
    assert event.payment_transaction_id == ids["payment_id"]
    assert _count(AuditLog, AuditLog.action == "payment.mismatch") == 1
    other, other_headers = _signed({"event": "order.paid", "payload": {}}, "evt_order_paid")
    assert _post(v1_client, other, other_headers).status_code == 200
    assert _event("evt_order_paid").outcome == "ignored"
    bill, _, payment = _state(ids["bill_id"])
    assert payment.status == PAYMENT_STATUS_CREATED
    assert bill.status == BILL_STATUS_PENDING


def test_verify_after_failed_attempt_rebinds_to_the_new_payment(v1_client, v1_db, monkeypatch):
    _patch(monkeypatch)
    headers = _super_headers(v1_client, v1_db, "pay-verify-retry-sa@eschool.com")
    ids = _school_bill(v1_client, headers, "PAYV13")
    _insert_payment(ids, payment_id="pay_old", status=PAYMENT_STATUS_FAILED)
    response = v1_client.post("/api/v1/payments/verify", headers=headers, json=_verify_body(payment_id="pay_new"))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "authorized"
    _, _, payment = _state(ids["bill_id"])
    assert payment.gateway_payment_id == "pay_new"
    assert payment.status == PAYMENT_STATUS_AUTHORIZED
