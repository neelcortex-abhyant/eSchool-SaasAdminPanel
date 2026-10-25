from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.v1.roles import ROLE_SUPER_ADMIN, ROLE_USER
from app.models.v1.user import User
from app.models.tables import School


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup(client, email: str = "schools-user@eschool.com", **overrides):
    body = {
        "email": email,
        "password": "secret123",
        "first_name": "Schools",
        "last_name": "Tester",
        **overrides,
    }
    return client.post("/api/v1/auth/signup", json=body)


def _super_admin_headers(client, v1_db, email: str = "schools-sa@eschool.com") -> dict[str, str]:
    res = _signup(client, email=email)
    assert res.status_code == 201
    user = v1_db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.role = ROLE_SUPER_ADMIN
    v1_db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert login.status_code == 200
    assert login.json()["user"]["role"] == ROLE_SUPER_ADMIN
    return _auth_header(login.json()["access_token"])


def _create_school(client, headers, **overrides):
    body = {
        "name": "Alpha School",
        "address": "1 Main St",
        "support_phone": "111",
        "code": "ALPHA1",
        **overrides,
    }
    if "support_email" not in overrides:
        code = (body.get("code") or "school").lower()
        body["support_email"] = f"{code}@eschool.com"
    return client.post("/api/v1/super-admin/schools", headers=headers, json=body)


# --- auth ---


def test_schools_list_unauthenticated_401(v1_client):
    res = v1_client.get("/api/v1/super-admin/schools")
    assert res.status_code == 401


def test_schools_list_normal_user_403(v1_client):
    token = _signup(v1_client).json()["access_token"]
    res = v1_client.get("/api/v1/super-admin/schools", headers=_auth_header(token))
    assert res.status_code == 403
    assert res.json()["detail"] == "Forbidden"


# --- CRUD ---


