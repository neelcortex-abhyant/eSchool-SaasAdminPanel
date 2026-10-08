"""Phase 8: Super Admin settings, audit logs, notifications."""

from __future__ import annotations

from sqlalchemy import select

from app.models.tables import AuditLog
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str = "p8-user@eschool.com", **overrides):
    body = {
        "email": email,
        "password": "secret123",
        "first_name": "Phase",
        "last_name": "Eight",
        **overrides,
    }
    return client.post("/api/v1/auth/signup", json=body)


def _sa(client, v1_db, email: str = "p8-sa@eschool.com") -> dict[str, str]:
    assert _signup(client, email=email).status_code == 201
    user = v1_db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200
    return _auth_header(login.json()["access_token"]), str(user.id), email


def test_settings_auth_and_secret_protection(v1_client, v1_db):
    assert v1_client.get("/api/v1/super-admin/settings").status_code == 401
    token = _signup(v1_client).json()["access_token"]
    assert (
        v1_client.get("/api/v1/super-admin/settings", headers=_auth_header(token)).status_code
        == 403
    )

    headers, actor_id, email = _sa(v1_client, v1_db)
    got = v1_client.get("/api/v1/super-admin/settings", headers=headers)
    assert got.status_code == 200
    settings = got.json()["settings"]
    assert "app_name" in settings
    assert "smtp_password" in settings
    assert settings["smtp_password"]["secret"] is True
    assert settings["smtp_password"]["value"] is None

    patched = v1_client.patch(
        "/api/v1/super-admin/settings",
        headers=headers,
        json={
            "settings": {
                "app_name": "eSchool SaaS",
                "smtp_password": "super-secret-password",
            }
        },
    )
    assert patched.status_code == 200
    assert patched.json()["settings"]["app_name"]["value"] == "eSchool SaaS"
    assert patched.json()["settings"]["smtp_password"]["value"] is None
    assert patched.json()["settings"]["smtp_password"]["configured"] is True
    assert "smtp_password" in patched.json()["updated_keys"]

    again = v1_client.get("/api/v1/super-admin/settings", headers=headers).json()
    assert again["settings"]["smtp_password"]["value"] is None
    assert again["settings"]["smtp_password"]["configured"] is True


def test_audit_log_from_school_create(v1_client, v1_db):
    headers, actor_id, email = _sa(v1_client, v1_db)
    school = v1_client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": "Audit School", "code": "AUD01"},
    ).json()

    logs = v1_client.get("/api/v1/super-admin/audit-logs", headers=headers)
    assert logs.status_code == 200
    assert logs.json()["total"] >= 1
    item = next(i for i in logs.json()["items"] if i["action"] == "school.create")
    assert item["actor_id"] == actor_id
    assert item["actor_email"] == email
    assert item["entity_type"] == "school"
    assert item["entity_id"] == str(school["id"])
    assert item["school_id"] == school["id"]
    assert "password" not in str(item["metadata"]).lower()
    assert "secret" not in item["metadata"]

    row = v1_db.scalar(select(AuditLog).where(AuditLog.action == "school.create"))
    assert row is not None
    assert row.actor_id == actor_id


def test_settings_audit_redacts_secrets(v1_client, v1_db):
    headers, actor_id, _email = _sa(v1_client, v1_db)
    v1_client.patch(
        "/api/v1/super-admin/settings",
        headers=headers,
        json={"settings": {"smtp_password": "do-not-log-this", "currency": "INR"}},
    )
    logs = v1_client.get(
        "/api/v1/super-admin/audit-logs",
        headers=headers,
        params={"action": "settings.update"},
    ).json()
    assert logs["total"] >= 1
    meta = logs["items"][0]["metadata"]
    assert "updated_keys" in meta
    assert "smtp_password" in meta["updated_keys"]
    assert "do-not-log-this" not in str(meta)


def test_notifications_crud_status(v1_client, v1_db):
    headers, actor_id, _email = _sa(v1_client, v1_db)
    created = v1_client.post(
        "/api/v1/super-admin/notifications",
        headers=headers,
        json={"title": "Welcome", "body": "Hello schools", "status": 0},
    )
    assert created.status_code == 201
    data = created.json()
    assert data["title"] == "Welcome"
    assert data["status"] == 0
    assert data["created_by"] == actor_id
    nid = data["id"]

    listing = v1_client.get("/api/v1/super-admin/notifications", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1

    got = v1_client.get(f"/api/v1/super-admin/notifications/{nid}", headers=headers)
    assert got.status_code == 200

    activated = v1_client.patch(
        f"/api/v1/super-admin/notifications/{nid}/status",
        headers=headers,
        json={"status": 1},
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == 1


def test_school_admin_forbidden(v1_client, v1_db):
    headers, _actor_id, _email = _sa(v1_client, v1_db)
    school = v1_client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": "Block", "code": "BLK01"},
    ).json()
    v1_client.post(
        f"/api/v1/super-admin/schools/{school['id']}/admins",
        headers=headers,
        json={
            "email": "p8-school-admin@eschool.com",
            "password": "adminpass1",
            "first_name": "SA",
            "last_name": "Admin",
        },
    )
    login = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "p8-school-admin@eschool.com", "password": "adminpass1"},
    )
    sa = _auth_header(login.json()["access_token"])
    for path in (
        "/api/v1/super-admin/settings",
        "/api/v1/super-admin/audit-logs",
        "/api/v1/super-admin/notifications",
    ):
        assert v1_client.get(path, headers=sa).status_code == 403


def test_audit_logs_not_writable(v1_client, v1_db):
    headers, _a, _e = _sa(v1_client, v1_db)
    # No POST/PATCH/DELETE for audit-logs
    assert (
        v1_client.post("/api/v1/super-admin/audit-logs", headers=headers, json={}).status_code
        == 405
    )
