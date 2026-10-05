from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import hash_token
from app.models.v1.session import AuthSession
from app.models.v1.user import User


SIGNUP = {
    "email": "amit@school.com",
    "password": "secret123",
    "first_name": "Amit",
    "last_name": "Sharma",
    "mobile": "9876543210",
}


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, **overrides):
    body = {**SIGNUP, **overrides}
    return client.post("/api/v1/auth/signup", json=body)


# --- SIGNUP ---


def test_signup_valid(v1_client):
    res = _signup(v1_client)
    assert res.status_code == 201
    data = res.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["expires_at"]
    assert data["user"]["email"] == "amit@school.com"
    assert data["user"]["first_name"] == "Amit"
    assert data["user"]["last_name"] == "Sharma"
    assert data["user"]["mobile"] == "9876543210"
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]


def test_signup_duplicate_email(v1_client):
    assert _signup(v1_client).status_code == 201
    res = _signup(v1_client)
    assert res.status_code == 409
    assert res.json()["detail"] == "Email already registered"


def test_signup_invalid_email(v1_client):
    res = _signup(v1_client, email="not-an-email")
    assert res.status_code == 422


def test_signup_short_password(v1_client):
    res = _signup(v1_client, password="short")
    assert res.status_code == 422


# --- LOGIN ---


def test_login_correct(v1_client):
    _signup(v1_client)
    res = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "amit@school.com", "password": "secret123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "amit@school.com"


def test_login_wrong_password(v1_client):
    _signup(v1_client)
    res = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "amit@school.com", "password": "wrongpass"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password"


def test_login_unknown_email(v1_client):
    res = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@school.com", "password": "secret123"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password"


def test_login_returns_bearer_token(v1_client):
    _signup(v1_client)
    res = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "amit@school.com", "password": "secret123"},
    )
    assert res.status_code == 200
    assert res.json()["access_token"]
    assert res.json()["token_type"] == "bearer"


# --- AUTH ME ---


def test_auth_me_valid_token(v1_client):
    token = _signup(v1_client).json()["access_token"]
    res = v1_client.get("/api/v1/auth/me", headers=_auth_header(token))
    assert res.status_code == 200
    assert res.json()["email"] == "amit@school.com"


def test_auth_me_missing_token(v1_client):
    res = v1_client.get("/api/v1/auth/me")
    assert res.status_code == 401


def test_auth_me_invalid_token(v1_client):
    res = v1_client.get("/api/v1/auth/me", headers=_auth_header("not-a-real-token"))
    assert res.status_code == 401


def test_auth_me_revoked_token(v1_client):
    token = _signup(v1_client).json()["access_token"]
    assert v1_client.post("/api/v1/auth/logout", headers=_auth_header(token)).status_code == 204
    res = v1_client.get("/api/v1/auth/me", headers=_auth_header(token))
    assert res.status_code == 401


def test_auth_me_expired_session(v1_client, v1_db):
    token = _signup(v1_client).json()["access_token"]
    session = v1_db.scalar(select(AuthSession))
    assert session is not None
    session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    v1_db.commit()

    res = v1_client.get("/api/v1/auth/me", headers=_auth_header(token))
    assert res.status_code == 401


# --- USERS ME ---


def test_users_me_valid_token(v1_client):
    token = _signup(v1_client).json()["access_token"]
    res = v1_client.get("/api/v1/users/me", headers=_auth_header(token))
    assert res.status_code == 200
    assert res.json()["email"] == "amit@school.com"


def test_users_me_without_token(v1_client):
    res = v1_client.get("/api/v1/users/me")
    assert res.status_code == 401


def test_patch_first_name(v1_client):
    token = _signup(v1_client).json()["access_token"]
    res = v1_client.patch(
        "/api/v1/users/me",
        headers=_auth_header(token),
        json={"first_name": "Amita"},
    )
    assert res.status_code == 200
    assert res.json()["first_name"] == "Amita"
    assert res.json()["last_name"] == "Sharma"


def test_patch_last_name(v1_client):
    token = _signup(v1_client).json()["access_token"]
    res = v1_client.patch(
        "/api/v1/users/me",
        headers=_auth_header(token),
        json={"last_name": "Verma"},
    )
    assert res.status_code == 200
    assert res.json()["last_name"] == "Verma"
    assert res.json()["first_name"] == "Amit"


