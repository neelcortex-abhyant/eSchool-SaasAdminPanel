"""Subscription receipts. Signatures are local HMACs. No live Razorpay calls."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date, datetime, timezone
from threading import Barrier, Thread

from pydantic import SecretStr
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.database import session_factory
from app.models.tables import (
    PAYMENT_STATUS_AUTHORIZED,
    PAYMENT_STATUS_CAPTURED,
    PAYMENT_STATUS_CREATED,
    PAYMENT_STATUS_FAILED,
    Package,
    PaymentTransaction,
    School,
    Subscription,
    SubscriptionBill,
    SubscriptionInvoice,
)
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User
from app.services.v1.invoice_service import issue_invoice_for_captured_payment
from app.services.v1.subscription_service import BILL_STATUS_PENDING, SUB_STATUS_ACTIVE


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        razorpay_currency="INR",
        razorpay_key_id="rzp_test_unit",
        razorpay_key_secret=SecretStr("unit-secret"),
        razorpay_webhook_secret=SecretStr("unit-webhook"),
    )


def _patch(monkeypatch) -> None:
    monkeypatch.setattr("app.api.v1.payments.get_settings", lambda: _settings())
    monkeypatch.setattr(
        "app.services.v1.payment_verification_service._build_fetcher",
        lambda _settings: None,
    )


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


def _seed(*, code: str, order_id: str, status: int, payment_ref: str | None) -> int:
    db = session_factory()()
    try:
        now = datetime(2026, 10, 2, 12, 0, 0)
        school = School(
            name=f"Invoice School {code}",
            address="12 School Road",
            support_email=f"{code.lower()}@eschool.com",
            support_phone="9000000000",
            code=code,
            status=1,
            installed=1,
            created_at=now,
            updated_at=now,
        )
        plan = Package(
            name=f"Plan {code}",
            description="Monthly subscription",
            monthly_price=10,
            yearly_price=100,
            status=1,
            created_at=now,
        )
        db.add_all([school, plan])
        db.flush()
        subscription = Subscription(
            school_id=school.id,
            package_id=plan.id,
            status=SUB_STATUS_ACTIVE,
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
            gateway_payment_id=payment_ref,
            idempotency_key=order_id,
            amount_paise=249900,
            currency="INR",
            status=status,
            created_at=now,
            updated_at=now,
        )
        db.add(payment)
        db.commit()
        return payment.id
    finally:
        db.close()


def _webhook(event: str, *, order_id: str, payment_id: str, event_id: str) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(
        {
            "event": event,
            "payload": {
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "order_id": order_id,
                        "amount": 249900,
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


def _invoice_count() -> int:
    db = session_factory()()
    try:
        return int(db.scalar(select(func.count()).select_from(SubscriptionInvoice)) or 0)
    finally:
        db.close()


def _one_invoice() -> SubscriptionInvoice:
    db = session_factory()()
    try:
        row = db.scalar(select(SubscriptionInvoice))
        assert row is not None
        db.expunge(row)
        return row
    finally:
        db.close()


def test_captured_webhook_issues_one_invoice_and_repeat_does_not_duplicate(v1_client, monkeypatch):
    _patch(monkeypatch)
    payment_id = _seed(
        code="INV01",
        order_id="order_inv_1",
        status=PAYMENT_STATUS_CREATED,
        payment_ref=None,
    )
    body, headers = _webhook(
        "payment.captured",
        order_id="order_inv_1",
        payment_id="pay_inv_1",
        event_id="evt_inv_1",
    )
    first = v1_client.post("/api/v1/payments/webhook/razorpay", content=body, headers=headers)
    assert first.status_code == 200, first.text
    assert _invoice_count() == 1
    invoice = _one_invoice()
    assert invoice.payment_transaction_id == payment_id
    assert invoice.invoice_number.startswith("SUB-")
    assert invoice.amount_paise == 249900
    assert invoice.total_amount_paise == 249900
    assert invoice.currency == "INR"
    assert invoice.gateway == "razorpay"
    assert invoice.gateway_payment_id == "pay_inv_1"
    assert invoice.tax_label is None
    assert invoice.tax_rate_percent is None
    assert invoice.tax_amount_paise is None
    assert invoice.school_name == "Invoice School INV01"
    assert invoice.plan_name == "Plan INV01"
    again, again_headers = _webhook(
        "payment.captured",
        order_id="order_inv_1",
        payment_id="pay_inv_1",
        event_id="evt_inv_1",
    )
    assert v1_client.post("/api/v1/payments/webhook/razorpay", content=again, headers=again_headers).status_code == 200
    other, other_headers = _webhook(
        "payment.captured",
        order_id="order_inv_1",
        payment_id="pay_inv_1",
        event_id="evt_inv_1b",
    )
    assert v1_client.post("/api/v1/payments/webhook/razorpay", content=other, headers=other_headers).status_code == 200
    assert _invoice_count() == 1


def test_non_captured_payments_do_not_issue_invoices(v1_client, monkeypatch):
    _patch(monkeypatch)
    for status, ref, order_id in (
        (PAYMENT_STATUS_CREATED, None, "order_inv_created"),
        (PAYMENT_STATUS_AUTHORIZED, "pay_auth", "order_inv_auth"),
        (PAYMENT_STATUS_FAILED, "pay_fail", "order_inv_fail"),
    ):
        payment_id = _seed(code=order_id[-6:].upper(), order_id=order_id, status=status, payment_ref=ref)
        db = session_factory()()
        try:
            row = db.get(PaymentTransaction, payment_id)
            assert row is not None
            assert issue_invoice_for_captured_payment(db, row) is None
            db.commit()
        finally:
            db.close()
    failed = _seed(code="INVFL", order_id="order_inv_webhook_fail", status=PAYMENT_STATUS_CREATED, payment_ref=None)
    body, headers = _webhook(
        "payment.failed",
        order_id="order_inv_webhook_fail",
        payment_id="pay_webhook_fail",
        event_id="evt_inv_fail",
    )
    assert v1_client.post("/api/v1/payments/webhook/razorpay", content=body, headers=headers).status_code == 200
    pending, pending_headers = _webhook(
        "payment.pending",
        order_id="order_inv_webhook_fail",
        payment_id="pay_webhook_fail",
        event_id="evt_inv_pending",
    )
    assert v1_client.post("/api/v1/payments/webhook/razorpay", content=pending, headers=pending_headers).status_code == 200
    db = session_factory()()
    try:
        row = db.get(PaymentTransaction, failed)
        assert row is not None
        assert row.status == PAYMENT_STATUS_FAILED
    finally:
        db.close()
    assert _invoice_count() == 0


def test_invoice_access_pdf_and_snapshot(v1_client, v1_db, monkeypatch):
    _patch(monkeypatch)
    headers = _super_headers(v1_client, v1_db, "invoice-sa@eschool.com")
    payment_id = _seed(code="INV02", order_id="order_inv_2", status=PAYMENT_STATUS_CREATED, payment_ref=None)
    body, hook_headers = _webhook(
        "payment.captured",
        order_id="order_inv_2",
        payment_id="pay_inv_2",
        event_id="evt_inv_2",
    )
    assert v1_client.post("/api/v1/payments/webhook/razorpay", content=body, headers=hook_headers).status_code == 200
    invoice = _one_invoice()
    db = session_factory()()
    try:
        school = db.scalar(select(School).where(School.code == "INV02"))
        plan = db.scalar(select(Package).where(Package.name == "Plan INV02"))
        assert school is not None and plan is not None
        school_id = school.id
        school.name = "Renamed School"
        school.address = "New address"
        plan.name = "Renamed Plan"
        plan.description = "Changed later"
        db.commit()
    finally:
        db.close()
    detail = v1_client.get(f"/api/v1/super-admin/invoices/{invoice.id}", headers=headers)
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["invoice_number"] == invoice.invoice_number
    assert payload["school_name"] == "Invoice School INV02"
    assert payload["school_address"] == "12 School Road"
    assert payload["plan_name"] == "Plan INV02"
    assert payload["plan_description"] == "Monthly subscription"
    assert payload["amount"] == 249900
    assert payload["tax_label"] is None
    assert payload["tax_amount"] is None
    assert payload["order_id"] == "order_inv_2"
    assert payload["payment_id"] == "pay_inv_2"
    assert "unit-secret" not in detail.text
    assert "signature" not in payload
    pdf = v1_client.get(f"/api/v1/super-admin/invoices/{invoice.id}/pdf", headers=headers)
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF")
    assert len(pdf.content) > 200
    assert invoice.invoice_number.encode() in pdf.content
    assert b"Invoice School INV02" in pdf.content
    assert b"Renamed School" not in pdf.content
    assert b"GST" not in pdf.content
    disposition = pdf.headers["content-disposition"]
    assert invoice.invoice_number in disposition
    admin = _school_admin_headers(v1_client, headers, school_id, "invoice-admin@eschool.com")
    own = v1_client.get(f"/api/v1/schools/{school_id}/invoices/{invoice.id}", headers=admin)
    assert own.status_code == 200, own.text
    own_pdf = v1_client.get(f"/api/v1/schools/{school_id}/invoices/{invoice.id}/pdf", headers=admin)
    assert own_pdf.status_code == 200
    assert own_pdf.content.startswith(b"%PDF")
    assert v1_client.get(f"/api/v1/super-admin/invoices/{invoice.id}", headers=admin).status_code == 403
    other_id = _seed(code="INV03", order_id="order_inv_3", status=PAYMENT_STATUS_CAPTURED, payment_ref="pay_inv_3")
    db = session_factory()()
    try:
        other_payment = db.get(PaymentTransaction, other_id)
        assert other_payment is not None
        other_invoice = issue_invoice_for_captured_payment(db, other_payment)
        db.commit()
        assert other_invoice is not None
        other_invoice_id = other_invoice.id
        other_school_id = other_invoice.school_id
    finally:
        db.close()
    hidden = v1_client.get(f"/api/v1/schools/{school_id}/invoices/{other_invoice_id}", headers=admin)
    assert hidden.status_code == 404
    assert hidden.json()["detail"] == "Invoice not found"
    cross_school = v1_client.get(
        f"/api/v1/schools/{other_school_id}/invoices/{other_invoice_id}",
        headers=admin,
    )
    assert cross_school.status_code == 403
    missing = v1_client.get("/api/v1/super-admin/invoices/999999", headers=headers)
    assert missing.status_code == 404
    assert v1_client.get(f"/api/v1/super-admin/invoices/{invoice.id}").status_code == 401
    db = session_factory()()
    try:
        stored = db.get(SubscriptionInvoice, invoice.id)
        assert stored is not None
        assert stored.school_name == "Invoice School INV02"
        assert stored.plan_name == "Plan INV02"
        assert stored.payment_transaction_id == payment_id
    finally:
        db.close()


def test_concurrent_invoice_numbers_are_unique(v1_client):
    first = _seed(code="INVC1", order_id="order_inv_c1", status=PAYMENT_STATUS_CAPTURED, payment_ref="pay_c1")
    second = _seed(code="INVC2", order_id="order_inv_c2", status=PAYMENT_STATUS_CAPTURED, payment_ref="pay_c2")
    barrier = Barrier(2)
    numbers: list[str] = []
    errors: list[BaseException] = []

    def _issue(payment_id: int) -> None:
        db = session_factory()()
        try:
            barrier.wait(timeout=30)
            row = db.get(PaymentTransaction, payment_id)
            assert row is not None
            invoice = issue_invoice_for_captured_payment(db, row)
            db.commit()
            assert invoice is not None
            numbers.append(invoice.invoice_number)
        except BaseException as exc:
            db.rollback()
            errors.append(exc)
        finally:
            db.close()

    threads = [Thread(target=_issue, args=(payment_id,)) for payment_id in (first, second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert errors == []
    assert len(numbers) == 2
    assert len(set(numbers)) == 2
    assert _invoice_count() == 2


def _issue(payment_id: int) -> SubscriptionInvoice:
    db = session_factory()()
    try:
        row = db.get(PaymentTransaction, payment_id)
        assert row is not None
        invoice = issue_invoice_for_captured_payment(db, row)
        db.commit()
        assert invoice is not None
        db.refresh(invoice)
        db.expunge(invoice)
        return invoice
    finally:
        db.close()


def test_invoice_lists_filters_pagination_and_scope(v1_client, v1_db, monkeypatch):
    _patch(monkeypatch)
    headers = _super_headers(v1_client, v1_db, "invoice-list-sa@eschool.com")
    first = _issue(_seed(code="INVL1", order_id="order_list_1", status=PAYMENT_STATUS_CAPTURED, payment_ref="pay_list_1"))
    second = _issue(_seed(code="INVL2", order_id="order_list_2", status=PAYMENT_STATUS_CAPTURED, payment_ref="pay_list_2"))

    listed = v1_client.get("/api/v1/super-admin/invoices", headers=headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] == 2
    assert {item["id"] for item in body["items"]} == {first.id, second.id}
    paged = v1_client.get("/api/v1/super-admin/invoices?page=2&page_size=1", headers=headers)
    assert paged.status_code == 200
    assert paged.json()["total"] == 2
    assert len(paged.json()["items"]) == 1
    by_school = v1_client.get(f"/api/v1/super-admin/invoices?school_id={first.school_id}", headers=headers)
    assert [item["id"] for item in by_school.json()["items"]] == [first.id]
    issued = first.issued_at.date().isoformat()
    by_date = v1_client.get(
        f"/api/v1/super-admin/invoices?from_date={issued}&to_date={issued}", headers=headers
    )
    assert by_date.json()["total"] == 2
    bad_range = v1_client.get(
        "/api/v1/super-admin/invoices?from_date=2026-10-10&to_date=2026-10-01", headers=headers
    )
    assert bad_range.status_code == 422
    assert v1_client.get("/api/v1/super-admin/invoices").status_code == 401

    admin = _school_admin_headers(v1_client, headers, first.school_id, "invoice-list-admin@eschool.com")
    own = v1_client.get(f"/api/v1/schools/{first.school_id}/invoices", headers=admin)
    assert own.status_code == 200, own.text
    assert [item["id"] for item in own.json()["items"]] == [first.id]
    assert own.json()["items"][0]["invoice_number"] == first.invoice_number
    assert v1_client.get(f"/api/v1/schools/{second.school_id}/invoices", headers=admin).status_code == 403
    assert v1_client.get("/api/v1/super-admin/invoices", headers=admin).status_code == 403
    missing_school = v1_client.get("/api/v1/schools/999999/invoices", headers=headers)
    assert missing_school.status_code == 404

    payments = v1_client.get(f"/api/v1/schools/{first.school_id}/payments", headers=admin)
    assert payments.status_code == 200
    assert payments.json()["items"][0]["invoice_id"] == first.id


def test_invoice_pdf_headers_are_safe(v1_client, v1_db, monkeypatch):
    _patch(monkeypatch)
    headers = _super_headers(v1_client, v1_db, "invoice-pdf-sa@eschool.com")
    invoice = _issue(_seed(code="INVP1", order_id="order_pdf_1", status=PAYMENT_STATUS_CAPTURED, payment_ref="pay_pdf_1"))
    pdf = v1_client.get(f"/api/v1/super-admin/invoices/{invoice.id}/pdf", headers=headers)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["content-disposition"] == f'attachment; filename="{invoice.invoice_number}.pdf"'
    assert pdf.headers["cache-control"] == "private, no-store"
    assert pdf.headers["x-content-type-options"] == "nosniff"
    assert pdf.content.startswith(b"%PDF")
