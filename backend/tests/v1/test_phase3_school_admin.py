"""Phase 3: school provisioning + School Admin management + isolation."""

from __future__ import annotations

from sqlalchemy import select

from app.core.security import verify_password
from app.models.tables import School, SessionYear
from app.models.v1.roles import ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN, ROLE_USER
from app.models.v1.user import STATUS_ACTIVE, STATUS_INACTIVE, User


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str = "p3-user@eschool.com", **overrides):
    body = {
        "email": email,
        "password": "secret123",
        "first_name": "Phase",
        "last_name": "Three",
        **overrides,
    }
    return client.post("/api/v1/auth/signup", json=body)


def _super_admin_headers(client, v1_db, email: str = "p3-sa@eschool.com") -> dict[str, str]:
    res = _signup(client, email=email)
    assert res.status_code == 201
    user = v1_db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200
    return _auth_header(login.json()["access_token"])


def _create_school(client, headers, **overrides):
    body = {
        "name": "Provision School",
        "address": "1 Main",
        "support_phone": "111",
        "support_email": "prov@eschool.com",
        "code": "PROV01",
        **overrides,
    }
    return client.post("/api/v1/super-admin/schools", headers=headers, json=body)


def _admin_body(**overrides):
    body = {
        "email": "school-admin@eschool.com",
        "password": "adminpass1",
        "first_name": "School",
        "last_name": "Admin",
        "mobile": "9999999999",
    }
    body.update(overrides)
    return body


# --- provisioning ---


def test_provision_school_idempotent(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers).json()["id"]

    first = v1_client.post(f"/api/v1/super-admin/schools/{school_id}/provision", headers=headers)
    assert first.status_code == 200
    body = first.json()
    assert body["provisioned"] is True
    assert body["first_provision"] is True
    assert body["school"]["id"] == school_id
    assert body["school"]["status"] == 1
    assert body["school"]["installed"] == 1
    assert body["school"]["provisioned_at"] is not None
    first_at = body["school"]["provisioned_at"]

    years = list(
        v1_db.scalars(select(SessionYear).where(SessionYear.school_id == school_id))
    )
    assert len(years) == 1
    assert years[0].default == 1

    second = v1_client.post(f"/api/v1/super-admin/schools/{school_id}/provision", headers=headers)
    assert second.status_code == 200
    assert second.json()["first_provision"] is False
    assert second.json()["school"]["provisioned_at"] == first_at
    years2 = list(
        v1_db.scalars(select(SessionYear).where(SessionYear.school_id == school_id))
    )
    assert len(years2) == 1

    school = v1_db.get(School, school_id)
    assert school is not None
    assert school.provisioned_at is not None


def test_provision_nonexistent_school_404(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    res = v1_client.post("/api/v1/super-admin/schools/999999/provision", headers=headers)
    assert res.status_code == 404


def test_provision_auth_gates(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers).json()["id"]

    assert (
        v1_client.post(f"/api/v1/super-admin/schools/{school_id}/provision").status_code
        == 401
    )
    assert (
        v1_client.post(
            f"/api/v1/super-admin/schools/{school_id}/provision",
            headers=_auth_header("not-a-real-token"),
        ).status_code
        == 401
    )
    user_token = _signup(v1_client, email="p3-normal@eschool.com").json()["access_token"]
    assert (
        v1_client.post(
            f"/api/v1/super-admin/schools/{school_id}/provision",
            headers=_auth_header(user_token),
        ).status_code
        == 403
    )


# --- create / manage school admins ---


def test_create_school_admin_role_school_id_hashed_password(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers).json()["id"]

    res = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=headers,
        json=_admin_body(),
    )
    assert res.status_code == 201
    data = res.json()
    assert data["role"] == ROLE_SCHOOL_ADMIN
    assert data["school_id"] == school_id
    assert data["email"] == "school-admin@eschool.com"
    assert data["status"] == STATUS_ACTIVE
    assert "password" not in data
    assert "password_hash" not in data

    user = v1_db.scalar(select(User).where(User.email == "school-admin@eschool.com"))
    assert user is not None
    assert user.role == ROLE_SCHOOL_ADMIN
    assert user.school_id == school_id
    assert user.password_hash != "adminpass1"
    assert verify_password("adminpass1", user.password_hash)

    school = v1_db.get(School, school_id)
    assert school is not None
    assert school.v1_admin_id == str(user.id)


