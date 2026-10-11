from __future__ import annotations

from sqlalchemy import select

from app.models.tables import School
from app.models.v1.roles import ROLE_SCHOOL_ADMIN
from app.models.v1.user import User
from app.services.v1.school_registration_service import reset_registration_limits
from tests.v1.test_super_admin_schools import _auth_header, _super_admin_headers


def _body(**overrides):
    body = {
        "name": "Hillside School",
        "support_email": "office@hillside.example",
        "support_phone": "9876543210",
        "address": "12 Lake Road",
        "city": "Pune",
        "state": "Maharashtra",
        "country": "India",
        "postal_code": "411001",
        "tagline": "Learn well",
        "logo": "https://cdn.example.com/logo.png",
        "domain": "hillside.example",
        "admin_first_name": "Asha",
        "admin_last_name": "Rao",
        "admin_email": "asha@hillside.example",
        "admin_mobile": "9876500000",
        "admin_password": "password1",
        "terms_accepted": True,
    }
    body.update(overrides)
    return body


def test_public_registration_is_pending_and_blocks_login(v1_client, v1_db):
    reset_registration_limits()
    created = v1_client.post("/api/v1/schools/register", json=_body())
    assert created.status_code == 201
    payload = created.json()
    assert payload["status"] == "pending_approval"
    assert "submitted successfully" in payload["message"]
    assert "password" not in payload
    assert "access_token" not in payload

    school = v1_db.get(School, payload["school_id"])
    assert school is not None
    assert school.status == 0
    assert school.installed == 0
    assert "Pune" in school.address
    admin = v1_db.scalar(select(User).where(User.email == "asha@hillside.example"))
    assert admin is not None
    assert admin.role == ROLE_SCHOOL_ADMIN
    assert admin.school_id == school.id
    assert admin.password_hash != "password1"

    denied = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "asha@hillside.example", "password": "password1"},
    )
    assert denied.status_code == 403
    assert "waiting for approval" in denied.json()["detail"]

    headers = _super_admin_headers(v1_client, v1_db, email="approver@eschool.com")
    listed = v1_client.get("/api/v1/super-admin/schools", headers=headers)
    assert listed.status_code == 200
    row = next(item for item in listed.json()["items"] if item["id"] == school.id)
    assert row["status"] == 0

    approved = v1_client.post(f"/api/v1/super-admin/schools/{school.id}/activate", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == 1

    signed_in = v1_client.post(
        "/api/v1/auth/login",
        json={"email": "asha@hillside.example", "password": "password1"},
    )
    assert signed_in.status_code == 200
    token = signed_in.json()["access_token"]
    assert signed_in.json()["user"]["role"] == ROLE_SCHOOL_ADMIN
    assert signed_in.json()["user"]["school_id"] == school.id

    blocked = v1_client.get("/api/v1/super-admin/schools", headers=_auth_header(token))
    assert blocked.status_code == 403

    own_school = v1_client.get("/api/v1/school-admin/school", headers=_auth_header(token))
    assert own_school.status_code == 200
    assert own_school.json()["id"] == school.id


def test_duplicate_school_email_and_invalid_registration(v1_client):
    reset_registration_limits()
    first = v1_client.post("/api/v1/schools/register", json=_body())
    assert first.status_code == 201
    duplicate = v1_client.post(
        "/api/v1/schools/register",
        json=_body(admin_email="other-admin@hillside.example", name="Hillside Copy"),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "School email already in use"

    missing = v1_client.post("/api/v1/schools/register", json=_body(name=""))
    assert missing.status_code == 422

    bad_email = v1_client.post("/api/v1/schools/register", json=_body(support_email="not-an-email", name="Other"))
    assert bad_email.status_code == 422

    short_phone = v1_client.post("/api/v1/schools/register", json=_body(support_phone="123", name="Phone School"))
    assert short_phone.status_code == 422

    terms = v1_client.post("/api/v1/schools/register", json=_body(terms_accepted=False, name="No Terms"))
    assert terms.status_code == 422

    short_password = v1_client.post(
        "/api/v1/schools/register",
        json=_body(admin_password="short", admin_email="short@hillside.example", support_email="short-office@hillside.example"),
    )
    assert short_password.status_code == 422
