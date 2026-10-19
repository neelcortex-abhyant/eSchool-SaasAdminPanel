"""Payment order service against the isolated test database. The gateway is mocked."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import session_factory
from app.models.tables import (
    PAYMENT_STATUS_CAPTURED,
    PAYMENT_STATUS_CREATED,
    PAYMENT_STATUS_REFUNDED,
    Package,
    PaymentTransaction,
    School,
    Subscription,
    SubscriptionBill,
)
from app.models.v1.roles import ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN, ROLE_USER
from app.services.v1.payment_order_service import PaymentCaller, PaymentOrderError, create_payment_order
from app.services.v1.subscription_service import BILL_STATUS_PAID, BILL_STATUS_PENDING, SUB_STATUS_ACTIVE


class FakeGateway:
    def __init__(self, *, order_id: str = "order_test_1", amount: int | None = None, currency: str = "INR"):
        self.order_id = order_id
        self.amount = amount
        self.currency = currency
        self.calls: list[dict] = []
        self.error: Exception | None = None

    def create_order(self, *, amount_paise: int, currency: str, receipt: str, notes: dict[str, str]) -> dict:
        self.calls.append(
            {
                "amount_paise": amount_paise,
                "currency": currency,
                "receipt": receipt,
                "notes": notes,
            }
        )
        if self.error is not None:
            raise self.error
        return {
            "id": self.order_id,
            "amount": amount_paise if self.amount is None else self.amount,
            "currency": self.currency,
        }


def _settings(**overrides) -> Settings:
    values = {
        "app_env": "test",
        "razorpay_currency": "INR",
        "razorpay_key_id": "",
        "razorpay_key_secret": SecretStr(""),
        "razorpay_webhook_secret": SecretStr("unit-webhook"),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _seed(db: Session, *, amount: float = 10.125, bill_status: int = BILL_STATUS_PENDING, code: str = "PAY01"):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    school = School(name="Pay School", code=code, status=1, installed=1, created_at=now, updated_at=now)
    other = School(name="Other School", code=f"{code}B", status=1, installed=1, created_at=now, updated_at=now)
    plan = Package(name=f"Pay Plan {code}", monthly_price=10.125, yearly_price=100, status=1, created_at=now)
    db.add_all([school, other, plan])
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
        amount=amount,
        status=bill_status,
        period_start=date(2026, 10, 1),
        period_end=date(2026, 11, 1),
        created_at=now,
        updated_at=now,
    )
    db.add(bill)
    db.commit()
    return school, other, subscription, bill


def test_order_uses_bill_amount_and_leaves_the_bill_unpaid(v1_client):
    db = session_factory()()
    try:
        school, _, subscription, bill = _seed(db)
        gateway = FakeGateway()
        row = create_payment_order(
            db,
            bill.id,
            caller=PaymentCaller(ROLE_SUPER_ADMIN),
            idempotency_key="same-request",
            settings=_settings(),
            gateway=gateway,
        )
        assert row.school_id == school.id
        assert row.bill_id == bill.id
        assert row.amount_paise == 1013
        assert row.currency == "INR"
        assert row.status == 0
        assert row.gateway_order_id == "order_test_1"
        assert gateway.calls[0]["amount_paise"] == 1013
        assert gateway.calls[0]["notes"]["school_id"] == str(school.id)
        assert "unit-webhook" not in str(gateway.calls)
        db.refresh(bill)
        db.refresh(subscription)
        assert bill.status == BILL_STATUS_PENDING
        assert subscription.status == SUB_STATUS_ACTIVE
    finally:
        db.close()


def test_repeat_with_the_same_key_does_not_create_another_order(v1_client):
    db = session_factory()()
    try:
        _, _, _, bill = _seed(db, code="PAY02")
        gateway = FakeGateway()
        caller = PaymentCaller(ROLE_SCHOOL_ADMIN, bill.school_id)
        first = create_payment_order(
            db, bill.id, caller=caller, idempotency_key="repeat-key", settings=_settings(), gateway=gateway
        )
        second = create_payment_order(
            db, bill.id, caller=caller, idempotency_key="repeat-key", settings=_settings(), gateway=gateway
        )
        assert first.id == second.id
        assert len(gateway.calls) == 1
        assert db.scalar(select(func.count()).select_from(PaymentTransaction)) == 1
        db.refresh(bill)
        assert bill.status == BILL_STATUS_PENDING
    finally:
        db.close()


def test_same_key_with_a_different_bill_is_rejected(v1_client):
    db = session_factory()()
    try:
        school, _, subscription, bill = _seed(db, code="PAY03")
        gateway = FakeGateway()
        create_payment_order(
            db,
            bill.id,
            caller=PaymentCaller(ROLE_SUPER_ADMIN),
            idempotency_key="shared-key",
            settings=_settings(),
            gateway=gateway,
        )
        other_bill = SubscriptionBill(
            subscription_id=subscription.id,
            school_id=school.id,
            amount=10.125,
            status=BILL_STATUS_PENDING,
            period_start=date(2026, 11, 2),
            period_end=date(2026, 12, 2),
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(other_bill)
        db.commit()
        with pytest.raises(PaymentOrderError) as caught:
            create_payment_order(
                db,
                other_bill.id,
                caller=PaymentCaller(ROLE_SUPER_ADMIN),
                idempotency_key="shared-key",
                settings=_settings(),
                gateway=gateway,
            )
        assert caught.value.status_code == 409
        assert len(gateway.calls) == 1
        assert db.scalar(select(func.count()).select_from(PaymentTransaction)) == 1
    finally:
        db.close()


def test_zero_amount_and_gateway_failure_do_not_store_a_payment(v1_client):
    db = session_factory()()
    try:
        _, _, _, zero_bill = _seed(db, amount=0, code="PAY04")
        gateway = FakeGateway()
        with pytest.raises(PaymentOrderError) as zero:
            create_payment_order(
                db,
                zero_bill.id,
                caller=PaymentCaller(ROLE_SUPER_ADMIN),
                idempotency_key="zero-key",
                settings=_settings(),
                gateway=gateway,
            )
        assert zero.value.status_code == 422
        assert gateway.calls == []

        _, _, _, bill = _seed(db, code="PAY05")
        gateway.error = PaymentOrderError("Payment gateway rejected the order", status_code=502)
        with pytest.raises(PaymentOrderError) as failed:
            create_payment_order(
                db,
                bill.id,
                caller=PaymentCaller(ROLE_SUPER_ADMIN),
                idempotency_key="fail-key",
                settings=_settings(),
                gateway=gateway,
            )
        assert failed.value.status_code == 502
        assert failed.value.outcome_unknown is False
        assert db.scalar(select(func.count()).select_from(PaymentTransaction)) == 0
        db.refresh(bill)
        assert bill.status == BILL_STATUS_PENDING
    finally:
        db.close()


def test_missing_credentials_stop_before_the_gateway(v1_client):
    db = session_factory()()
    try:
        _, _, _, bill = _seed(db, code="PAY06")
        with pytest.raises(PaymentOrderError) as caught:
            create_payment_order(
                db,
                bill.id,
                caller=PaymentCaller(ROLE_SUPER_ADMIN),
                idempotency_key="missing-key",
                settings=_settings(),
            )
        assert caught.value.status_code == 503
        assert caught.value.detail == "Payment configuration is missing"
        assert db.scalar(select(func.count()).select_from(PaymentTransaction)) == 0
    finally:
        db.close()


def test_other_school_cannot_order_and_paid_bill_stays_paid(v1_client):
    db = session_factory()()
    try:
        _, other, subscription, bill = _seed(db, code="PAY07")
        gateway = FakeGateway()
        with pytest.raises(PaymentOrderError) as forbidden:
            create_payment_order(
                db,
                bill.id,
                caller=PaymentCaller(ROLE_SCHOOL_ADMIN, other.id),
                idempotency_key="cross-school",
                settings=_settings(),
                gateway=gateway,
            )
        assert forbidden.value.status_code == 403
        with pytest.raises(PaymentOrderError) as user_denied:
            create_payment_order(
                db,
                bill.id,
                caller=PaymentCaller(ROLE_USER, bill.school_id),
                idempotency_key="user-key",
                settings=_settings(),
                gateway=gateway,
            )
        assert user_denied.value.status_code == 403
        bill.status = BILL_STATUS_PAID
        db.commit()
        with pytest.raises(PaymentOrderError) as paid:
            create_payment_order(
                db,
                bill.id,
                caller=PaymentCaller(ROLE_SUPER_ADMIN),
                idempotency_key="paid-key",
                settings=_settings(),
                gateway=gateway,
            )
        assert paid.value.status_code == 422
        assert gateway.calls == []
        db.refresh(bill)
        db.refresh(subscription)
        assert bill.status == BILL_STATUS_PAID
        assert subscription.status == SUB_STATUS_ACTIVE
    finally:
        db.close()


def test_commit_failure_rolls_back_the_payment_and_keeps_the_bill(v1_client, monkeypatch):
    db = session_factory()()
    try:
        _, _, _, bill = _seed(db, code="PAY08")
        bill_id = bill.id
        gateway = FakeGateway(order_id="order_commit_fail")

        def fail_commit(self):
            self.flush()
            raise RuntimeError("commit failed")

        monkeypatch.setattr(Session, "commit", fail_commit)
        with pytest.raises(PaymentOrderError) as caught:
            create_payment_order(
                db,
                bill.id,
                caller=PaymentCaller(ROLE_SUPER_ADMIN),
                idempotency_key="commit-key",
                settings=_settings(),
                gateway=gateway,
            )
        assert caught.value.outcome_unknown is True
        assert len(gateway.calls) == 1
    finally:
        db.close()
    check = session_factory()()
    try:
        stored_bill = check.get(SubscriptionBill, bill_id)
        assert stored_bill is not None
        assert stored_bill.status == BILL_STATUS_PENDING
        assert check.scalar(select(func.count()).select_from(PaymentTransaction)) == 0
    finally:
        check.close()


def test_different_keys_for_one_bill_share_one_order(v1_client):
    db = session_factory()()
    try:
        _, _, _, bill = _seed(db, code="PAY09")
        gateway = FakeGateway()
        caller = PaymentCaller(ROLE_SCHOOL_ADMIN, bill.school_id)
        first = create_payment_order(
            db, bill.id, caller=caller, idempotency_key="key-a", settings=_settings(), gateway=gateway
        )
        second = create_payment_order(
            db, bill.id, caller=caller, idempotency_key="key-b", settings=_settings(), gateway=gateway
        )
        assert first.id == second.id
        assert second.idempotency_key == "key-a"
        assert len(gateway.calls) == 1
        assert db.scalar(select(func.count()).select_from(PaymentTransaction)) == 1
    finally:
        db.close()


def test_database_allows_one_non_refunded_transaction_per_bill(v1_client):
    db = session_factory()()
    try:
        school, _, _, bill = _seed(db, code="PAY10")
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        def _row(order_id: str, status: int) -> PaymentTransaction:
            return PaymentTransaction(
                bill_id=bill.id,
                school_id=school.id,
                gateway_order_id=order_id,
                idempotency_key=order_id,
                amount_paise=1013,
                currency="INR",
                status=status,
                created_at=now,
                updated_at=now,
            )

        db.add(_row("order_guard_1", PAYMENT_STATUS_CAPTURED))
        db.commit()
        db.add(_row("order_guard_2", PAYMENT_STATUS_CREATED))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        first = db.scalar(select(PaymentTransaction).where(PaymentTransaction.gateway_order_id == "order_guard_1"))
        assert first is not None
        first.status = PAYMENT_STATUS_REFUNDED
        db.commit()
        db.add(_row("order_guard_3", PAYMENT_STATUS_CREATED))
        db.commit()
        assert db.scalar(select(func.count()).select_from(PaymentTransaction)) == 2
    finally:
        db.close()
