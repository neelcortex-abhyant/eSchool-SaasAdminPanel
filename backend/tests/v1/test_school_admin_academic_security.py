"""Phase 9: auth, RBAC, and tenant isolation for School Admin academic APIs."""

from __future__ import annotations

from sqlalchemy import select

from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User

DIRECT = {
    "classes": "/api/v1/school-admin/classes",
    "sections": "/api/v1/school-admin/sections",
    "subjects": "/api/v1/school-admin/subjects",
    "assignments": "/api/v1/school-admin/teacher-assignments",
    "sessions_compact": "/api/v1/school-admin/sessions",
}
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


def _school(client, sa, code: str) -> int:
    res = client.post(
        "/api/v1/super-admin/schools",
        headers=sa,
        json={"name": f"School {code}", "code": code},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _admin(client, sa, school_id: int, email: str, roles: list[str] | None = None) -> dict[str, str]:
    created = client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=sa,
        json={"email": email, "password": "adminpass1", "first_name": "S", "last_name": "A"},
    )
    assert created.status_code == 201, created.text
    if roles is not None:
        patched = client.patch(
            f"/api/v1/super-admin/schools/{school_id}/admins/{created.json()['id']}/roles",
            headers=sa,
            json={"roles": roles},
        )
        assert patched.status_code == 200, patched.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "adminpass1"})
    assert login.status_code == 200, login.text
    return _auth(login.json()["access_token"])


def _seed_class(client, headers):
    medium = client.post(f"{ACADEMICS}/mediums", headers=headers, json={"name": "English"})
    assert medium.status_code == 201, medium.text
    klass = client.post(
        DIRECT["classes"],
        headers=headers,
        json={"name": "Grade 1", "medium_id": medium.json()["id"]},
    )
    assert klass.status_code == 201, klass.text
    return {"medium_id": medium.json()["id"], "class_id": klass.json()["id"]}


def test_unauthenticated_academic_routes_return_401(v1_client):
    paths = [
        DIRECT["classes"],
        DIRECT["sections"],
        DIRECT["subjects"],
        DIRECT["assignments"],
        DIRECT["sessions_compact"],
        f"{ACADEMICS}/sessions",
        f"{ACADEMICS}/classes",
        f"{ACADEMICS}/summary",
    ]
    for path in paths:
        assert v1_client.get(path).status_code == 401, path
        assert v1_client.post(path, json={}).status_code in {401, 405}, path


def test_accounts_admin_cannot_write_structure_or_assignments(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "sec9-sa@eschool.com")
    school_id = _school(v1_client, sa, "SEC9A")
    full = _admin(v1_client, sa, school_id, "sec9-full@eschool.com")
    accounts = _admin(v1_client, sa, school_id, "sec9-acc@eschool.com", ["accounts_admin"])
    ids = _seed_class(v1_client, full)

    assert v1_client.get(DIRECT["classes"], headers=accounts).status_code == 200
    assert (
        v1_client.post(
            DIRECT["classes"],
            headers=accounts,
            json={"name": "X", "medium_id": ids["medium_id"]},
        ).status_code
        == 403
    )
    assert (
        v1_client.post(
            f"{ACADEMICS}/sessions",
            headers=accounts,
            json={"name": "Y", "start_date": "2026-04-01", "end_date": "2027-03-31"},
        ).status_code
        == 403
    )
    assert v1_client.get(DIRECT["assignments"], headers=accounts).status_code == 403


def test_forged_school_id_rejected_on_direct_and_academics(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "sec9-forge-sa@eschool.com")
    school_id = _school(v1_client, sa, "SEC9F")
    admin = _admin(v1_client, sa, school_id, "sec9-forge@eschool.com")
    ids = _seed_class(v1_client, admin)

    forged_direct = v1_client.post(
        DIRECT["classes"],
        headers=admin,
        json={"name": "Hijack", "medium_id": ids["medium_id"], "school_id": school_id + 99},
    )
    assert forged_direct.status_code == 422

    forged_academics = v1_client.post(
        f"{ACADEMICS}/mediums",
        headers=admin,
        json={"name": "Hindi", "school_id": school_id + 99},
    )
    assert forged_academics.status_code == 422


