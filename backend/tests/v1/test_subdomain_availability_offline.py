"""Offline unit tests for GET /api/v1/schools/subdomain-availability (service layer)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.v1 import school_service as svc


@pytest.fixture(autouse=True)
def _base_domain(monkeypatch):
    settings = SimpleNamespace(resolved_school_base_domain="eschool.example")
    monkeypatch.setattr(svc, "get_settings", lambda: settings)


def test_available_subdomain():
    db = MagicMock()
    db.scalar.return_value = None
    out = svc.check_subdomain_availability(db, slug="greenvalley", name="Green Valley", city="Pune")
    assert out["slug"] == "greenvalley"
    assert out["available"] is True
    assert out["problem"] is None
    assert out["suggestions"] == []


def test_existing_subdomain_taken():
    db = MagicMock()
    db.scalar.side_effect = [99, None, None, None, None, None, None]
    out = svc.check_subdomain_availability(db, slug="greenvalley", name="Green Valley", city="Pune")
    assert out["available"] is False
    assert "taken" in (out["problem"] or "")
    assert out["slug"] == "greenvalley"
    assert isinstance(out["suggestions"], list)


def test_invalid_format():
    db = MagicMock()
    out = svc.check_subdomain_availability(db, slug="Bad_Slug!", name=None, city=None)
    assert out["available"] is False
    assert "3–40" in (out["problem"] or "") or "lowercase" in (out["problem"] or "")


def test_reserved_subdomain():
    db = MagicMock()
    out = svc.check_subdomain_availability(db, slug="admin", name=None, city=None)
    assert out["available"] is False
    assert "reserved" in (out["problem"] or "").lower()


def test_all_digits_rejected():
    db = MagicMock()
    out = svc.check_subdomain_availability(db, slug="12345", name=None, city=None)
    assert out["available"] is False
    assert "digits" in (out["problem"] or "").lower()


def test_suggestions_do_not_expose_school_ids():
    db = MagicMock()
    db.scalar.return_value = 42
    out = svc.check_subdomain_availability(db, slug="taken-slug", name="River School", city="Pune")
    blob = str(out)
    assert "school_id" not in blob
    assert "42" not in out.get("suggestions", [])
    assert out["available"] is False


def test_missing_slug_and_name():
    db = MagicMock()
    out = svc.check_subdomain_availability(db, slug=None, name=None, city=None)
    assert out["available"] is False
    assert "required" in (out["problem"] or "").lower()
