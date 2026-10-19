"""POST /api/v1/payments/initiate. The gateway is mocked."""

from __future__ import annotations

from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import Settings
from app.core.database import session_factory
from app.models.tables import (
    PAYMENT_STATUS_AUTHORIZED,
    PAYMENT_STATUS_CAPTURED,
    PAYMENT_STATUS_FAILED,
    PaymentTransaction,
    Subscription,
    SubscriptionBill,
)
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User
from app.services.v1.payment_order_service import PaymentOrderError


class FakeGateway:
    def __init__(self):
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.order_id = "order_test_1"

    def create_order(self, *, amount_paise: int, currency: str, receipt: str, notes: dict[str, str]) -> dict:
        self.calls.append({"amount_paise": amount_paise, "currency": currency, "notes": notes})
        if self.error is not None:
            raise self.error
        return {"id": self.order_id, "amount": amount_paise, "currency": currency}


def _settings(**overrides) -> Settings:
    values = {
        "app_env": "test",
        "razorpay_currency": "INR",
        "razorpay_key_id": "rzp_test_unit",
        "razorpay_key_secret": SecretStr("unit-secret"),
        "razorpay_webhook_secret": SecretStr("unit-webhook"),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str):
    return client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "secret123", "first_name": "Pay", "last_name": "Admin"},
    )


def _super_headers(client, v1_db, email: str) -> dict[str, str]:
    assert _signup(client, email).status_code == 201
    user = v1_db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200
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


def _bill(client, headers, *, code: str, amount: float = 2499, bill_status: int = 0):
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
    bill = client.post(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions/{subscription_id}/bills",
        headers=headers,
        json={
            "period_start": "2026-10-01",
            "period_end": "2026-11-01",
            "amount": amount,
            "status": bill_status,
        },
    )
    assert bill.status_code == 201, bill.text
    return {
        "school_id": school_id,
        "subscription_id": subscription_id,
        "bill_id": bill.json()["id"],
    }


def _body(ids: dict, key: str, **extra) -> dict:
    body = {
        "bill_id": ids["bill_id"],
        "school_id": ids["school_id"],
        "subscription_id": ids["subscription_id"],
        "idempotency_key": key,
    }
    body.update(extra)
    return body


def _use_gateway(monkeypatch, gateway: FakeGateway | None = None) -> FakeGateway:
    fake = gateway or FakeGateway()
    monkeypatch.setattr("app.api.v1.payments.get_settings", lambda: _settings())
    monkeypatch.setattr("app.services.v1.payment_order_service._build_gateway", lambda _settings: fake)
    return fake


def test_school_admin_initiate_returns_paise_and_hides_secrets(v1_client, v1_db, monkeypatch):
    gateway = _use_gateway(monkeypatch)
    super_headers = _super_headers(v1_client, v1_db, "pay-init-sa@eschool.com")
    ids = _bill(v1_client, super_headers, code="PAYI01")
    admin_headers = _school_admin_headers(v1_client, super_headers, ids["school_id"], "pay-init-admin@eschool.com")
    response = v1_client.post("/api/v1/payments/initiate", headers=admin_headers, json=_body(ids, "admin-key"))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload == {
        "order_id": "order_test_1",
        "amount": 249900,
        "currency": "INR",
        "gateway": "razorpay",
        "key_id": "rzp_test_unit",
        "status": "created",
    }
    assert gateway.calls[0]["amount_paise"] == 249900
    assert "unit-secret" not in response.text
    assert "unit-webhook" not in response.text
    assert "key_secret" not in response.text
    check = session_factory()()
    try:
        bill = check.get(SubscriptionBill, ids["bill_id"])
        subscription = check.get(Subscription, ids["subscription_id"])
        assert bill is not None and bill.status == 0
        assert subscription is not None and subscription.status == 1
    finally:
        check.close()


