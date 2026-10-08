"""Phase 6: Super Admin addons + school addon assignments."""

from __future__ import annotations

from sqlalchemy import select

from app.models.tables import Addon, AddonSubscription
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str = "p6-user@eschool.com", **overrides):
    body = {
        "email": email,
        "password": "secret123",
        "first_name": "Phase",
        "last_name": "Six",
        **overrides,
    }
    return client.post("/api/v1/auth/signup", json=body)


def _sa(client, v1_db, email: str = "p6-sa@eschool.com") -> dict[str, str]:
    assert _signup(client, email=email).status_code == 201
    user = v1_db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200
    return _auth_header(login.json()["access_token"])


def _school(client, headers, **overrides):
    body = {"name": "Addon School", "code": "ADDON1", **overrides}
    res = client.post("/api/v1/super-admin/schools", headers=headers, json=body)
    assert res.status_code == 201
    return res.json()


def _plan(client, headers, **overrides):
    body = {"name": "Addon Plan", "monthly_price": 40.0, **overrides}
    res = client.post("/api/v1/super-admin/plans", headers=headers, json=body)
    assert res.status_code == 201
    return res.json()


def _subscribe(client, headers, school_id: int, package_id: int):
    res = client.post(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions",
        headers=headers,
        json={
            "package_id": package_id,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "cycle": "monthly",
            "status": 1,
        },
    )
    assert res.status_code == 201
    return res.json()


def _addon(client, headers, **overrides):
    body = {"name": "Chat Module", "description": "Messaging", "price": 15.0, **overrides}
    res = client.post("/api/v1/super-admin/addons", headers=headers, json=body)
    assert res.status_code == 201
    addon = res.json()
    client.patch(
        f"/api/v1/super-admin/addons/{addon['id']}/status",
        headers=headers,
        json={"status": 1},
    )
    return client.get(f"/api/v1/super-admin/addons/{addon['id']}", headers=headers).json()


def test_addon_auth_gates(v1_client, v1_db):
    assert v1_client.get("/api/v1/super-admin/addons").status_code == 401
    assert (
        v1_client.get("/api/v1/super-admin/addons", headers=_auth_header("bad")).status_code
        == 401
    )
    token = _signup(v1_client).json()["access_token"]
    assert (
        v1_client.get("/api/v1/super-admin/addons", headers=_auth_header(token)).status_code
        == 403
    )