def test_create_school_admin_duplicate_email_409(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers).json()["id"]
    assert (
        v1_client.post(
            f"/api/v1/super-admin/schools/{school_id}/admins",
            headers=headers,
            json=_admin_body(),
        ).status_code
        == 201
    )
    again = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=headers,
        json=_admin_body(first_name="Other"),
    )
    assert again.status_code == 409
    assert again.json()["detail"] == "Email already registered"


def test_create_school_admin_rejects_client_role_and_school_id(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers).json()["id"]
    res = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=headers,
        json=_admin_body(role="super_admin", school_id=999),
    )
    assert res.status_code == 422


def test_list_get_patch_status_school_admin(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers).json()["id"]
    created = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=headers,
        json=_admin_body(),
    ).json()
    admin_id = created["id"]

    listing = v1_client.get(
        f"/api/v1/super-admin/schools/{school_id}/admins", headers=headers
    )
    assert listing.status_code == 200
    assert any(item["id"] == admin_id for item in listing.json()["items"])

    got = v1_client.get(
        f"/api/v1/super-admin/schools/{school_id}/admins/{admin_id}", headers=headers
    )
    assert got.status_code == 200
    assert got.json()["email"] == "school-admin@eschool.com"
    assert "password_hash" not in got.json()

    patched = v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}/admins/{admin_id}",
        headers=headers,
        json={"first_name": "Updated", "school_id": 999, "role": "super_admin"},
    )
    # school_id/role forbidden by schema → 422
    assert patched.status_code == 422

    patched_ok = v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}/admins/{admin_id}",
        headers=headers,
        json={"first_name": "Updated"},
    )
    assert patched_ok.status_code == 200
    assert patched_ok.json()["first_name"] == "Updated"
    assert patched_ok.json()["school_id"] == school_id
    assert patched_ok.json()["role"] == ROLE_SCHOOL_ADMIN

    deactivated = v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}/admins/{admin_id}/status",
        headers=headers,
        json={"status": STATUS_INACTIVE},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == STATUS_INACTIVE

    activated = v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}/admins/{admin_id}/status",
        headers=headers,
        json={"status": STATUS_ACTIVE},
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == STATUS_ACTIVE


def test_admin_wrong_school_404(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    a = _create_school(v1_client, headers, code="SCHA01", name="A").json()["id"]
    b = _create_school(
        v1_client, headers, code="SCHB01", name="B", support_email="b@eschool.com"
    ).json()["id"]
    admin = v1_client.post(
        f"/api/v1/super-admin/schools/{a}/admins",
        headers=headers,
        json=_admin_body(),
    ).json()
    res = v1_client.get(
        f"/api/v1/super-admin/schools/{b}/admins/{admin['id']}", headers=headers
    )
    assert res.status_code == 404


def test_school_admin_forbidden_on_super_admin_routes(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers).json()["id"]
    v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=headers,
        json=_admin_body(),
    )
    login = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "school-admin@eschool.com", "password": "adminpass1"},
    )
    assert login.status_code == 200
    sa_headers = _auth_header(login.json()["access_token"])

    assert v1_client.get("/api/v1/super-admin/schools", headers=sa_headers).status_code == 403
    assert (
        v1_client.post(
            f"/api/v1/super-admin/schools/{school_id}/provision", headers=sa_headers
        ).status_code
        == 403
    )
    assert (
        v1_client.post(
            f"/api/v1/super-admin/schools/{school_id}/admins",
            headers=sa_headers,
            json=_admin_body(email="other@eschool.com"),
        ).status_code
        == 403
    )


