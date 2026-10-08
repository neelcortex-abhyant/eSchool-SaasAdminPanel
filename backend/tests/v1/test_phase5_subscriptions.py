"""Phase 5: Super Admin subscriptions + subscription bills."""

from __future__ import annotations

from sqlalchemy import select

from app.models.tables import Subscription, SubscriptionBill
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str = "p5-user@eschool.com", **overrides):
    body = {
        "email": email,
        "password": "secret123",
        "first_name": "Phase",
        "last_name": "Five",
        **overrides,
    }
    return client.post("/api/v1/auth/signup", json=body)


def _super_admin_headers(client, v1_db, email: str = "p5-sa@eschool.com") -> dict[str, str]:
    res = _signup(client, email=email)
    assert res.status_code == 201
    user = v1_db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200
    return _auth_header(login.json()["access_token"])


def _school(client, headers, **overrides):
    body = {"name": "Sub School", "code": "SUBS01", **overrides}
    res = client.post("/api/v1/super-admin/schools", headers=headers, json=body)
    assert res.status_code == 201
    return res.json()


def _plan(client, headers, **overrides):
    body = {
        "name": "Sub Plan",
        "monthly_price": 50.0,
        "yearly_price": 500.0,
        "student_limit": 50,
        **overrides,
    }
    res = client.post("/api/v1/super-admin/plans", headers=headers, json=body)
    assert res.status_code == 201
    # activate for realism (not required by service)
    client.patch(
        f"/api/v1/super-admin/plans/{res.json()['id']}/status",
        headers=headers,
        json={"status": 1},
    )
    return res.json()


def _sub_body(package_id: int, **overrides):
    body = {
        "package_id": package_id,
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "cycle": "monthly",
        "auto_renew": 1,
        "status": 1,
    }
    body.update(overrides)
    return body


