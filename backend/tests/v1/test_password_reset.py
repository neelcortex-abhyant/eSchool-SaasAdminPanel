"""Forgot / reset password and School Admin invitations."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import hash_token
from app.models.tables import AuditLog
from app.models.v1.reset_token import PasswordResetToken
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.session import AuthSession
from app.models.v1.user import User

RESET_URL = "https://admin.example.test/login/reset"
FORGOT_MESSAGE = {"message": "If an account exists for that email, a reset link has been sent."}


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str):
    res = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "secret123", "first_name": "Reset", "last_name": "User"},
    )
    assert res.status_code == 201, res.text
    return res


def _super_admin_headers(client, v1_db, email: str = "reset-sa@eschool.com") -> dict[str, str]:
    _signup(client, email)
    user = v1_db.scalar(select(User).where(User.email == email))
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200, login.text
    return _auth_header(login.json()["access_token"])


class Outbox:
    def __init__(self):
        self.messages: list[dict] = []
        self.accept = True

    def send(self, to, subject, body):
        self.messages.append({"to": to, "subject": subject, "body": body})
        return self.accept

    def token(self, index: int = -1) -> str:
        match = re.search(r"token=([A-Za-z0-9_\-]+)", self.messages[index]["body"])
        assert match, self.messages[index]["body"]
        return match.group(1)


@pytest.fixture()
def outbox(v1_client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "smtp_from", "no-reply@example.test")
    monkeypatch.setattr(settings, "admin_reset_url", RESET_URL)
    box = Outbox()
    monkeypatch.setattr("app.services.v1.mailer.send_mail", box.send)
    return box


@pytest.fixture()
def no_mail(v1_client, monkeypatch):
    """Mail off regardless of the developer's .env."""
    monkeypatch.setattr(get_settings(), "smtp_host", "")


@pytest.fixture()
def school_admin(v1_client, v1_db):
    sa = _super_admin_headers(v1_client, v1_db)
    school = v1_client.post(
        "/api/v1/super-admin/schools",
        headers=sa,
        json={"name": "Reset School", "address": "1", "support_phone": "1", "support_email": "rs@eschool.com", "code": "RST01"},
    )
    assert school.status_code == 201, school.text
    school_id = school.json()["id"]
    created = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=sa,
        json={"email": "admin@reset.edu", "password": "oldpass123", "first_name": "Ria", "last_name": "Sen"},
    )
    assert created.status_code == 201, created.text
    return {"sa": sa, "school_id": school_id, "id": created.json()["id"], "email": "admin@reset.edu"}


def _forgot(client, email: str, **extra):
    return client.post("/api/v1/auth/forgot-password", json={"email": email, **extra})


def _reset(client, token: str, password: str = "freshpass9", confirm: str | None = None):
    return client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": password, "confirm_password": confirm or password},
    )


def _login(client, email: str, password: str):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def _tokens(v1_db) -> list[PasswordResetToken]:
    v1_db.expire_all()
    return list(v1_db.scalars(select(PasswordResetToken)))


def _audit(v1_db, action: str) -> list[AuditLog]:
    v1_db.expire_all()
    return list(v1_db.scalars(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)))


# --- forgot password ---


def test_forgot_same_response_for_every_email(v1_client, v1_db, outbox, school_admin):
    _signup(v1_client, "plain@reset.edu")  # role user: not eligible
    v1_client.patch(
        f"/api/v1/super-admin/schools/{school_admin['school_id']}/admins/{school_admin['id']}/status",
        headers=school_admin["sa"],
        json={"status": 0},
    )
    responses = [
        _forgot(v1_client, "nobody@reset.edu"),
        _forgot(v1_client, "plain@reset.edu"),
        _forgot(v1_client, school_admin["email"]),  # inactive
    ]
    for res in responses:
        assert res.status_code == 202
        assert res.json() == FORGOT_MESSAGE
    assert outbox.messages == []
    assert _tokens(v1_db) == []

    v1_client.patch(
        f"/api/v1/super-admin/schools/{school_admin['school_id']}/admins/{school_admin['id']}/status",
        headers=school_admin["sa"],
        json={"status": 1},
    )
    valid = _forgot(v1_client, "ADMIN@reset.edu")
    assert valid.status_code == 202
    assert valid.json() == FORGOT_MESSAGE
    assert [m["to"] for m in outbox.messages] == ["admin@reset.edu"]


