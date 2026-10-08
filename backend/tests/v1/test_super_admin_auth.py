from __future__ import annotations

from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.v1.roles import ROLE_SUPER_ADMIN, ROLE_USER
from app.models.v1.user import User
from app.services.v1 import auth_service


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, **overrides):
    body = {
        "email": "user@eschool.com",
        "password": "secret123",
        "first_name": "Normal",
        "last_name": "User",
        "mobile": "9000000001",
        **overrides,
    }
    return client.post("/api/v1/auth/signup", json=body)


def _promote_super_admin(v1_db, email: str) -> User:
    user = v1_db.scalar(select(User).where(User.email == email.lower()))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    v1_db.refresh(user)
    return user


# --- role on signup / me ---


def test_signup_always_assigns_role_user(v1_client):
    res = _signup(v1_client)
    assert res.status_code == 201
    assert res.json()["user"]["role"] == ROLE_USER


def test_signup_rejects_client_supplied_role(v1_client):
    res = v1_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "attacker@eschool.com",
            "password": "secret123",
            "first_name": "Bad",
            "last_name": "Actor",
            "role": ROLE_SUPER_ADMIN,
        },
    )
    assert res.status_code == 422


def test_auth_me_and_users_me_expose_role(v1_client):
    token = _signup(v1_client).json()["access_token"]
    headers = _auth_header(token)
    me = v1_client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role"] == ROLE_USER
    users_me = v1_client.get("/api/v1/users/me", headers=headers)
    assert users_me.status_code == 200
    assert users_me.json()["role"] == ROLE_USER


# --- /super-admin/ping auth matrix ---


def test_super_admin_ping_unauthenticated_401(v1_client):
    res = v1_client.get("/api/v1/super-admin/ping")
    assert res.status_code == 401
    assert res.json()["detail"] == "Not authenticated"


def test_super_admin_ping_invalid_token_401(v1_client):
    res = v1_client.get("/api/v1/super-admin/ping", headers=_auth_header("bogus-token"))
    assert res.status_code == 401


def test_super_admin_ping_normal_user_403(v1_client):
    token = _signup(v1_client).json()["access_token"]
    res = v1_client.get("/api/v1/super-admin/ping", headers=_auth_header(token))
    assert res.status_code == 403
    assert res.json()["detail"] == "Forbidden"


def test_super_admin_ping_super_admin_200(v1_client, v1_db):
    signup = _signup(v1_client, email="sa@eschool.com")
    assert signup.status_code == 201
    assert signup.json()["user"]["role"] == ROLE_USER
    _promote_super_admin(v1_db, "sa@eschool.com")

    login = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "sa@eschool.com", "password": "secret123"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == ROLE_SUPER_ADMIN

    res = v1_client.get(
        "/api/v1/super-admin/ping",
        headers=_auth_header(login.json()["access_token"]),
    )
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "role": ROLE_SUPER_ADMIN}


# --- bootstrap ---


def test_bootstrap_promotes_configured_email(v1_client, v1_db, monkeypatch):
    email = "bootstrap-sa@eschool.com"
    assert _signup(v1_client, email=email).status_code == 201
    user = v1_db.scalar(select(User).where(User.email == email))
    assert user is not None
    assert user.role == ROLE_USER

    monkeypatch.setenv("V1_SUPER_ADMIN_EMAIL", email)
    get_settings.cache_clear()

    promoted = auth_service.bootstrap_super_admin(v1_db)
    assert promoted is not None
    assert promoted.role == ROLE_SUPER_ADMIN

    get_settings.cache_clear()


def test_bootstrap_noop_when_email_unset(v1_client, v1_db, monkeypatch):
    monkeypatch.delenv("V1_SUPER_ADMIN_EMAIL", raising=False)
    get_settings.cache_clear()
    assert auth_service.bootstrap_super_admin(v1_db) is None
    get_settings.cache_clear()


def test_bootstrap_noop_when_user_missing(v1_db, monkeypatch):
    monkeypatch.setenv("V1_SUPER_ADMIN_EMAIL", "missing@eschool.com")
    get_settings.cache_clear()
    assert auth_service.bootstrap_super_admin(v1_db) is None
    get_settings.cache_clear()


def test_bootstrap_does_not_create_user(v1_db, monkeypatch):
    monkeypatch.setenv("V1_SUPER_ADMIN_EMAIL", "brand-new@eschool.com")
    get_settings.cache_clear()
    assert auth_service.bootstrap_super_admin(v1_db) is None
    assert v1_db.scalar(select(User).where(User.email == "brand-new@eschool.com")) is None
    get_settings.cache_clear()


def test_v1_users_role_column_exists(v1_client, v1_db):
    row = v1_db.execute(
        text(
            "SELECT column_name, data_type, column_default "
            "FROM information_schema.columns "
            "WHERE table_name = 'v1_users' AND column_name = 'role'"
        )
    ).one()
    assert row[0] == "role"
    assert "character varying" in row[1]


def test_hash_password_still_used_for_manual_super_admin(v1_db):
    # Sanity: promoting role does not involve plaintext password storage.
    user = User(
        email="manual-sa@eschool.com",
        password_hash=hash_password("secret123"),
        first_name="Manual",
        last_name="SA",
        role=ROLE_SUPER_ADMIN,
    )
    v1_db.add(user)
    v1_db.commit()
    stored = v1_db.scalar(select(User).where(User.email == "manual-sa@eschool.com"))
    assert stored is not None
    assert stored.password_hash.startswith("$2")
    assert stored.role == ROLE_SUPER_ADMIN