def test_subscriptions_auth_gates(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _school(v1_client, headers)["id"]
    path = f"/api/v1/super-admin/schools/{school_id}/subscriptions"
    assert v1_client.get(path).status_code == 401
    assert v1_client.get(path, headers=_auth_header("bad")).status_code == 401
    token = _signup(v1_client, email="p5-normal@eschool.com").json()["access_token"]
    assert v1_client.get(path, headers=_auth_header(token)).status_code == 403


def test_create_list_get_patch_subscription(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school = _school(v1_client, headers)
    plan = _plan(v1_client, headers)
    base = f"/api/v1/super-admin/schools/{school['id']}/subscriptions"

    created = v1_client.post(base, headers=headers, json=_sub_body(plan["id"]))
    assert created.status_code == 201
    data = created.json()
    assert data["school_id"] == school["id"]
    assert data["package_id"] == plan["id"]
    assert data["status"] == 1
    assert data["start_date"] == "2026-01-01"
    assert data["end_date"] == "2026-12-31"
    assert data["cycle"] == "monthly"
    sub_id = data["id"]

    got = v1_client.get(f"{base}/{sub_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["id"] == sub_id

    listing = v1_client.get(base, headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1

    patched = v1_client.patch(
        f"{base}/{sub_id}",
        headers=headers,
        json={"end_date": "2027-01-31", "auto_renew": 0},
    )
    assert patched.status_code == 200
    assert patched.json()["end_date"] == "2027-01-31"
    assert patched.json()["auto_renew"] == 0
    assert patched.json()["school_id"] == school["id"]

    row = v1_db.get(Subscription, sub_id)
    assert row is not None
    assert str(row.end_date) == "2027-01-31"


def test_invalid_school_and_package(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    plan = _plan(v1_client, headers)
    school = _school(v1_client, headers)

    missing_school = v1_client.post(
        "/api/v1/super-admin/schools/999999/subscriptions",
        headers=headers,
        json=_sub_body(plan["id"]),
    )
    assert missing_school.status_code == 404

    bad_pkg = v1_client.post(
        f"/api/v1/super-admin/schools/{school['id']}/subscriptions",
        headers=headers,
        json=_sub_body(999999),
    )
    assert bad_pkg.status_code == 404


def test_invalid_date_range(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school = _school(v1_client, headers)
    plan = _plan(v1_client, headers)
    res = v1_client.post(
        f"/api/v1/super-admin/schools/{school['id']}/subscriptions",
        headers=headers,
        json=_sub_body(plan["id"], start_date="2026-06-01", end_date="2026-01-01"),
    )
    assert res.status_code == 422


def test_subscription_status_and_replace_active(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school = _school(v1_client, headers)
    plan_a = _plan(v1_client, headers, name="Plan A")
    plan_b = _plan(v1_client, headers, name="Plan B", monthly_price=80)
    base = f"/api/v1/super-admin/schools/{school['id']}/subscriptions"

    first = v1_client.post(base, headers=headers, json=_sub_body(plan_a["id"])).json()
    second = v1_client.post(base, headers=headers, json=_sub_body(plan_b["id"])).json()

    first_row = v1_db.get(Subscription, first["id"])
    second_row = v1_db.get(Subscription, second["id"])
    assert first_row is not None and second_row is not None
    assert first_row.status == 3  # cancelled when second became active
    assert second_row.status == 1

    cancelled = v1_client.patch(
        f"{base}/{second['id']}/status",
        headers=headers,
        json={"status": 3},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == 3


def test_bills_create_list_get_status(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school = _school(v1_client, headers)
    plan = _plan(v1_client, headers)
    base = f"/api/v1/super-admin/schools/{school['id']}/subscriptions"
    sub = v1_client.post(base, headers=headers, json=_sub_body(plan["id"])).json()
    bills = f"{base}/{sub['id']}/bills"

    # amount defaults from package monthly_price
    created = v1_client.post(
        bills,
        headers=headers,
        json={
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "due_date": "2026-02-05",
            "description": "January",
        },
    )
    assert created.status_code == 201
    data = created.json()
    assert data["school_id"] == school["id"]
    assert data["subscription_id"] == sub["id"]
    assert data["amount"] == 50.0
    assert data["status"] == 0
    bill_id = data["id"]

    listing = v1_client.get(bills, headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1

    got = v1_client.get(f"{bills}/{bill_id}", headers=headers)
    assert got.status_code == 200

    paid = v1_client.patch(
        f"{bills}/{bill_id}/status",
        headers=headers,
        json={"status": 1},
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == 1

    row = v1_db.get(SubscriptionBill, bill_id)
    assert row is not None
    assert row.status == 1
    assert row.school_id == school["id"]


def test_bill_wrong_school_404(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_a = _school(v1_client, headers, code="SUBA01", name="A")
    school_b = _school(v1_client, headers, code="SUBB01", name="B", support_email="b@eschool.com")
    plan = _plan(v1_client, headers)
    sub = v1_client.post(
        f"/api/v1/super-admin/schools/{school_a['id']}/subscriptions",
        headers=headers,
        json=_sub_body(plan["id"]),
    ).json()
    bill = v1_client.post(
        f"/api/v1/super-admin/schools/{school_a['id']}/subscriptions/{sub['id']}/bills",
        headers=headers,
        json={"period_start": "2026-01-01", "period_end": "2026-01-31", "amount": 10},
    ).json()

    # Same subscription id under school B must 404
    res = v1_client.get(
        f"/api/v1/super-admin/schools/{school_b['id']}/subscriptions/{sub['id']}/bills/{bill['id']}",
        headers=headers,
    )
    assert res.status_code == 404


def test_school_admin_forbidden(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school = _school(v1_client, headers)
    plan = _plan(v1_client, headers)
    v1_client.post(
        f"/api/v1/super-admin/schools/{school['id']}/admins",
        headers=headers,
        json={
            "email": "p5-school-admin@eschool.com",
            "password": "adminpass1",
            "first_name": "SA",
            "last_name": "Admin",
        },
    )
    login = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "p5-school-admin@eschool.com", "password": "adminpass1"},
    )
    sa = _auth_header(login.json()["access_token"])
    path = f"/api/v1/super-admin/schools/{school['id']}/subscriptions"
    assert v1_client.get(path, headers=sa).status_code == 403
    assert (
        v1_client.post(path, headers=sa, json=_sub_body(plan["id"])).status_code == 403
    )


def test_super_admin_can_manage_both_schools(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    a = _school(v1_client, headers, code="BOTH01", name="Both A")
    b = _school(
        v1_client, headers, code="BOTH02", name="Both B", support_email="bothb@eschool.com"
    )
    plan = _plan(v1_client, headers)
    sa = v1_client.post(
        f"/api/v1/super-admin/schools/{a['id']}/subscriptions",
        headers=headers,
        json=_sub_body(plan["id"]),
    )
    sb = v1_client.post(
        f"/api/v1/super-admin/schools/{b['id']}/subscriptions",
        headers=headers,
        json=_sub_body(plan["id"]),
    )
    assert sa.status_code == 201
    assert sb.status_code == 201
    assert (
        v1_client.get(
            f"/api/v1/super-admin/schools/{a['id']}/subscriptions/{sa.json()['id']}",
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        v1_client.get(
            f"/api/v1/super-admin/schools/{b['id']}/subscriptions/{sb.json()['id']}",
            headers=headers,
        ).status_code
        == 200
    )
