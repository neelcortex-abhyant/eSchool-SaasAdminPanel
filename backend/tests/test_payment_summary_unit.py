"""GET /api/v1/super-admin/payments/summary routing and shape. Does not open a database."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.api.deps import central_db
from app.api.v1.deps import require_super_admin
from app.main import app
from app.services.v1 import payment_history_service

SUMMARY_KEYS = {
    "currency",
    "successful_amount_paise",
    "successful_amount",
    "successful_count",
    "pending_count",
    "failed_count",
    "refunded_count",
    "total_count",
}


class FakeResult:
    def __init__(self, row):
        self._row = row

    def one(self):
        return self._row


class FakeDb:
    """Records the summary statement and returns one aggregate row."""

    def __init__(self, row=(249900, 1, 2, 3, 0, 6)):
        self.row = row
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)
        return FakeResult(self.row)

    def get(self, model, key):
        return None


@pytest.fixture()
def client():
    db = FakeDb()
    app.dependency_overrides[require_super_admin] = lambda: SimpleNamespace(user=SimpleNamespace(role="super_admin"))
    app.dependency_overrides[central_db] = lambda: db
    try:
        yield TestClient(app), db
    finally:
        app.dependency_overrides.clear()


def test_summary_route_is_not_parsed_as_a_payment_id(client):
    http, db = client
    response = http.get("/api/v1/super-admin/payments/summary")
    assert response.status_code == 200, response.text
    assert set(response.json()) == SUMMARY_KEYS
    assert len(db.statements) == 1


def test_summary_values_come_from_the_aggregate_row(client):
    http, _ = client
    body = http.get("/api/v1/super-admin/payments/summary").json()
    assert body == {
        "currency": "INR",
        "successful_amount_paise": 249900,
        "successful_amount": 2499.0,
        "successful_count": 1,
        "pending_count": 2,
        "failed_count": 3,
        "refunded_count": 0,
        "total_count": 6,
    }


def test_empty_table_returns_zeros(client):
    http, db = client
    db.row = (None, 0, 0, 0, 0, 0)
    body = http.get("/api/v1/super-admin/payments/summary").json()
    assert body["successful_amount_paise"] == 0
    assert body["successful_amount"] == 0
    assert body["total_count"] == 0


def test_numeric_payment_id_still_uses_the_detail_route(client):
    http, _ = client
    response = http.get("/api/v1/super-admin/payments/12345")
    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found"


def test_summary_validates_filters(client):
    http, _ = client
    assert http.get("/api/v1/super-admin/payments/summary?from_date=2026-10-10&to_date=2026-10-01").status_code == 422
    assert http.get("/api/v1/super-admin/payments/summary?school_id=0").status_code == 422
    assert http.get("/api/v1/super-admin/payments/summary?school_id=4&from_date=2026-10-01").status_code == 200


def test_summary_requires_authentication():
    app.dependency_overrides.clear()
    response = TestClient(app).get("/api/v1/super-admin/payments/summary")
    assert response.status_code in (401, 403)
    assert "currency" not in response.text


def test_summary_sql_filters_currency_and_uses_status_aggregates():
    db = FakeDb()
    payment_history_service.summarize_payments(db, currency="INR", school_id=4)
    sql = str(db.statements[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "FROM payment_transactions" in sql
    assert "payment_transactions.currency = 'INR'" in sql
    assert "payment_transactions.school_id = 4" in sql
    assert "FILTER (WHERE payment_transactions.status = 2)" in sql
    assert "FILTER (WHERE payment_transactions.status IN (0, 1))" in sql


def test_summary_is_registered_before_the_payment_id_route():
    from fastapi.routing import APIRoute

    from app.schemas.v1.payments import PaymentSummaryResponse

    paths = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/v1/super-admin/payments/")
    ]
    order = [route.path for route in paths]
    assert "/api/v1/super-admin/payments/summary" in order
    assert order.index("/api/v1/super-admin/payments/summary") < order.index(
        "/api/v1/super-admin/payments/{payment_id}"
    )
    summary = next(route for route in paths if route.path.endswith("/summary"))
    assert summary.methods == {"GET"}
    assert summary.response_model is PaymentSummaryResponse


def test_summary_never_returns_the_payment_id_parse_error(client):
    """Production 422 on the old code: int_parsing at path.payment_id with input "summary"."""
    http, _ = client
    response = http.get("/api/v1/super-admin/payments/summary")
    assert response.status_code == 200
    assert "int_parsing" not in response.text
    assert "payment_id" not in response.text
