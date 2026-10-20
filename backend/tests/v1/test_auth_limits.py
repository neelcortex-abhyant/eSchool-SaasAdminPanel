"""Rate limits on sensitive auth endpoints, equal-time login failures, password-change audit."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.core import rate_limit
from app.models.tables import AuditLog
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User
from app.services.v1 import auth_service

TOO_MANY = {"detail": "Too many attempts. Try again later."}


def _signup(client, email: str, password: str = "secret123"):
    res = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "first_name": "Lim", "last_name": "It"},
    )
    assert res.status_code == 201, res.text
    return res


def _login(client, email: str, password: str, path: str = "/api/v1/auth/login"):
    return client.post(path, json={"email": email, "password": password})


@pytest.mark.parametrize("path", ["/api/v1/auth/login", "/api/v1/super-admin/login"])
def test_failed_logins_per_email_return_429(v1_client, path):
    _signup(v1_client, "victim@limits.edu")
    for _ in range(rate_limit.LOGIN_PER_EMAIL.limit):
        assert _login(v1_client, "victim@limits.edu", "wrongpass", path).status_code == 401

    blocked = _login(v1_client, "VICTIM@limits.edu", "wrongpass", path)
    assert blocked.status_code == 429
    assert blocked.json() == TOO_MANY
    assert int(blocked.headers["Retry-After"]) > 0
    # Even the right password waits until the window passes.
    assert _login(v1_client, "victim@limits.edu", "secret123", path).status_code == 429


def test_unknown_email_is_limited_like_a_real_one(v1_client):
    for _ in range(rate_limit.LOGIN_PER_EMAIL.limit):
        assert _login(v1_client, "ghost@limits.edu", "wrongpass").status_code == 401
    assert _login(v1_client, "ghost@limits.edu", "wrongpass").status_code == 429


def test_shared_limit_across_login_endpoints(v1_client):
    _signup(v1_client, "both@limits.edu")
    half = rate_limit.LOGIN_PER_EMAIL.limit // 2
    for _ in range(half):
        _login(v1_client, "both@limits.edu", "wrongpass")
    for _ in range(rate_limit.LOGIN_PER_EMAIL.limit - half):
        _login(v1_client, "both@limits.edu", "wrongpass", "/api/v1/super-admin/login")
    assert _login(v1_client, "both@limits.edu", "wrongpass").status_code == 429


def test_successful_logins_are_not_counted_and_clear_failures(v1_client):
    _signup(v1_client, "regular@limits.edu")
    for _ in range(rate_limit.LOGIN_PER_EMAIL.limit - 1):
        _login(v1_client, "regular@limits.edu", "wrongpass")
    assert _login(v1_client, "regular@limits.edu", "secret123").status_code == 200
    for _ in range(rate_limit.LOGIN_PER_EMAIL.limit + 5):
        assert _login(v1_client, "regular@limits.edu", "secret123").status_code == 200


def test_other_emails_unaffected_until_ip_limit(v1_client):
    _signup(v1_client, "bystander@limits.edu")
    for _ in range(rate_limit.LOGIN_PER_EMAIL.limit):
        _login(v1_client, "target@limits.edu", "wrongpass")
    assert _login(v1_client, "bystander@limits.edu", "secret123").status_code == 200


def test_ip_limit_across_many_emails(v1_client):
    for i in range(rate_limit.LOGIN_PER_IP.limit):
        assert _login(v1_client, f"spray{i}@limits.edu", "wrongpass").status_code == 401
    assert _login(v1_client, "fresh@limits.edu", "wrongpass").status_code == 429


def test_forgot_password_limit_same_for_any_email(v1_client):
    for email in ("nobody@limits.edu",):
        for _ in range(rate_limit.FORGOT_PER_EMAIL.limit):
            assert v1_client.post("/api/v1/auth/forgot-password", json={"email": email}).status_code == 202
        res = v1_client.post("/api/v1/auth/forgot-password", json={"email": email})
        assert res.status_code == 429
        assert res.json() == TOO_MANY


def test_reset_password_limit_per_ip(v1_client):
    body = {"token": "guess", "new_password": "freshpass9", "confirm_password": "freshpass9"}
    for _ in range(rate_limit.RESET_PER_IP.limit):
        assert v1_client.post("/api/v1/auth/reset-password", json=body).status_code == 400
    assert v1_client.post("/api/v1/auth/reset-password", json=body).status_code == 429


def test_unknown_email_still_runs_bcrypt(v1_client, monkeypatch):
    checked = []
    real = auth_service.verify_password

    def spy(password, password_hash):
        checked.append(password_hash)
        return real(password, password_hash)

    monkeypatch.setattr(auth_service, "verify_password", spy)
    assert _login(v1_client, "nobody-at-all@limits.edu", "whatever1").status_code == 401
    assert len(checked) == 1 and checked[0].startswith("$2")


def test_change_password_is_audited_without_secrets(v1_client, v1_db):
    token = _signup(v1_client, "changer@limits.edu").json()["access_token"]
    other = _login(v1_client, "changer@limits.edu", "secret123").json()["access_token"]

    res = v1_client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "secret123", "new_password": "newsecret9", "confirm_password": "newsecret9"},
    )
    assert res.status_code == 200, res.text

    v1_db.expire_all()
    user = v1_db.scalar(select(User).where(User.email == "changer@limits.edu"))
    rows = list(v1_db.scalars(select(AuditLog).where(AuditLog.action == "auth.password_change")))
    assert len(rows) == 1
    assert rows[0].entity_id == str(user.id) and rows[0].actor_id == str(user.id)
    assert json.loads(rows[0].metadata_json) == {"other_sessions_revoked": 1}
    for secret in ("secret123", "newsecret9", token, other):
        assert secret not in (rows[0].metadata_json or "")
    assert v1_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {other}"}).status_code == 401


def test_super_admin_login_still_works(v1_client, v1_db):
    _signup(v1_client, "boss@limits.edu")
    user = v1_db.scalar(select(User).where(User.email == "boss@limits.edu"))
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    assert _login(v1_client, "boss@limits.edu", "secret123", "/api/v1/super-admin/login").status_code == 200
    assert _login(v1_client, "nobody@limits.edu", "secret123", "/api/v1/super-admin/login").status_code == 401
