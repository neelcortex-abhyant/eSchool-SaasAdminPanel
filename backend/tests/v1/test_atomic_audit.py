"""Business changes and their audit rows commit together."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models.tables import AuditLog, Package, Subscription, SubscriptionBill
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str):
    return client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "secret123",
            "first_name": "Audit",
            "last_name": "Atomic",
        },
    )


def _super_admin_headers(client, v1_db, email: str) -> dict[str, str]:
    res = _signup(client, email)
    assert res.status_code == 201, res.text
    user = v1_db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200, login.text
    return _auth_header(login.json()["access_token"])


def _fail_audit(monkeypatch, module: str) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("forced audit failure")

    monkeypatch.setattr(f"{module}.audit_service.record_audit", fail)


def _count(v1_db, model, *where) -> int:
    v1_db.expire_all()
    query = select(func.count()).select_from(model)
    for clause in where:
        query = query.where(clause)
    return int(v1_db.scalar(query) or 0)


def test_successful_writes_persist_business_row_and_audit(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "atomic-ok@eschool.com")
    created = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": "Atomic Plan", "monthly_price": 10, "yearly_price": 100},
    )
    assert created.status_code == 201, created.text
    plan_id = created.json()["id"]
    assert _count(v1_db, AuditLog, AuditLog.action == "plan.create") == 1

    updated = v1_client.patch(
        f"/api/v1/super-admin/plans/{plan_id}",
        headers=headers,
        json={"name": "Atomic Plan Updated"},
    )
    assert updated.status_code == 200, updated.text
    assert _count(v1_db, AuditLog, AuditLog.action == "plan.update") == 1

    activated = v1_client.patch(
        f"/api/v1/super-admin/plans/{plan_id}/status",
        headers=headers,
        json={"status": 1},
    )
    assert activated.status_code == 200, activated.text
    assert _count(v1_db, AuditLog, AuditLog.action == "plan.status") == 1

    school = v1_client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": "Atomic School", "code": "ATOM1"},
    )
    assert school.status_code == 201, school.text
    school_id = school.json()["id"]
    assigned = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions",
        headers=headers,
        json={
            "package_id": plan_id,
            "start_date": "2026-01-01",
            "end_date": "2026-06-30",
            "cycle": "monthly",
            "status": 1,
        },
    )
    assert assigned.status_code == 201, assigned.text
    sub_id = assigned.json()["id"]
    assert _count(v1_db, AuditLog, AuditLog.action == "subscription.create") == 1

    patched = v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions/{sub_id}",
        headers=headers,
        json={"auto_renew": 0},
    )
    assert patched.status_code == 200, patched.text
    assert _count(v1_db, AuditLog, AuditLog.action == "subscription.update") == 1

    status_change = v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions/{sub_id}/status",
        headers=headers,
        json={"status": 0},
    )
    assert status_change.status_code == 200, status_change.text
    assert _count(v1_db, AuditLog, AuditLog.action == "subscription.status") == 1

    bill = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions/{sub_id}/bills",
        headers=headers,
        json={"period_start": "2026-01-01", "period_end": "2026-02-01", "amount": 10},
    )
    assert bill.status_code == 201, bill.text
    assert _count(v1_db, AuditLog, AuditLog.action == "bill.create") == 0
    paid = v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions/{sub_id}/bills/{bill.json()['id']}/status",
        headers=headers,
        json={"status": 1},
    )
    assert paid.status_code == 200, paid.text
    assert _count(v1_db, AuditLog, AuditLog.action == "bill.status") == 1
    v1_db.expire_all()
    stored = v1_db.get(SubscriptionBill, bill.json()["id"])
    assert stored is not None and stored.status == 1


def test_plan_audit_failure_rolls_back_create_update_and_status(v1_client, v1_db, monkeypatch):
    headers = _super_admin_headers(v1_client, v1_db, "atomic-plan@eschool.com")
    created = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": "Keep Plan", "monthly_price": 5, "yearly_price": 50},
    )
    assert created.status_code == 201, created.text
    plan_id = created.json()["id"]
    _fail_audit(monkeypatch, "app.api.v1.super_admin.plans")

    rejected_update = v1_client.patch(
        f"/api/v1/super-admin/plans/{plan_id}",
        headers=headers,
        json={"name": "Should Not Save"},
    )
    assert rejected_update.status_code == 500
    assert rejected_update.json()["detail"] == "Plan could not be recorded"
    assert "forced audit failure" not in rejected_update.text
    v1_db.expire_all()
    kept = v1_db.get(Package, plan_id)
    assert kept is not None and kept.name == "Keep Plan"
    assert _count(v1_db, AuditLog, AuditLog.action == "plan.update") == 0

    rejected_status = v1_client.patch(
        f"/api/v1/super-admin/plans/{plan_id}/status",
        headers=headers,
        json={"status": 1},
    )
    assert rejected_status.status_code == 500
    v1_db.expire_all()
    kept = v1_db.get(Package, plan_id)
    assert kept is not None and kept.status == 0
    assert _count(v1_db, AuditLog, AuditLog.action == "plan.status") == 0

    rejected_create = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": "Unsaved Plan", "monthly_price": 1, "yearly_price": 2},
    )
    assert rejected_create.status_code == 500
    assert _count(v1_db, Package, Package.name == "Unsaved Plan") == 0
    assert _count(v1_db, AuditLog, AuditLog.action == "plan.create") == 1


def test_subscription_and_bill_audit_failure_rolls_back(v1_client, v1_db, monkeypatch):
    headers = _super_admin_headers(v1_client, v1_db, "atomic-sub@eschool.com")
    plan = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": "Sub Atomic Plan", "monthly_price": 10, "yearly_price": 100},
    )
    assert plan.status_code == 201, plan.text
    plan_id = plan.json()["id"]
    activated = v1_client.patch(
        f"/api/v1/super-admin/plans/{plan_id}/status",
        headers=headers,
        json={"status": 1},
    )
    assert activated.status_code == 200, activated.text
    school = v1_client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": "Sub Atomic School", "code": "ATOM2"},
    )
    assert school.status_code == 201, school.text
    school_id = school.json()["id"]
    body = {
        "package_id": plan_id,
        "start_date": "2026-01-01",
        "end_date": "2026-06-30",
        "cycle": "monthly",
        "status": 1,
    }
    first = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions",
        headers=headers,
        json=body,
    )
    assert first.status_code == 201, first.text
    first_id = first.json()["id"]
    bill = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions/{first_id}/bills",
        headers=headers,
        json={"period_start": "2026-01-01", "period_end": "2026-02-01", "amount": 10},
    )
    assert bill.status_code == 201, bill.text
    creates_before = _count(v1_db, AuditLog, AuditLog.action == "subscription.create")
    _fail_audit(monkeypatch, "app.api.v1.super_admin.subscriptions")

    rejected = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions",
        headers=headers,
        json={**body, "end_date": "2026-07-31"},
    )
    assert rejected.status_code == 500
    assert rejected.json()["detail"] == "Subscription could not be recorded"
    assert "forced audit failure" not in rejected.text
    v1_db.expire_all()
    original = v1_db.get(Subscription, first_id)
    assert original is not None and original.status == 1
    assert _count(v1_db, Subscription, Subscription.school_id == school_id) == 1
    assert _count(v1_db, AuditLog, AuditLog.action == "subscription.create") == creates_before

    rejected_update = v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions/{first_id}",
        headers=headers,
        json={"auto_renew": 0},
    )
    assert rejected_update.status_code == 500
    v1_db.expire_all()
    original = v1_db.get(Subscription, first_id)
    assert original is not None and original.auto_renew == 1
    assert _count(v1_db, AuditLog, AuditLog.action == "subscription.update") == 0

    rejected_status = v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions/{first_id}/status",
        headers=headers,
        json={"status": 0},
    )
    assert rejected_status.status_code == 500
    v1_db.expire_all()
    original = v1_db.get(Subscription, first_id)
    assert original is not None and original.status == 1
    assert _count(v1_db, AuditLog, AuditLog.action == "subscription.status") == 0

    rejected_bill = v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions/{first_id}/bills/{bill.json()['id']}/status",
        headers=headers,
        json={"status": 1},
    )
    assert rejected_bill.status_code == 500
    assert rejected_bill.json()["detail"] == "Bill status could not be recorded"
    v1_db.expire_all()
    stored = v1_db.get(SubscriptionBill, bill.json()["id"])
    assert stored is not None and stored.status == 0
    assert _count(v1_db, AuditLog, AuditLog.action == "bill.status") == 0