def test_initiate_requires_authentication(v1_client):
    response = v1_client.post(
        "/api/v1/payments/initiate",
        json={"bill_id": 1, "school_id": 1, "subscription_id": 1, "idempotency_key": "anon"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_school_admin_cannot_initiate_another_schools_bill(v1_client, v1_db, monkeypatch):
    gateway = _use_gateway(monkeypatch)
    super_headers = _super_headers(v1_client, v1_db, "pay-cross-sa@eschool.com")
    own = _bill(v1_client, super_headers, code="PAYI02")
    other = _bill(v1_client, super_headers, code="PAYI03")
    admin_headers = _school_admin_headers(v1_client, super_headers, own["school_id"], "pay-cross-admin@eschool.com")
    response = v1_client.post("/api/v1/payments/initiate", headers=admin_headers, json=_body(other, "cross-key"))
    assert response.status_code == 403
    assert gateway.calls == []


def test_invalid_and_ineligible_bills_are_rejected(v1_client, v1_db, monkeypatch):
    gateway = _use_gateway(monkeypatch)
    super_headers = _super_headers(v1_client, v1_db, "pay-bad-sa@eschool.com")
    ids = _bill(v1_client, super_headers, code="PAYI04")
    paid = _bill(v1_client, super_headers, code="PAYI05", bill_status=1)
    admin_headers = _school_admin_headers(v1_client, super_headers, ids["school_id"], "pay-bad-admin@eschool.com")
    missing = v1_client.post(
        "/api/v1/payments/initiate",
        headers=admin_headers,
        json=_body({**ids, "bill_id": 999999}, "missing-bill"),
    )
    assert missing.status_code == 404
    mismatched = v1_client.post(
        "/api/v1/payments/initiate",
        headers=admin_headers,
        json=_body({**ids, "subscription_id": paid["subscription_id"]}, "wrong-subscription"),
    )
    assert mismatched.status_code == 404
    paid_admin = _school_admin_headers(v1_client, super_headers, paid["school_id"], "pay-paid-admin@eschool.com")
    ineligible = v1_client.post("/api/v1/payments/initiate", headers=paid_admin, json=_body(paid, "paid-bill"))
    assert ineligible.status_code == 422
    assert ineligible.json()["detail"] == "Bill is not payable"
    assert gateway.calls == []


def test_super_admin_can_initiate(v1_client, v1_db, monkeypatch):
    _use_gateway(monkeypatch)
    headers = _super_headers(v1_client, v1_db, "pay-super-init@eschool.com")
    ids = _bill(v1_client, headers, code="PAYI06", amount=10.125)
    response = v1_client.post("/api/v1/payments/initiate", headers=headers, json=_body(ids, "super-key"))
    assert response.status_code == 200, response.text
    assert response.json()["amount"] == 1013
    assert response.json()["key_id"] == "rzp_test_unit"


def test_missing_gateway_configuration(v1_client, v1_db, monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.payments.get_settings",
        lambda: _settings(razorpay_key_id="", razorpay_key_secret=SecretStr("")),
    )
    headers = _super_headers(v1_client, v1_db, "pay-missing-sa@eschool.com")
    ids = _bill(v1_client, headers, code="PAYI07")
    response = v1_client.post("/api/v1/payments/initiate", headers=headers, json=_body(ids, "missing-config"))
    assert response.status_code == 503
    assert response.json()["detail"] == "Payment configuration is missing"
    assert "unit-webhook" not in response.text
    check = session_factory()()
    try:
        assert check.scalar(select(PaymentTransaction.id)) is None
    finally:
        check.close()


def test_repeated_idempotency_key_reuses_the_order(v1_client, v1_db, monkeypatch):
    gateway = _use_gateway(monkeypatch)
    headers = _super_headers(v1_client, v1_db, "pay-repeat-sa@eschool.com")
    ids = _bill(v1_client, headers, code="PAYI08")
    first = v1_client.post("/api/v1/payments/initiate", headers=headers, json=_body(ids, "repeat-key"))
    second = v1_client.post("/api/v1/payments/initiate", headers=headers, json=_body(ids, "repeat-key"))
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["order_id"] == second.json()["order_id"]
    assert len(gateway.calls) == 1


def test_gateway_failure_does_not_expose_secrets_or_change_the_bill(v1_client, v1_db, monkeypatch):
    gateway = _use_gateway(monkeypatch)
    gateway.error = PaymentOrderError("Payment gateway rejected the order", status_code=502)
    headers = _super_headers(v1_client, v1_db, "pay-fail-sa@eschool.com")
    ids = _bill(v1_client, headers, code="PAYI09")
    response = v1_client.post("/api/v1/payments/initiate", headers=headers, json=_body(ids, "fail-key"))
    assert response.status_code == 502
    assert response.json()["detail"] == "Payment gateway rejected the order"
    assert "unit-secret" not in response.text
    assert "unit-webhook" not in response.text
    check = session_factory()()
    try:
        bill = check.get(SubscriptionBill, ids["bill_id"])
        subscription = check.get(Subscription, ids["subscription_id"])
        assert bill is not None and bill.status == 0
        assert subscription is not None and subscription.status == 1
        assert check.scalar(select(PaymentTransaction.id)) is None
    finally:
        check.close()


def test_client_amount_is_rejected(v1_client, v1_db, monkeypatch):
    gateway = _use_gateway(monkeypatch)
    headers = _super_headers(v1_client, v1_db, "pay-amount-sa@eschool.com")
    ids = _bill(v1_client, headers, code="PAYI10")
    response = v1_client.post(
        "/api/v1/payments/initiate",
        headers=headers,
        json=_body(ids, "amount-key", amount=1),
    )
    assert response.status_code == 422
    assert gateway.calls == []


def test_captured_payment_is_not_charged_again(v1_client, v1_db, monkeypatch):
    gateway = _use_gateway(monkeypatch)
    headers = _super_headers(v1_client, v1_db, "pay-captured-sa@eschool.com")
    ids = _bill(v1_client, headers, code="PAYI11")
    created = v1_client.post("/api/v1/payments/initiate", headers=headers, json=_body(ids, "captured-key"))
    assert created.status_code == 200
    db = session_factory()()
    try:
        row = db.scalar(select(PaymentTransaction).where(PaymentTransaction.bill_id == ids["bill_id"]))
        assert row is not None
        row.status = PAYMENT_STATUS_CAPTURED
        db.commit()
    finally:
        db.close()
    again = v1_client.post("/api/v1/payments/initiate", headers=headers, json=_body(ids, "new-key"))
    assert again.status_code == 409
    assert again.json()["detail"] == "Bill already has a captured payment"
    replay = v1_client.post("/api/v1/payments/initiate", headers=headers, json=_body(ids, "captured-key"))
    assert replay.status_code == 200
    assert replay.json()["status"] == "captured"
    assert replay.json()["order_id"] == "order_test_1"
    assert len(gateway.calls) == 1


def _set_payment_status(bill_id: int, status: int) -> None:
    db = session_factory()()
    try:
        row = db.scalar(select(PaymentTransaction).where(PaymentTransaction.bill_id == bill_id))
        assert row is not None
        row.status = status
        db.commit()
    finally:
        db.close()


def test_a_new_key_reuses_the_bills_open_order(v1_client, v1_db, monkeypatch):
    gateway = _use_gateway(monkeypatch)
    headers = _super_headers(v1_client, v1_db, "pay-newkey-sa@eschool.com")
    ids = _bill(v1_client, headers, code="PAYI12")
    admin = _school_admin_headers(v1_client, headers, ids["school_id"], "pay-newkey-admin@eschool.com")
    first = v1_client.post("/api/v1/payments/initiate", headers=admin, json=_body(ids, "click-1"))
    second = v1_client.post("/api/v1/payments/initiate", headers=admin, json=_body(ids, "click-2"))
    from_super = v1_client.post("/api/v1/payments/initiate", headers=headers, json=_body(ids, "super-click"))
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert from_super.status_code == 200, from_super.text
    assert first.json()["order_id"] == second.json()["order_id"] == from_super.json()["order_id"]
    assert len(gateway.calls) == 1
    check = session_factory()()
    try:
        rows = check.scalars(select(PaymentTransaction).where(PaymentTransaction.bill_id == ids["bill_id"])).all()
        assert len(rows) == 1
    finally:
        check.close()


def test_a_failed_order_is_reused_and_an_authorized_order_blocks(v1_client, v1_db, monkeypatch):
    gateway = _use_gateway(monkeypatch)
    headers = _super_headers(v1_client, v1_db, "pay-reuse-sa@eschool.com")
    ids = _bill(v1_client, headers, code="PAYI13")
    assert v1_client.post("/api/v1/payments/initiate", headers=headers, json=_body(ids, "attempt-1")).status_code == 200
    _set_payment_status(ids["bill_id"], PAYMENT_STATUS_FAILED)
    retry = v1_client.post("/api/v1/payments/initiate", headers=headers, json=_body(ids, "attempt-2"))
    assert retry.status_code == 200, retry.text
    assert retry.json()["order_id"] == "order_test_1"
    assert retry.json()["status"] == "failed"
    _set_payment_status(ids["bill_id"], PAYMENT_STATUS_AUTHORIZED)
    blocked = v1_client.post("/api/v1/payments/initiate", headers=headers, json=_body(ids, "attempt-3"))
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "A payment for this bill is awaiting capture"
    assert len(gateway.calls) == 1
