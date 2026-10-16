"""Idempotent subscription expiry. Dates are fixed and do not follow the clock."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select

from app.models.tables import AuditLog, School, Subscription
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User

TODAY = date(2026, 6, 15)
EXPIRE_PATH = "/api/v1/super-admin/subscriptions/expire-due"


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str):
    return client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "secret123",
            "first_name": "Expire",
            "last_name": "Admin",
        },
    )


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


def _freeze_today(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.v1.subscription_service.utc_today",
        lambda: TODAY,
    )


def _school(client, headers, **overrides):
    body = {"name": "Expire School", "code": "EXP001", **overrides}
    res = client.post("/api/v1/super-admin/schools", headers=headers, json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _plan(client, headers):
    created = client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": "Expire Plan", "monthly_price": 10, "yearly_price": 100},
    )
    assert created.status_code == 201, created.text
    plan = created.json()
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
        "end_date": "2026-06-14",
        "cycle": "monthly",
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


def _status(v1_db, subscription_id: int) -> int:
    v1_db.expire_all()
    row = v1_db.get(Subscription, subscription_id)
    assert row is not None
    return row.status


def test_expire_due_rules_school_unchanged_and_idempotent(v1_client, v1_db, monkeypatch):
    _freeze_today(monkeypatch)
    headers = _super_admin_headers(v1_client, v1_db, "expire-rules@eschool.com")
    school = _school(v1_client, headers, code="EXP01A")
    other = _school(v1_client, headers, code="EXP01B", name="Second Expire School")
    plan = _plan(v1_client, headers)
    school_before = v1_db.get(School, school["id"])
    other_before = v1_db.get(School, other["id"])
    assert school_before is not None and other_before is not None
    school_status, school_installed = school_before.status, school_before.installed
    other_status, other_installed = other_before.status, other_before.installed

    removed = _assign(v1_client, headers, school["id"], plan["id"], end_date="2026-06-01")
    removed_row = v1_db.get(Subscription, removed["id"])
    assert removed_row is not None
    removed_row.deleted_at = datetime(2026, 6, 2, 0, 0, 0)
    v1_db.commit()

    inactive = _assign(
        v1_client, headers, school["id"], plan["id"], end_date="2026-06-01", status=0
    )
    already = _assign(
        v1_client, headers, school["id"], plan["id"], end_date="2026-06-01", status=2
    )
    cancelled = _assign(
        v1_client, headers, school["id"], plan["id"], end_date="2026-06-01", status=3
    )
    due = _assign(v1_client, headers, school["id"], plan["id"], end_date="2026-06-14")
    due_other = _assign(v1_client, headers, other["id"], plan["id"], end_date="2026-06-10")
    ends_today = _assign(v1_client, headers, other["id"], plan["id"], end_date="2026-06-15", status=0)
    ends_today_row = v1_db.get(Subscription, ends_today["id"])
    assert ends_today_row is not None
    ends_today_row.status = 1
    v1_db.commit()
    future = _assign(
        v1_client, headers, school["id"], plan["id"], end_date="2026-12-31", status=0
    )
    future_row = v1_db.get(Subscription, future["id"])
    assert future_row is not None
    future_row.status = 1
    v1_db.commit()

    first = v1_client.post(EXPIRE_PATH, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json() == {"expired": 2}
    assert "success" not in first.json()

    assert _status(v1_db, due["id"]) == 2
    assert _status(v1_db, due_other["id"]) == 2
    assert _status(v1_db, ends_today["id"]) == 1
    assert _status(v1_db, future["id"]) == 1
    assert _status(v1_db, inactive["id"]) == 0
    assert _status(v1_db, already["id"]) == 2
    assert _status(v1_db, cancelled["id"]) == 3
    removed_after = v1_db.get(Subscription, removed["id"])
    assert removed_after is not None
    assert removed_after.status == 1
    assert removed_after.deleted_at is not None

    v1_db.expire_all()
    school_after = v1_db.get(School, school["id"])
    other_after = v1_db.get(School, other["id"])
    assert school_after is not None and other_after is not None
    assert (school_after.status, school_after.installed) == (school_status, school_installed)
    assert (other_after.status, other_after.installed) == (other_status, other_installed)

    audits = v1_db.scalars(select(AuditLog).where(AuditLog.action == "subscription.expire")).all()
    assert len(audits) == 1
    assert audits[0].entity_type == "subscription"
    assert audits[0].entity_id is None
    assert audits[0].school_id is None
    assert '"expired": 2' in (audits[0].metadata_json or "")

    second = v1_client.post(EXPIRE_PATH, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json() == {"expired": 0}
    v1_db.expire_all()
    assert len(v1_db.scalars(select(AuditLog).where(AuditLog.action == "subscription.expire")).all()) == 1


def test_expire_due_auth(v1_client, v1_db):
    assert v1_client.post(EXPIRE_PATH).status_code == 401
    token = _signup(v1_client, "expire-user@eschool.com").json()["access_token"]
    forbidden = v1_client.post(EXPIRE_PATH, headers=_auth_header(token))
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Forbidden"


def test_expire_due_database_failure_rolls_back(v1_client, v1_db, monkeypatch):
    _freeze_today(monkeypatch)
    headers = _super_admin_headers(v1_client, v1_db, "expire-fail@eschool.com")
    school = _school(v1_client, headers, code="EXPFAIL")
    plan = _plan(v1_client, headers)
    due = _assign(v1_client, headers, school["id"], plan["id"], end_date="2026-06-01")

    def fail_audit(*args, **kwargs):
        raise RuntimeError("forced database failure")

    monkeypatch.setattr(
        "app.api.v1.super_admin.subscriptions.audit_service.record_audit",
        fail_audit,
    )
    res = v1_client.post(EXPIRE_PATH, headers=headers)
    assert res.status_code == 500
    assert res.json()["detail"] == "Subscriptions could not be expired"

    v1_db.rollback()
    row = v1_db.get(Subscription, due["id"])
    assert row is not None
    assert row.status == 1
    assert row.deleted_at is None
    assert list(v1_db.scalars(select(AuditLog).where(AuditLog.action == "subscription.expire"))) == []