def test_create_get_list_patch_school(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    created = _create_school(v1_client, headers)
    assert created.status_code == 201
    data = created.json()
    assert data["name"] == "Alpha School"
    assert data["code"] == "ALPHA1"
    assert data["status"] == 1
    assert data["installed"] == 1
    assert data["deleted_at"] is None
    school_id = data["id"]

    got = v1_client.get(f"/api/v1/super-admin/schools/{school_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["id"] == school_id

    listing = v1_client.get("/api/v1/super-admin/schools", headers=headers)
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] >= 1
    assert body["page"] == 1
    assert any(item["id"] == school_id for item in body["items"])

    patched = v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}",
        headers=headers,
        json={"name": "Alpha Renamed", "tagline": "Learn"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Alpha Renamed"
    assert patched.json()["tagline"] == "Learn"


def test_create_generates_code_when_omitted(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    res = v1_client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": "Beta Campus"},
    )
    assert res.status_code == 201
    assert res.json()["code"]
    assert res.json()["name"] == "Beta Campus"


def test_duplicate_code_conflict(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    assert _create_school(v1_client, headers, code="DUP01").status_code == 201
    again = _create_school(v1_client, headers, name="Other", code="DUP01")
    assert again.status_code == 409
    assert again.json()["detail"] == "School code already in use"


def test_create_validation_empty_name(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    res = v1_client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": ""},
    )
    assert res.status_code == 422


def test_get_school_404(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    res = v1_client.get("/api/v1/super-admin/schools/999999", headers=headers)
    assert res.status_code == 404


# --- pagination / filter ---


def test_list_pagination_and_filters(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    for i in range(3):
        assert (
            _create_school(
                v1_client,
                headers,
                name=f"Filter School {i}",
                code=f"FLT{i}",
            ).status_code
            == 201
        )

    page1 = v1_client.get(
        "/api/v1/super-admin/schools",
        headers=headers,
        params={"page": 1, "page_size": 2},
    )
    assert page1.status_code == 200
    assert len(page1.json()["items"]) == 2
    assert page1.json()["page_size"] == 2
    assert page1.json()["total"] >= 3

    by_code = v1_client.get(
        "/api/v1/super-admin/schools",
        headers=headers,
        params={"code": "FLT1"},
    )
    assert by_code.status_code == 200
    assert by_code.json()["total"] == 1
    assert by_code.json()["items"][0]["code"] == "FLT1"

    by_name = v1_client.get(
        "/api/v1/super-admin/schools",
        headers=headers,
        params={"name": "Filter School 2"},
    )
    assert by_name.status_code == 200
    assert by_name.json()["total"] == 1

    by_q = v1_client.get(
        "/api/v1/super-admin/schools",
        headers=headers,
        params={"q": "flt1"},
    )
    assert by_q.status_code == 200
    assert by_q.json()["total"] == 1
    assert by_q.json()["items"][0]["code"] == "FLT1"

    named = v1_client.get(
        "/api/v1/super-admin/schools",
        headers=headers,
        params={"q": "Filter School", "sort": "name", "page_size": 10},
    )
    assert named.status_code == 200
    names = [item["name"] for item in named.json()["items"]]
    assert names == sorted(names)


# --- soft delete ---


def test_soft_delete_hides_from_list_and_get(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    created = _create_school(v1_client, headers, code="SOFT1").json()
    school_id = created["id"]

    deleted = v1_client.delete(f"/api/v1/super-admin/schools/{school_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted_at"] is not None

    assert v1_client.get(f"/api/v1/super-admin/schools/{school_id}", headers=headers).status_code == 404

    listing = v1_client.get("/api/v1/super-admin/schools", headers=headers)
    assert all(item["id"] != school_id for item in listing.json()["items"])

    with_deleted = v1_client.get(
        "/api/v1/super-admin/schools",
        headers=headers,
        params={"include_deleted": True},
    )
    assert any(item["id"] == school_id for item in with_deleted.json()["items"])

    row = v1_db.get(School, school_id)
    assert row is not None
    assert row.deleted_at is not None


# --- status actions ---


def test_activate_suspend_deactivate(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers, code="STAT1").json()["id"]

    suspended = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/suspend",
        headers=headers,
    )
    assert suspended.status_code == 200
    assert suspended.json()["status"] == 0
    assert suspended.json()["installed"] == 1  # suspend leaves installed

    activated = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/activate",
        headers=headers,
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == 1
    assert activated.json()["installed"] == 1

    deactivated = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/deactivate",
        headers=headers,
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == 0
    assert deactivated.json()["installed"] == 0

    reactivated = v1_client.post(
        f"/api/v1/super-admin/schools/{school_id}/activate",
        headers=headers,
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["status"] == 1
    assert reactivated.json()["installed"] == 1


def test_status_actions_require_super_admin(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="owner@eschool.com")
    school_id = _create_school(v1_client, headers, code="AUTHZ1").json()["id"]
    user_token = _signup(v1_client, email="not-sa@eschool.com").json()["access_token"]
    user_headers = _auth_header(user_token)

    for path in (
        f"/api/v1/super-admin/schools/{school_id}/activate",
        f"/api/v1/super-admin/schools/{school_id}/suspend",
        f"/api/v1/super-admin/schools/{school_id}/deactivate",
    ):
        assert v1_client.post(path, headers=user_headers).status_code == 403


def test_status_filter(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db)
    school_id = _create_school(v1_client, headers, code="SFILT").json()["id"]
    assert (
        v1_client.post(
            f"/api/v1/super-admin/schools/{school_id}/suspend",
            headers=headers,
        ).status_code
        == 200
    )
    inactive = v1_client.get(
        "/api/v1/super-admin/schools",
        headers=headers,
        params={"status": 0},
    )
    assert inactive.status_code == 200
    assert any(item["id"] == school_id for item in inactive.json()["items"])
    assert all(item["status"] == 0 for item in inactive.json()["items"])


def test_signup_user_still_role_user_after_schools_ops(v1_client):
    res = _signup(v1_client, email="still-user@eschool.com")
    assert res.status_code == 201
    assert res.json()["user"]["role"] == ROLE_USER


# --- email search, validation, profile fields ---


def test_support_email_search_is_case_insensitive_partial(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="email-search-sa@eschool.com")
    created = _create_school(
        v1_client,
        headers,
        name="Email Campus",
        code="EML01",
        support_email="Alpha.Desk@Example.com",
    )
    assert created.status_code == 201
    school_id = created.json()["id"]
    other = _create_school(
        v1_client,
        headers,
        name="Other Campus",
        code="EML02",
        support_email="other@example.com",
    )
    assert other.status_code == 201

    found = v1_client.get(
        "/api/v1/super-admin/schools",
        headers=headers,
        params={"support_email": "ALPHA.DESK"},
    )
    assert found.status_code == 200
    assert found.json()["total"] == 1
    assert found.json()["items"][0]["id"] == school_id

    paged = v1_client.get(
        "/api/v1/super-admin/schools",
        headers=headers,
        params={"support_email": "example.com", "page": 1, "page_size": 1, "status": 1},
    )
    assert paged.status_code == 200
    assert paged.json()["page_size"] == 1
    assert len(paged.json()["items"]) == 1
    assert paged.json()["total"] == 2


def test_valid_email_create_and_update(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="email-valid-sa@eschool.com")
    created = _create_school(
        v1_client,
        headers,
        code="VAL01",
        support_email="Office@eschool.com",
    )
    assert created.status_code == 201
    school_id = created.json()["id"]
    assert "@" in created.json()["support_email"]

    patched = v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}",
        headers=headers,
        json={"support_email": "desk@eschool.com"},
    )
    assert patched.status_code == 200
    assert patched.json()["support_email"] == "desk@eschool.com"

    got = v1_client.get(f"/api/v1/super-admin/schools/{school_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["support_email"] == "desk@eschool.com"


def test_invalid_email_rejected_on_create_and_patch(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="email-bad-sa@eschool.com")
    created = v1_client.post(
        "/api/v1/super-admin/schools",
        headers=headers,
        json={"name": "Bad Email", "code": "BAD01", "support_email": "not-an-email"},
    )
    assert created.status_code == 422

    school_id = _create_school(v1_client, headers, code="BAD02").json()["id"]
    patched = v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}",
        headers=headers,
        json={"support_email": "still-not-an-email"},
    )
    assert patched.status_code == 422
    current = v1_client.get(f"/api/v1/super-admin/schools/{school_id}", headers=headers)
    assert current.json()["support_email"] == "bad02@eschool.com"


def test_blank_email_allowed_and_not_unique(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="email-blank-sa@eschool.com")
    first = _create_school(v1_client, headers, code="BLK01", support_email="")
    second = _create_school(v1_client, headers, code="BLK02", support_email="   ")
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["support_email"] == ""
    assert second.json()["support_email"] == ""

    cleared = v1_client.patch(
        f"/api/v1/super-admin/schools/{first.json()['id']}",
        headers=headers,
        json={"support_email": "kept@eschool.com"},
    )
    assert cleared.status_code == 200
    cleared_again = v1_client.patch(
        f"/api/v1/super-admin/schools/{first.json()['id']}",
        headers=headers,
        json={"support_email": ""},
    )
    assert cleared_again.status_code == 200
    assert cleared_again.json()["support_email"] == ""


def test_duplicate_nonblank_email_conflict_is_case_insensitive(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="email-dup-sa@eschool.com")
    assert (
        _create_school(
            v1_client, headers, code="DUPM1", support_email="shared@eschool.com"
        ).status_code
        == 201
    )
    again = _create_school(
        v1_client, headers, code="DUPM2", name="Second", support_email="SHARED@eschool.com"
    )
    assert again.status_code == 409
    assert again.json()["detail"] == "School email already in use"

    school_id = _create_school(
        v1_client, headers, code="DUPM3", support_email="unique@eschool.com"
    ).json()["id"]
    patched = v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}",
        headers=headers,
        json={"support_email": "shared@eschool.com"},
    )
    assert patched.status_code == 409


