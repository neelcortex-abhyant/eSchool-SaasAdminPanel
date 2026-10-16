"""One school activation at a time. A later activation cancels the earlier active row."""

from __future__ import annotations

from datetime import date
from threading import Barrier, Thread

from sqlalchemy import select

from app.core.database import session_factory
from app.models.tables import Subscription
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User
from app.services.v1.subscription_service import create_subscription, set_subscription_status


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _super_admin_headers(client, v1_db, email: str) -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "secret123",
            "first_name": "Active",
            "last_name": "One",
        },
    )
    assert res.status_code == 201, res.text
    user = v1_db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200, login.text
    return _auth_header(login.json()["access_token"])


def _school_and_plan(client, headers, code: str) -> tuple[int, int]:
    school = client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": f"School {code}", "code": code},
    )
    assert school.status_code == 201, school.text
    plan = client.post(
        "/api/v1/super-admin/plans",
        headers=headers,
        json={"name": f"Plan {code}", "monthly_price": 10, "yearly_price": 100},
    )
    assert plan.status_code == 201, plan.text
    activated = client.patch(
        f"/api/v1/super-admin/plans/{plan.json()['id']}/status",
        headers=headers,
        json={"status": 1},
    )
    assert activated.status_code == 200, activated.text
    return school.json()["id"], plan.json()["id"]


def _active_ids(v1_db, school_id: int) -> list[int]:
    v1_db.expire_all()
    rows = v1_db.scalars(
        select(Subscription).where(
            Subscription.school_id == school_id,
            Subscription.deleted_at.is_(None),
        )
    ).all()
    return [row.id for row in rows if row.status == 1]


def test_second_assignment_cancels_the_previous_active(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "one-active-seq@eschool.com")
    school_id, plan_id = _school_and_plan(v1_client, headers, "ONESEQ")
    base = f"/api/v1/super-admin/schools/{school_id}/subscriptions"
    body = {
        "package_id": plan_id,
        "start_date": "2026-01-01",
        "end_date": "2026-06-30",
        "cycle": "monthly",
        "status": 1,
    }
    first = v1_client.post(base, headers=headers, json=body)
    second = v1_client.post(base, headers=headers, json={**body, "end_date": "2026-08-31"})
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert _active_ids(v1_db, school_id) == [second.json()["id"]]
    v1_db.expire_all()
    previous = v1_db.get(Subscription, first.json()["id"])
    assert previous is not None and previous.status == 3


def _run_pair(calls) -> list[BaseException]:
    barrier = Barrier(2)
    errors: list[BaseException] = []

    def run(fn) -> None:
        db = session_factory()()
        try:
            barrier.wait(timeout=30)
            fn(db)
        except BaseException as exc:  # noqa: BLE001 — reported by the assertion
            errors.append(exc)
        finally:
            db.close()

    threads = [Thread(target=run, args=(fn,)) for fn in calls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    return errors


def test_concurrent_creates_leave_one_active(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "one-active-create@eschool.com")
    school_id, plan_id = _school_and_plan(v1_client, headers, "ONECRE")

    def make(end: date):
        def fn(db) -> None:
            create_subscription(
                db,
                school_id,
                package_id=plan_id,
                start_date=date(2026, 1, 1),
                end_date=end,
                status=1,
            )

        return fn

    errors = _run_pair([make(date(2026, 6, 30)), make(date(2026, 8, 31))])
    assert errors == []
    assert len(_active_ids(v1_db, school_id)) == 1


def test_concurrent_status_activation_leaves_one_active(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, "one-active-status@eschool.com")
    school_id, plan_id = _school_and_plan(v1_client, headers, "ONESTA")
    base = f"/api/v1/super-admin/schools/{school_id}/subscriptions"
    body = {
        "package_id": plan_id,
        "start_date": "2026-01-01",
        "end_date": "2026-06-30",
        "cycle": "monthly",
        "status": 0,
    }
    first = v1_client.post(base, headers=headers, json=body)
    second = v1_client.post(base, headers=headers, json={**body, "end_date": "2026-09-30"})
    assert first.status_code == 201 and second.status_code == 201
    ids = [first.json()["id"], second.json()["id"]]

    def activate(subscription_id: int):
        def fn(db) -> None:
            set_subscription_status(db, school_id, subscription_id, status=1)

        return fn

    errors = _run_pair([activate(ids[0]), activate(ids[1])])
    assert errors == []
    assert len(_active_ids(v1_db, school_id)) == 1
