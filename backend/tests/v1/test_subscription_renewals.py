"""Subscription renewal, immutable history, and active-plan assignment."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import session_factory
from app.models.tables import AuditLog, Package, Subscription, SubscriptionBill, SubscriptionRenewal
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User
from app.services.v1.subscription_service import (
    SubscriptionServiceError,
    add_calendar_months,
    add_calendar_years,
    renew_subscription,
)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str, **overrides):
    body = {
        "email": email,
        "password": "secret123",
        "first_name": "Renew",
        "last_name": "Admin",
        **overrides,
    }
    return client.post("/api/v1/auth/signup", json=body)


def _super_admin_headers(client, v1_db, email: str) -> dict[str, str]:
    res = _signup(client, email)
    assert res.status_code == 201
    user = v1_db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200
    return _auth_header(login.json()["access_token"])


def _school(client, headers, **overrides):
    body = {"name": "Renew School", "code": "RENEW01", **overrides}
    res = client.post("/api/v1/super-admin/schools", headers=headers, json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _plan(client, headers, *, active: bool = True, **overrides):
    body = {
        "name": "Renew Plan",
        "monthly_price": 19.99,
        "yearly_price": 199.99,
        **overrides,
    }
    res = client.post("/api/v1/super-admin/plans", headers=headers, json=body)
    assert res.status_code == 201, res.text
    plan = res.json()
    if active:
        activated = client.patch(
            f"/api/v1/super-admin/plans/{plan['id']}/status",
            headers=headers,
            json={"status": 1},
        )
        assert activated.status_code == 200, activated.text
    return plan


def _assign(client, headers, school_id: int, package_id: int, **overrides):
    body = {
        "package_id": package_id,
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "cycle": "monthly",
        "auto_renew": 1,
        "status": 1,
    }
    body.update(overrides)
    res = client.post(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions",
        headers=headers,
        json=body,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _renew_path(school_id: int, subscription_id: int) -> str:
    return (
        f"/api/v1/super-admin/schools/{school_id}/subscriptions/{subscription_id}/renew"
    )


def _count(db, model, *where) -> int:
    query = select(func.count()).select_from(model)
    for clause in where:
        query = query.where(clause)
    return int(db.scalar(query) or 0)


def test_calendar_clamping_helpers():
    assert add_calendar_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_calendar_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_calendar_years(date(2024, 2, 29), 1) == date(2025, 2, 28)
    assert add_calendar_years(date(2024, 2, 29), 4) == date(2028, 2, 29)


def test_monthly_renewal_before_expiry_keeps_remaining_term(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "renew-month@eschool.com")
    school = _school(v1_client, headers, code="RNM01")
    plan = _plan(v1_client, headers, name="Monthly Plan")
    sub = _assign(
        v1_client,
        headers,
        school["id"],
        plan["id"],
        end_date="2026-12-31",
        cycle="monthly",
    )
    renewed = renew_subscription(
        v1_db,
        school["id"],
        sub["id"],
        today=date(2026, 10, 15),
    )
    assert renewed.id == sub["id"]
    assert renewed.status == 1
    assert renewed.cycle == "monthly"
    assert renewed.package_id == plan["id"]
    assert renewed.start_date == date(2027, 1, 1)
    assert renewed.end_date == date(2027, 2, 1)
    history = v1_db.scalars(
        select(SubscriptionRenewal).where(SubscriptionRenewal.subscription_id == sub["id"])
    ).all()
    assert len(history) == 1
    assert history[0].period_start == date(2027, 1, 1)
    assert history[0].period_end == date(2027, 2, 1)
    assert history[0].amount == Decimal("19.99")
    assert history[0].plan_name == "Monthly Plan"
    assert history[0].cycle == "monthly"


def test_yearly_renewal_before_expiry(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "renew-year@eschool.com")
    school = _school(v1_client, headers, code="RNY01")
    plan = _plan(v1_client, headers, name="Yearly Plan")
    sub = _assign(
        v1_client,
        headers,
        school["id"],
        plan["id"],
        end_date="2099-06-15",
        cycle="yearly",
    )
    renewed = renew_subscription(
        v1_db,
        school["id"],
        sub["id"],
        today=date(2026, 10, 15),
    )
    assert renewed.id == sub["id"]
    assert renewed.status == 1
    assert renewed.start_date == date(2099, 6, 16)
    assert renewed.end_date == date(2100, 6, 16)
    history = v1_db.scalar(
        select(SubscriptionRenewal).where(SubscriptionRenewal.subscription_id == sub["id"])
    )
    assert history is not None
    assert history.amount == Decimal("199.99")
    assert history.cycle == "yearly"


def test_expired_by_date_active_subscription_starts_today(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "renew-past@eschool.com")
    school = _school(v1_client, headers, code="RNP01")
    plan = _plan(v1_client, headers)
    sub = _assign(
        v1_client,
        headers,
        school["id"],
        plan["id"],
        end_date="2026-01-15",
        cycle="monthly",
    )
    renewed = renew_subscription(
        v1_db,
        school["id"],
        sub["id"],
        today=date(2026, 3, 10),
    )
    assert renewed.start_date == date(2026, 3, 10)
    assert renewed.end_date == date(2026, 4, 10)
    assert renewed.status == 1


def test_january_31_month_end_clamp(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "renew-jan@eschool.com")
    school = _school(v1_client, headers, code="RNJ01")
    plan = _plan(v1_client, headers)
    sub = _assign(
        v1_client,
        headers,
        school["id"],
        plan["id"],
        end_date="2026-01-30",
        cycle="monthly",
    )
    renewed = renew_subscription(
        v1_db,
        school["id"],
        sub["id"],
        today=date(2026, 1, 31),
    )
    assert renewed.start_date == date(2026, 1, 31)
    assert renewed.end_date == date(2026, 2, 28)


def test_february_29_into_non_leap_year(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "renew-leap@eschool.com")
    school = _school(v1_client, headers, code="RNL01")
    plan = _plan(v1_client, headers)
    sub = _assign(
        v1_client,
        headers,
        school["id"],
        plan["id"],
        start_date="2024-02-01",
        end_date="2024-02-28",
        cycle="yearly",
    )
    renewed = renew_subscription(
        v1_db,
        school["id"],
        sub["id"],
        today=date(2024, 2, 29),
    )
    assert renewed.start_date == date(2024, 2, 29)
    assert renewed.end_date == date(2025, 2, 28)


def test_http_renewal_writes_history_bill_and_audit(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "renew-http@eschool.com")
    school = _school(v1_client, headers, code="RNH01")
    plan = _plan(v1_client, headers, name="Snapshot Plan")
    sub = _assign(
        v1_client,
        headers,
        school["id"],
        plan["id"],
        end_date="2099-06-15",
        cycle="monthly",
    )
    res = v1_client.post(_renew_path(school["id"], sub["id"]), headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["id"] == sub["id"]
    assert body["status"] == 1
    assert body["start_date"] == "2099-06-16"
    assert body["end_date"] == "2099-07-16"
    assert "success" not in body

    v1_db.expire_all()
    history = v1_db.scalars(
        select(SubscriptionRenewal).where(SubscriptionRenewal.subscription_id == sub["id"])
    ).all()
    bills = v1_db.scalars(
        select(SubscriptionBill).where(SubscriptionBill.subscription_id == sub["id"])
    ).all()
    audits = v1_db.scalars(
        select(AuditLog).where(AuditLog.action == "subscription.renew")
    ).all()
    assert len(history) == 1
    assert len(bills) == 1
    assert len(audits) == 1
    assert history[0].plan_name == "Snapshot Plan"
    assert history[0].amount == Decimal("19.99")
    assert history[0].period_start == date(2099, 6, 16)
    assert history[0].period_end == date(2099, 7, 16)
    assert bills[0].status == 0
    assert bills[0].period_start == history[0].period_start
    assert bills[0].period_end == history[0].period_end
    assert Decimal(str(bills[0].amount)).quantize(Decimal("0.01")) == history[0].amount
    assert audits[0].entity_type == "subscription"
    assert audits[0].entity_id == str(sub["id"])
    assert audits[0].school_id == school["id"]
    assert audits[0].metadata_json is not None
    assert "package_id" in audits[0].metadata_json
    assert "2099-06-16" in audits[0].metadata_json
    assert "2099-07-16" in audits[0].metadata_json

    activities = v1_client.get(
        "/api/v1/super-admin/dashboard/recent-activities",
        headers=headers,
    )
    assert activities.status_code == 200
    match = next(item for item in activities.json()["items"] if item["action"] == "subscription.renew")
    assert match["title"] == "Subscription renewed"
    assert match["description"] == "A subscription was renewed."
    assert match["entity_id"] == str(sub["id"])
    assert match["school_id"] == school["id"]


def test_plan_edit_does_not_change_history_or_bill(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "renew-edit@eschool.com")
    school = _school(v1_client, headers, code="RNE01")
    plan = _plan(v1_client, headers, name="Original Name")
    sub = _assign(v1_client, headers, school["id"], plan["id"], end_date="2099-01-15")
    renewed = v1_client.post(_renew_path(school["id"], sub["id"]), headers=headers)
    assert renewed.status_code == 200, renewed.text

    edited = v1_client.patch(
        f"/api/v1/super-admin/plans/{plan['id']}",
        headers=headers,
        json={"name": "Renamed Plan", "monthly_price": 80, "yearly_price": 800},
    )
    assert edited.status_code == 200

    v1_db.expire_all()
    history = v1_db.scalar(
        select(SubscriptionRenewal).where(SubscriptionRenewal.subscription_id == sub["id"])
    )
    bill = v1_db.scalar(
        select(SubscriptionBill).where(SubscriptionBill.subscription_id == sub["id"])
    )
    assert history is not None and bill is not None
    assert history.plan_name == "Original Name"
    assert history.amount == Decimal("19.99")
    assert Decimal(str(bill.amount)).quantize(Decimal("0.01")) == Decimal("19.99")


def test_renew_rejects_inactive_and_deleted_plans(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "renew-plan@eschool.com")
    school = _school(v1_client, headers, code="RNI01")
    inactive = _plan(v1_client, headers, name="Soon Inactive")
    deleted = _plan(v1_client, headers, name="Soon Deleted")
    active_sub = _assign(v1_client, headers, school["id"], inactive["id"], end_date="2099-04-01")
    school_b = _school(v1_client, headers, code="RNI02", name="Second Renew School")
    deleted_sub = _assign(v1_client, headers, school_b["id"], deleted["id"], end_date="2099-04-01")

    deactivated = v1_client.patch(
        f"/api/v1/super-admin/plans/{inactive['id']}/status",
        headers=headers,
        json={"status": 0},
    )
    assert deactivated.status_code == 200
    v1_db.expire_all()
    still_active = v1_db.get(Subscription, active_sub["id"])
    assert still_active is not None
    assert still_active.status == 1
    assert str(still_active.end_date) == "2099-04-01"

    rejected = v1_client.post(_renew_path(school["id"], active_sub["id"]), headers=headers)
    assert rejected.status_code == 422
    assert rejected.json()["detail"] == "Plan is not active"
    v1_db.expire_all()
    unchanged = v1_db.get(Subscription, active_sub["id"])
    assert unchanged is not None
    assert str(unchanged.end_date) == "2099-04-01"
    assert _count(v1_db, AuditLog, AuditLog.action == "subscription.renew") == 0

    package = v1_db.get(Package, deleted["id"])
    assert package is not None
    package.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    v1_db.commit()
    missing = v1_client.post(_renew_path(school_b["id"], deleted_sub["id"]), headers=headers)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Plan not found"
    assert _count(v1_db, AuditLog, AuditLog.action == "subscription.renew") == 0


def test_renew_rejects_invalid_subscription_and_mismatch(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "renew-bad@eschool.com")
    school = _school(v1_client, headers, code="RNB01")
    other = _school(v1_client, headers, code="RNB02", name="Other Renew School")
    plan = _plan(v1_client, headers, name="Bad Status Plan")
    sub = _assign(v1_client, headers, school["id"], plan["id"], end_date="2099-05-01")

    missing = v1_client.post(_renew_path(school["id"], 999999), headers=headers)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Subscription not found"

    mismatch = v1_client.post(_renew_path(other["id"], sub["id"]), headers=headers)
    assert mismatch.status_code == 404

    for status_code in (0, 2, 3):
        patched = v1_client.patch(
            f"/api/v1/super-admin/schools/{school['id']}/subscriptions/{sub['id']}/status",
            headers=headers,
            json={"status": status_code},
        )
        assert patched.status_code == 200
        rejected = v1_client.post(_renew_path(school["id"], sub["id"]), headers=headers)
        assert rejected.status_code == 422
        assert rejected.json()["detail"] == "Only an active subscription can be renewed"

    v1_db.expire_all()
    row = v1_db.get(Subscription, sub["id"])
    assert row is not None
    row.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    row.status = 1
    v1_db.commit()
    deleted = v1_client.post(_renew_path(school["id"], sub["id"]), headers=headers)
    assert deleted.status_code == 404
    assert _count(v1_db, AuditLog, AuditLog.action == "subscription.renew") == 0


def test_duplicate_period_is_conflict_and_rolls_back(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "renew-dup@eschool.com")
    school = _school(v1_client, headers, code="RND01")
    plan = _plan(v1_client, headers, name="Duplicate Plan")
    sub = _assign(v1_client, headers, school["id"], plan["id"], end_date="2099-08-01")
    first = renew_subscription(v1_db, school["id"], sub["id"], today=date(2026, 10, 15))
    assert first.start_date == date(2099, 8, 2)

    row = v1_db.get(Subscription, sub["id"])
    assert row is not None
    row.end_date = date(2099, 8, 1)
    v1_db.commit()

    with pytest.raises(SubscriptionServiceError) as caught:
        renew_subscription(v1_db, school["id"], sub["id"], today=date(2026, 10, 15))
    assert caught.value.status_code == 409
    assert caught.value.detail == "This subscription period has already been renewed"

    v1_db.expire_all()
    again = v1_db.get(Subscription, sub["id"])
    assert again is not None
    assert again.end_date == date(2099, 8, 1)
    assert _count(v1_db, SubscriptionRenewal, SubscriptionRenewal.subscription_id == sub["id"]) == 1
    assert _count(v1_db, SubscriptionBill, SubscriptionBill.subscription_id == sub["id"]) == 1
    assert _count(v1_db, AuditLog, AuditLog.action == "subscription.renew") == 0


def test_concurrent_renewal_cannot_both_succeed(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "renew-lock@eschool.com")
    school = _school(v1_client, headers, code="RNK01")
    plan = _plan(v1_client, headers, name="Lock Plan")
    sub = _assign(v1_client, headers, school["id"], plan["id"], end_date="2099-09-01")

    holder = session_factory()()
    worker = session_factory()()
    try:
        locked = holder.scalar(
            select(Subscription).where(Subscription.id == sub["id"]).with_for_update()
        )
        assert locked is not None
        with pytest.raises(SubscriptionServiceError) as caught:
            renew_subscription(worker, school["id"], sub["id"], today=date(2026, 10, 15))
        assert caught.value.status_code == 409
        assert caught.value.detail == "A renewal for this subscription is already in progress"
    finally:
        holder.rollback()
        holder.close()
        worker.rollback()
        worker.close()

    v1_db.expire_all()
    unchanged = v1_db.get(Subscription, sub["id"])
    assert unchanged is not None
    assert str(unchanged.end_date) == "2099-09-01"
    assert _count(v1_db, SubscriptionRenewal, SubscriptionRenewal.subscription_id == sub["id"]) == 0
    assert _count(v1_db, SubscriptionBill, SubscriptionBill.subscription_id == sub["id"]) == 0


def test_commit_failure_rolls_back_dates_history_and_bill(v1_client, v1_db, monkeypatch):
    headers = _super_admin_headers(v1_client, v1_db, "renew-fail@eschool.com")
    school = _school(v1_client, headers, code="RNF01")
    plan = _plan(v1_client, headers, name="Fail Plan")
    sub = _assign(v1_client, headers, school["id"], plan["id"], end_date="2099-03-01")

    def fail_commit(self):
        raise RuntimeError("forced commit failure")

    monkeypatch.setattr(Session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="forced commit failure"):
        renew_subscription(v1_db, school["id"], sub["id"], today=date(2026, 10, 15))
    monkeypatch.undo()

    v1_db.rollback()
    row = v1_db.get(Subscription, sub["id"])
    assert row is not None
    assert str(row.end_date) == "2099-03-01"
    assert _count(v1_db, SubscriptionRenewal, SubscriptionRenewal.subscription_id == sub["id"]) == 0
    assert _count(v1_db, SubscriptionBill, SubscriptionBill.subscription_id == sub["id"]) == 0
    assert _count(v1_db, AuditLog, AuditLog.action == "subscription.renew") == 0


def test_audit_failure_rolls_back_renewal_and_writes_no_audit(v1_client, v1_db, monkeypatch):
    headers = _super_admin_headers(v1_client, v1_db, "renew-audit-fail@eschool.com")
    school = _school(v1_client, headers, code="RNAF1")
    plan = _plan(v1_client, headers, name="Audit Fail Plan")
    sub = _assign(v1_client, headers, school["id"], plan["id"], end_date="2099-11-01")

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit failed")

    monkeypatch.setattr(
        "app.api.v1.super_admin.subscriptions.audit_service.record_audit",
        fail_audit,
    )
    res = v1_client.post(_renew_path(school["id"], sub["id"]), headers=headers)
    assert res.status_code == 500
    assert res.json()["detail"] == "Renewal could not be recorded"

    v1_db.expire_all()
    row = v1_db.get(Subscription, sub["id"])
    assert row is not None
    assert str(row.end_date) == "2099-11-01"
    assert _count(v1_db, SubscriptionRenewal, SubscriptionRenewal.subscription_id == sub["id"]) == 0
    assert _count(v1_db, SubscriptionBill, SubscriptionBill.subscription_id == sub["id"]) == 0
    assert _count(v1_db, AuditLog, AuditLog.action == "subscription.renew") == 0


def test_stored_price_above_history_limit_rejects_renewal(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "renew-price-limit@eschool.com")
    school = _school(v1_client, headers, code="RNPL1")
    plan = _plan(v1_client, headers, name="Oversized Price Plan")
    sub = _assign(v1_client, headers, school["id"], plan["id"], end_date="2099-11-15")
    package = v1_db.get(Package, plan["id"])
    assert package is not None
    package.monthly_price = 10000000000.0
    v1_db.commit()

    res = v1_client.post(_renew_path(school["id"], sub["id"]), headers=headers)
    assert res.status_code == 422
    assert res.json()["detail"] == "Plan price exceeds the supported amount"
    v1_db.expire_all()
    row = v1_db.get(Subscription, sub["id"])
    assert row is not None
    assert str(row.end_date) == "2099-11-15"
    assert _count(v1_db, SubscriptionRenewal, SubscriptionRenewal.subscription_id == sub["id"]) == 0
    assert _count(v1_db, AuditLog, AuditLog.action == "subscription.renew") == 0


def test_new_assignment_rejects_inactive_plan(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "renew-assign@eschool.com")
    school = _school(v1_client, headers, code="RNA01")
    plan = _plan(v1_client, headers, name="Unpublished Plan", active=False)
    res = v1_client.post(
        f"/api/v1/super-admin/schools/{school['id']}/subscriptions",
        headers=headers,
        json={
            "package_id": plan["id"],
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "cycle": "monthly",
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"] == "Plan is not active"
    assert _count(v1_db, Subscription, Subscription.school_id == school["id"]) == 0


def test_renew_requires_super_admin(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "renew-auth@eschool.com")
    school = _school(v1_client, headers, code="RNU01")
    plan = _plan(v1_client, headers, name="Auth Plan")
    sub = _assign(v1_client, headers, school["id"], plan["id"])
    path = _renew_path(school["id"], sub["id"])
    assert v1_client.post(path).status_code == 401
    token = _signup(v1_client, "renew-user@eschool.com").json()["access_token"]
    assert v1_client.post(path, headers=_auth_header(token)).status_code == 403
