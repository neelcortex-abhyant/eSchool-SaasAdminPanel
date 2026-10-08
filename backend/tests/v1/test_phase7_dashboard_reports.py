"""Phase 7: Super Admin dashboard + reports."""

from __future__ import annotations

from sqlalchemy import select

from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str = "p7-user@eschool.com", **overrides):
    body = {
        "email": email,
        "password": "secret123",
        "first_name": "Phase",
        "last_name": "Seven",
        **overrides,
    }
    return client.post("/api/v1/auth/signup", json=body)


def _sa(client, v1_db, email: str = "p7-sa@eschool.com") -> dict[str, str]:
    assert _signup(client, email=email).status_code == 201
    user = v1_db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200
    return _auth_header(login.json()["access_token"])


def _seed_saas(client, headers):
    school = client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": "Dash School", "code": "DASH01"},
    ).json()
    plan = client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": "Dash Plan", "monthly_price": 100.0, "yearly_price": 1000.0},
    ).json()
    client.patch(
        f"/api/v1/super-admin/plans/{plan['id']}/status",
        headers=headers,
        json={"status": 1},
    )
    sub = client.post(
        f"/api/v1/super-admin/schools/{school['id']}/subscriptions",
        headers=headers,
        json={
            "package_id": plan["id"],
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "cycle": "monthly",
            "status": 1,
        },
    ).json()
    bill = client.post(
        f"/api/v1/super-admin/schools/{school['id']}/subscriptions/{sub['id']}/bills",
        headers=headers,
        json={
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "amount": 100.0,
        },
    ).json()
    addon = client.post(
        "/api/v1/super-admin/addons",
        headers=headers,
        json={"name": "Dash Addon", "price": 20.0},
    ).json()
    client.patch(
        f"/api/v1/super-admin/addons/{addon['id']}/status",
        headers=headers,
        json={"status": 1},
    )
    assignment = client.post(
        f"/api/v1/super-admin/schools/{school['id']}/addons",
        headers=headers,
        json={"addon_id": addon["id"], "subscription_id": sub["id"]},
    ).json()
    return {
        "school": school,
        "plan": plan,
        "sub": sub,
        "bill": bill,
        "addon": addon,
        "assignment": assignment,
    }


def test_dashboard_auth(v1_client, v1_db):
    assert v1_client.get("/api/v1/super-admin/dashboard").status_code == 401
    assert (
        v1_client.get(
            "/api/v1/super-admin/dashboard", headers=_auth_header("bad")
        ).status_code
        == 401
    )
    token = _signup(v1_client).json()["access_token"]
    assert (
        v1_client.get(
            "/api/v1/super-admin/dashboard", headers=_auth_header(token)
        ).status_code
        == 403
    )


def test_dashboard_empty_and_seeded_metrics(v1_client, v1_db):
    headers = _sa(v1_client, v1_db)
    empty = v1_client.get("/api/v1/super-admin/dashboard", headers=headers)
    assert empty.status_code == 200
    body = empty.json()
    # Legacy keys preserved
    for key in ("schools", "schools_active", "packages", "packages_active", "super_admins"):
        assert key in body
    assert body["super_admins"] >= 1
    assert body["schools"] == 0
    assert body["subscriptions"] == 0
    assert body["bills"] == 0
    assert "payment_gateway_revenue" in body["unavailable_metrics"]
    assert "payment_transactions" in body["unavailable_metrics"]

    seeded = _seed_saas(v1_client, headers)
    # suspend one more school to exercise inactive count
    other = v1_client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": "Inactive School", "code": "DASH02"},
    ).json()
    v1_client.post(
        f"/api/v1/super-admin/schools/{other['id']}/suspend", headers=headers
    )

    dash = v1_client.get("/api/v1/super-admin/dashboard", headers=headers).json()
    assert dash["schools"] == 2
    assert dash["schools_active"] == 1
    assert dash["schools_inactive"] == 1
    assert dash["plans"] == 1
    assert dash["plans_active"] == 1
    assert dash["packages"] == dash["plans"]
    assert dash["subscriptions"] == 1
    assert dash["subscriptions_active"] == 1
    assert dash["addons"] == 1
    assert dash["addons_active"] == 1
    assert dash["addon_assignments_active"] == 1
    assert dash["bills"] == 1
    assert dash["bills_pending"] == 1
    assert dash["bill_amount_total"] == 100.0
    assert dash["bill_amount_pending"] == 100.0
    assert dash["bill_amount_paid"] == 0.0
    assert seeded["school"]["id"]


