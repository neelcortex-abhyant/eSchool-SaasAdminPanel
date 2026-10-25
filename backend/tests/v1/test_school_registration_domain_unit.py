"""DB-free checks: registration schema + forwarding into create_school."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.v1.school_registration import SchoolRegistrationRequest
from app.services.v1 import school_registration_service as reg


def test_registration_schema_accepts_legacy_and_new_fields():
    legacy = SchoolRegistrationRequest.model_validate(
        {
            "name": "Hillside School",
            "support_email": "office@hillside.example",
            "support_phone": "9876543210",
            "address": "12 Lake Road",
            "city": "Pune",
            "state": "Maharashtra",
            "country": "India",
            "postal_code": "411001",
            "domain": "hillside.example",
            "admin_first_name": "Asha",
            "admin_last_name": "Rao",
            "admin_email": "asha@hillside.example",
            "admin_mobile": "9876500000",
            "admin_password": "password1",
            "terms_accepted": True,
        }
    )
    assert legacy.domain_type is None
    assert legacy.school_website == ""

    typed = SchoolRegistrationRequest.model_validate(
        {
            **legacy.model_dump(),
            "domain": "vidhata",
            "domain_type": "default",
            "school_website": "https://www.vidhata.edu",
        }
    )
    assert typed.domain_type == "default"
    assert typed.school_website == "https://www.vidhata.edu"

    with pytest.raises(ValidationError):
        SchoolRegistrationRequest.model_validate({**legacy.model_dump(), "domain_type": "other"})


def test_register_school_forwards_domain_fields_to_create_school(monkeypatch):
    reg.reset_registration_limits()
    captured: dict = {}

    def fake_create_school(db, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=42, name=kwargs["name"])

    def fake_create_admin(*args, **kwargs):
        return SimpleNamespace(id=1)

    def fake_audit(*args, **kwargs):
        return None

    monkeypatch.setattr(reg, "create_school", fake_create_school)
    monkeypatch.setattr(reg, "create_school_admin", fake_create_admin)
    monkeypatch.setattr(reg.audit_service, "record_audit", fake_audit)

    school = reg.register_school(
        db=SimpleNamespace(rollback=lambda: None, refresh=lambda *_: None),
        name="Forward School",
        support_email="office@fwd.example",
        support_phone="9876543210",
        address="1 Road",
        city="Pune",
        state="MH",
        country="India",
        postal_code="411001",
        tagline="",
        logo="",
        domain="vidhata",
        domain_type="default",
        school_website="https://www.vidhata.edu",
        admin_first_name="A",
        admin_last_name="B",
        admin_email="admin@fwd.example",
        admin_mobile="9876500000",
        admin_password="password1",
        terms_accepted=True,
    )
    assert school.id == 42
    assert captured["domain"] == "vidhata"
    assert captured["domain_type"] == "default"
    assert captured["school_website"] == "https://www.vidhata.edu"
    assert captured["status"] == reg.STATUS_INACTIVE
    assert captured["installed"] == reg.INSTALLED_NO
