"""Phase 4: Super Admin plans (/api/v1/super-admin/plans) on Package table."""

from __future__ import annotations

from sqlalchemy import select

from app.models.tables import Package
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str = "p4-user@eschool.com", **overrides):
    body = {
        "email": email,
        "password": "secret123",
        "first_name": "Phase",
        "last_name": "Four",
        **overrides,
    }
    return client.post("/api/v1/auth/signup", json=body)


def _super_admin_headers(client, v1_db, email: str = "p4-sa@eschool.com") -> dict[str, str]:
    res = _signup(client, email=email)
    assert res.status_code == 201
    user = v1_db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200
    return _auth_header(login.json()["access_token"])


def _plan_body(**overrides):
    body = {
        "name": "Starter Plan",
        "description": "Entry package",
        "monthly_price": 99.0,
        "yearly_price": 999.0,
        "student_limit": 100,
        "staff_limit": 20,
    }
    body.update(overrides)
    return body


def test_plans_unauthenticated_401(v1_client):
    assert v1_client.get("/api/v1/super-admin/plans").status_code == 401
    assert (
        v1_client.get(
            "/api/v1/super-admin/plans", headers=_auth_header("bad-token")
        ).status_code
        == 401
    )


def test_plans_normal_user_403(v1_client):
    token = _signup(v1_client).json()["access_token"]
    res = v1_client.get("/api/v1/super-admin/plans", headers=_auth_header(token))
    assert res.status_code == 403


def test_create_list_get_patch_plan(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    created = v1_client.post(
        "/api/v1/super-admin/plans", headers=headers, json=_plan_body()
    )
    assert created.status_code == 201
    data = created.json()
    assert data["name"] == "Starter Plan"
    assert data["monthly_price"] == 99.0
    assert data["yearly_price"] == 999.0
    assert data["student_limit"] == 100
    assert data["staff_limit"] == 20
    assert data["status"] == 0  # unpublished by default
    plan_id = data["id"]

    got = v1_client.get(f"/api/v1/super-admin/plans/{plan_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["id"] == plan_id

    listing = v1_client.get("/api/v1/super-admin/plans", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1
    assert any(item["id"] == plan_id for item in listing.json()["items"])

    patched = v1_client.patch(
        f"/api/v1/super-admin/plans/{plan_id}",
        headers=headers,
        json={"name": "Starter Plus", "monthly_price": 149.0, "student_limit": None},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Starter Plus"
    assert patched.json()["monthly_price"] == 149.0
    assert patched.json()["student_limit"] is None

    row = v1_db.get(Package, plan_id)
    assert row is not None
    assert row.name == "Starter Plus"
    assert float(row.monthly_price) == 149.0


def test_duplicate_plan_name_409(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    assert (
        v1_client.post(
            "/api/v1/super-admin/plans", headers=headers, json=_plan_body()
        ).status_code
        == 201
    )
    again = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json=_plan_body(description="Other"),
    )
    assert again.status_code == 409
    assert again.json()["detail"] == "Plan name already in use"


def test_validation_negative_price(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    res = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json=_plan_body(monthly_price=-1),
    )
    assert res.status_code == 422


def test_validation_empty_name(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    res = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json=_plan_body(name=""),
    )
    assert res.status_code == 422


def test_plan_status_activate_deactivate(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    plan_id = v1_client.post(
        "/api/v1/super-admin/plans", headers=headers, json=_plan_body()
    ).json()["id"]

    activated = v1_client.patch(
        f"/api/v1/super-admin/plans/{plan_id}/status",
        headers=headers,
        json={"status": 1},
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == 1

    deactivated = v1_client.patch(
        f"/api/v1/super-admin/plans/{plan_id}/status",
        headers=headers,
        json={"status": 0},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == 0

    bad = v1_client.patch(
        f"/api/v1/super-admin/plans/{plan_id}/status",
        headers=headers,
        json={"status": 5},
    )
    assert bad.status_code == 422


def test_get_plan_404(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    assert (
        v1_client.get("/api/v1/super-admin/plans/999999", headers=headers).status_code
        == 404
    )


def test_school_admin_forbidden_on_plans(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school = v1_client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": "P4 School", "code": "P4SCH1"},
    ).json()
    v1_client.post(
        f"/api/v1/super-admin/schools/{school['id']}/admins",
        headers=headers,
        json={
            "email": "p4-school-admin@eschool.com",
            "password": "adminpass1",
            "first_name": "SA",
            "last_name": "Admin",
        },
    )
    login = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "p4-school-admin@eschool.com", "password": "adminpass1"},
    )
    assert login.status_code == 200
    sa = _auth_header(login.json()["access_token"])
    assert v1_client.get("/api/v1/super-admin/plans", headers=sa).status_code == 403
    assert (
        v1_client.post(
            "/api/v1/super-admin/plans", headers=sa, json=_plan_body()
        ).status_code
        == 403
    )


def test_list_status_filter(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    a = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json=_plan_body(name="Active Plan"),
    ).json()["id"]
    v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json=_plan_body(name="Inactive Plan"),
    )
    v1_client.patch(
        f"/api/v1/super-admin/plans/{a}/status",
        headers=headers,
        json={"status": 1},
    )
    active = v1_client.get(
        "/api/v1/super-admin/plans", headers=headers, params={"status": 1}
    )
    assert active.status_code == 200
    assert all(item["status"] == 1 for item in active.json()["items"])
    assert any(item["id"] == a for item in active.json()["items"])
