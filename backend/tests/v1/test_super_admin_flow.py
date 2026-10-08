from __future__ import annotations

from app.models.v1.roles import ROLE_SUPER_ADMIN, ROLE_USER


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_body(**overrides):
    body = {
        "email": "first-sa@eschool.com",
        "password": "secret123",
        "first_name": "Super",
        "last_name": "Admin",
        "mobile": "9000000099",
        **overrides,
    }
    return body


def test_super_admin_register_first_user(v1_client):
    res = v1_client.post("/api/v1/super-admin/register", json=_register_body())
    assert res.status_code == 201
    data = res.json()
    assert data["access_token"]
    assert data["user"]["role"] == ROLE_SUPER_ADMIN
    assert data["user"]["email"] == "first-sa@eschool.com"


def test_super_admin_register_second_blocked_without_env(v1_client, monkeypatch):
    monkeypatch.delenv("V1_SUPER_ADMIN_EMAIL", raising=False)
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert v1_client.post("/api/v1/super-admin/register", json=_register_body()).status_code == 201
    res = v1_client.post(
        "/api/v1/super-admin/register",
        json=_register_body(email="second-sa@eschool.com"),
    )
    assert res.status_code == 403
    get_settings.cache_clear()


def test_super_admin_login_requires_role(v1_client):
    # Normal signup user cannot use SA login
    signup = v1_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "plain@eschool.com",
            "password": "secret123",
            "first_name": "Plain",
            "last_name": "User",
        },
    )
    assert signup.status_code == 201
    denied = v1_client.post(
        "/api/v1/super-admin/login",
        json={"email": "plain@eschool.com", "password": "secret123"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Forbidden"

    sa = v1_client.post("/api/v1/super-admin/register", json=_register_body(email="login-sa@eschool.com"))
    assert sa.status_code == 201
    ok = v1_client.post(
        "/api/v1/super-admin/login",
        json={"email": "login-sa@eschool.com", "password": "secret123"},
    )
    assert ok.status_code == 200
    assert ok.json()["user"]["role"] == ROLE_SUPER_ADMIN


def test_super_admin_login_bad_password_401(v1_client):
    assert v1_client.post("/api/v1/super-admin/register", json=_register_body(email="badpw@eschool.com")).status_code == 201
    res = v1_client.post(
        "/api/v1/super-admin/login",
        json={"email": "badpw@eschool.com", "password": "wrong-password"},
    )
    assert res.status_code == 401


def test_super_admin_me_and_dashboard(v1_client):
    reg = v1_client.post("/api/v1/super-admin/register", json=_register_body(email="dash-sa@eschool.com"))
    token = reg.json()["access_token"]
    headers = _auth_header(token)

    me = v1_client.get("/api/v1/super-admin/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role"] == ROLE_SUPER_ADMIN
    assert me.json()["email"] == "dash-sa@eschool.com"

    # Normal user blocked from SA me
    user_token = v1_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "dash-user@eschool.com",
            "password": "secret123",
            "first_name": "U",
            "last_name": "Ser",
        },
    ).json()["access_token"]
    assert v1_client.get("/api/v1/super-admin/me", headers=_auth_header(user_token)).status_code == 403

    dash = v1_client.get("/api/v1/super-admin/dashboard", headers=headers)
    assert dash.status_code == 200
    body = dash.json()
    for key in ("schools", "schools_active", "packages", "packages_active", "super_admins"):
        assert key in body
        assert isinstance(body[key], int)
    assert body["super_admins"] >= 1

    assert v1_client.get("/api/v1/super-admin/dashboard", headers=_auth_header(user_token)).status_code == 403


def test_generic_auth_me_still_works_for_super_admin(v1_client):
    token = v1_client.post(
        "/api/v1/super-admin/register",
        json=_register_body(email="reuse-me@eschool.com"),
    ).json()["access_token"]
    headers = _auth_header(token)
    assert v1_client.get("/api/v1/auth/me", headers=headers).json()["role"] == ROLE_SUPER_ADMIN
    assert v1_client.get("/api/v1/users/me", headers=headers).json()["role"] == ROLE_SUPER_ADMIN
    # role must never be user after SA register
    assert v1_client.get("/api/v1/auth/me", headers=headers).json()["role"] != ROLE_USER
