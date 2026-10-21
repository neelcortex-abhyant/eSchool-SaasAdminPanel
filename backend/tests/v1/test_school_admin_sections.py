"""Phase 5: direct /api/v1/school-admin/sections management."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.routing import APIRoute
from sqlalchemy import select

from app.main import app
from app.models.tables import ClassSection, Section
from app.models.v1.roles import ROLE_SUPER_ADMIN
from app.models.v1.user import User

SECTIONS = "/api/v1/school-admin/sections"
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


def _seed_classes(client, headers):
    medium = client.post(f"{ACADEMICS}/mediums", headers=headers, json={"name": "English"})
    assert medium.status_code == 201, medium.text
    medium_id = medium.json()["id"]
    c1 = client.post(CLASSES, headers=headers, json={"name": "Grade 1", "medium_id": medium_id})
    c2 = client.post(CLASSES, headers=headers, json={"name": "Grade 2", "medium_id": medium_id})
    assert c1.status_code == 201, c1.text
    assert c2.status_code == 201, c2.text
    return {"medium_id": medium_id, "class_1": c1.json()["id"], "class_2": c2.json()["id"]}


def test_section_crud_filter_duplicates_and_detail(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "sec-sa@eschool.com")
    school_id = _school(v1_client, sa, "SEC01")
    admin = _school_admin(v1_client, sa, school_id, "sec-admin@eschool.com")
    ids = _seed_classes(v1_client, admin)

    assert v1_client.post(SECTIONS, headers=admin, json={"name": "  "}).status_code == 422
    assert v1_client.post(SECTIONS, headers=admin, json={"name": "A"}).status_code == 422

    created = v1_client.post(
        SECTIONS,
        headers=admin,
        json={"name": "  A  ", "class_id": ids["class_1"]},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "A"
    assert body["class_id"] == ids["class_1"]
    assert body["class_section_id"]
    section_id = body["id"]

    # Multiple different sections under the same class.
    created_b = v1_client.post(
        SECTIONS, headers=admin, json={"name": "B", "class_id": ids["class_1"]}
    )
    assert created_b.status_code == 201, created_b.text

    # Duplicate name within class → 409; same name under other class → ok (shared Section).
    assert (
        v1_client.post(
            SECTIONS, headers=admin, json={"name": "a", "class_id": ids["class_1"]}
        ).status_code
        == 409
    )
    shared = v1_client.post(
        SECTIONS, headers=admin, json={"name": "A", "class_id": ids["class_2"]}
    )
    assert shared.status_code == 201, shared.text
    assert shared.json()["id"] == section_id  # reused school-level section

    listed = v1_client.get(SECTIONS, headers=admin, params={"q": "A", "page": 1, "page_size": 10})
    assert listed.status_code == 200
    assert set(listed.json().keys()) == {"items", "total", "page", "page_size"}
    assert any(item["id"] == section_id for item in listed.json()["items"])

    filtered = v1_client.get(SECTIONS, headers=admin, params={"class_id": ids["class_1"]})
    assert filtered.status_code == 200
    filtered_ids = {item["id"] for item in filtered.json()["items"]}
    assert section_id in filtered_ids
    assert created_b.json()["id"] in filtered_ids
    assert all(item["class_id"] == ids["class_1"] for item in filtered.json()["items"])

    detail = v1_client.get(f"{SECTIONS}/{section_id}", headers=admin)
    assert detail.status_code == 200, detail.text
    assert detail.json()["name"] == "A"
    class_ids = {c["class_id"] for c in detail.json()["classes"]}
    assert class_ids == {ids["class_1"], ids["class_2"]}

    patched = v1_client.patch(f"{SECTIONS}/{section_id}", headers=admin, json={"name": "Alpha"})
    assert patched.status_code == 200, patched.text
    assert patched.json()["name"] == "Alpha"

    # Soft-deleted section excluded; detail 404.
    row = v1_db.get(Section, section_id)
    assert row is not None
    row.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    v1_db.commit()
    assert section_id not in {
        item["id"] for item in v1_client.get(SECTIONS, headers=admin).json()["items"]
    }
    assert v1_client.get(f"{SECTIONS}/{section_id}", headers=admin).status_code == 404


def test_section_cross_school_and_invalid_class(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "sec-x-sa@eschool.com")
    school_a = _school(v1_client, sa, "SECA")
    school_b = _school(v1_client, sa, "SECB")
    admin_a = _school_admin(v1_client, sa, school_a, "sec-a@eschool.com")
    admin_b = _school_admin(v1_client, sa, school_b, "sec-b@eschool.com")
    ids_a = _seed_classes(v1_client, admin_a)
    ids_b = _seed_classes(v1_client, admin_b)

    created = v1_client.post(
        SECTIONS, headers=admin_a, json={"name": "A", "class_id": ids_a["class_1"]}
    )
    assert created.status_code == 201
    section_id = created.json()["id"]

    assert (
        v1_client.post(
            SECTIONS, headers=admin_a, json={"name": "X", "class_id": ids_b["class_1"]}
        ).status_code
        == 404
    )
    assert v1_client.get(f"{SECTIONS}/{section_id}", headers=admin_b).status_code == 404
    assert (
        v1_client.patch(
            f"{SECTIONS}/{section_id}", headers=admin_b, json={"name": "Hijack"}
        ).status_code
        == 404
    )
    assert (
        v1_client.get(SECTIONS, headers=admin_a, params={"class_id": ids_b["class_1"]}).status_code
        == 404
    )


def test_section_class_reassign_and_academics_compat(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "sec-map-sa@eschool.com")
    school_id = _school(v1_client, sa, "SECM")
    admin = _school_admin(v1_client, sa, school_id, "sec-map-admin@eschool.com")
    ids = _seed_classes(v1_client, admin)

    created = v1_client.post(
        SECTIONS, headers=admin, json={"name": "C", "class_id": ids["class_1"]}
    )
    assert created.status_code == 201
    section_id = created.json()["id"]
    link_id = created.json()["class_section_id"]

    moved = v1_client.patch(
        f"{SECTIONS}/{section_id}",
        headers=admin,
        json={"class_id": ids["class_2"]},
    )
    assert moved.status_code == 200, moved.text
    class_ids = {c["class_id"] for c in moved.json()["classes"]}
    assert class_ids == {ids["class_2"]}
    link = v1_db.get(ClassSection, link_id)
    assert link is not None
    assert link.class_id == ids["class_2"]
    assert link.deleted_at is None

    # Academics name-only create still works and does not invent a class link.
    bare = v1_client.post(f"{ACADEMICS}/sections", headers=admin, json={"name": "Standalone"})
    assert bare.status_code == 201, bare.text
    bare_id = bare.json()["id"]
    bare_detail = v1_client.get(f"{SECTIONS}/{bare_id}", headers=admin)
    assert bare_detail.status_code == 200
    assert bare_detail.json()["classes"] == []


def test_section_write_permission(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "sec-perm-sa@eschool.com")
    school_id = _school(v1_client, sa, "SECP")
    full = _school_admin(v1_client, sa, school_id, "sec-full@eschool.com")
    ids = _seed_classes(v1_client, full)

    created_admin = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/admins",
        headers=sa,
        json={
            "email": "sec-academic@eschool.com",
            "password": "adminpass1",
            "first_name": "Acad",
            "last_name": "Admin",
        },
    )
    assert created_admin.status_code == 201, created_admin.text
    assert (
        v1_client.patch(
            f"/api/v1/super-admin/schools/{school_id}/admins/{created_admin.json()['id']}/roles",
            headers=sa,
            json={"roles": ["academic_admin"]},
        ).status_code
        == 200
    )
    login = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "sec-academic@eschool.com", "password": "adminpass1"},
    )
    assert login.status_code == 200
    academic = _auth(login.json()["access_token"])

    assert v1_client.get(SECTIONS, headers=academic).status_code == 200
    assert (
        v1_client.post(
            SECTIONS, headers=academic, json={"name": "Z", "class_id": ids["class_1"]}
        ).status_code
        == 403
    )


def test_direct_section_routes_openapi():
    routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/v1/school-admin/sections")
    ]
    method_paths = {(frozenset(route.methods), route.path) for route in routes}
    assert any("GET" in m and p == "/api/v1/school-admin/sections" for m, p in method_paths)
    assert any("POST" in m and p == "/api/v1/school-admin/sections" for m, p in method_paths)
    assert any("GET" in m and p == "/api/v1/school-admin/sections/{section_id}" for m, p in method_paths)
    assert any("PATCH" in m and p == "/api/v1/school-admin/sections/{section_id}" for m, p in method_paths)
    assert len(routes) == len({(frozenset(r.methods), r.path) for r in routes})
    for route in routes:
        assert route.tags == ["v1-school-admin"], route.path
    assert any(
        isinstance(route, APIRoute) and route.path == "/api/v1/school-admin/academics/{resource}"
        for route in app.routes
    )


def test_phase3_sessions_and_phase4_classes_regression(v1_client, v1_db):
    sa = _super(v1_client, v1_db, "sec-reg-sa@eschool.com")
    school_id = _school(v1_client, sa, "SECR")
    admin = _school_admin(v1_client, sa, school_id, "sec-reg-admin@eschool.com")

    session = v1_client.post(
        f"{ACADEMICS}/sessions",
        headers=admin,
        json={
            "name": "2026-27",
            "start_date": "2026-04-01",
            "end_date": "2027-03-31",
            "default": 1,
        },
    )
    assert session.status_code == 201, session.text
    compact = v1_client.get(SESSIONS_COMPACT, headers=admin)
    assert compact.status_code == 200
    for item in compact.json()["items"]:
        assert set(item.keys()) == {"id", "name", "default"}

    medium = v1_client.post(f"{ACADEMICS}/mediums", headers=admin, json={"name": "Eng"})
    assert medium.status_code == 201
    klass = v1_client.post(
        CLASSES, headers=admin, json={"name": "Reg Class", "medium_id": medium.json()["id"]}
    )
    assert klass.status_code == 201, klass.text
    assert v1_client.get(f"{CLASSES}/{klass.json()['id']}", headers=admin).status_code == 200