def test_forgot_without_mail_configured_creates_nothing(v1_client, v1_db, no_mail, school_admin, monkeypatch):
    sent = []
    monkeypatch.setattr("app.services.v1.mailer.send_mail", lambda *a: sent.append(a) or True)
    res = _forgot(v1_client, school_admin["email"])
    assert res.status_code == 202 and res.json() == FORGOT_MESSAGE
    assert sent == [] and _tokens(v1_db) == []


def test_forgot_ignores_client_origin_and_stores_only_hash(v1_client, v1_db, outbox, school_admin):
    res = _forgot(v1_client, school_admin["email"], app_origin="https://evil.example")
    assert res.status_code == 202
    body = outbox.messages[0]["body"]
    assert "evil.example" not in body
    assert f"{RESET_URL}?token=" in body

    plain = outbox.token()
    rows = _tokens(v1_db)
    assert len(rows) == 1
    assert rows[0].token_hash == hash_token(plain)
    assert rows[0].purpose == "reset"
    assert plain not in rows[0].token_hash
    assert plain not in res.text


def test_forgot_for_super_admin(v1_client, v1_db, outbox):
    _super_admin_headers(v1_client, v1_db, "boss@reset.edu")
    _forgot(v1_client, "boss@reset.edu")
    assert [m["to"] for m in outbox.messages] == ["boss@reset.edu"]


def test_forgot_blocked_while_school_inactive(v1_client, v1_db, outbox, school_admin):
    v1_client.post(f"/api/v1/super-admin/schools/{school_admin['school_id']}/deactivate", headers=school_admin["sa"])
    assert _forgot(v1_client, school_admin["email"]).json() == FORGOT_MESSAGE
    assert outbox.messages == []


def test_new_request_invalidates_older_link(v1_client, outbox, school_admin):
    _forgot(v1_client, school_admin["email"])
    _forgot(v1_client, school_admin["email"])
    first, second = outbox.token(0), outbox.token(1)
    assert _reset(v1_client, first).status_code == 400
    assert _reset(v1_client, second).status_code == 200


# --- reset password ---


def test_reset_sets_password_revokes_sessions_and_audits(v1_client, v1_db, outbox, school_admin):
    old_login = _login(v1_client, school_admin["email"], "oldpass123")
    old_headers = _auth_header(old_login.json()["access_token"])
    _forgot(v1_client, school_admin["email"])
    plain = outbox.token()

    res = _reset(v1_client, plain)

    assert res.status_code == 200
    assert res.json() == {"message": "Password has been reset."}
    assert v1_client.get("/api/v1/auth/me", headers=old_headers).status_code == 401
    v1_db.expire_all()
    open_sessions = v1_db.scalar(
        select(func.count()).select_from(AuthSession).where(
            AuthSession.user_id == uuid.UUID(school_admin["id"]), AuthSession.revoked_at.is_(None)
        )
    )
    assert open_sessions == 0
    assert _login(v1_client, school_admin["email"], "oldpass123").status_code == 401
    assert _login(v1_client, school_admin["email"], "freshpass9").status_code == 200
    assert _tokens(v1_db)[0].used_at is not None

    rows = _audit(v1_db, "auth.password_reset")
    assert len(rows) == 1
    assert rows[0].entity_id == school_admin["id"]
    assert rows[0].school_id == school_admin["school_id"]
    assert json.loads(rows[0].metadata_json) == {"purpose": "reset", "sessions_revoked": 1}
    assert plain not in (rows[0].metadata_json or "")
    assert "freshpass9" not in (rows[0].metadata_json or "")


def test_reset_token_is_single_use(v1_client, outbox, school_admin):
    _forgot(v1_client, school_admin["email"])
    plain = outbox.token()
    assert _reset(v1_client, plain).status_code == 200
    again = _reset(v1_client, plain, "another99")
    assert again.status_code == 400
    assert again.json() == {"detail": "Invalid or expired reset link."}


@pytest.mark.parametrize("token", ["not-a-real-token", "x" * 200])
def test_reset_rejects_unknown_token(v1_client, outbox, school_admin, token):
    _forgot(v1_client, school_admin["email"])
    res = _reset(v1_client, token)
    assert res.status_code == 400
    assert res.json() == {"detail": "Invalid or expired reset link."}


