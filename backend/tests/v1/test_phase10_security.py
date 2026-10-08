"""Phase 10 — security matrix: auth, escalation, isolation, secrets, validation.

Phase 9 payments remain BLOCKED / DEFERRED — this file never tests or fakes gateways.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.models.v1.roles import ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN, ROLE_USER
from app.models.v1.session import AuthSession
from app.models.v1.user import STATUS_INACTIVE, User
from app.services.v1 import audit_service


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str = "p10-user@eschool.com", **overrides):
    body = {
        "email": email,
        "password": "secret123",
        "first_name": "Phase",
        "last_name": "Ten",
        **overrides,
    }
    return client.post("/api/v1/auth/signup", json=body)


def _sa_headers(client, v1_db, email: str = "p10-sa@eschool.com") -> dict[str, str]:
    assert _signup(client, email=email).status_code == 201
    user = v1_db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200
    return _auth(login.json()["access_token"])


def _school(client, headers, **overrides):
    body = {"name": "P10 School", "code": "P10S01", **overrides}
    res = client.post("/api/v1/super-admin/schools", headers=headers, json=body)
    assert res.status_code == 201
    return res.json()


def _plan(client, headers, **overrides):
    body = {
        "name": "P10 Plan",
        "monthly_price": 10.0,
        "yearly_price": 100.0,
        **overrides,
    }
    res = client.post("/api/v1/super-admin/plans", headers=headers, json=body)
    assert res.status_code == 201
    return res.json()


def _school_admin_token(client, headers, school_id: int, email: str) -> str:
    res = client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=headers,
        json={
            "email": email,
            "password": "adminpass1",
            "first_name": "School",
            "last_name": "Admin",
        },
    )
    assert res.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "adminpass1"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


# --- Phase 9 status frozen ---


def test_phase9_remains_blocked_deferred():
    doc = Path(__file__).resolve().parents[2] / "docs" / "PHASE9_AUDIT.md"
    text = doc.read_text(encoding="utf-8")
    assert "BLOCKED / DEFERRED" in text
    assert "NOT STARTED" in text
    assert "NOT AVAILABLE" in text
    assert "NOT IMPLEMENTED" in text


# --- Authentication ---


def test_auth_missing_invalid_expired_revoked(v1_client, v1_db):
    path = "/api/v1/super-admin/ping"
    assert v1_client.get(path).status_code == 401
    assert v1_client.get(path, headers=_auth("not-a-token")).status_code == 401

    token = _signup(v1_client, email="p10-exp@eschool.com").json()["access_token"]
    # Promote then use SA path after expiry
    user = v1_db.scalar(select(User).where(User.email == "p10-exp@eschool.com"))
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "p10-exp@eschool.com", "password": "secret123"},
    )
    token = login.json()["access_token"]
    session = v1_db.scalar(
        select(AuthSession).where(AuthSession.user_id == user.id).order_by(AuthSession.created_at.desc())
    )
    assert session is not None
    session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    v1_db.commit()
    assert v1_client.get(path, headers=_auth(token)).status_code == 401

    again = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "p10-exp@eschool.com", "password": "secret123"},
    ).json()["access_token"]
    assert v1_client.post("/api/v1/auth/logout", headers=_auth(again)).status_code == 204
    assert v1_client.get(path, headers=_auth(again)).status_code == 401


def test_inactive_user_existing_token_rejected(v1_client, v1_db):
    headers = _sa_headers(v1_client, v1_db)
    school_id = _school(v1_client, headers)["id"]
    token = _school_admin_token(v1_client, headers, school_id, "p10-inactive@eschool.com")
    assert v1_client.get("/api/v1/school-admin/me", headers=_auth(token)).status_code == 200

    admin = v1_db.scalar(select(User).where(User.email == "p10-inactive@eschool.com"))
    assert admin is not None
    v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}/admins/{admin.id}/status",
        headers=headers,
        json={"status": STATUS_INACTIVE},
    )
    # Existing opaque session must die (revoked + inactive check).
    res = v1_client.get("/api/v1/school-admin/me", headers=_auth(token))
    assert res.status_code in (401, 403)


# --- Authorization / privilege ---


def test_user_and_school_admin_cannot_hit_sa_endpoints(v1_client, v1_db):
    headers = _sa_headers(v1_client, v1_db)
    school = _school(v1_client, headers)
    plan = _plan(v1_client, headers)
    sub = v1_client.post(
        f"/api/v1/super-admin/schools/{school['id']}/subscriptions",
        headers=headers,
        json={
            "package_id": plan["id"],
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        },
    ).json()

    user_token = _signup(v1_client, email="p10-normal@eschool.com").json()["access_token"]
    sa_token = _school_admin_token(v1_client, headers, school["id"], "p10-schadm@eschool.com")

    sa_paths = [
        "/api/v1/super-admin/ping",
        "/api/v1/super-admin/me",
        "/api/v1/super-admin/dashboard",
        "/api/v1/super-admin/schools",
        "/api/v1/super-admin/plans",
        "/api/v1/super-admin/settings",
        "/api/v1/super-admin/audit-logs",
        "/api/v1/super-admin/notifications",
        f"/api/v1/super-admin/schools/{school['id']}/subscriptions",
        f"/api/v1/super-admin/schools/{school['id']}/subscriptions/{sub['id']}",
        f"/api/v1/super-admin/schools/{school['id']}/subscriptions/{sub['id']}/bills",
        f"/api/v1/super-admin/schools/{school['id']}/addons",
    ]
    for path in sa_paths:
        assert v1_client.get(path, headers=_auth(user_token)).status_code == 403, path
        assert v1_client.get(path, headers=_auth(sa_token)).status_code == 403, path


def test_cannot_signup_or_self_promote_to_super_admin(v1_client, v1_db):
    forged = v1_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "p10-forge@eschool.com",
            "password": "secret123",
            "first_name": "Forge",
            "last_name": "Role",
            "role": ROLE_SUPER_ADMIN,
            "school_id": 1,
        },
    )
    assert forged.status_code == 422

    token = _signup(v1_client, email="p10-self@eschool.com").json()["access_token"]
    patch = v1_client.patch(
        "/api/v1/users/me",
        headers=_auth(token),
        json={"role": ROLE_SUPER_ADMIN, "school_id": 99},
    )
    assert patch.status_code == 422
    me = v1_client.get("/api/v1/auth/me", headers=_auth(token)).json()
    assert me["role"] == ROLE_USER
    assert me["school_id"] is None

    user = v1_db.scalar(select(User).where(User.email == "p10-self@eschool.com"))
    assert user.role == ROLE_USER


def test_second_super_admin_register_blocked_without_env(v1_client, v1_db, monkeypatch):
    monkeypatch.delenv("V1_SUPER_ADMIN_EMAIL", raising=False)
    from app.core.config import get_settings

    get_settings.cache_clear()
    first = v1_client.post(
        "/api/v1/super-admin/register",
        json={
            "email": "p10-first-sa@eschool.com",
            "password": "secret123",
            "first_name": "First",
            "last_name": "SA",
        },
    )
    assert first.status_code == 201
    assert first.json()["user"]["role"] == ROLE_SUPER_ADMIN

    second = v1_client.post(
        "/api/v1/super-admin/register",
        json={
            "email": "p10-second-sa@eschool.com",
            "password": "secret123",
            "first_name": "Second",
            "last_name": "SA",
        },
    )
    assert second.status_code == 403
    get_settings.cache_clear()


# --- Tenant isolation / IDOR ---


def test_school_admin_cannot_access_other_school_resources(v1_client, v1_db):
    headers = _sa_headers(v1_client, v1_db)
    school_a = _school(v1_client, headers, code="P10A", name="A", support_email="a@eschool.com")
    school_b = _school(v1_client, headers, code="P10B", name="B", support_email="b@eschool.com")
    plan = _plan(v1_client, headers, name="Iso Plan")

    sub_b = v1_client.post(
        f"/api/v1/super-admin/schools/{school_b['id']}/subscriptions",
        headers=headers,
        json={
            "package_id": plan["id"],
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        },
    ).json()
    bill_b = v1_client.post(
        f"/api/v1/super-admin/schools/{school_b['id']}/subscriptions/{sub_b['id']}/bills",
        headers=headers,
        json={"period_start": "2026-01-01", "period_end": "2026-01-31", "amount": 10},
    ).json()

    addon = v1_client.post(
        "/api/v1/super-admin/addons",
        headers=headers,
        json={"name": "P10 Addon", "price": 5.0},
    ).json()
    v1_client.patch(
        f"/api/v1/super-admin/addons/{addon['id']}/status",
        headers=headers,
        json={"status": 1},
    )
    assign_b = v1_client.post(
        f"/api/v1/super-admin/schools/{school_b['id']}/addons",
        headers=headers,
        json={"addon_id": addon["id"]},
    )
    assert assign_b.status_code == 201
    assign_id = assign_b.json()["id"]

    admin_b = v1_client.post(
        f"/api/v1/super-admin/schools/{school_b['id']}/admins",
        headers=headers,
        json={
            "email": "p10-admin-b@eschool.com",
            "password": "adminpass1",
            "first_name": "B",
            "last_name": "Admin",
        },
    ).json()

    token_a = _school_admin_token(v1_client, headers, school_a["id"], "p10-admin-a@eschool.com")
    ha = _auth(token_a)

    assert v1_client.get(f"/api/v1/school-admin/schools/{school_b['id']}", headers=ha).status_code == 403

    # School Admin has no Super Admin routes — all 403 (not data leak)
    assert (
        v1_client.get(f"/api/v1/super-admin/schools/{school_b['id']}", headers=ha).status_code == 403
    )
    assert (
        v1_client.get(
            f"/api/v1/super-admin/schools/{school_b['id']}/admins/{admin_b['id']}",
            headers=ha,
        ).status_code
        == 403
    )
    assert (
        v1_client.get(
            f"/api/v1/super-admin/schools/{school_b['id']}/subscriptions/{sub_b['id']}",
            headers=ha,
        ).status_code
        == 403
    )
    assert (
        v1_client.get(
            f"/api/v1/super-admin/schools/{school_b['id']}/subscriptions/{sub_b['id']}/bills/{bill_b['id']}",
            headers=ha,
        ).status_code
        == 403
    )
    assert (
        v1_client.get(
            f"/api/v1/super-admin/schools/{school_b['id']}/addons/{assign_id}",
            headers=ha,
        ).status_code
        == 403
    )


def test_super_admin_cross_school_resource_mismatch_404(v1_client, v1_db):
    """SA may access platform-wide data, but wrong school_id in path still 404."""
    headers = _sa_headers(v1_client, v1_db, email="p10-sa2@eschool.com")
    school_a = _school(v1_client, headers, code="P10X", name="X", support_email="x@eschool.com")
    school_b = _school(v1_client, headers, code="P10Y", name="Y", support_email="y@eschool.com")
    plan = _plan(v1_client, headers, name="Mismatch Plan")
    sub_a = v1_client.post(
        f"/api/v1/super-admin/schools/{school_a['id']}/subscriptions",
        headers=headers,
        json={
            "package_id": plan["id"],
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        },
    ).json()
    res = v1_client.get(
        f"/api/v1/super-admin/schools/{school_b['id']}/subscriptions/{sub_a['id']}",
        headers=headers,
    )
    assert res.status_code == 404


# --- Validation / mass assignment ---


def test_validation_and_mass_assignment_guards(v1_client, v1_db):
    headers = _sa_headers(v1_client, v1_db, email="p10-val@eschool.com")
    school = _school(v1_client, headers, code="P10V", name="Val")

    assert (
        v1_client.post(
            "/api/v1/super-admin/plans",
            headers=headers,
            json={"name": "Neg", "monthly_price": -1},
        ).status_code
        == 422
    )
    assert (
        v1_client.post(
            "/api/v1/super-admin/plans",
            headers=headers,
            json={"name": "x" * 300},
        ).status_code
        == 422
    )
    assert (
        v1_client.post(
            "/api/v1/super-admin/plans",
            headers=headers,
            json={"name": ""},
        ).status_code
        == 422
    )
    assert (
        v1_client.post(
            f"/api/v1/super-admin/schools/{school['id']}/subscriptions",
            headers=headers,
            json={
                "package_id": 1,
                "start_date": "not-a-date",
                "end_date": "2026-12-31",
            },
        ).status_code
        == 422
    )
    assert (
        v1_client.post(
            f"/api/v1/super-admin/schools/{school['id']}/subscriptions",
            headers=headers,
            json={
                "package_id": 1,
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "status": 99,
            },
        ).status_code
        == 422
    )
    assert (
        v1_client.get(
            "/api/v1/super-admin/schools/not-an-int",
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        v1_client.get(
            f"/api/v1/super-admin/schools/{school['id']}/admins/not-a-uuid",
            headers=headers,
        ).status_code
        == 422
    )

    # Protected fields forbidden on school create
    assert (
        v1_client.post(
            "/api/v1/super-admin/schools",
            headers=headers,
            json={
                "name": "Inject",
                "code": "INJ01",
                "id": 999999,
                "v1_admin_id": "x",
                "provisioned_at": "2020-01-01T00:00:00",
                "deleted_at": "2020-01-01T00:00:00",
            },
        ).status_code
        == 422
    )


# --- Secrets ---


def test_responses_never_leak_password_or_token_hash(v1_client, v1_db):
    signup = _signup(v1_client, email="p10-sec@eschool.com").json()
    blob = str(signup)
    assert "password_hash" not in blob
    assert "secret123" not in signup["user"].values()

    headers = _sa_headers(v1_client, v1_db, email="p10-sec-sa@eschool.com")
    v1_client.patch(
        "/api/v1/super-admin/settings",
        headers=headers,
        json={"settings": {"smtp_password": "smtp-real-secret", "webhook_secret": "whsec"}},
    )
    settings = v1_client.get("/api/v1/super-admin/settings", headers=headers).json()
    assert settings["settings"]["smtp_password"]["value"] is None
    assert settings["settings"]["webhook_secret"]["value"] is None
    assert "smtp-real-secret" not in str(settings)
    assert "whsec" not in str(settings)

    me = v1_client.get("/api/v1/super-admin/me", headers=headers).json()
    assert "password" not in me
    assert "password_hash" not in me

    logs = v1_client.get("/api/v1/super-admin/audit-logs", headers=headers).json()
    assert "smtp-real-secret" not in str(logs)
    assert "whsec" not in str(logs)


def test_audit_actor_cannot_be_spoofed_by_client(v1_client, v1_db):
    headers = _sa_headers(v1_client, v1_db, email="p10-audit@eschool.com")
    actor = v1_db.scalar(select(User).where(User.email == "p10-audit@eschool.com"))
    assert actor is not None

    # No public POST for audit-logs; client body fields cannot invent actor.
    res = v1_client.post(
        "/api/v1/super-admin/audit-logs",
        headers=headers,
        json={"actor_id": "00000000-0000-0000-0000-000000000099", "action": "fake"},
    )
    assert res.status_code in (405, 404, 422)

    school = v1_client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": "Actor School", "code": "ACT01", "actor_id": "spoofed"},
    )
    assert school.status_code == 422  # extra forbid

    school_ok = v1_client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": "Actor School", "code": "ACT01"},
    )
    assert school_ok.status_code == 201
    logs = v1_client.get(
        "/api/v1/super-admin/audit-logs",
        headers=headers,
        params={"action": "school.create"},
    ).json()
    item = next(i for i in logs["items"] if i["entity_id"] == str(school_ok.json()["id"]))
    assert item["actor_id"] == str(actor.id)
    assert item["actor_email"] == "p10-audit@eschool.com"


def test_sanitize_metadata_strips_secrets():
    cleaned = audit_service.sanitize_metadata(
        {
            "password": "x",
            "smtp_password": "y",
            "ok": "value",
            "nested": {"api_key": "z", "count": 1},
            "note": "authorization bearer " + ("a" * 40),
        }
    )
    assert "password" not in cleaned
    assert "smtp_password" not in cleaned
    assert cleaned["ok"] == "value"
    assert "api_key" not in cleaned["nested"]
    assert cleaned["nested"]["count"] == 1
    assert cleaned["note"] == "[redacted]"


# --- Soft-delete safety smoke ---


def test_soft_deleted_school_not_listed_as_active(v1_client, v1_db):
    headers = _sa_headers(v1_client, v1_db, email="p10-del@eschool.com")
    school = _school(v1_client, headers, code="P10D", name="DeleteMe")
    assert (
        v1_client.delete(f"/api/v1/super-admin/schools/{school['id']}", headers=headers).status_code
        == 200
    )
    listing = v1_client.get("/api/v1/super-admin/schools", headers=headers).json()
    assert all(item["id"] != school["id"] for item in listing["items"])
    assert (
        v1_client.get(f"/api/v1/super-admin/schools/{school['id']}", headers=headers).status_code
        == 404
    )


# --- Config / CORS / env example ---


def test_env_example_has_placeholders_only():
    example = (Path(__file__).resolve().parents[2] / ".env.example").read_text(encoding="utf-8")
    assert "USER:PASS@HOST" in example or "NEON_DATABASE_URL=" in example
    assert "npg_" not in example
    assert "change-me" in example or "SESSION_SECRET=" in example


def test_cors_configured_from_settings(v1_client):
    from app.core.config import get_settings

    settings = get_settings()
    assert settings.cors_origins
    # Preflight against a configured origin
    origin = settings.cors_origins[0]
    res = v1_client.options(
        "/api/v1/auth/me",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.status_code in (200, 204)
    assert res.headers.get("access-control-allow-origin") == origin


def test_error_responses_do_not_expose_stack_or_sql(v1_client, v1_db):
    headers = _sa_headers(v1_client, v1_db, email="p10-err@eschool.com")
    res = v1_client.get("/api/v1/super-admin/schools/99999999", headers=headers)
    assert res.status_code == 404
    body = res.text.lower()
    assert "traceback" not in body
    assert "select " not in body
    assert "postgresql" not in body
    assert "password" not in body