def test_addon_crud_and_status(v1_client, v1_db):
    headers = _sa(v1_client, v1_db)
    created = v1_client.post(
        "/api/v1/super-admin/addons",
        headers=headers,
        json={"name": "Gallery", "description": "Photos", "price": 10.0},
    )
    assert created.status_code == 201
    data = created.json()
    assert data["name"] == "Gallery"
    assert data["price"] == 10.0
    assert data["status"] == 0
    addon_id = data["id"]

    got = v1_client.get(f"/api/v1/super-admin/addons/{addon_id}", headers=headers)
    assert got.status_code == 200

    listing = v1_client.get("/api/v1/super-admin/addons", headers=headers)
    assert listing.status_code == 200
    assert any(item["id"] == addon_id for item in listing.json()["items"])

    patched = v1_client.patch(
        f"/api/v1/super-admin/addons/{addon_id}",
        headers=headers,
        json={"name": "School Gallery", "price": 12.5},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "School Gallery"
    assert patched.json()["price"] == 12.5

    activated = v1_client.patch(
        f"/api/v1/super-admin/addons/{addon_id}/status",
        headers=headers,
        json={"status": 1},
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == 1

    deactivated = v1_client.patch(
        f"/api/v1/super-admin/addons/{addon_id}/status",
        headers=headers,
        json={"status": 0},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == 0

    row = v1_db.get(Addon, addon_id)
    assert row is not None
    assert row.name == "School Gallery"


def test_duplicate_addon_name(v1_client, v1_db):
    headers = _sa(v1_client, v1_db)
    assert (
        v1_client.post(
            "/api/v1/super-admin/addons",
            headers=headers,
            json={"name": "DupAddon", "price": 1},
        ).status_code
        == 201
    )
    again = v1_client.post(
        "/api/v1/super-admin/addons",
        headers=headers,
        json={"name": "DupAddon", "price": 2},
    )
    assert again.status_code == 409


def test_assign_list_deactivate_school_addon(v1_client, v1_db):
    headers = _sa(v1_client, v1_db)
    school = _school(v1_client, headers)
    plan = _plan(v1_client, headers)
    sub = _subscribe(v1_client, headers, school["id"], plan["id"])
    addon = _addon(v1_client, headers)
    base = f"/api/v1/super-admin/schools/{school['id']}/addons"

    assigned = v1_client.post(
        base,
        headers=headers,
        json={"addon_id": addon["id"], "subscription_id": sub["id"]},
    )
    assert assigned.status_code == 201
    data = assigned.json()
    assert data["school_id"] == school["id"]
    assert data["addon_id"] == addon["id"]
    assert data["subscription_id"] == sub["id"]
    assert data["status"] == 1
    assignment_id = data["id"]

    listing = v1_client.get(base, headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1

    got = v1_client.get(f"{base}/{assignment_id}", headers=headers)
    assert got.status_code == 200

    deactivated = v1_client.patch(
        f"{base}/{assignment_id}/status",
        headers=headers,
        json={"status": 0},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == 0

    row = v1_db.get(AddonSubscription, assignment_id)
    assert row is not None
    assert row.status == 0


def test_duplicate_active_assignment(v1_client, v1_db):
    headers = _sa(v1_client, v1_db)
    school = _school(v1_client, headers)
    plan = _plan(v1_client, headers)
    _subscribe(v1_client, headers, school["id"], plan["id"])
    addon = _addon(v1_client, headers)
    base = f"/api/v1/super-admin/schools/{school['id']}/addons"
    assert (
        v1_client.post(base, headers=headers, json={"addon_id": addon["id"]}).status_code
        == 201
    )
    again = v1_client.post(base, headers=headers, json={"addon_id": addon["id"]})
    assert again.status_code == 409
    assert again.json()["detail"] == "Addon already assigned to this school"


def test_assign_requires_active_addon_and_subscription(v1_client, v1_db):
    headers = _sa(v1_client, v1_db)
    school = _school(v1_client, headers)
    plan = _plan(v1_client, headers)
    base = f"/api/v1/super-admin/schools/{school['id']}/addons"

    inactive = v1_client.post(
        "/api/v1/super-admin/addons",
        headers=headers,
        json={"name": "InactiveAddon", "price": 5},
    ).json()
    no_sub = v1_client.post(base, headers=headers, json={"addon_id": inactive["id"]})
    assert no_sub.status_code in (409, 422)

    _subscribe(v1_client, headers, school["id"], plan["id"])
    inactive_assign = v1_client.post(
        base, headers=headers, json={"addon_id": inactive["id"]}
    )
    assert inactive_assign.status_code == 422

    missing = v1_client.post(base, headers=headers, json={"addon_id": 999999})
    assert missing.status_code == 404


def test_invalid_school_and_cross_school_isolation(v1_client, v1_db):
    headers = _sa(v1_client, v1_db)
    school_a = _school(v1_client, headers, code="ADDA01", name="A")
    school_b = _school(
        v1_client, headers, code="ADDB01", name="B", support_email="b@eschool.com"
    )
    plan = _plan(v1_client, headers)
    _subscribe(v1_client, headers, school_a["id"], plan["id"])
    addon = _addon(v1_client, headers)
    assigned = v1_client.post(
        f"/api/v1/super-admin/schools/{school_a['id']}/addons",
        headers=headers,
        json={"addon_id": addon["id"]},
    ).json()

    assert (
        v1_client.get(
            f"/api/v1/super-admin/schools/999999/addons", headers=headers
        ).status_code
        == 404
    )
    assert (
        v1_client.get(
            f"/api/v1/super-admin/schools/{school_b['id']}/addons/{assigned['id']}",
            headers=headers,
        ).status_code
        == 404
    )


def test_school_admin_forbidden(v1_client, v1_db):
    headers = _sa(v1_client, v1_db)
    school = _school(v1_client, headers)
    addon = _addon(v1_client, headers)
    v1_client.post(
        f"/api/v1/super-admin/schools/{school['id']}/admins",
        headers=headers,
        json={
            "email": "p6-school-admin@eschool.com",
            "password": "adminpass1",
            "first_name": "SA",
            "last_name": "Admin",
        },
    )
    login = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "p6-school-admin@eschool.com", "password": "adminpass1"},
    )
    sa = _auth_header(login.json()["access_token"])
    assert v1_client.get("/api/v1/super-admin/addons", headers=sa).status_code == 403
    assert (
        v1_client.post(
            f"/api/v1/super-admin/schools/{school['id']}/addons",
            headers=sa,
            json={"addon_id": addon["id"]},
        ).status_code
        == 403
    )


def test_super_admin_both_schools(v1_client, v1_db):
    headers = _sa(v1_client, v1_db)
    a = _school(v1_client, headers, code="BOTHA1", name="BothA")
    b = _school(
        v1_client, headers, code="BOTHB1", name="BothB", support_email="bb@eschool.com"
    )
    plan = _plan(v1_client, headers, name="BothPlan")
    _subscribe(v1_client, headers, a["id"], plan["id"])
    _subscribe(v1_client, headers, b["id"], plan["id"])
    addon = _addon(v1_client, headers, name="SharedAddon")
    ra = v1_client.post(
        f"/api/v1/super-admin/schools/{a['id']}/addons",
        headers=headers,
        json={"addon_id": addon["id"]},
    )
    rb = v1_client.post(
        f"/api/v1/super-admin/schools/{b['id']}/addons",
        headers=headers,
        json={"addon_id": addon["id"]},
    )
    assert ra.status_code == 201
    assert rb.status_code == 201
