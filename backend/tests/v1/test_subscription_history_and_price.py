"""Renewal history reads, agreed-price snapshots, and the access-policy default."""

from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import select

from app.models.tables import Package, Subscription, SubscriptionBill, SubscriptionRenewal
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User
from app.services.v1.subscription_access import subscription_expiry_blocks_access


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _super_admin_headers(client, v1_db, email: str) -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "secret123",
            "first_name": "History",
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


def _school_plan_sub(client, headers, *, monthly=10.125, yearly=120.0, code="HIST01"):
    school = client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": "History School", "code": code},
    )
    assert school.status_code == 201, school.text
    plan = client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": f"History Plan {code}", "monthly_price": monthly, "yearly_price": yearly},
    )
    assert plan.status_code == 201, plan.text
    assert client.patch(
        f"/api/v1/super-admin/plans/{plan.json()['id']}/status",
        headers=headers,
        json={"status": 1},
    ).status_code == 200
    sub = client.post(
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
    return school.json(), plan.json(), sub.json()


def _renewals_path(school_id: int, subscription_id: int) -> str:
    return (
        f"/api/v1/super-admin/schools/{school_id}/subscriptions/{subscription_id}/renewals"
    )


def test_renewal_history_auth_empty_page_and_missing_ids(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "history-auth@eschool.com")
    school, _plan, sub = _school_plan_sub(v1_client, headers)
    path = _renewals_path(school["id"], sub["id"])

    assert v1_client.get(path).status_code == 401
    assert v1_client.get(path, headers=_auth_header("bad-token")).status_code == 401

    created_admin = v1_client.post(
        f"/api/v1/super-admin/schools/{school['id']}/admins",
        headers=headers,
        json={
            "email": "history-school@eschool.com",
            "password": "adminpass1",
            "first_name": "School",
            "last_name": "Admin",
        },
    )
    assert created_admin.status_code == 201, created_admin.text
    login = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "history-school@eschool.com", "password": "adminpass1"},
    )
    assert login.status_code == 200, login.text
    assert v1_client.get(path, headers=_auth_header(login.json()["access_token"])).status_code == 403

    empty = v1_client.get(path, headers=headers)
    assert empty.status_code == 200, empty.text
    body = empty.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1

    missing_school = v1_client.get(_renewals_path(999999, sub["id"]), headers=headers)
    assert missing_school.status_code == 404
    missing_sub = v1_client.get(_renewals_path(school["id"], 999999), headers=headers)
    assert missing_sub.status_code == 404

    other = v1_client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": "Other History School", "code": "HIST02"},
    )
    assert other.status_code == 201, other.text
    mismatch = v1_client.get(_renewals_path(other.json()["id"], sub["id"]), headers=headers)
    assert mismatch.status_code == 404

    assert v1_client.get(path, headers=headers, params={"page": 0}).status_code == 422


def test_renewal_history_returns_snapshots_newest_first(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "history-list@eschool.com")
    school, plan, sub = _school_plan_sub(v1_client, headers, code="HIST03")
    path = _renewals_path(school["id"], sub["id"])
    renew = f"/api/v1/super-admin/schools/{school['id']}/subscriptions/{sub['id']}/renew"
    assert v1_client.post(renew, headers=headers).status_code == 200
    edited = v1_client.patch(
        f"/api/v1/super-admin/plans/{plan['id']}",
        headers=headers,
        json={"monthly_price": 30.125},
    )
    assert edited.status_code == 200, edited.text
    assert v1_client.post(renew, headers=headers).status_code == 200

    listed = v1_client.get(path, headers=headers, params={"page": 1, "page_size": 1})
    assert listed.status_code == 200, listed.text
    page = json.loads(listed.text)
    assert page["total"] == 2
    assert page["page_size"] == 1
    assert len(page["items"]) == 1
    newest = page["items"][0]
    assert newest["amount"] == 30.13
    assert isinstance(newest["amount"], float)
    assert newest["plan_name"] == "History Plan HIST03"
    assert newest["cycle"] == "monthly"
    assert newest["subscription_id"] == sub["id"]
    assert newest["school_id"] == school["id"]
    assert newest["package_id"] == plan["id"]
    assert newest["period_start"]
    assert newest["period_end"]
    assert newest["created_at"]
    assert '"amount": "' not in listed.text

    older = v1_client.get(path, headers=headers, params={"page": 2, "page_size": 1})
    assert older.status_code == 200, older.text
    assert older.json()["items"][0]["amount"] == 10.13
    assert older.json()["items"][0]["id"] < newest["id"]

    v1_db.expire_all()
    row = v1_db.get(Subscription, sub["id"])
    assert row is not None
    row.deleted_at = row.updated_at
    v1_db.commit()
    assert v1_client.get(path, headers=headers).status_code == 404


