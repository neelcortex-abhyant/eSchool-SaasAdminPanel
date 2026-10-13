"""Super Admin subscription distribution."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select

from app.models.tables import Package, Subscription
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
            "first_name": "Plan",
            "last_name": "Chart",
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


def _create_plan(client, headers, *, name: str) -> dict:
    created = client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": name, "monthly_price": 10, "yearly_price": 100},
    )
    assert created.status_code == 201
    return created.json()


def _add_subscription(
    v1_db,
    *,
    school_id: int,
    package_id: int,
    status: int = 1,
    deleted: bool = False,
    end_date: date = date(2026, 12, 31),
) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    v1_db.add(
        Subscription(
            school_id=school_id,
            package_id=package_id,
            status=status,
            start_date=date(2020, 1, 1),
            end_date=end_date,
            cycle="monthly",
            auto_renew=0,
            deleted_at=now if deleted else None,
            created_at=now,
            updated_at=now,
        )
    )
    v1_db.commit()


def test_subscription_distribution_requires_super_admin(v1_client, v1_db):
    assert v1_client.get("/api/v1/super-admin/dashboard/subscriptions").status_code == 401
    signup = _signup(v1_client, "subdist-user@eschool.com")
    assert signup.status_code == 201
    forbidden = v1_client.get(
        "/api/v1/super-admin/dashboard/subscriptions",
        headers=_auth_header(signup.json()["access_token"]),
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Forbidden"


def test_subscription_distribution_empty(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="subdist-empty-sa@eschool.com")
    response = v1_client.get("/api/v1/super-admin/dashboard/subscriptions", headers=headers)
    assert response.status_code == 200
    assert response.json() == {
        "by_plan": [],
        "schools_with_active_subscription": 0,
        "schools_without_active_subscription": 0,
    }


def test_subscription_distribution_counts(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="subdist-count-sa@eschool.com")
    basic = _create_plan(v1_client, headers, name="Basic")
    unnamed = _create_plan(v1_client, headers, name="Placeholder")
    retired = _create_plan(v1_client, headers, name="Retired Plan")
    unnamed_row = v1_db.get(Package, unnamed["id"])
    retired_row = v1_db.get(Package, retired["id"])
    assert unnamed_row is not None and retired_row is not None
    unnamed_row.name = None
    retired_row.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    v1_db.commit()

    duplicate = _create_school(v1_client, headers, name="Duplicate Rows", code="SDDUP")
    past_end = _create_school(v1_client, headers, name="Past End", code="SDEND")
    null_plan = _create_school(v1_client, headers, name="Null Plan Name", code="SDNUL")
    retired_school = _create_school(v1_client, headers, name="Retired Plan School", code="SDRET")
    removed = _create_school(v1_client, headers, name="Removed School", code="SDDEL")
    bare = _create_school(v1_client, headers, name="No Subscription", code="SDBARE")
    inactive = _create_school(v1_client, headers, name="Inactive Subscription", code="SDINA")
    dropped = _create_school(v1_client, headers, name="Deleted Subscription", code="SDDRP")

    _add_subscription(v1_db, school_id=duplicate["id"], package_id=basic["id"])
    _add_subscription(v1_db, school_id=duplicate["id"], package_id=basic["id"])
    _add_subscription(
        v1_db,
        school_id=past_end["id"],
        package_id=basic["id"],
        end_date=date(2020, 1, 31),
    )
    _add_subscription(v1_db, school_id=null_plan["id"], package_id=unnamed["id"])
    _add_subscription(v1_db, school_id=retired_school["id"], package_id=retired["id"])
    _add_subscription(v1_db, school_id=removed["id"], package_id=basic["id"])
    _add_subscription(v1_db, school_id=inactive["id"], package_id=basic["id"], status=0)
    _add_subscription(v1_db, school_id=dropped["id"], package_id=basic["id"], deleted=True)
    assert v1_client.delete(f"/api/v1/super-admin/schools/{removed['id']}", headers=headers).status_code == 200

    response = v1_client.get("/api/v1/super-admin/dashboard/subscriptions", headers=headers)
    stats = v1_client.get("/api/v1/super-admin/dashboard/stats", headers=headers)
    assert response.status_code == 200
    assert stats.status_code == 200
    body = response.json()
    by_plan = {item["package_id"]: item for item in body["by_plan"]}
    assert list(by_plan) == sorted(by_plan)
    assert len(by_plan) == len(body["by_plan"]) == 3
    assert by_plan[basic["id"]] == {"package_id": basic["id"], "plan_name": "Basic", "school_count": 2}
    assert by_plan[unnamed["id"]] == {"package_id": unnamed["id"], "plan_name": None, "school_count": 1}
    assert by_plan[retired["id"]] == {
        "package_id": retired["id"],
        "plan_name": "Retired Plan",
        "school_count": 1,
    }
    assert body["schools_with_active_subscription"] == 4
    assert body["schools_without_active_subscription"] == 3
    assert bare["id"] not in by_plan
    # Stats counts qualifying rows, including the duplicate and the deleted school's row.
    assert stats.json()["active_subscriptions"] == 6
    assert sum(item["school_count"] for item in body["by_plan"]) == 4


def test_subscription_distribution_counts_one_school_on_two_plans(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="subdist-two-sa@eschool.com")
    basic = _create_plan(v1_client, headers, name="Basic Two")
    gold = _create_plan(v1_client, headers, name="Gold Two")
    both = _create_school(v1_client, headers, name="Two Plans", code="SDTWO")
    _create_school(v1_client, headers, name="Unsubscribed", code="SDNON")
    _add_subscription(v1_db, school_id=both["id"], package_id=basic["id"])
    _add_subscription(v1_db, school_id=both["id"], package_id=gold["id"])

    response = v1_client.get("/api/v1/super-admin/dashboard/subscriptions", headers=headers)
    stats = v1_client.get("/api/v1/super-admin/dashboard/stats", headers=headers)
    assert response.status_code == 200
    assert stats.status_code == 200
    body = response.json()
    by_plan = {item["package_id"]: item for item in body["by_plan"]}
    assert len(by_plan) == 2
    assert by_plan[basic["id"]]["school_count"] == 1
    assert by_plan[gold["id"]]["school_count"] == 1
    assert body["schools_with_active_subscription"] == 1
    assert body["schools_without_active_subscription"] == 1
    assert stats.json()["active_subscriptions"] == 2
