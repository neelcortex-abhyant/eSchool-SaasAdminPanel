"""DB-free checks for School Admin Settings wave (Alembic 0040 + crypto + OpenAPI)."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from cryptography.fernet import Fernet
from fastapi.routing import APIRoute

from app.core.config import Settings, get_settings
from app.main import app
from app.models.tables import (
    ContactInquiry,
    PlatformBackup,
    SchoolContentPage,
    SchoolEmailTemplate,
    SchoolFaq,
    SchoolFormField,
    SchoolIntegrationSecret,
    SchoolLeaveSetting,
    SchoolOnlineExamTerms,
    SupportTicket,
    SupportTicketMessage,
)
from app.services.v1 import school_secrets_crypto as crypto
from app.services.v1.school_academics import AcademicError
from app.services.v1.school_settings_cms import CONTENT_SLUGS, WEB_CONTENT_SLUG

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_migration_0040_revises_0039():
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    rev = script.get_revision("20261028_0040")
    assert rev is not None
    assert rev.down_revision == "20261027_0039"
    assert script.get_heads() == ["20261028_0040"]


def test_content_slugs_allowlist():
    assert CONTENT_SLUGS == frozenset(
        {
            "privacy_policy",
            "terms_condition",
            "refund_cancellation",
            "contact_us",
            "about_us",
        }
    )
    assert WEB_CONTENT_SLUG == "web_content"
    assert WEB_CONTENT_SLUG not in CONTENT_SLUGS


def test_fernet_roundtrip_with_temp_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("SCHOOL_SECRETS_KEY", key)
    get_settings.cache_clear()
    try:
        assert get_settings().school_secrets_configured is True
        token = crypto.encrypt_secret("hello-secret")
        assert token != "hello-secret"
        assert crypto.decrypt_secret(token) == "hello-secret"
    finally:
        get_settings.cache_clear()


def test_fernet_unconfigured_raises_503(monkeypatch):
    monkeypatch.setenv("SCHOOL_SECRETS_KEY", "")
    get_settings.cache_clear()
    try:
        assert get_settings().school_secrets_configured is False
        try:
            crypto.encrypt_secret("x")
            raise AssertionError("expected AcademicError")
        except AcademicError as exc:
            assert exc.status_code == 503
    finally:
        get_settings.cache_clear()


def test_settings_cms_models_have_school_id():
    for model in (
        SchoolContentPage,
        SchoolFaq,
        SchoolLeaveSetting,
        SchoolOnlineExamTerms,
        SchoolEmailTemplate,
        SchoolIntegrationSecret,
        SchoolFormField,
        ContactInquiry,
        SupportTicket,
        SupportTicketMessage,
    ):
        assert "school_id" in model.__table__.c, model.__tablename__
    assert "school_id" not in PlatformBackup.__table__.c
    assert "created_by" in PlatformBackup.__table__.c


def test_openapi_registers_settings_paths():
    route_paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    for path in (
        "/api/v1/school-admin/content/{slug}",
        "/api/v1/school-admin/web-content",
        "/api/v1/school-admin/faqs",
        "/api/v1/school-admin/leave-settings",
        "/api/v1/school-admin/online-exam-terms",
        "/api/v1/school-admin/email-templates",
        "/api/v1/school-admin/whatsapp-settings",
        "/api/v1/school-admin/payment-gateway-settings",
        "/api/v1/school-admin/third-party-integrations",
        "/api/v1/school-admin/third-party-integrations/{provider}",
        "/api/v1/school-admin/user-form-fields",
        "/api/v1/school-admin/contact-inquiries",
        "/api/v1/school-admin/support-tickets",
        "/api/v1/school-admin/support-tickets/{ticket_id}/messages",
        "/api/v1/public/schools/{code}/contact-inquiries",
        "/api/v1/super-admin/backups",
        "/api/v1/super-admin/backups/{backup_id}/restore",
    ):
        assert path in route_paths, path


def test_backup_storage_flags_default_off():
    s = Settings(
        school_secrets_key="",
        backup_storage_path="",
        allow_backup_restore=False,
    )
    assert s.school_secrets_configured is False
    assert s.backup_storage_configured is False
    assert s.allow_backup_restore is False
