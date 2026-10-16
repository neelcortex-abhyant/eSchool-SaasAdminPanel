"""Platform-wide subscription list. Each test starts from an empty schema."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.models.tables import AuditLog, School, Subscription
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User

LIST_PATH = "/api/v1/super-admin/subscriptions"


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str):
    return client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "secret123",
            "first_name": "List",
            "last_name": "Admin",
        },
    )


def _super_admin_headers(client, v1_db, email: str) -> dict[str, str]:
    res = _signup(client, email)
    assert res.status_code == 201, res.text
    user = v1_db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200, login.text
    return _auth_header(login.json()["access_token"])


def _school(client, headers, **overrides):
    body = {"name": "List School", "code": "LST001", **overrides}
    res = client.post("/api/v1/super-admin/schools", headers=headers, json=body)
    assert res.status_code == 201, res.text
    return res.json()


def _plan(client, headers, name: str):
    created = client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": name, "monthly_price": 10, "yearly_price": 100},
    )
    assert created.status_code == 201, created.text
    plan = created.json()
    activated = client.patch(
        f"/api/v1/super-admin/plans/{plan['id']}/status",
        headers=headers,
        json={"status": 1},
    )
    assert activated.status_code == 200, activated.text
    return plan


def _assign(client, headers, school_id: int, package_id: int, **overrides):
    body = {
        "package_id": package_id,
        "start_date": "2026-01-01",
        "end_date": "2026-06-30",
        "cycle": "monthly",
        "status": 0,
    }
    body.update(overrides)
    res = client.post(
        f"/api/v1/super-admin/schools/{school_id}/subscriptions",
        headers=headers,
        json=body,
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_platform_list_auth(v1_client, v1_db):
    assert v1_client.get(LIST_PATH).status_code == 401
    token = _signup(v1_client, "list-user@eschool.com").json()["access_token"]
    forbidden = v1_client.get(LIST_PATH, headers=_auth_header(token))
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Forbidden"


def test_platform_list_filters_pagination_and_soft_delete(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "list-filters@eschool.com")

    empty = v1_client.get(LIST_PATH, headers=headers)
    assert empty.status_code == 200, empty.text
    assert empty.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}
    assert "success" not in empty.json()

    alpha = _school(v1_client, headers, name="Alpha Academy", code="LSTA")
    beta = _school(v1_client, headers, name="Beta Campus", code="LSTB")
    gamma = _school(v1_client, headers, name="Gamma Hall", code="LSTG")
    removed_school = _school(v1_client, headers, name="Removed School", code="LSTR")
    basic = _plan(v1_client, headers, "Basic List")
    plus = _plan(v1_client, headers, "Plus List")

    alpha_sub = _assign(
        v1_client, headers, alpha["id"], basic["id"], end_date="2026-03-01", status=1
    )
    beta_sub = _assign(
        v1_client, headers, beta["id"], plus["id"], end_date="2026-01-15", status=2
    )
    gamma_sub = _assign(
        v1_client, headers, gamma["id"], basic["id"], end_date="2026-06-01", status=0
    )
    removed_sub = _assign(
        v1_client, headers, removed_school["id"], basic["id"], end_date="2026-02-01", status=1
    )
    deleted_sub = _assign(
        v1_client, headers, alpha["id"], basic["id"], end_date="2026-04-01", status=0
    )
    removed_school_row = v1_db.get(School, removed_school["id"])
    deleted_row = v1_db.get(Subscription, deleted_sub["id"])
    assert removed_school_row is not None and deleted_row is not None
    removed_school_row.deleted_at = datetime(2026, 4, 1, 0, 0, 0)
    deleted_row.deleted_at = datetime(2026, 4, 1, 0, 0, 0)
    v1_db.commit()

    audits_before = int(v1_db.scalar(select(func.count()).select_from(AuditLog)) or 0)
    listed = v1_client.get(LIST_PATH, headers=headers, params={"page_size": 2})
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert [item["id"] for item in body["items"]] == [beta_sub["id"], alpha_sub["id"]]
    assert body["items"][0]["school_name"] == "Beta Campus"
    assert body["items"][0]["plan_name"] == "Plus List"
    assert body["items"][0]["status"] == 2
    assert "success" not in body
    v1_db.expire_all()
    audits_after = int(v1_db.scalar(select(func.count()).select_from(AuditLog)) or 0)
    assert audits_after == audits_before

    page2 = v1_client.get(LIST_PATH, headers=headers, params={"page": 2, "page_size": 2})
    assert page2.status_code == 200, page2.text
    assert page2.json()["total"] == 3
    assert [item["id"] for item in page2.json()["items"]] == [gamma_sub["id"]]

    search = v1_client.get(LIST_PATH, headers=headers, params={"q": "aLpHa"})
    assert search.status_code == 200, search.text
    assert [item["id"] for item in search.json()["items"]] == [alpha_sub["id"]]
    assert search.json()["total"] == 1

    by_status = v1_client.get(LIST_PATH, headers=headers, params={"status": 0})
    assert [item["id"] for item in by_status.json()["items"]] == [gamma_sub["id"]]

    by_plan = v1_client.get(LIST_PATH, headers=headers, params={"package_id": plus["id"]})
    assert [item["id"] for item in by_plan.json()["items"]] == [beta_sub["id"]]

    by_school = v1_client.get(LIST_PATH, headers=headers, params={"school_id": gamma["id"]})
    assert [item["id"] for item in by_school.json()["items"]] == [gamma_sub["id"]]

    none = v1_client.get(LIST_PATH, headers=headers, params={"q": "zzzz-no-school"})
    assert none.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}

    ids = {item["id"] for item in v1_client.get(LIST_PATH, headers=headers, params={"page_size": 100}).json()["items"]}
    assert removed_sub["id"] not in ids
    assert deleted_sub["id"] not in ids

    school_list = v1_client.get(
        f"/api/v1/super-admin/schools/{alpha['id']}/subscriptions",
        headers=headers,
    )
    assert school_list.status_code == 200, school_list.text
    assert school_list.json()["items"]
    assert "school_name" not in school_list.json()["items"][0]


def test_platform_list_sorting(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "list-sort@eschool.com")
    school = _school(v1_client, headers, name="Sort School", code="LSTS")
    plan = _plan(v1_client, headers, "Sort Plan")
    first = _assign(v1_client, headers, school["id"], plan["id"], end_date="2026-05-01")
    second = _assign(v1_client, headers, school["id"], plan["id"], end_date="2026-05-01")
    third = _assign(v1_client, headers, school["id"], plan["id"], end_date="2026-08-01")
    rows = {
        first["id"]: v1_db.get(Subscription, first["id"]),
        second["id"]: v1_db.get(Subscription, second["id"]),
        third["id"]: v1_db.get(Subscription, third["id"]),
    }
    assert all(rows.values())
    rows[first["id"]].created_at = datetime(2026, 2, 1, 0, 0, 0)
    rows[second["id"]].created_at = datetime(2026, 4, 1, 0, 0, 0)
    rows[third["id"]].created_at = None
    v1_db.commit()

    def ids(params: dict) -> list[int]:
        res = v1_client.get(LIST_PATH, headers=headers, params=params)
        assert res.status_code == 200, res.text
        return [item["id"] for item in res.json()["items"]]

    assert ids({"sort": "end_date"}) == [first["id"], second["id"], third["id"]]
    assert ids({"sort": "-end_date"}) == [third["id"], second["id"], first["id"]]
    assert ids({}) == [first["id"], second["id"], third["id"]]
    assert ids({"sort": "created_at"}) == [first["id"], second["id"], third["id"]]
    assert ids({"sort": "-created_at"}) == [second["id"], first["id"], third["id"]]


def test_platform_list_invalid_query(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "list-invalid@eschool.com")
    for params in (
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
        {"status": 4},
        {"sort": "name"},
    ):
        res = v1_client.get(LIST_PATH, headers=headers, params=params)
        assert res.status_code == 422, (params, res.text)
