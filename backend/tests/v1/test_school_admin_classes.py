"""Phase 4: direct /api/v1/school-admin/classes management."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.routing import APIRoute
from sqlalchemy import select

from app.main import app
from app.models.tables import SchoolClass
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User

CLASSES = "/api/v1/school-admin/classes"
ACADEMICS = "/api/v1/school-admin/academics"
SESSIONS_COMPACT = "/api/v1/school-admin/sessions"


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


def _school_admin(client, sa_headers, school_id: int, email: str, password: str = "adminpass1") -> dict[str, str]:
    created = client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=sa_headers,
        json={"email": email, "password": password, "first_name": "School", "last_name": "Admin"},
    )
    assert created.status_code == 201, created.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
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


def _medium(client, headers, name: str = "English") -> int:
    res = client.post(f"{ACADEMICS}/mediums", headers=headers, json={"name": name})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_class_crud_search_pagination_and_detail(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "cls-sa@eschool.com")
    school_id = _school(v1_client, sa, "CLS01")
    admin = _school_admin(v1_client, sa, school_id, "cls-admin@eschool.com")
    medium_id = _medium(v1_client, admin)
    other_medium = _medium(v1_client, admin, "Hindi")

    assert (
        v1_client.post(CLASSES, headers=admin, json={"name": "  ", "medium_id": medium_id}).status_code
        == 422
    )
    assert v1_client.post(CLASSES, headers=admin, json={"name": "Grade 1"}).status_code == 422

    created = v1_client.post(
        CLASSES,
        headers=admin,
        json={"name": "  Grade 1  ", "medium_id": medium_id, "include_semesters": 0},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "Grade 1"
    assert body["medium_id"] == medium_id
    assert body["include_semesters"] == 0
    class_id = body["id"]

    # Same name + medium → 409; same name other medium → ok.
    assert (
        v1_client.post(
            CLASSES, headers=admin, json={"name": "grade 1", "medium_id": medium_id}
        ).status_code
        == 409
    )
    other = v1_client.post(
        CLASSES, headers=admin, json={"name": "Grade 1", "medium_id": other_medium}
    )
    assert other.status_code == 201, other.text

    second = v1_client.post(
        CLASSES, headers=admin, json={"name": "Grade 2", "medium_id": medium_id}
    )
    assert second.status_code == 201, second.text

    listed = v1_client.get(CLASSES, headers=admin, params={"q": "Grade", "page": 1, "page_size": 10})
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    assert set(payload.keys()) == {"items", "total", "page", "page_size"}
    assert payload["total"] == 3
    assert all("medium_id" in item for item in payload["items"])

    filtered = v1_client.get(CLASSES, headers=admin, params={"medium_id": medium_id})
    assert filtered.status_code == 200
    assert {item["id"] for item in filtered.json()["items"]} == {class_id, second.json()["id"]}

    section = v1_client.post(f"{ACADEMICS}/sections", headers=admin, json={"name": "A"})
    assert section.status_code == 201
    linked = v1_client.post(
        f"{ACADEMICS}/class-sections",
        headers=admin,
        json={"class_id": class_id, "section_id": section.json()["id"], "medium_id": medium_id},
    )
    assert linked.status_code == 201, linked.text
    subject = v1_client.post(
        f"{ACADEMICS}/subjects",
        headers=admin,
        json={"name": "Math", "medium_id": medium_id, "code": "M1"},
    )
    assert subject.status_code == 201
    mapped = v1_client.post(
        f"{ACADEMICS}/class-subjects",
        headers=admin,
        json={"class_id": class_id, "subject_id": subject.json()["id"]},
    )
    assert mapped.status_code == 201, mapped.text

    detail = v1_client.get(f"{CLASSES}/{class_id}", headers=admin)
    assert detail.status_code == 200, detail.text
    detail_body = detail.json()
    assert detail_body["id"] == class_id
    assert detail_body["name"] == "Grade 1"
    assert len(detail_body["sections"]) == 1
    assert detail_body["sections"][0]["section_name"] == "A"
    assert len(detail_body["subjects"]) == 1
    assert detail_body["subjects"][0]["subject_name"] == "Math"

    patched = v1_client.patch(
        f"{CLASSES}/{class_id}",
        headers=admin,
        json={"name": "Grade One", "include_semesters": 1},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["name"] == "Grade One"
    assert patched.json()["include_semesters"] == 1
    assert patched.json()["medium_id"] == medium_id

    # Partial omit preserves medium; name clash with Grade 2 under same medium.
    clash = v1_client.patch(
        f"{CLASSES}/{class_id}",
        headers=admin,
        json={"name": "Grade 2"},
    )
    assert clash.status_code == 409

    # Soft-deleted excluded from list; detail 404.
    row = v1_db.get(SchoolClass, class_id)
    assert row is not None
    row.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    v1_db.commit()
    assert class_id not in {
        item["id"] for item in v1_client.get(CLASSES, headers=admin).json()["items"]
    }
    assert v1_client.get(f"{CLASSES}/{class_id}", headers=admin).status_code == 404
    # Soft-deleted name may be reused.
    reused = v1_client.post(
        CLASSES, headers=admin, json={"name": "Grade One", "medium_id": medium_id}
    )
    assert reused.status_code == 201, reused.text


def test_class_cross_school_and_invalid_medium(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "cls-x-sa@eschool.com")
    school_a = _school(v1_client, sa, "CLSA")
    school_b = _school(v1_client, sa, "CLSB")
    admin_a = _school_admin(v1_client, sa, school_a, "cls-a@eschool.com")
    admin_b = _school_admin(v1_client, sa, school_b, "cls-b@eschool.com")
    medium_a = _medium(v1_client, admin_a)
    medium_b = _medium(v1_client, admin_b)

    created = v1_client.post(
        CLASSES, headers=admin_a, json={"name": "Mine", "medium_id": medium_a}
    )
    assert created.status_code == 201
    class_id = created.json()["id"]

    assert (
        v1_client.post(
            CLASSES, headers=admin_a, json={"name": "Bad", "medium_id": medium_b}
        ).status_code
        == 422
    )
    assert v1_client.get(f"{CLASSES}/{class_id}", headers=admin_b).status_code == 404
    assert (
        v1_client.patch(
            f"{CLASSES}/{class_id}", headers=admin_b, json={"name": "Hijack"}
        ).status_code
        == 404
    )
    assert class_id not in {
        item["id"] for item in v1_client.get(CLASSES, headers=admin_b).json()["items"]
    }


def test_class_write_permission_and_academics_compat(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "cls-perm-sa@eschool.com")
    school_id = _school(v1_client, sa, "CLSP")
    full = _school_admin(v1_client, sa, school_id, "cls-full@eschool.com")
    medium_id = _medium(v1_client, full)

    # Academic admin: dashboard.view yes, school.manage no (roles assigned after create).
    created_admin = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=sa,
        json={
            "email": "cls-academic@eschool.com",
            "password": "adminpass1",
            "first_name": "Acad",
            "last_name": "Admin",
        },
    )
    assert created_admin.status_code == 201, created_admin.text
    admin_id = created_admin.json()["id"]
    roles = v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}/admins/{admin_id}/roles",
        headers=sa,
        json={"roles": ["academic_admin"]},
    )
    assert roles.status_code == 200, roles.text
    login = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "cls-academic@eschool.com", "password": "adminpass1"},
    )
    assert login.status_code == 200
    academic = _auth(login.json()["access_token"])

    assert v1_client.get(CLASSES, headers=academic).status_code == 200
    assert (
        v1_client.post(
            CLASSES, headers=academic, json={"name": "X", "medium_id": medium_id}
        ).status_code
        == 403
    )

    via_academics = v1_client.post(
        f"{ACADEMICS}/classes",
        headers=full,
        json={"name": "Via Academics", "medium_id": medium_id},
    )
    assert via_academics.status_code == 201, via_academics.text
    class_id = via_academics.json()["id"]
    assert class_id in {item["id"] for item in v1_client.get(CLASSES, headers=full).json()["items"]}
    patched = v1_client.patch(
        f"{CLASSES}/{class_id}", headers=full, json={"name": "Renamed Direct"}
    )
    assert patched.status_code == 200
    academics_list = v1_client.get(f"{ACADEMICS}/classes", headers=full).json()["items"]
    assert any(item["id"] == class_id and item["name"] == "Renamed Direct" for item in academics_list)
    assert (
        v1_client.patch(
            f"{ACADEMICS}/classes/{class_id}", headers=academic, json={"name": "Nope"}
        ).status_code
        == 403
    )


def test_direct_class_routes_openapi_and_no_duplicate_paths():
    class_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/v1/school-admin/classes")
    ]
    method_paths = {(tuple(sorted(route.methods)), route.path) for route in class_routes}
    assert any("GET" in methods and path == "/api/v1/school-admin/classes" for methods, path in method_paths)
    assert any("POST" in methods and path == "/api/v1/school-admin/classes" for methods, path in method_paths)
    assert any("GET" in methods and path == "/api/v1/school-admin/classes/{class_id}" for methods, path in method_paths)
    assert any("PATCH" in methods and path == "/api/v1/school-admin/classes/{class_id}" for methods, path in method_paths)
    # One route registration per method+path (no duplicate handlers).
    assert len(class_routes) == len({(frozenset(r.methods), r.path) for r in class_routes})
    for route in class_routes:
        assert route.tags == ["v1-school-admin"], route.path

    # Academics class path still registered (compat).
    academics_resource = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == "/api/v1/school-admin/academics/{resource}"
    ]
    assert academics_resource


def test_phase3_compact_sessions_unchanged(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "cls-sess-sa@eschool.com")
    school_id = _school(v1_client, sa, "CLSS")
    admin = _school_admin(v1_client, sa, school_id, "cls-sess-admin@eschool.com")
    created = v1_client.post(
        f"{ACADEMICS}/sessions",
        headers=admin,
        json={
            "name": "2026-27",
            "start_date": "2026-04-01",
            "end_date": "2027-03-31",
            "default": 1,
        },
    )
    assert created.status_code == 201, created.text
    compact = v1_client.get(SESSIONS_COMPACT, headers=admin)
    assert compact.status_code == 200, compact.text
    assert compact.json()["items"]
    for item in compact.json()["items"]:
        assert set(item.keys()) == {"id", "name", "default"}
