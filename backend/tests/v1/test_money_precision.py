"""Plan and bill amounts are stored and returned as two-decimal JSON numbers."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.tables import Package, SubscriptionBill, SubscriptionRenewal
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User
from app.services.v1.plan_service import PlanServiceError, create_plan
from app.services.v1.subscription_service import SubscriptionServiceError, create_bill


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _super_admin_headers(client, v1_db, email: str) -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "secret123",
            "first_name": "Money",
            "last_name": "Admin",
        },
    )
    assert res.status_code == 201, res.text
    user = v1_db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    )
    assert login.status_code == 200, login.text
    return _auth_header(login.json()["access_token"])


def _body(payload: str) -> dict:
    data = json.loads(payload)
    assert isinstance(data, dict)
    return data


def test_plan_half_cent_is_stored_and_returned_as_cents(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "money-plan@eschool.com")
    created = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": "Half Cent", "monthly_price": 10.125, "yearly_price": 10.124},
    )
    assert created.status_code == 201, created.text
    body = _body(created.text)
    assert body["monthly_price"] == 10.13
    assert body["yearly_price"] == 10.12
    plan_id = body["id"]

    updated = v1_client.patch(
        f"/api/v1/super-admin/plans/{plan_id}",
        headers=headers,
        json={"monthly_price": 10.135, "yearly_price": 0.005},
    )
    assert updated.status_code == 200, updated.text
    patched = _body(updated.text)
    assert patched["monthly_price"] == 10.14
    assert patched["yearly_price"] == 0.01

    v1_db.expire_all()
    row = v1_db.get(Package, plan_id)
    assert row is not None
    assert Decimal(str(row.monthly_price)).quantize(Decimal("0.01")) == Decimal("10.14")
    assert Decimal(str(row.yearly_price)).quantize(Decimal("0.01")) == Decimal("0.01")


def test_plan_bounds_accept_zero_cent_and_maximum(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "money-bounds@eschool.com")
    accepted = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": "Bounds", "monthly_price": 0, "yearly_price": 0.01},
    )
    assert accepted.status_code == 201, accepted.text
    body = _body(accepted.text)
    assert body["monthly_price"] == 0
    assert body["yearly_price"] == 0.01

    maximum = v1_client.patch(
        f"/api/v1/super-admin/plans/{body['id']}",
        headers=headers,
        json={"monthly_price": 9999999999.99, "yearly_price": 9999999999.99},
    )
    assert maximum.status_code == 200, maximum.text
    capped = _body(maximum.text)
    assert capped["monthly_price"] == 9999999999.99
    assert capped["yearly_price"] == 9999999999.99


def test_plan_rejects_negative_and_value_that_rounds_above_maximum(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "money-reject@eschool.com")
    created = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": "Stay", "monthly_price": 1, "yearly_price": 2},
    )
    assert created.status_code == 201, created.text
    plan_id = created.json()["id"]

    negative = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": "Negative", "monthly_price": -0.001, "yearly_price": 1},
    )
    assert negative.status_code == 422

    over = v1_client.patch(
        f"/api/v1/super-admin/plans/{plan_id}",
        headers=headers,
        json={"yearly_price": 9999999999.995},
    )
    assert over.status_code == 422
    assert "9999999999.99" in over.text
    v1_db.expire_all()
    row = v1_db.get(Package, plan_id)
    assert row is not None
    assert float(row.yearly_price) == 2.0


def test_direct_plan_call_rejects_negative_zero_artifact(v1_client, v1_db):
    with pytest.raises(PlanServiceError) as caught:
        create_plan(v1_db, name="Tiny Negative", monthly_price=-0.001, yearly_price=0, commit=False)
    assert caught.value.status_code == 422
    assert v1_db.scalar(select(Package.id).where(Package.name == "Tiny Negative")) is None


def test_manual_bill_rounds_and_omitted_amount_uses_plan_price(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "money-bill@eschool.com")
    school = v1_client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": "Bill School", "code": "BILL01"},
    )
    assert school.status_code == 201, school.text
    plan = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": "Bill Plan", "monthly_price": 10.125, "yearly_price": 100},
    )
    assert plan.status_code == 201, plan.text
    assert plan.json()["monthly_price"] == 10.13
    activated = v1_client.patch(
        f"/api/v1/super-admin/plans/{plan.json()['id']}/status",
        headers=headers,
        json={"status": 1},
    )
    assert activated.status_code == 200, activated.text
    sub = v1_client.post(
        f"/api/v1/super-admin/schools/{school.json()['id']}/subscriptions",
        headers=headers,
        json={
            "package_id": plan.json()["id"],
            "start_date": "2026-01-01",
            "end_date": "2099-06-15",
            "cycle": "monthly",
        },
    )
    assert sub.status_code == 201, sub.text
    bills = (
        f"/api/v1/super-admin/schools/{school.json()['id']}/subscriptions/{sub.json()['id']}/bills"
    )

    manual = v1_client.post(
        bills,
        headers=headers,
        json={"period_start": "2026-01-01", "period_end": "2026-01-31", "amount": 10.125},
    )
    assert manual.status_code == 201, manual.text
    manual_body = _body(manual.text)
    assert manual_body["amount"] == 10.13

    omitted = v1_client.post(
        bills,
        headers=headers,
        json={"period_start": "2026-02-01", "period_end": "2026-02-28"},
    )
    assert omitted.status_code == 201, omitted.text
    assert _body(omitted.text)["amount"] == 10.13

    zero = v1_client.post(
        bills,
        headers=headers,
        json={"period_start": "2026-03-01", "period_end": "2026-03-31", "amount": 0},
    )
    assert zero.status_code == 201, zero.text
    assert _body(zero.text)["amount"] == 0

    cent = v1_client.post(
        bills,
        headers=headers,
        json={"period_start": "2026-04-01", "period_end": "2026-04-30", "amount": 0.01},
    )
    assert cent.status_code == 201, cent.text
    assert _body(cent.text)["amount"] == 0.01

    maximum = v1_client.post(
        bills,
        headers=headers,
        json={
            "period_start": "2026-05-01",
            "period_end": "2026-05-31",
            "amount": 9999999999.99,
        },
    )
    assert maximum.status_code == 201, maximum.text
    assert _body(maximum.text)["amount"] == 9999999999.99

    negative = v1_client.post(
        bills,
        headers=headers,
        json={"period_start": "2026-06-01", "period_end": "2026-06-30", "amount": -1},
    )
    assert negative.status_code == 422

    over = v1_client.post(
        bills,
        headers=headers,
        json={
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "amount": 9999999999.995,
        },
    )
    assert over.status_code == 422
    assert "9999999999.99" in over.text

    with pytest.raises(SubscriptionServiceError) as caught:
        create_bill(
            v1_db,
            school.json()["id"],
            sub.json()["id"],
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
            amount=-0.001,
        )
    assert caught.value.status_code == 422


def test_renewal_cents_stay_stable_when_plan_price_changes(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "money-renew@eschool.com")
    school = v1_client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": "Renew Money School", "code": "RMON1"},
    )
    assert school.status_code == 201, school.text
    plan = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": "Renew Money", "monthly_price": 10.125, "yearly_price": 100},
    )
    assert plan.status_code == 201, plan.text
    plan_id = plan.json()["id"]
    assert v1_client.patch(
        f"/api/v1/super-admin/plans/{plan_id}/status",
        headers=headers,
        json={"status": 1},
    ).status_code == 200
    sub = v1_client.post(
        f"/api/v1/super-admin/schools/{school.json()['id']}/subscriptions",
        headers=headers,
        json={
            "package_id": plan_id,
            "start_date": "2026-01-01",
            "end_date": "2099-06-15",
            "cycle": "monthly",
        },
    )
    assert sub.status_code == 201, sub.text
    school_id = school.json()["id"]
    sub_id = sub.json()["id"]
    renewed = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions/{sub_id}/renew",
        headers=headers,
    )
    assert renewed.status_code == 200, renewed.text

    manual = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions/{sub_id}/bills",
        headers=headers,
        json={"period_start": "2026-01-01", "period_end": "2026-01-31", "amount": 10.125},
    )
    assert manual.status_code == 201, manual.text
    manual_id = manual.json()["id"]

    edited = v1_client.patch(
        f"/api/v1/super-admin/plans/{plan_id}",
        headers=headers,
        json={"monthly_price": 30.125},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["monthly_price"] == 30.13

    v1_db.expire_all()
    history = v1_db.scalars(
        select(SubscriptionRenewal)
        .where(SubscriptionRenewal.subscription_id == sub_id)
        .order_by(SubscriptionRenewal.id)
    ).all()
    bills = v1_db.scalars(
        select(SubscriptionBill)
        .where(SubscriptionBill.subscription_id == sub_id)
        .order_by(SubscriptionBill.id)
    ).all()
    assert len(history) == 1
    assert history[0].amount == Decimal("10.13")
    renewal_bill = next(row for row in bills if row.description == "Subscription renewal")
    manual_bill = next(row for row in bills if row.id == manual_id)
    assert Decimal(str(renewal_bill.amount)).quantize(Decimal("0.01")) == Decimal("10.13")
    assert Decimal(str(manual_bill.amount)).quantize(Decimal("0.01")) == Decimal("10.13")

    again = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions/{sub_id}/renew",
        headers=headers,
    )
    assert again.status_code == 200, again.text
    v1_db.expire_all()
    history = v1_db.scalars(
        select(SubscriptionRenewal)
        .where(SubscriptionRenewal.subscription_id == sub_id)
        .order_by(SubscriptionRenewal.id)
    ).all()
    assert [row.amount for row in history] == [Decimal("10.13"), Decimal("30.13")]
    v1_db.expire_all()
    renewal_bill = v1_db.get(SubscriptionBill, renewal_bill.id)
    manual_bill = v1_db.get(SubscriptionBill, manual_bill.id)
    assert renewal_bill is not None and manual_bill is not None
    assert Decimal(str(renewal_bill.amount)).quantize(Decimal("0.01")) == Decimal("10.13")
    assert Decimal(str(manual_bill.amount)).quantize(Decimal("0.01")) == Decimal("10.13")


def test_dashboard_and_report_amounts_are_json_numbers(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "money-json@eschool.com")
    school = v1_client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": "JSON School", "code": "JSON01"},
    )
    assert school.status_code == 201, school.text
    plan = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": "JSON Plan", "monthly_price": 10.125, "yearly_price": 20},
    )
    assert plan.status_code == 201, plan.text
    assert v1_client.patch(
        f"/api/v1/super-admin/plans/{plan.json()['id']}/status",
        headers=headers,
        json={"status": 1},
    ).status_code == 200
    sub = v1_client.post(
        f"/api/v1/super-admin/schools/{school.json()['id']}/subscriptions",
        headers=headers,
        json={
            "package_id": plan.json()["id"],
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "cycle": "monthly",
        },
    )
    assert sub.status_code == 201, sub.text
    bill = v1_client.post(
        f"/api/v1/super-admin/schools/{school.json()['id']}/subscriptions/{sub.json()['id']}/bills",
        headers=headers,
        json={"period_start": "2026-01-01", "period_end": "2026-01-31", "amount": 10.125},
    )
    assert bill.status_code == 201, bill.text

    stats = v1_client.get("/api/v1/super-admin/dashboard", headers=headers)
    assert stats.status_code == 200, stats.text
    stats_body = json.loads(stats.text)
    assert stats_body["bill_amount_total"] == 10.13
    assert stats_body["bill_amount_pending"] == 10.13
    assert isinstance(stats_body["bill_amount_total"], float)
    assert '"bill_amount_total": "' not in stats.text

    report = v1_client.get("/api/v1/super-admin/reports/bills", headers=headers)
    assert report.status_code == 200, report.text
    report_body = json.loads(report.text)
    assert report_body["amount_sum"] == 10.13
    assert report_body["items"][0]["amount"] == 10.13
    assert isinstance(report_body["amount_sum"], float)
    assert isinstance(report_body["items"][0]["amount"], float)
    assert '"amount_sum": "' not in report.text
