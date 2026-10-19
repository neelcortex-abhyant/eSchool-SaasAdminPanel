"""Payment list query parameters (repeated status) on both list routes. Does not open a database."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.api.deps import central_db
from app.api.v1.deps import require_super_admin
from app.api.v1.payments import require_payment_initiator
from app.main import app
from app.models.tables import School


class FakeDb:
    """Answers count and row queries with empty results; records SQL."""

    def __init__(self):
        self.sql: list[str] = []

    def _record(self, statement):
        self.sql.append(
            str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        )

    def scalar(self, statement):
        self._record(statement)
        return 0

    def scalars(self, statement):
        self._record(statement)
        return []

    def execute(self, statement):
        self._record(statement)
        return SimpleNamespace(all=lambda: [])

    def get(self, model, key):
        if model is School:
            return SimpleNamespace(id=key, deleted_at=None)
        return None


@pytest.fixture()
def client():
    db = FakeDb()
    super_admin = SimpleNamespace(user=SimpleNamespace(role="super_admin", school_id=None))
    app.dependency_overrides[require_super_admin] = lambda: super_admin
    app.dependency_overrides[require_payment_initiator] = lambda: super_admin
    app.dependency_overrides[central_db] = lambda: db
    try:
        yield TestClient(app), db
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("path", ["/api/v1/super-admin/payments", "/api/v1/schools/7/payments"])
def test_repeated_status_matches_any_listed_status(client, path):
    http, db = client
    response = http.get(f"{path}?status=0&status=1&from_date=2026-10-01&to_date=2026-10-19")
    assert response.status_code == 200, response.text
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}
    assert any("payment_transactions.status IN (0, 1)" in sql for sql in db.sql)


@pytest.mark.parametrize("path", ["/api/v1/super-admin/payments", "/api/v1/schools/7/payments"])
def test_single_status_still_works(client, path):
    http, db = client
    assert http.get(f"{path}?status=2").status_code == 200
    assert any("payment_transactions.status IN (2)" in sql for sql in db.sql)


@pytest.mark.parametrize("path", ["/api/v1/super-admin/payments", "/api/v1/schools/7/payments"])
def test_out_of_range_or_text_status_is_rejected(client, path):
    http, _ = client
    out_of_range = http.get(f"{path}?status=0&status=9")
    assert out_of_range.status_code == 422
    assert out_of_range.json()["detail"] == "status must be from 0 through 4"
    assert http.get(f"{path}?status=successful").status_code == 422


def test_frontend_style_super_admin_school_path_does_not_exist(client):
    http, _ = client
    assert http.get("/api/v1/super-admin/schools/7/payments").status_code in (404, 405)