def test_reports_auth_and_filters(v1_client, v1_db):
    headers = _sa(v1_client, v1_db)
    seeded = _seed_saas(v1_client, headers)

    assert v1_client.get("/api/v1/super-admin/reports/schools").status_code == 401
    token = _signup(v1_client, email="p7-rep-user@eschool.com").json()["access_token"]
    assert (
        v1_client.get(
            "/api/v1/super-admin/reports/schools", headers=_auth_header(token)
        ).status_code
        == 403
    )

    schools = v1_client.get("/api/v1/super-admin/reports/schools", headers=headers)
    assert schools.status_code == 200
    assert schools.json()["total"] >= 1

    active_only = v1_client.get(
        "/api/v1/super-admin/reports/schools",
        headers=headers,
        params={"status": 1},
    )
    assert active_only.status_code == 200
    assert all(item["status"] == 1 for item in active_only.json()["items"])

    subs = v1_client.get(
        "/api/v1/super-admin/reports/subscriptions",
        headers=headers,
        params={
            "status": 1,
            "package_id": seeded["plan"]["id"],
            "school_id": seeded["school"]["id"],
        },
    )
    assert subs.status_code == 200
    assert subs.json()["total"] == 1
    assert subs.json()["items"][0]["id"] == seeded["sub"]["id"]

    bills = v1_client.get(
        "/api/v1/super-admin/reports/bills",
        headers=headers,
        params={
            "school_id": seeded["school"]["id"],
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        },
    )
    assert bills.status_code == 200
    assert bills.json()["total"] == 1
    assert bills.json()["amount_sum"] == 100.0

    bad_range = v1_client.get(
        "/api/v1/super-admin/reports/bills",
        headers=headers,
        params={"start_date": "2026-06-01", "end_date": "2026-01-01"},
    )
    assert bad_range.status_code == 422


def test_reports_empty(v1_client, v1_db):
    headers = _sa(v1_client, v1_db)
    schools = v1_client.get("/api/v1/super-admin/reports/schools", headers=headers)
    assert schools.status_code == 200
    assert schools.json()["total"] == 0
    assert schools.json()["items"] == []

    subs = v1_client.get("/api/v1/super-admin/reports/subscriptions", headers=headers)
    assert subs.status_code == 200
    assert subs.json()["total"] == 0

    bills = v1_client.get("/api/v1/super-admin/reports/bills", headers=headers)
    assert bills.status_code == 200
    assert bills.json()["total"] == 0
    assert bills.json()["amount_sum"] == 0.0


def test_school_admin_forbidden_dashboard_reports(v1_client, v1_db):
    headers = _sa(v1_client, v1_db)
    school = v1_client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": "SA Block", "code": "SABLK1"},
    ).json()
    v1_client.post(
        f"/api/v1/super-admin/schools/{school['id']}/admins",
        headers=headers,
        json={
            "email": "p7-school-admin@eschool.com",
            "password": "adminpass1",
            "first_name": "SA",
            "last_name": "Admin",
        },
    )
    login = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "p7-school-admin@eschool.com", "password": "adminpass1"},
    )
    sa = _auth_header(login.json()["access_token"])
    assert v1_client.get("/api/v1/super-admin/dashboard", headers=sa).status_code == 403
    assert (
        v1_client.get("/api/v1/super-admin/reports/schools", headers=sa).status_code
        == 403
    )
