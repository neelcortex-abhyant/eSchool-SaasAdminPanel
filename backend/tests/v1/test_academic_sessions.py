"""Academic session management under /api/v1/school-admin/academics/sessions."""

from __future__ import annotations

from sqlalchemy import select

from app.models.tables import SessionYear
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User

ACADEMICS = "/api/v1/school-admin/academics"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _super(client, v1_db, email: str) -> dict[str, str]:
    created = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "secret123", "first_name": "A", "last_name": "B"},
    )
    assert created.status_code == 201, created.text
    user = v1_db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200, login.text
    return _auth(login.json()["access_token"])


def _school_admin(client, sa_headers, school_id: int, email: str) -> dict[str, str]:
    created = client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=sa_headers,
        json={"email": email, "password": "adminpass1", "first_name": "School", "last_name": "Admin"},
    )
    assert created.status_code == 201, created.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "adminpass1"})
    assert login.status_code == 200, login.text
    return _auth(login.json()["access_token"])


def _school(client, sa_headers, code: str) -> int:
    school = client.post(
        "/api/v1/super-admin/schools",
        headers=sa_headers,
        json={"name": f"School {code}", "code": code},
    )
    assert school.status_code == 201, school.text
    return school.json()["id"]


def test_session_crud_validation_duplicate_and_activate(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "sess-sa@eschool.com")
    school_id = _school(v1_client, sa, "SESS01")
    admin = _school_admin(v1_client, sa, school_id, "sess-admin@eschool.com")

    assert (
        v1_client.post(
            f"{ACADEMICS}/sessions",
            headers=admin,
            json={"name": "  ", "start_date": "2026-04-01", "end_date": "2027-03-31"},
        ).status_code
        == 422
    )
    assert (
        v1_client.post(
            f"{ACADEMICS}/sessions",
            headers=admin,
            json={"name": "Bad", "start_date": "2027-04-01", "end_date": "2026-03-31"},
        ).status_code
        == 422
    )

    created = v1_client.post(
        f"{ACADEMICS}/sessions",
        headers=admin,
        json={
            "name": " 2026-27 ",
            "start_date": "2026-04-01",
            "end_date": "2027-03-31",
            "default": 1,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["name"] == "2026-27"
    assert created.json()["default"] == 1
    session_id = created.json()["id"]

    detail = v1_client.get(f"{ACADEMICS}/sessions/{session_id}", headers=admin)
    assert detail.status_code == 200, detail.text
    assert detail.json()["id"] == session_id
    assert detail.json()["start_date"] == "2026-04-01"

    dup = v1_client.post(
        f"{ACADEMICS}/sessions",
        headers=admin,
        json={"name": "2026-27", "start_date": "2026-04-01", "end_date": "2027-03-31"},
    )
    assert dup.status_code == 409
    assert dup.json()["detail"] == "A session with this name already exists"

    second = v1_client.post(
        f"{ACADEMICS}/sessions",
        headers=admin,
        json={"name": "2027-28", "start_date": "2027-04-01", "end_date": "2028-03-31"},
    )
    assert second.status_code == 201
    second_id = second.json()["id"]

    activated = v1_client.post(f"{ACADEMICS}/sessions/{second_id}/activate", headers=admin)
    assert activated.status_code == 200
    assert activated.json()["default"] == 1

    first_again = v1_client.get(f"{ACADEMICS}/sessions/{session_id}", headers=admin)
    assert first_again.json()["default"] == 0

    patched = v1_client.patch(
        f"{ACADEMICS}/sessions/{session_id}",
        headers=admin,
        json={"name": "2026-27B"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "2026-27B"

    compact = v1_client.get("/api/v1/school-admin/sessions", headers=admin)
    assert compact.status_code == 200
    for item in compact.json()["items"]:
        assert set(item.keys()) == {"id", "name", "default"}

    deleted = v1_client.delete(f"{ACADEMICS}/sessions/{second_id}", headers=admin)
    assert deleted.status_code == 200
    assert v1_client.get(f"{ACADEMICS}/sessions/{second_id}", headers=admin).status_code == 404
    row = v1_db.get(SessionYear, second_id)
    assert row is not None and row.deleted_at is not None and row.default == 0


def test_session_tenant_isolation_and_auth(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "sess-iso-sa@eschool.com")
    school_a = _school(v1_client, sa, "SESS02")
    school_b = _school(v1_client, sa, "SESS03")
    admin_a = _school_admin(v1_client, sa, school_a, "sess-a@eschool.com")
    admin_b = _school_admin(v1_client, sa, school_b, "sess-b@eschool.com")

    created = v1_client.post(
        f"{ACADEMICS}/sessions",
        headers=admin_a,
        json={"name": "OnlyA", "start_date": "2026-04-01", "end_date": "2027-03-31", "default": 1},
    )
    assert created.status_code == 201
    session_id = created.json()["id"]

    assert v1_client.get(f"{ACADEMICS}/sessions/{session_id}", headers=admin_b).status_code == 404
    assert v1_client.post(f"{ACADEMICS}/sessions/{session_id}/activate", headers=admin_b).status_code == 404
    assert (
        v1_client.patch(
            f"{ACADEMICS}/sessions/{session_id}",
            headers=admin_b,
            json={"name": "Hijack"},
        ).status_code
        == 404
    )
    assert v1_client.get(f"{ACADEMICS}/sessions").status_code == 401