# --- login / me / isolation ---


def test_school_admin_login_and_me(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers).json()["id"]
    v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=headers,
        json=_admin_body(),
    )

    login = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "school-admin@eschool.com", "password": "adminpass1"},
    )
    assert login.status_code == 200
    payload = login.json()
    assert payload["user"]["role"] == ROLE_SCHOOL_ADMIN
    assert payload["user"]["school_id"] == school_id
    assert "password" not in payload["user"]
    assert "password_hash" not in payload["user"]
    token = payload["access_token"]

    me = v1_client.get("/api/v1/auth/me", headers=_auth_header(token))
    assert me.status_code == 200
    assert me.json()["role"] == ROLE_SCHOOL_ADMIN
    assert me.json()["school_id"] == school_id

    sa_me = v1_client.get("/api/v1/school-admin/me", headers=_auth_header(token))
    assert sa_me.status_code == 200
    assert sa_me.json()["role"] == ROLE_SCHOOL_ADMIN
    assert sa_me.json()["school_id"] == school_id
    assert sa_me.json()["email"] == "school-admin@eschool.com"
    assert "password_hash" not in sa_me.json()


def test_inactive_school_admin_cannot_login(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers).json()["id"]
    admin = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=headers,
        json=_admin_body(),
    ).json()
    v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}/admins/{admin['id']}/status",
        headers=headers,
        json={"status": STATUS_INACTIVE},
    )
    login = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "school-admin@eschool.com", "password": "adminpass1"},
    )
    assert login.status_code == 403


def test_public_signup_cannot_become_school_admin(v1_client, v1_db):
    res = _signup(v1_client, email="public@eschool.com")
    assert res.status_code == 201
    assert res.json()["user"]["role"] == ROLE_USER
    assert res.json()["user"]["school_id"] is None
    user = v1_db.scalar(select(User).where(User.email == "public@eschool.com"))
    assert user is not None
    assert user.role == ROLE_USER


def test_tenant_isolation_school_a_vs_b(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_a = _create_school(
        v1_client, headers, code="ISOLA", name="School A", support_email="a@eschool.com"
    ).json()["id"]
    school_b = _create_school(
        v1_client, headers, code="ISOLB", name="School B", support_email="b@eschool.com"
    ).json()["id"]

    v1_client.post(
        f"/api/v1/super-admin/schools/{school_a}/admins",
        headers=headers,
        json=_admin_body(email="admin-a@eschool.com"),
    )
    v1_client.post(
        f"/api/v1/super-admin/schools/{school_b}/admins",
        headers=headers,
        json=_admin_body(email="admin-b@eschool.com", first_name="B"),
    )

    login_a = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "admin-a@eschool.com", "password": "adminpass1"},
    )
    assert login_a.status_code == 200
    token_a = _auth_header(login_a.json()["access_token"])

    own = v1_client.get(f"/api/v1/school-admin/schools/{school_a}", headers=token_a)
    assert own.status_code == 200
    assert own.json()["id"] == school_a

    other = v1_client.get(f"/api/v1/school-admin/schools/{school_b}", headers=token_a)
    assert other.status_code == 403

    # Super Admin can access both via super-admin routes
    assert (
        v1_client.get(f"/api/v1/super-admin/schools/{school_a}", headers=headers).status_code
        == 200
    )
    assert (
        v1_client.get(f"/api/v1/super-admin/schools/{school_b}", headers=headers).status_code
        == 200
    )


def test_school_admin_me_auth_gates(v1_client, v1_db):
    assert v1_client.get("/api/v1/school-admin/me").status_code == 401
    assert (
        v1_client.get(
            "/api/v1/school-admin/me", headers=_auth_header("bad-token")
        ).status_code
        == 401
    )
    user_token = _signup(v1_client, email="p3-me-user@eschool.com").json()["access_token"]
    assert (
        v1_client.get("/api/v1/school-admin/me", headers=_auth_header(user_token)).status_code
        == 403
    )
