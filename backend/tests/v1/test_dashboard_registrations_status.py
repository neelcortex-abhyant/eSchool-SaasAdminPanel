"""Super Admin registration analytics and school status distribution."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.models.tables import School
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User as V1User


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str):
    return client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "secret123",
            "first_name": "Phase",
            "last_name": "Three",
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


def _create_school(client, headers, *, name: str, code: str) -> dict:
    created = client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": name, "code": code, "support_email": f"{code.lower()}@eschool.com"},
    )
    assert created.status_code == 201
    return created.json()


def _set_created_at(v1_db, school_id: int, created_at: datetime | None) -> None:
    school = v1_db.get(School, school_id)
    assert school is not None
    school.created_at = created_at
    v1_db.commit()


def _zero_months() -> list[dict[str, int]]:
    return [{"month": month, "count": 0} for month in range(1, 13)]


def test_registrations_requires_super_admin(v1_client, v1_db):
    assert v1_client.get("/api/v1/super-admin/dashboard/registrations?year=2026").status_code == 401
    signup = _signup(v1_client, "reg-user@eschool.com")
    assert signup.status_code == 201
    forbidden = v1_client.get(
        "/api/v1/super-admin/dashboard/registrations?year=2026",
        headers=_auth_header(signup.json()["access_token"]),
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Forbidden"


def test_registrations_rejects_invalid_year(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="reg-year-sa@eschool.com")
    missing = v1_client.get("/api/v1/super-admin/dashboard/registrations", headers=headers)
    assert missing.status_code == 422
    for value in ("1999", "2101", "abc"):
        response = v1_client.get(
            f"/api/v1/super-admin/dashboard/registrations?year={value}",
            headers=headers,
        )
        assert response.status_code == 422


def test_registrations_empty(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="reg-empty-sa@eschool.com")
    for year in (2000, 2026, 2100):
        response = v1_client.get(
            f"/api/v1/super-admin/dashboard/registrations?year={year}",
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json() == {
            "year": year,
            "total": 0,
            "unscheduled": 0,
            "months": _zero_months(),
        }


def test_registrations_counts_boundaries_deleted_and_unscheduled(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="reg-count-sa@eschool.com")
    january = _create_school(v1_client, headers, name="January School", code="RGJAN")
    march_a = _create_school(v1_client, headers, name="March A", code="RGMAR")
    march_b = _create_school(v1_client, headers, name="March B", code="RGMR2")
    december = _create_school(v1_client, headers, name="December School", code="RGDEC")
    previous = _create_school(v1_client, headers, name="Previous Year", code="RGPRV")
    next_year = _create_school(v1_client, headers, name="Next Year", code="RGNXT")
    removed = _create_school(v1_client, headers, name="Removed March", code="RGDEL")
    unscheduled = _create_school(v1_client, headers, name="No Date", code="RGNUL")
    removed_null = _create_school(v1_client, headers, name="Removed Null", code="RGNL2")

    _set_created_at(v1_db, january["id"], datetime(2026, 1, 1, 0, 0, 0))
    _set_created_at(v1_db, march_a["id"], datetime(2026, 3, 15, 8, 0, 0))
    _set_created_at(v1_db, march_b["id"], datetime(2026, 3, 20, 8, 0, 0))
    _set_created_at(v1_db, december["id"], datetime(2026, 12, 31, 23, 59, 59))
    _set_created_at(v1_db, previous["id"], datetime(2025, 12, 31, 23, 59, 59))
    _set_created_at(v1_db, next_year["id"], datetime(2027, 1, 1, 0, 0, 0))
    _set_created_at(v1_db, removed["id"], datetime(2026, 3, 1, 0, 0, 0))
    _set_created_at(v1_db, unscheduled["id"], None)
    _set_created_at(v1_db, removed_null["id"], None)
    assert v1_client.delete(f"/api/v1/super-admin/schools/{removed['id']}", headers=headers).status_code == 200
    assert v1_client.delete(f"/api/v1/super-admin/schools/{removed_null['id']}", headers=headers).status_code == 200

    response = v1_client.get("/api/v1/super-admin/dashboard/registrations?year=2026", headers=headers)
    assert response.status_code == 200
    body = response.json()
    counts = {item["month"]: item["count"] for item in body["months"]}
    assert list(counts) == list(range(1, 13))
    assert counts[1] == 1
    assert counts[3] == 2
    assert counts[12] == 1
    assert all(counts[month] == 0 for month in range(1, 13) if month not in (1, 3, 12))
    assert body["total"] == sum(counts.values()) == 4
    assert body["unscheduled"] == 1
    assert body["year"] == 2026

    following = v1_client.get("/api/v1/super-admin/dashboard/registrations?year=2027", headers=headers)
    assert following.status_code == 200
    next_body = following.json()
    next_counts = {item["month"]: item["count"] for item in next_body["months"]}
    assert next_counts[1] == 1
    assert next_body["total"] == 1
    assert next_body["unscheduled"] == 1


def test_school_status_requires_super_admin(v1_client, v1_db):
    assert v1_client.get("/api/v1/super-admin/dashboard/school-status").status_code == 401
    signup = _signup(v1_client, "status-user@eschool.com")
    assert signup.status_code == 201
    forbidden = v1_client.get(
        "/api/v1/super-admin/dashboard/school-status",
        headers=_auth_header(signup.json()["access_token"]),
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Forbidden"


def test_school_status_zero(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="status-empty-sa@eschool.com")
    response = v1_client.get("/api/v1/super-admin/dashboard/school-status", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"active_schools": 0, "inactive_schools": 0}


def test_school_status_matches_stats_and_skips_deleted(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="status-count-sa@eschool.com")
    active = _create_school(v1_client, headers, name="Active Status", code="STACT")
    suspended = _create_school(v1_client, headers, name="Suspended Status", code="STSUS")
    deactivated = _create_school(v1_client, headers, name="Deactivated Status", code="STDEA")
    removed = _create_school(v1_client, headers, name="Removed Status", code="STDEL")
    assert v1_client.post(f"/api/v1/super-admin/schools/{suspended['id']}/suspend", headers=headers).status_code == 200
    assert (
        v1_client.post(f"/api/v1/super-admin/schools/{deactivated['id']}/deactivate", headers=headers).status_code
        == 200
    )
    assert v1_client.delete(f"/api/v1/super-admin/schools/{removed['id']}", headers=headers).status_code == 200
    assert active["status"] == 1

    status = v1_client.get("/api/v1/super-admin/dashboard/school-status", headers=headers)
    stats = v1_client.get("/api/v1/super-admin/dashboard/stats", headers=headers)
    assert status.status_code == 200
    assert stats.status_code == 200
    assert status.json() == {"active_schools": 1, "inactive_schools": 2}
    assert status.json()["active_schools"] == stats.json()["active_schools"]
    assert status.json()["inactive_schools"] == stats.json()["inactive_schools"]
