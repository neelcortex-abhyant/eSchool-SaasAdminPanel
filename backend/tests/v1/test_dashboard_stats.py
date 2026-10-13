"""Super Admin dashboard statistics."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.models.tables import USER_MODEL, ModelHasRole, Role, Student, Subscription, User
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
            "first_name": "Dash",
            "last_name": "Stats",
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


def _legacy_user(v1_db, *, school_id: int, email: str, deleted_at: datetime | None = None) -> User:
    user = User(
        first_name="Ada",
        last_name="Teacher",
        email=email,
        password=hash_password("secret"),
        status=1,
        school_id=school_id,
        deleted_at=deleted_at,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    v1_db.add(user)
    v1_db.flush()
    return user


def _assign_teacher(v1_db, user: User) -> None:
    role = v1_db.scalar(
        select(Role).where(Role.school_id == user.school_id, Role.name == "Teacher", Role.guard_name == "web")
    )
    if role is None:
        role = Role(
            name="Teacher",
            guard_name="web",
            school_id=user.school_id,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        v1_db.add(role)
        v1_db.flush()
    v1_db.add(ModelHasRole(role_id=role.id, model_type=USER_MODEL, model_id=user.id))
    v1_db.commit()


def _add_student(v1_db, *, school_id: int, user_id: int, deleted_at: datetime | None = None) -> None:
    v1_db.add(
        Student(
            user_id=user_id,
            class_section_id=1,
            admission_no=f"ADM-{user_id}",
            roll_number=1,
            admission_date=date(2026, 4, 1),
            school_id=school_id,
            guardian_id=user_id,
            session_year_id=1,
            deleted_at=deleted_at,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    v1_db.commit()


def test_dashboard_stats_requires_super_admin(v1_client, v1_db):
    assert v1_client.get("/api/v1/super-admin/dashboard/stats").status_code == 401
    signup = _signup(v1_client, "stats-user@eschool.com")
    assert signup.status_code == 201
    forbidden = v1_client.get(
        "/api/v1/super-admin/dashboard/stats",
        headers=_auth_header(signup.json()["access_token"]),
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Forbidden"


def test_dashboard_stats_zero_when_empty(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="stats-empty-sa@eschool.com")
    stats = v1_client.get("/api/v1/super-admin/dashboard/stats", headers=headers)
    assert stats.status_code == 200
    assert stats.json() == {
        "total_schools": 0,
        "active_schools": 0,
        "inactive_schools": 0,
        "total_students": 0,
        "total_teachers": 0,
        "active_subscriptions": 0,
    }
    existing = v1_client.get("/api/v1/super-admin/dashboard", headers=headers)
    assert existing.status_code == 200
    assert "schools" in existing.json()
    assert "total_schools" not in existing.json()


def test_dashboard_stats_counts_and_skips_deleted_records(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="stats-count-sa@eschool.com")
    active = _create_school(v1_client, headers, name="Active Stats", code="STATA")
    inactive = _create_school(v1_client, headers, name="Inactive Stats", code="STATI")
    removed = _create_school(v1_client, headers, name="Removed Stats", code="STATR")
    assert (
        v1_client.post(
            f"/api/v1/super-admin/schools/{inactive['id']}/suspend",
            headers=headers,
        ).status_code
        == 200
    )
    assert v1_client.delete(f"/api/v1/super-admin/schools/{removed['id']}", headers=headers).status_code == 200

    plan = v1_client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": "Stats Plan", "monthly_price": 10, "yearly_price": 100},
    )
    assert plan.status_code == 201
    package_id = plan.json()["id"]
    active_sub = v1_client.post(
        f"/api/v1/super-admin/schools/{active['id']}/subscriptions",
        headers=headers,
        json={
            "package_id": package_id,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "cycle": "monthly",
            "status": 1,
        },
    )
    assert active_sub.status_code == 201
    inactive_sub = v1_client.post(
        f"/api/v1/super-admin/schools/{inactive['id']}/subscriptions",
        headers=headers,
        json={
            "package_id": package_id,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "cycle": "monthly",
            "status": 0,
        },
    )
    assert inactive_sub.status_code == 201
    removed_sub = Subscription(
        school_id=removed["id"],
        package_id=package_id,
        status=1,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        cycle="monthly",
        auto_renew=0,
        deleted_at=datetime.now(timezone.utc).replace(tzinfo=None),
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    v1_db.add(removed_sub)
    v1_db.commit()

    teacher = _legacy_user(v1_db, school_id=active["id"], email="teacher-live@eschool.com")
    _assign_teacher(v1_db, teacher)
    other_role_user = _legacy_user(v1_db, school_id=active["id"], email="clerk-live@eschool.com")
    clerk = Role(
        name="Clerk",
        guard_name="web",
        school_id=active["id"],
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    v1_db.add(clerk)
    v1_db.flush()
    v1_db.add(ModelHasRole(role_id=clerk.id, model_type=USER_MODEL, model_id=other_role_user.id))
    deleted_teacher = _legacy_user(
        v1_db,
        school_id=active["id"],
        email="teacher-gone@eschool.com",
        deleted_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    _assign_teacher(v1_db, deleted_teacher)
    removed_school_teacher = _legacy_user(v1_db, school_id=removed["id"], email="teacher-removed@eschool.com")
    _assign_teacher(v1_db, removed_school_teacher)

    _add_student(v1_db, school_id=active["id"], user_id=teacher.id)
    _add_student(
        v1_db,
        school_id=active["id"],
        user_id=other_role_user.id,
        deleted_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    _add_student(v1_db, school_id=removed["id"], user_id=removed_school_teacher.id)

    stats = v1_client.get("/api/v1/super-admin/dashboard/stats", headers=headers)
    assert stats.status_code == 200
    assert stats.json() == {
        "total_schools": 2,
        "active_schools": 1,
        "inactive_schools": 1,
        "total_students": 1,
        "total_teachers": 1,
        "active_subscriptions": 1,
    }