def test_phone_address_logo_round_trip(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="profile-sa@eschool.com")
    created = _create_school(
        v1_client,
        headers,
        code="PROF1",
        address="12 Lake Road",
        support_phone="9876543210",
        logo="logo-a.png",
    )
    assert created.status_code == 201
    school_id = created.json()["id"]
    assert created.json()["address"] == "12 Lake Road"
    assert created.json()["support_phone"] == "9876543210"
    assert created.json()["logo"] == "logo-a.png"

    got = v1_client.get(f"/api/v1/super-admin/schools/{school_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["address"] == "12 Lake Road"
    assert got.json()["support_phone"] == "9876543210"
    assert got.json()["logo"] == "logo-a.png"

    patched = v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}",
        headers=headers,
        json={"address": "99 Hill St", "support_phone": "5550001", "logo": "logo-b.png"},
    )
    assert patched.status_code == 200
    assert patched.json()["address"] == "99 Hill St"
    assert patched.json()["support_phone"] == "5550001"
    assert patched.json()["logo"] == "logo-b.png"
    assert patched.json()["status"] == 1


def test_list_sort_name_and_created_at(v1_client, v1_db):
    from datetime import datetime

    headers = _super_admin_headers(v1_client, v1_db, email="sort-sa@eschool.com")
    first = _create_school(v1_client, headers, name="Cedar School", code="SRT1").json()
    second = _create_school(v1_client, headers, name="Alder School", code="SRT2").json()
    third = _create_school(v1_client, headers, name="Birch School", code="SRT3").json()
    times = {
        first["id"]: datetime(2024, 1, 1),
        second["id"]: datetime(2024, 6, 1),
        third["id"]: datetime(2024, 3, 1),
    }
    for school_id, created_at in times.items():
        row = v1_db.get(School, school_id)
        assert row is not None
        row.created_at = created_at
    v1_db.commit()

    def ids(sort: str) -> list[int]:
        res = v1_client.get(
            "/api/v1/super-admin/schools",
            headers=headers,
            params={"sort": sort, "page_size": 20},
        )
        assert res.status_code == 200
        return [item["id"] for item in res.json()["items"]]

    assert ids("name") == [second["id"], third["id"], first["id"]]
    assert ids("-name") == [first["id"], third["id"], second["id"]]
    assert ids("created_at") == [first["id"], third["id"], second["id"]]
    assert ids("-created_at") == [second["id"], third["id"], first["id"]]

    default = v1_client.get("/api/v1/super-admin/schools", headers=headers)
    assert default.status_code == 200
    assert [item["id"] for item in default.json()["items"]] == [
        third["id"],
        second["id"],
        first["id"],
    ]


