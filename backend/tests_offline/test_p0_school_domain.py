"""P0 regression: school hostnames are full FQDNs on the production base (DB-free)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.schemas.v1.school_registration import SubdomainAvailabilityResponse
from app.services.v1 import school_service as svc


def _settings(**env) -> Settings:
    base = {"app_env": "production", "school_base_domain": "schoolsarthi.com", "neon_database_url": ""}
    base.update(env)
    return Settings(_env_file=None, **base)


@pytest.fixture
def use_settings(monkeypatch):
    def apply(**env):
        settings = _settings(**env)
        monkeypatch.setattr(svc, "get_settings", lambda: settings)
        return settings

    return apply


def test_availability_returns_full_hostname(use_settings):
    use_settings()
    db = MagicMock()
    db.scalar.return_value = None
    out = svc.check_subdomain_availability(db, slug="qa-sunrise-1105")
    assert out["available"] is True
    assert out["hostname"] == "qa-sunrise-1105.schoolsarthi.com"
    assert out["base_domain"] == "schoolsarthi.com"
    assert ".localhost" not in out["hostname"]
    # Response model keeps the new fields
    model = SubdomainAvailabilityResponse(**out)
    assert model.hostname == "qa-sunrise-1105.schoolsarthi.com"


def test_taken_slug_still_reports_hostname(use_settings):
    use_settings()
    db = MagicMock()
    db.scalar.side_effect = [42] + [None] * 20
    out = svc.check_subdomain_availability(db, slug="qa-sunrise-1105")
    assert out["available"] is False
    assert out["problem"] == "qa-sunrise-1105.schoolsarthi.com is taken."
    assert out["hostname"] == "qa-sunrise-1105.schoolsarthi.com"


def test_invalid_slug_has_no_hostname(use_settings):
    use_settings()
    out = svc.check_subdomain_availability(MagicMock(), slug="Bad_Slug!")
    assert out["available"] is False
    assert SubdomainAvailabilityResponse(**out).hostname is None


def test_default_domain_is_stored_as_fqdn(use_settings):
    use_settings()
    host, dtype, verified = svc.resolve_school_domain(domain="QA-Sunrise-1105", domain_type="default")
    assert (host, dtype, verified) == ("qa-sunrise-1105.schoolsarthi.com", "default", 1)


def test_default_domain_rejects_full_hostname_as_prefix(use_settings):
    use_settings()
    with pytest.raises(svc.SchoolServiceError):
        svc.resolve_school_domain(domain="qa.schoolsarthi.com", domain_type="default")


@pytest.mark.parametrize(
    "env",
    [
        {"school_base_domain": "localhost"},
        {"school_base_domain": "qa.localhost"},
        {"school_base_domain": "", "app_url": "https://eschool-saas.wrteam.me"},
        {"school_base_domain": "eschool-backend-8322.onrender.com"},
        {"school_base_domain": "schoolsarthi.netlify.app"},
        {"school_base_domain": "", "app_url": ""},
    ],
    ids=["localhost", "sub.localhost", "vendor-default", "render", "netlify", "unset"],
)
def test_production_refuses_non_production_base(use_settings, env):
    use_settings(**env)
    with pytest.raises(svc.SchoolServiceError) as err:
        svc.resolve_school_domain(domain="qa-sunrise-1105", domain_type="default")
    assert err.value.status_code == 500
    assert "SCHOOL_BASE_DOMAIN" in err.value.detail


def test_local_dev_may_use_localhost(use_settings):
    use_settings(app_env="local", school_base_domain="localhost")
    host, _, _ = svc.resolve_school_domain(domain="qa-sunrise-1105", domain_type="default")
    assert host == "qa-sunrise-1105.localhost"


def test_base_domain_is_normalized():
    settings = _settings(school_base_domain=" SchoolSarthi.com. ")
    assert settings.resolved_school_base_domain == "schoolsarthi.com"
    assert settings.school_base_domain_problem is None


def test_duplicate_domain_is_409_case_insensitive():
    db = MagicMock()
    db.scalar.return_value = 5
    with pytest.raises(svc.SchoolServiceError) as err:
        svc._ensure_domain_available(db, "QA-Sunrise-1105.SchoolSarthi.com")
    assert err.value.status_code == 409
    compiled = str(db.scalar.call_args[0][0].compile(compile_kwargs={"literal_binds": True}))
    assert "lower(btrim(schools.domain)) = 'qa-sunrise-1105.schoolsarthi.com'" in compiled


def test_availability_counts_deleted_schools_like_create():
    """A slug shown as available must not then fail with 409 on save."""
    db = MagicMock()
    db.scalar.return_value = None
    svc._domain_taken(db, "qa-sunrise-1105.schoolsarthi.com")
    compiled = str(db.scalar.call_args[0][0].compile())
    assert "deleted_at" not in compiled


def test_public_payload_exposes_full_hostname():
    from types import SimpleNamespace

    from app.services.v1.public_school_lookup import _public_payload

    school = SimpleNamespace(
        id=7, name="QA Sunrise", domain="QA-Sunrise-1105.schoolsarthi.com", domain_type="default",
        domain_verified=1, tagline="", logo="", address="", support_phone="", support_email="",
        status=1, provisioned_at=None,
    )
    payload = _public_payload(school)
    assert payload["hostname"] == "qa-sunrise-1105.schoolsarthi.com"
    assert payload["slug"] == "qa-sunrise-1105"