def test_agreed_price_survives_plan_edit_and_renewal_uses_current_price(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "agreed-price@eschool.com")
    school, plan, sub = _school_plan_sub(v1_client, headers, monthly=10.125, yearly=200.5, code="AGRD1")
    detail = f"/api/v1/super-admin/schools/{school['id']}/subscriptions/{sub['id']}"
    assert sub["agreed_price"] == 10.13
    assert isinstance(sub["agreed_price"], float)

    edited = v1_client.patch(
        f"/api/v1/super-admin/plans/{plan['id']}",
        headers=headers,
        json={"monthly_price": 30.125},
    )
    assert edited.status_code == 200, edited.text
    unchanged = v1_client.get(detail, headers=headers)
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["agreed_price"] == 10.13

    renewed = v1_client.post(f"{detail}/renew", headers=headers)
    assert renewed.status_code == 200, renewed.text
    assert renewed.json()["agreed_price"] == 10.13
    v1_db.expire_all()
    history = v1_db.scalar(
        select(SubscriptionRenewal).where(SubscriptionRenewal.subscription_id == sub["id"])
    )
    bill = v1_db.scalar(
        select(SubscriptionBill).where(SubscriptionBill.subscription_id == sub["id"])
    )
    assert history is not None and bill is not None
    assert history.amount == Decimal("30.13")
    assert Decimal(str(bill.amount)).quantize(Decimal("0.01")) == Decimal("30.13")
    stored = v1_db.get(Subscription, sub["id"])
    assert stored is not None
    assert stored.agreed_price == Decimal("10.13")

    rebound = v1_client.patch(detail, headers=headers, json={"cycle": "yearly"})
    assert rebound.status_code == 200, rebound.text
    assert rebound.json()["agreed_price"] == 200.5
    dates_only = v1_client.patch(detail, headers=headers, json={"end_date": "2099-12-31"})
    assert dates_only.status_code == 200, dates_only.text
    assert dates_only.json()["agreed_price"] == 200.5


def test_agreed_price_bounds_and_legacy_null(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "agreed-bounds@eschool.com")
    school, plan, sub = _school_plan_sub(
        v1_client,
        headers,
        monthly=0,
        yearly=0.01,
        code="AGRD2",
    )
    assert sub["agreed_price"] == 0

    maximum = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": "Max Agree", "monthly_price": 9999999999.99, "yearly_price": 1},
    )
    assert maximum.status_code == 201, maximum.text
    assert v1_client.patch(
        f"/api/v1/super-admin/plans/{maximum.json()['id']}/status",
        headers=headers,
        json={"status": 1},
    ).status_code == 200
    capped = v1_client.post(
        f"/api/v1/super-admin/schools/{school['id']}/subscriptions",
        headers=headers,
        json={
            "package_id": maximum.json()["id"],
            "start_date": "2026-02-01",
            "end_date": "2026-03-01",
            "cycle": "monthly",
            "status": 0,
        },
    )
    assert capped.status_code == 201, capped.text
    assert capped.json()["agreed_price"] == 9999999999.99

    v1_db.expire_all()
    package = v1_db.get(Package, plan["id"])
    assert package is not None
    package.monthly_price = -1
    v1_db.commit()
    rejected = v1_client.post(
        f"/api/v1/super-admin/schools/{school['id']}/subscriptions",
        headers=headers,
        json={
            "package_id": plan["id"],
            "start_date": "2026-04-01",
            "end_date": "2026-05-01",
            "status": 0,
        },
    )
    assert rejected.status_code == 422

    legacy = v1_db.get(Subscription, sub["id"])
    assert legacy is not None
    legacy.agreed_price = None
    v1_db.commit()
    detail = v1_client.get(
        f"/api/v1/super-admin/schools/{school['id']}/subscriptions/{sub['id']}",
        headers=headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["agreed_price"] is None


def test_default_access_policy_does_not_block_expired_subscription(v1_client, v1_db, monkeypatch):
    assert subscription_expiry_blocks_access(1) is False
    headers = _super_admin_headers(v1_client, v1_db, "access-policy@eschool.com")
    school, _plan, sub = _school_plan_sub(v1_client, headers, code="ACCS1")
    activated = v1_client.post(
        f"/api/v1/super-admin/schools/{school['id']}/activate",
        headers=headers,
    )
    assert activated.status_code == 200, activated.text
    created_admin = v1_client.post(
        f"/api/v1/super-admin/schools/{school['id']}/admins",
        headers=headers,
        json={
            "email": "access-school@eschool.com",
            "password": "adminpass1",
            "first_name": "Access",
            "last_name": "Admin",
        },
    )
    assert created_admin.status_code == 201, created_admin.text
    login = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "access-school@eschool.com", "password": "adminpass1"},
    )
    assert login.status_code == 200, login.text
    school_headers = _auth_header(login.json()["access_token"])
    expired = v1_client.patch(
        f"/api/v1/super-admin/schools/{school['id']}/subscriptions/{sub['id']}/status",
        headers=headers,
        json={"status": 2},
    )
    assert expired.status_code == 200, expired.text
    own_school = v1_client.get("/api/v1/school-admin/school", headers=school_headers)
    assert own_school.status_code == 200, own_school.text

    monkeypatch.setattr(
        "app.api.v1.deps.subscription_expiry_blocks_access",
        lambda _school_id: True,
    )
    blocked = v1_client.get("/api/v1/school-admin/school", headers=school_headers)
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "Subscription access is not available"
    still_super = v1_client.get("/api/v1/super-admin/plans", headers=headers)
    assert still_super.status_code == 200, still_super.text