def test_list_sort_tie_breaks_on_id(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="sort-tie-sa@eschool.com")
    older = _create_school(v1_client, headers, name="Same School", code="TIE1").json()
    newer = _create_school(v1_client, headers, name="Same School", code="TIE2").json()
    assert older["id"] < newer["id"]

    asc = v1_client.get(
        "/api/v1/super-admin/schools",
        headers=headers,
        params={"sort": "name"},
    )
    desc = v1_client.get(
        "/api/v1/super-admin/schools",
        headers=headers,
        params={"sort": "-name"},
    )
    assert asc.status_code == 200
    assert desc.status_code == 200
    assert [item["id"] for item in asc.json()["items"]] == [older["id"], newer["id"]]
    assert [item["id"] for item in desc.json()["items"]] == [newer["id"], older["id"]]


def test_list_sort_and_status_validation(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="sort-val-sa@eschool.com")
    active = _create_school(v1_client, headers, name="Active Sort", code="ST1").json()
    inactive = _create_school(v1_client, headers, name="Inactive Sort", code="ST0").json()
    assert (
        v1_client.post(
            f"/api/v1/super-admin/schools/{inactive['id']}/suspend",
            headers=headers,
        ).status_code
        == 200
    )

    only_active = v1_client.get(
        "/api/v1/super-admin/schools",
        headers=headers,
        params={"status": 1},
    )
    only_inactive = v1_client.get(
        "/api/v1/super-admin/schools",
        headers=headers,
        params={"status": 0},
    )
    assert only_active.status_code == 200
    assert [item["id"] for item in only_active.json()["items"]] == [active["id"]]
    assert only_inactive.status_code == 200
    assert [item["id"] for item in only_inactive.json()["items"]] == [inactive["id"]]
    assert all(item["status"] == 0 for item in only_inactive.json()["items"])

    assert (
        v1_client.get(
            "/api/v1/super-admin/schools",
            headers=headers,
            params={"status": 2},
        ).status_code
        == 422
    )
    assert (
        v1_client.get(
            "/api/v1/super-admin/schools",
            headers=headers,
            params={"sort": "updated_at"},
        ).status_code
        == 422
    )


def test_nonblank_email_unique_index_blocks_direct_insert(v1_client, v1_db):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    def row(name: str, code: str, email: str) -> School:
        return School(
            name=name,
            address="",
            support_phone="",
            support_email=email,
            tagline="",
            logo="",
            status=1,
            code=code,
            installed=1,
            created_at=now,
            updated_at=now,
        )

    v1_db.add(row("One", "RACE1", "race@eschool.com"))
    v1_db.commit()
    v1_db.add(row("Two", "RACE2", "RACE@eschool.com"))
    with pytest.raises(IntegrityError):
        v1_db.commit()
    v1_db.rollback()


# --- domain / school_website ---