def test_reset_rejects_expired_token(v1_client, v1_db, outbox, school_admin):
    _forgot(v1_client, school_admin["email"])
    row = _tokens(v1_db)[0]
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    v1_db.commit()
    assert _reset(v1_client, outbox.token()).status_code == 400
    assert _login(v1_client, school_admin["email"], "oldpass123").status_code == 200


def test_reset_rejected_after_deactivation(v1_client, outbox, school_admin):
    _forgot(v1_client, school_admin["email"])
    v1_client.patch(
        f"/api/v1/super-admin/schools/{school_admin['school_id']}/admins/{school_admin['id']}/status",
        headers=school_admin["sa"],
        json={"status": 0},
    )
    assert _reset(v1_client, outbox.token()).status_code == 400


@pytest.mark.parametrize(
    "password,confirm",
    [("freshpass9", "different9"), ("short", "short")],
)
def test_reset_validation_422(v1_client, outbox, school_admin, password, confirm):
    _forgot(v1_client, school_admin["email"])
    res = _reset(v1_client, outbox.token(), password, confirm)
    assert res.status_code == 422
    assert _reset(v1_client, outbox.token()).status_code == 200  # token not consumed by the failed try


def test_reset_rejects_extra_fields(v1_client):
    res = v1_client.post(
        "/api/v1/auth/reset-password",
        json={"token": "t", "new_password": "freshpass9", "confirm_password": "freshpass9", "email": "a@b.c"},
    )
    assert res.status_code == 422


# --- invitations ---


def _invite_create(client, school_admin, email="invited@reset.edu", **extra):
    return client.post(
        f"/api/v1/super-admin/schools/{school_admin['school_id']}/admins",
        headers=school_admin["sa"],
        json={"email": email, "first_name": "Ina", "last_name": "Vite", **extra},
    )


def test_create_without_password_sends_setup_link(v1_client, v1_db, outbox, school_admin):
    res = _invite_create(v1_client, school_admin)

    assert res.status_code == 201, res.text
    assert res.json()["invite_sent"] is True
    assert [m["to"] for m in outbox.messages] == ["invited@reset.edu"]
    plain = outbox.token()
    assert plain not in res.text
    setup = [t for t in _tokens(v1_db) if t.purpose == "setup"]
    assert len(setup) == 1 and setup[0].token_hash == hash_token(plain)

    assert _reset(v1_client, plain, "chosenpass1").status_code == 200
    assert _login(v1_client, "invited@reset.edu", "chosenpass1").status_code == 200
    assert json.loads(_audit(v1_db, "auth.password_reset")[-1].metadata_json)["purpose"] == "setup"
    assert json.loads(_audit(v1_db, "school_admin.invite")[-1].metadata_json) == {"invite_sent": True}
    assert json.loads(_audit(v1_db, "school_admin.create")[-1].metadata_json)["invitation"] is True


def test_create_without_password_reports_unsent_when_mail_off(v1_client, v1_db, no_mail, school_admin, monkeypatch):
    monkeypatch.setattr("app.services.v1.mailer.send_mail", lambda *a: pytest.fail("must not send"))
    res = _invite_create(v1_client, school_admin)

    assert res.status_code == 201, res.text
    assert res.json()["invite_sent"] is False
    assert [t for t in _tokens(v1_db) if t.purpose == "setup"] == []
    assert json.loads(_audit(v1_db, "school_admin.invite")[-1].metadata_json) == {"invite_sent": False}


def test_create_reports_unsent_when_delivery_fails(v1_client, v1_db, outbox, school_admin):
    outbox.accept = False
    res = _invite_create(v1_client, school_admin)
    assert res.status_code == 201
    assert res.json()["invite_sent"] is False
    assert json.loads(_audit(v1_db, "school_admin.invite")[-1].metadata_json) == {"invite_sent": False}


def test_inactive_admin_gets_no_invitation(v1_client, v1_db, outbox, school_admin):
    res = _invite_create(v1_client, school_admin, status=0)
    assert res.status_code == 201
    assert res.json()["invite_sent"] is False
    assert outbox.messages == []

    resend = v1_client.post(
        f"/api/v1/super-admin/schools/{school_admin['school_id']}/admins/{res.json()['id']}/invite",
        headers=school_admin["sa"],
    )
    assert resend.status_code == 422