def test_patch_mobile(v1_client):
    token = _signup(v1_client).json()["access_token"]
    res = v1_client.patch(
        "/api/v1/users/me",
        headers=_auth_header(token),
        json={"mobile": "9000000000"},
    )
    assert res.status_code == 200
    assert res.json()["mobile"] == "9000000000"


def test_patch_email_cannot_be_changed(v1_client, v1_db):
    signup = _signup(v1_client).json()
    token = signup["access_token"]
    res = v1_client.patch(
        "/api/v1/users/me",
        headers=_auth_header(token),
        json={"email": "other@school.com", "first_name": "X"},
    )
    assert res.status_code == 422

    user = v1_db.scalar(select(User).where(User.email == "amit@school.com"))
    assert user is not None
    assert user.email == "amit@school.com"
    assert v1_db.scalar(select(User).where(User.email == "other@school.com")) is None


def test_patch_rejects_password_field(v1_client):
    token = _signup(v1_client).json()["access_token"]
    res = v1_client.patch(
        "/api/v1/users/me",
        headers=_auth_header(token),
        json={"password": "newsecret1", "first_name": "X"},
    )
    assert res.status_code == 422


# --- LOGOUT ---


def test_logout_valid_token(v1_client):
    token = _signup(v1_client).json()["access_token"]
    res = v1_client.post("/api/v1/auth/logout", headers=_auth_header(token))
    assert res.status_code == 204


def test_logout_then_token_rejected(v1_client):
    token = _signup(v1_client).json()["access_token"]
    assert v1_client.post("/api/v1/auth/logout", headers=_auth_header(token)).status_code == 204
    assert v1_client.get("/api/v1/auth/me", headers=_auth_header(token)).status_code == 401
    assert v1_client.get("/api/v1/users/me", headers=_auth_header(token)).status_code == 401


# --- SESSION SECURITY ---


def test_plaintext_token_not_stored(v1_client, v1_db):
    token = _signup(v1_client).json()["access_token"]
    sessions = list(v1_db.scalars(select(AuthSession)).all())
    assert len(sessions) == 1
    stored = sessions[0].token_hash
    assert stored != token
    assert stored == hash_token(token)
    assert len(stored) == 64
    assert all(c in "0123456789abcdef" for c in stored)


def test_password_not_plaintext_uses_bcrypt(v1_client, v1_db):
    plain = "secret123"
    _signup(v1_client, password=plain)
    user = v1_db.scalar(select(User).where(User.email == "amit@school.com"))
    assert user is not None
    assert user.password_hash != plain
    assert user.password_hash.startswith("$2")
    # bcrypt hashes are typically 60 chars
    assert len(user.password_hash) >= 50


def test_session_expiry_enforced(v1_client, v1_db):
    token = _signup(v1_client).json()["access_token"]
    session = v1_db.scalar(select(AuthSession))
    assert session is not None
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    assert expires > datetime.now(timezone.utc)
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    v1_db.commit()
    assert v1_client.get("/api/v1/auth/me", headers=_auth_header(token)).status_code == 401


def test_logout_revokes_server_side(v1_client, v1_db):
    token = _signup(v1_client).json()["access_token"]
    assert v1_client.post("/api/v1/auth/logout", headers=_auth_header(token)).status_code == 204
    v1_db.expire_all()
    session = v1_db.scalar(select(AuthSession))
    assert session is not None
    assert session.revoked_at is not None
    assert v1_client.get("/api/v1/auth/me", headers=_auth_header(token)).status_code == 401


def test_me_returns_only_own_user(v1_client):
    a = _signup(v1_client).json()
    b = _signup(v1_client, email="bhavya@school.com", first_name="Bhavya").json()

    res_a = v1_client.get("/api/v1/users/me", headers=_auth_header(a["access_token"]))
    res_b = v1_client.get("/api/v1/users/me", headers=_auth_header(b["access_token"]))
    assert res_a.status_code == 200
    assert res_b.status_code == 200
    assert res_a.json()["id"] == a["user"]["id"]
    assert res_b.json()["id"] == b["user"]["id"]
    assert res_a.json()["id"] != res_b.json()["id"]


def test_legacy_student_login_route_still_mounted(v1_client):
    paths = {route.path for route in v1_client.app.routes}
    assert "/api/student/login" in paths
    assert "/api/v1/auth/signup" in paths
