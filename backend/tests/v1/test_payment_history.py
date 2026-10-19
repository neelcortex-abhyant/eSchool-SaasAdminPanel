"""Payment history reads. Does not call Razorpay or change payment state."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.database import session_factory
from app.models.tables import (
    PAYMENT_STATUS_CAPTURED,
    PAYMENT_STATUS_CREATED,
    Package,
    PaymentTransaction,
    School,
    Subscription,
    SubscriptionBill,
)
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User
from app.services.v1.subscription_service import BILL_STATUS_PENDING, SUB_STATUS_ACTIVE

SAFE_FIELDS = {
    "id",
    "school_id",
    "bill_id",
    "gateway",
    "order_id",
    "payment_id",
    "amount",
    "currency",
    "status",
    "invoice_id",
    "created_at",
    "updated_at",
}


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


def _payment(
    *,
    code: str,
    order_id: str,
    status: int = PAYMENT_STATUS_CREATED,
    payment_ref: str | None = None,
    created_at: datetime | None = None,
    idempotency_key: str | None = None,
) -> dict:
    db = session_factory()()
    try:
        now = created_at or datetime(2026, 10, 2, 12, 0, 0)
        school = School(name=f"School {code}", code=code, status=1, installed=1, created_at=now, updated_at=now)
        plan = Package(name=f"Plan {code}", monthly_price=10, yearly_price=100, status=1, created_at=now)
        db.add_all([school, plan])
        db.flush()
        subscription = Subscription(
            school_id=school.id,
            package_id=plan.id,
            status=SUB_STATUS_ACTIVE,
            start_date=now.date(),
            end_date=now.date(),
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
            period_start=now.date(),
            period_end=now.date(),
            created_at=now,
            updated_at=now,
        )
        db.add(bill)
        db.flush()
        row = PaymentTransaction(
            bill_id=bill.id,
            school_id=school.id,
            gateway_order_id=order_id,
            gateway_payment_id=payment_ref,
            idempotency_key=idempotency_key or order_id,
            amount_paise=249900,
            currency="INR",
            status=status,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.commit()
        return {"id": row.id, "school_id": school.id, "bill_id": bill.id, "status": row.status}
    finally:
        db.close()


def test_super_admin_list_and_detail(v1_client, v1_db):
    headers = _super_headers(v1_client, v1_db, "pay-hist-sa@eschool.com")
    created = _payment(code="PAYH01", order_id="order_hist_1", payment_ref=None, idempotency_key="secret-looking-key")
    listed = v1_client.get("/api/v1/super-admin/payments", headers=headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] == 1
    assert body["page"] == 1
    item = body["items"][0]
    assert set(item) == SAFE_FIELDS
    assert item["id"] == created["id"]
    assert item["school_id"] == created["school_id"]
    assert item["bill_id"] == created["bill_id"]
    assert item["gateway"] == "razorpay"
    assert item["order_id"] == "order_hist_1"
    assert item["payment_id"] is None
    assert item["amount"] == 249900
    assert item["currency"] == "INR"
    assert item["status"] == "created"
    assert "secret-looking-key" not in listed.text
    assert "signature" not in item
    detail = v1_client.get(f"/api/v1/super-admin/payments/{created['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["order_id"] == "order_hist_1"
    assert set(detail.json()) == SAFE_FIELDS
    db = session_factory()()
    try:
        row = db.get(PaymentTransaction, created["id"])
        assert row is not None and row.status == PAYMENT_STATUS_CREATED
    finally:
        db.close()


def test_school_admin_cannot_read_admin_payments(v1_client, v1_db):
    headers = _super_headers(v1_client, v1_db, "pay-hist-forbid-sa@eschool.com")
    created = _payment(code="PAYH02", order_id="order_hist_2")
    admin = _school_admin_headers(v1_client, headers, created["school_id"], "pay-hist-forbid-admin@eschool.com")
    assert v1_client.get("/api/v1/super-admin/payments", headers=admin).status_code == 403
    assert v1_client.get(f"/api/v1/super-admin/payments/{created['id']}", headers=admin).status_code == 403
    assert v1_client.get("/api/v1/super-admin/payments").status_code == 401


def test_unknown_payment_returns_404(v1_client, v1_db):
    headers = _super_headers(v1_client, v1_db, "pay-hist-missing-sa@eschool.com")
    response = v1_client.get("/api/v1/super-admin/payments/999999", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found"


def test_school_history_and_cross_school_denial(v1_client, v1_db):
    headers = _super_headers(v1_client, v1_db, "pay-hist-school-sa@eschool.com")
    own = _payment(code="PAYH03", order_id="order_hist_3", payment_ref="pay_hist_3", status=PAYMENT_STATUS_CAPTURED)
    other = _payment(code="PAYH04", order_id="order_hist_4")
    admin = _school_admin_headers(v1_client, headers, own["school_id"], "pay-hist-own-admin@eschool.com")
    own_history = v1_client.get(f"/api/v1/schools/{own['school_id']}/payments", headers=admin)
    assert own_history.status_code == 200, own_history.text
    assert own_history.json()["total"] == 1
    assert own_history.json()["items"][0]["status"] == "captured"
    assert own_history.json()["items"][0]["payment_id"] == "pay_hist_3"
    assert set(own_history.json()["items"][0]) == SAFE_FIELDS
    denied = v1_client.get(f"/api/v1/schools/{other['school_id']}/payments", headers=admin)
    assert denied.status_code == 403
    super_view = v1_client.get(f"/api/v1/schools/{other['school_id']}/payments", headers=headers)
    assert super_view.status_code == 200
    assert super_view.json()["total"] == 1


def test_filters_pagination_and_empty_history(v1_client, v1_db):
    headers = _super_headers(v1_client, v1_db, "pay-hist-filter-sa@eschool.com")
    _payment(
        code="PAYH05",
        order_id="order_hist_5",
        created_at=datetime(2026, 10, 1, 8, 0, 0),
        status=PAYMENT_STATUS_CREATED,
    )
    middle = _payment(
        code="PAYH06",
        order_id="order_hist_6",
        created_at=datetime(2026, 10, 2, 8, 0, 0),
        status=PAYMENT_STATUS_CAPTURED,
        payment_ref="pay_hist_6",
    )
    _payment(
        code="PAYH07",
        order_id="order_hist_7",
        created_at=datetime(2026, 10, 3, 8, 0, 0),
        status=PAYMENT_STATUS_CREATED,
    )
    empty = _payment(code="PAYH08", order_id="order_hist_8")
    db = session_factory()()
    try:
        extra = db.scalar(select(PaymentTransaction).where(PaymentTransaction.gateway_order_id == "order_hist_8"))
        assert extra is not None
        db.delete(extra)
        db.commit()
        empty_school = empty["school_id"]
    finally:
        db.close()
    by_school = v1_client.get(
        "/api/v1/super-admin/payments",
        headers=headers,
        params={"school_id": middle["school_id"]},
    )
    assert by_school.status_code == 200
    assert [item["id"] for item in by_school.json()["items"]] == [middle["id"]]
    by_status = v1_client.get("/api/v1/super-admin/payments", headers=headers, params={"status": 2})
    assert [item["id"] for item in by_status.json()["items"]] == [middle["id"]]
    by_date = v1_client.get(
        "/api/v1/super-admin/payments",
        headers=headers,
        params={"from_date": "2026-10-02", "to_date": "2026-10-02"},
    )
    assert [item["id"] for item in by_date.json()["items"]] == [middle["id"]]
    page = v1_client.get(
        "/api/v1/super-admin/payments",
        headers=headers,
        params={"page": 2, "page_size": 1, "from_date": "2026-10-01", "to_date": "2026-10-03"},
    )
    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert page.json()["items"][0]["id"] == middle["id"]
    empty_history = v1_client.get(f"/api/v1/schools/{empty_school}/payments", headers=headers)
    assert empty_history.status_code == 200
    assert empty_history.json()["items"] == []
    assert empty_history.json()["total"] == 0


def test_invalid_payment_query_parameters(v1_client, v1_db):
    headers = _super_headers(v1_client, v1_db, "pay-hist-invalid-sa@eschool.com")
    assert v1_client.get("/api/v1/super-admin/payments", headers=headers, params={"page": 0}).status_code == 422
    assert v1_client.get("/api/v1/super-admin/payments", headers=headers, params={"status": 9}).status_code == 422
    bad_range = v1_client.get(
        "/api/v1/super-admin/payments",
        headers=headers,
        params={"from_date": "2026-10-05", "to_date": "2026-10-01"},
    )
    assert bad_range.status_code == 422
    assert bad_range.json()["detail"] == "from_date must be on or before to_date"


def test_payment_summary_aggregates_real_rows(v1_client, v1_db):
    headers = _super_headers(v1_client, v1_db, "pay-summary-sa@eschool.com")
    empty = v1_client.get("/api/v1/super-admin/payments/summary", headers=headers)
    assert empty.status_code == 200, empty.text
    assert empty.json()["total_count"] == 0
    assert empty.json()["successful_amount_paise"] == 0
    _payment(code="PAYS01", order_id="order_sum_1", status=PAYMENT_STATUS_CAPTURED, payment_ref="pay_sum_1")
    _payment(code="PAYS02", order_id="order_sum_2", status=PAYMENT_STATUS_CAPTURED, payment_ref="pay_sum_2")
    _payment(code="PAYS03", order_id="order_sum_3", status=PAYMENT_STATUS_CREATED)
    _payment(code="PAYS04", order_id="order_sum_4", status=3, payment_ref="pay_sum_4")
    body = v1_client.get("/api/v1/super-admin/payments/summary", headers=headers).json()
    assert body == {
        "currency": "INR",
        "successful_amount_paise": 499800,
        "successful_amount": 4998.0,
        "successful_count": 2,
        "pending_count": 1,
        "failed_count": 1,
        "refunded_count": 0,
        "total_count": 4,
    }
    admin_school = _payment(code="PAYS05", order_id="order_sum_5")
    admin = _school_admin_headers(v1_client, headers, admin_school["school_id"], "pay-summary-admin@eschool.com")
    assert v1_client.get("/api/v1/super-admin/payments/summary", headers=admin).status_code == 403