def test_cross_school_isolation_list_detail_update_filter(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "sec9-iso-sa@eschool.com")
    school_a = _school(v1_client, sa, "SEC9X")
    school_b = _school(v1_client, sa, "SEC9Y")
    admin_a = _admin(v1_client, sa, school_a, "sec9-a@eschool.com")
    admin_b = _admin(v1_client, sa, school_b, "sec9-b@eschool.com")
    ids_a = _seed_class(v1_client, admin_a)
    ids_b = _seed_class(v1_client, admin_b)

    class_a = ids_a["class_id"]
    class_b = ids_b["class_id"]

    listed_b = v1_client.get(DIRECT["classes"], headers=admin_b)
    assert listed_b.status_code == 200
    assert class_a not in {item["id"] for item in listed_b.json()["items"]}
    assert class_b in {item["id"] for item in listed_b.json()["items"]}

    assert v1_client.get(f"{DIRECT['classes']}/{class_a}", headers=admin_b).status_code == 404
    assert (
        v1_client.patch(
            f"{DIRECT['classes']}/{class_a}", headers=admin_b, json={"name": "Stolen"}
        ).status_code
        == 404
    )
    assert (
        v1_client.patch(
            f"{ACADEMICS}/classes/{class_a}", headers=admin_b, json={"name": "Stolen"}
        ).status_code
        == 404
    )

    # Foreign medium filter must not return empty-success for another school's medium.
    assert (
        v1_client.get(
            DIRECT["classes"], headers=admin_a, params={"medium_id": ids_b["medium_id"]}
        ).status_code
        == 404
    )
    assert (
        v1_client.get(
            f"{ACADEMICS}/classes", headers=admin_a, params={"medium_id": ids_b["medium_id"]}
        ).status_code
        == 404
    )

    # Cross-school reference on create.
    assert (
        v1_client.post(
            DIRECT["classes"],
            headers=admin_a,
            json={"name": "Bad", "medium_id": ids_b["medium_id"]},
        ).status_code
        == 422
    )


def test_academic_admin_can_manage_assignments_not_structure(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "sec9-acad-sa@eschool.com")
    school_id = _school(v1_client, sa, "SEC9C")
    full = _admin(v1_client, sa, school_id, "sec9-c-full@eschool.com")
    academic = _admin(v1_client, sa, school_id, "sec9-c-acad@eschool.com", ["academic_admin"])
    ids = _seed_class(v1_client, full)

    assert v1_client.get(DIRECT["classes"], headers=academic).status_code == 200
    assert (
        v1_client.post(
            DIRECT["classes"],
            headers=academic,
            json={"name": "Nope", "medium_id": ids["medium_id"]},
        ).status_code
        == 403
    )
    assert v1_client.get(DIRECT["assignments"], headers=academic).status_code == 200


def test_error_bodies_are_safe_strings(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "sec9-err-sa@eschool.com")
    school_id = _school(v1_client, sa, "SEC9E")
    admin = _admin(v1_client, sa, school_id, "sec9-err@eschool.com")
    ids = _seed_class(v1_client, admin)
    first = v1_client.post(
        DIRECT["classes"],
        headers=admin,
        json={"name": "Dup", "medium_id": ids["medium_id"]},
    )
    assert first.status_code == 201
    dup = v1_client.post(
        DIRECT["classes"],
        headers=admin,
        json={"name": "Dup", "medium_id": ids["medium_id"]},
    )
    assert dup.status_code == 409
    detail = dup.json()["detail"]
    assert isinstance(detail, str)
    assert "duplicate key" not in detail.lower()
    assert "integrity" not in detail.lower()
    assert "sql" not in detail.lower()
