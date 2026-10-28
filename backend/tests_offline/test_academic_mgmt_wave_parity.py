"""DB-free checks for Academic Management Wave (Alembic 0039 + grading lookup)."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.models.tables import (
    FeePayment,
    FeeType,
    GradingScale,
    Holiday,
    QuestionBankQuestion,
    ReportCard,
    TransportVehicle,
)
from app.services.v1.school_academic_mgmt import letter_for_percentage

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_migration_0039_revises_0038():
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    rev = script.get_revision("20261027_0039")
    assert rev is not None
    assert rev.down_revision == "20261025_0038"
    assert script.get_heads() == ["20261028_0040"]


def test_key_wave_models_have_school_id():
    for model in (
        GradingScale,
        ReportCard,
        QuestionBankQuestion,
        Holiday,
        FeeType,
        FeePayment,
        TransportVehicle,
    ):
        assert "school_id" in model.__table__.c, model.__tablename__


def test_letter_for_percentage_band_lookup():
    bands = [
        {"letter": "A", "min_percent": 80, "max_percent": 100},
        {"letter": "B", "min_percent": 60, "max_percent": 79.99},
        {"letter": "C", "min_percent": 0, "max_percent": 59.99},
    ]
    assert letter_for_percentage(bands, 91) == "A"
    assert letter_for_percentage(bands, 80) == "A"
    assert letter_for_percentage(bands, 60) == "B"
    assert letter_for_percentage(bands, 0) == "C"
    assert letter_for_percentage(bands, 100) == "A"
    assert letter_for_percentage(bands, -1) is None