def test_create_school_default_domain_builds_hostname(v1_client, v1_db, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("SCHOOL_BASE_DOMAIN", "schools.test")
    get_settings.cache_clear()
    headers = _super_admin_headers(v1_client, v1_db, email="dom-def@eschool.com")
    created = _create_school(
        v1_client,
        headers,
        code="DOMDEF",
        domain="alpha",
        domain_type="default",
        school_website="https://alpha-school.example/about",
    )
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["domain"] == "alpha.schools.test"
    assert data["domain_type"] == "default"
    assert data["domain_verified"] == 1
    assert data["school_website"] == "https://alpha-school.example/about"

    got = v1_client.get(f"/api/v1/super-admin/schools/{data['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["domain"] == "alpha.schools.test"
    assert got.json()["domain_type"] == "default"
    get_settings.cache_clear()


def test_create_school_custom_domain_unverified(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="dom-cus@eschool.com")
    created = _create_school(
        v1_client,
        headers,
        code="DOMCUS",
        domain="portal.custom-school.org",
        domain_type="custom",
    )
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["domain"] == "portal.custom-school.org"
    assert data["domain_type"] == "custom"
    assert data["domain_verified"] == 0


def test_create_school_legacy_json_without_domain_type(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="dom-leg@eschool.com")
    created = _create_school(
        v1_client,
        headers,
        code="DOMLEG",
        domain="legacy.example.com",
        tagline="",
        logo="",
        address="",
        support_phone="",
    )
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["domain"] == "legacy.example.com"
    assert data["domain_type"] is None
    assert data["domain_verified"] == 0
    assert data["school_website"] == ""


def test_create_school_rejects_invalid_domain_type_and_hostnames(v1_client, v1_db, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("SCHOOL_BASE_DOMAIN", "schools.test")
    get_settings.cache_clear()
    headers = _super_admin_headers(v1_client, v1_db, email="dom-bad@eschool.com")

    bad_type = _create_school(
        v1_client, headers, code="BADT1", domain="x", domain_type="other"
    )
    assert bad_type.status_code == 422

    bad_prefix = _create_school(
        v1_client,
        headers,
        code="BADP1",
        domain="Alpha_School",
        domain_type="default",
    )
    assert bad_prefix.status_code == 422

    fqdn_as_default = _create_school(
        v1_client,
        headers,
        code="BADP2",
        domain="alpha.schools.test",
        domain_type="default",
    )
    assert fqdn_as_default.status_code == 422

    bad_custom = _create_school(
        v1_client,
        headers,
        code="BADC1",
        domain="https://not-a-host.example",
        domain_type="custom",
    )
    assert bad_custom.status_code == 422

    single_label = _create_school(
        v1_client,
        headers,
        code="BADC2",
        domain="onlylabel",
        domain_type="custom",
    )
    assert single_label.status_code == 422
    get_settings.cache_clear()


def test_create_school_rejects_duplicate_domain(v1_client, v1_db, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("SCHOOL_BASE_DOMAIN", "schools.test")
    get_settings.cache_clear()
    headers = _super_admin_headers(v1_client, v1_db, email="dom-dup@eschool.com")
    first = _create_school(
        v1_client, headers, code="DUPD1", domain="twin", domain_type="default"
    )
    assert first.status_code == 201, first.text
    again = _create_school(
        v1_client, headers, code="DUPD2", domain="twin", domain_type="default"
    )
    assert again.status_code == 409
    custom_clash = _create_school(
        v1_client,
        headers,
        code="DUPD3",
        domain="twin.schools.test",
        domain_type="custom",
    )
    assert custom_clash.status_code == 409
    get_settings.cache_clear()


def test_create_school_website_validation_and_patch(v1_client, v1_db):
    headers = _super_admin_headers(v1_client, v1_db, email="web-sa@eschool.com")
    bad = _create_school(
        v1_client,
        headers,
        code="WEB1",
        school_website="ftp://files.example/school",
    )
    assert bad.status_code == 422

    created = _create_school(v1_client, headers, code="WEB2", school_website="")
    assert created.status_code == 201, created.text
    school_id = created.json()["id"]

    patched = v1_client.patch(
        f"/api/v1/super-admin/schools/{school_id}",
        headers=headers,
        json={
            "school_website": "https://www.example.edu",
            "domain": "campus.example.edu",
            "domain_type": "custom",
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["school_website"] == "https://www.example.edu"
    assert patched.json()["domain"] == "campus.example.edu"
    assert patched.json()["domain_type"] == "custom"
    assert patched.json()["domain_verified"] == 0


def test_create_school_domain_requires_super_admin(v1_client):
    token = _signup(v1_client, email="dom-user@eschool.com").json()["access_token"]
    res = v1_client.post(
        "/api/v1/super-admin/schools",
        headers=_auth_header(token),
        json={"name": "Nope", "domain": "x.example.com", "domain_type": "custom"},
    )
    assert res.status_code == 403
