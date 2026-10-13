"""Super Admin recent activities."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.models.tables import AuditLog
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User as V1User

_ITEM_KEYS = {
    "id",
    "action",
    "entity_type",
    "entity_id",
    "school_id",
    "created_at",
    "title",
    "description",
}
_SECRET_EMAIL = "hidden-actor@eschool.com"
_SECRET_METADATA = "raw-metadata-marker"


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str):
    return client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "secret123",
            "first_name": "Recent",
            "last_name": "Activity",
        },
    )


def _super_admin_headers(client, v1_db, email: str) -> dict[str, str]:
    assert _signup(client, email).status_code == 201
    user = v1_db.scalar(select(V1User).where(V1User.email == email))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200
    return _auth_header(login.json()["access_token"])


def _add_log(v1_db, *, action: str, created_at: datetime, entity_id: str, school_id: int) -> AuditLog:
    row = AuditLog(
        actor_id="hidden-actor-id",
        actor_email=_SECRET_EMAIL,
        action=action,
        entity_type="school" if action.startswith("school") else "subscription",
        entity_id=entity_id,
        school_id=school_id,
        metadata_json=json.dumps({"note": _SECRET_METADATA, "token": "super-secret-token-value"}),
        created_at=created_at,
    )
    v1_db.add(row)
    v1_db.commit()
    v1_db.refresh(row)
    return row


def test_recent_activities_requires_super_admin(v1_client, v1_db):
    assert v1_client.get("/api/v1/super-admin/dashboard/recent-activities").status_code == 401
    signup = _signup(v1_client, "activity-user@eschool.com")
    assert signup.status_code == 201
    forbidden = v1_client.get(
        "/api/v1/super-admin/dashboard/recent-activities",
        headers=_auth_header(signup.json()["access_token"]),
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Forbidden"


def test_recent_activities_empty(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="activity-empty-sa@eschool.com")
    response = v1_client.get("/api/v1/super-admin/dashboard/recent-activities", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_recent_activities_invalid_limit(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="activity-limit-sa@eschool.com")
    for value in ("0", "51", "-1", "abc"):
        response = v1_client.get(
            f"/api/v1/super-admin/dashboard/recent-activities?limit={value}",
            headers=headers,
        )
        assert response.status_code == 422


def test_recent_activities_titles_order_and_privacy(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="activity-count-sa@eschool.com")
    registered = _add_log(
        v1_db,
        action="school.register",
        created_at=datetime(2026, 10, 1, 12, 0, 0),
        entity_id="1",
        school_id=1,
    )
    activated = _add_log(
        v1_db,
        action="school.activate",
        created_at=datetime(2026, 10, 2, 12, 0, 0),
        entity_id="1",
        school_id=1,
    )
    deactivated = _add_log(
        v1_db,
        action="school.deactivate",
        created_at=datetime(2026, 10, 3, 12, 0, 0),
        entity_id="1",
        school_id=1,
    )
    created = _add_log(
        v1_db,
        action="subscription.create",
        created_at=datetime(2026, 10, 4, 12, 0, 0),
        entity_id="9",
        school_id=1,
    )
    updated = _add_log(
        v1_db,
        action="subscription.update",
        created_at=datetime(2026, 10, 5, 12, 0, 0),
        entity_id="9",
        school_id=1,
    )
    unknown = _add_log(
        v1_db,
        action="not.a.real.action",
        created_at=datetime(2026, 10, 6, 12, 0, 0),
        entity_id="9",
        school_id=1,
    )

    response = v1_client.get("/api/v1/super-admin/dashboard/recent-activities", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [
        unknown.id,
        updated.id,
        created.id,
        deactivated.id,
        activated.id,
        registered.id,
    ]
    by_action = {item["action"]: item for item in body["items"]}
    assert by_action["school.register"]["title"] == "New school registration"
    assert by_action["school.activate"]["title"] == "School activation"
    assert by_action["school.deactivate"]["title"] == "School deactivation"
    assert by_action["subscription.create"]["title"] == "Subscription creation"
    assert by_action["subscription.update"]["title"] == "Subscription updated"
    assert "renew" not in by_action["subscription.update"]["title"].lower()
    assert by_action["not.a.real.action"]["title"] == "Activity recorded"
    assert by_action["not.a.real.action"]["description"] == "An activity was recorded."
    assert all(set(item) == _ITEM_KEYS for item in body["items"])
    raw = response.text
    assert _SECRET_EMAIL not in raw
    assert _SECRET_METADATA not in raw
    assert "super-secret-token-value" not in raw
    assert "actor_email" not in raw
    assert "metadata" not in raw

    newest = v1_client.get("/api/v1/super-admin/dashboard/recent-activities?limit=1", headers=headers)
    assert newest.status_code == 200
    assert [item["id"] for item in newest.json()["items"]] == [unknown.id]

    wide = v1_client.get("/api/v1/super-admin/dashboard/recent-activities?limit=50", headers=headers)
    assert wide.status_code == 200
    assert len(wide.json()["items"]) == 6


def test_recent_activities_default_limit_returns_ten_newest(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="activity-bound-sa@eschool.com")
    rows = [
        _add_log(
            v1_db,
            action="school.create",
            created_at=datetime(2026, 1, 1, 0, 0, index),
            entity_id=str(index),
            school_id=1,
        )
        for index in range(1, 12)
    ]
    response = v1_client.get("/api/v1/super-admin/dashboard/recent-activities", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 10
    assert [item["id"] for item in body["items"]] == [row.id for row in reversed(rows[-10:])]
    assert rows[0].id not in {item["id"] for item in body["items"]}