def test_resend_invite_replaces_old_link(v1_client, outbox, school_admin):
    created = _invite_create(v1_client, school_admin).json()
    first = outbox.token()
    url = f"/api/v1/super-admin/schools/{school_admin['school_id']}/admins/{created['id']}/invite"

    resend = v1_client.post(url, headers=school_admin["sa"])

    assert resend.status_code == 200, resend.text
    assert resend.json()["invite_sent"] is True
    second = outbox.token()
    assert first != second
    assert _reset(v1_client, first).status_code == 400
    assert _reset(v1_client, second).status_code == 200


def test_resend_invite_requires_super_admin(v1_client, outbox, school_admin):
    url = f"/api/v1/super-admin/schools/{school_admin['school_id']}/admins/{school_admin['id']}/invite"
    admin_headers = _auth_header(_login(v1_client, school_admin["email"], "oldpass123").json()["access_token"])
    assert v1_client.post(url).status_code == 401
    assert v1_client.post(url, headers=admin_headers).status_code == 403
    other = v1_client.post(
        f"/api/v1/super-admin/schools/999999/admins/{school_admin['id']}/invite", headers=school_admin["sa"]
    )
    assert other.status_code == 404
    assert outbox.messages == []


# --- School Admin change password (/api/v1/auth/change-password) ---


def _change(client, headers, current: str, new: str, confirm: str | None = None):
    return client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": current,
            "new_password": new,
            "confirm_password": confirm if confirm is not None else new,
        },
    )


def test_school_admin_change_password_success_and_login(v1_client, v1_db, school_admin):
    login = _login(v1_client, school_admin["email"], "oldpass123")
    assert login.status_code == 200
    headers = _auth_header(login.json()["access_token"])
    other = _auth_header(_login(v1_client, school_admin["email"], "oldpass123").json()["access_token"])

    res = _change(v1_client, headers, "oldpass123", "brandnew99")
    assert res.status_code == 200, res.text
    assert res.json() == {"message": "Password changed."}

    # Current session remains usable; other sessions are revoked (existing strategy).
    assert v1_client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert v1_client.get("/api/v1/auth/me", headers=other).status_code == 401
    assert _login(v1_client, school_admin["email"], "oldpass123").status_code == 401
    assert _login(v1_client, school_admin["email"], "brandnew99").status_code == 200

    rows = _audit(v1_db, "auth.password_change")
    assert rows and rows[-1].entity_id == school_admin["id"]
    assert rows[-1].school_id == school_admin["school_id"]
    for secret in ("oldpass123", "brandnew99"):
        assert secret not in (rows[-1].metadata_json or "")


def test_school_admin_change_password_rejects_wrong_current_and_unchanged(v1_client, school_admin):
    headers = _auth_header(_login(v1_client, school_admin["email"], "oldpass123").json()["access_token"])

    wrong = _change(v1_client, headers, "not-the-password", "brandnew99")
    assert wrong.status_code == 400
    assert wrong.json()["detail"] == "Current password is incorrect."

    same = _change(v1_client, headers, "oldpass123", "oldpass123")
    assert same.status_code == 422
    assert same.json()["detail"] == "Choose a different password."

    mismatch = _change(v1_client, headers, "oldpass123", "brandnew99", "otherpass9")
    assert mismatch.status_code == 422

    short = _change(v1_client, headers, "oldpass123", "short")
    assert short.status_code == 422

    # Password unchanged after failed attempts.
    assert _login(v1_client, school_admin["email"], "oldpass123").status_code == 200


def test_change_password_requires_authentication(v1_client, school_admin):
    res = v1_client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": "oldpass123",
            "new_password": "brandnew99",
            "confirm_password": "brandnew99",
        },
    )
    assert res.status_code == 401


def test_forgot_still_generic_when_mail_send_fails(v1_client, v1_db, outbox, school_admin):
    outbox.accept = False
    res = _forgot(v1_client, school_admin["email"])
    assert res.status_code == 202
    assert res.json() == FORGOT_MESSAGE
    # Token was committed before send; plaintext never appears in the API body.
    assert _tokens(v1_db)
    assert outbox.token() not in res.text
