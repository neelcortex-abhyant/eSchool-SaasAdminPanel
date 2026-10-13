"""Super Admin recent schools."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select

from app.models.tables import School, Subscription
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User as V1User

_ITEM_KEYS = {
    "id",
    "name",
    "code",
    "created_at",
    "status",
    "installed",
    "package_id",
    "plan_name",
}
_SECRET_EMAIL = "hidden-recent@eschool.com"
_SECRET_PHONE = "9000001111"
_SECRET_ADDRESS = "Hidden Recent Address"
_SECRET_DATABASE = "hidden_recent_database"


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str):
    return client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "secret123",
            "first_name": "Recent",
            "last_name": "Schools",
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


def _create_school(client, headers, *, name: str, code: str, **extra) -> dict:
    created = client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": name, "code": code, "support_email": f"{code.lower()}@eschool.com", **extra},
    )
    assert created.status_code == 201
    return created.json()


def _set_created_at(v1_db, school_id: int, created_at: datetime | None) -> None:
    school = v1_db.get(School, school_id)
    assert school is not None
    school.created_at = created_at
    v1_db.commit()


def _add_subscription(
    v1_db,
    *,
    school_id: int,
    package_id: int,
    status: int = 1,
    deleted: bool = False,
) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    v1_db.add(
        Subscription(
            school_id=school_id,
            package_id=package_id,
            status=status,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            cycle="monthly",
            auto_renew=0,
            deleted_at=now if deleted else None,
            created_at=now,
            updated_at=now,
        )
    )
    v1_db.commit()


def test_recent_schools_requires_super_admin(v1_client, v1_db):
    assert v1_client.get("/api/v1/super-admin/dashboard/recent-schools").status_code == 401
    signup = _signup(v1_client, "recent-user@eschool.com")
    assert signup.status_code == 201
    forbidden = v1_client.get(
        "/api/v1/super-admin/dashboard/recent-schools",
        headers=_auth_header(signup.json()["access_token"]),
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Forbidden"


def test_recent_schools_empty(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="recent-empty-sa@eschool.com")
    response = v1_client.get("/api/v1/super-admin/dashboard/recent-schools", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"items": [], "limit": 10}


def test_recent_schools_order_deleted_and_limits(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="recent-order-sa@eschool.com")
    older = _create_school(v1_client, headers, name="Older School", code="RCOLD")
    null_low = _create_school(v1_client, headers, name="Null Low", code="RCNULL")
    newest = _create_school(v1_client, headers, name="Newest School", code="RCNEW")
    middle = _create_school(v1_client, headers, name="Middle School", code="RCMID")
    null_high = _create_school(v1_client, headers, name="Null High", code="RCNUL2")
    removed = _create_school(
        v1_client,
        headers,
        name="Removed School",
        code="RCDEL",
        address=_SECRET_ADDRESS,
        support_phone=_SECRET_PHONE,
        support_email=_SECRET_EMAIL,
    )
    _set_created_at(v1_db, older["id"], datetime(2026, 1, 1, 12, 0, 0))
    _set_created_at(v1_db, null_low["id"], None)
    _set_created_at(v1_db, newest["id"], datetime(2026, 10, 10, 12, 0, 0))
    _set_created_at(v1_db, middle["id"], datetime(2026, 6, 1, 12, 0, 0))
    _set_created_at(v1_db, null_high["id"], None)
    _set_created_at(v1_db, removed["id"], datetime(2099, 1, 1, 12, 0, 0))
    removed_row = v1_db.get(School, removed["id"])
    assert removed_row is not None
    removed_row.database_name = _SECRET_DATABASE
    v1_db.commit()
    assert v1_client.delete(f"/api/v1/super-admin/schools/{removed['id']}", headers=headers).status_code == 200

    expected_ids = [newest["id"], middle["id"], older["id"], null_high["id"], null_low["id"]]
    default = v1_client.get("/api/v1/super-admin/dashboard/recent-schools", headers=headers)
    assert default.status_code == 200
    body = default.json()
    assert body["limit"] == 10
    assert [item["id"] for item in body["items"]] == expected_ids
    assert body["items"][0]["created_at"] == "2026-10-10T12:00:00"
    assert body["items"][3]["created_at"] is None
    assert body["items"][4]["created_at"] is None
    assert all(set(item) == _ITEM_KEYS for item in body["items"])
    raw = default.text
    assert _SECRET_EMAIL not in raw
    assert _SECRET_PHONE not in raw
    assert _SECRET_ADDRESS not in raw
    assert _SECRET_DATABASE not in raw

    one = v1_client.get("/api/v1/super-admin/dashboard/recent-schools?limit=1", headers=headers)
    assert one.status_code == 200
    assert one.json()["limit"] == 1
    assert [item["id"] for item in one.json()["items"]] == [newest["id"]]

    wide = v1_client.get("/api/v1/super-admin/dashboard/recent-schools?limit=50", headers=headers)
    assert wide.status_code == 200
    assert wide.json()["limit"] == 50
    assert [item["id"] for item in wide.json()["items"]] == expected_ids


def test_recent_schools_invalid_limit(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="recent-limit-sa@eschool.com")
    for value in ("0", "51", "-1", "abc"):
        response = v1_client.get(
            f"/api/v1/super-admin/dashboard/recent-schools?limit={value}",
            headers=headers,
        )
        assert response.status_code == 422


def test_recent_schools_plan_fields(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="recent-plan-sa@eschool.com")
    none_school = _create_school(v1_client, headers, name="No Plan", code="RCPL0")
    one_school = _create_school(v1_client, headers, name="One Plan", code="RCPL1")
    many_school = _create_school(v1_client, headers, name="Many Plans", code="RCPL2")
    _set_created_at(v1_db, many_school["id"], datetime(2026, 10, 3, 12, 0, 0))
    _set_created_at(v1_db, one_school["id"], datetime(2026, 10, 2, 12, 0, 0))
    _set_created_at(v1_db, none_school["id"], datetime(2026, 10, 1, 12, 0, 0))

    gold = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": "Gold Plan", "monthly_price": 10, "yearly_price": 100},
    )
    silver = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": "Silver Plan", "monthly_price": 5, "yearly_price": 50},
    )
    assert gold.status_code == 201
    assert silver.status_code == 201
    gold_id = gold.json()["id"]
    silver_id = silver.json()["id"]

    _add_subscription(v1_db, school_id=none_school["id"], package_id=gold_id, status=0)
    _add_subscription(v1_db, school_id=one_school["id"], package_id=gold_id, status=1)
    _add_subscription(v1_db, school_id=one_school["id"], package_id=silver_id, status=1, deleted=True)
    _add_subscription(v1_db, school_id=many_school["id"], package_id=gold_id, status=1)
    _add_subscription(v1_db, school_id=many_school["id"], package_id=silver_id, status=1)

    response = v1_client.get("/api/v1/super-admin/dashboard/recent-schools", headers=headers)
    assert response.status_code == 200
    by_id = {item["id"]: item for item in response.json()["items"]}
    assert by_id[none_school["id"]]["package_id"] is None
    assert by_id[none_school["id"]]["plan_name"] is None
    assert by_id[one_school["id"]]["package_id"] == gold_id
    assert by_id[one_school["id"]]["plan_name"] == "Gold Plan"
    assert by_id[many_school["id"]]["package_id"] is None
    assert by_id[many_school["id"]]["plan_name"] is None
    assert all(set(item) == _ITEM_KEYS for item in response.json()["items"])
