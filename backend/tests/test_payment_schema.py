"""Metadata checks for payment tables. Does not open a database."""

from __future__ import annotations

import inspect

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import BigInteger, CheckConstraint, Float, Index, PrimaryKeyConstraint, UniqueConstraint

from app.models.tables import PaymentTransaction, PaymentWebhookEvent, SubscriptionBill


def test_payment_transaction_columns_and_constraints():
    table = PaymentTransaction.__table__
    columns = {column.name: column for column in table.columns}
    assert columns["amount_paise"].type.__class__ is BigInteger
    assert columns["gateway_order_id"].nullable is False
    assert columns["gateway_payment_id"].nullable is True
    assert columns["currency"].type.length == 3
    assert set(columns) == {
        "id",
        "bill_id",
        "school_id",
        "gateway_order_id",
        "gateway_payment_id",
        "idempotency_key",
        "amount_paise",
        "currency",
        "status",
        "created_at",
        "updated_at",
    }
    secret_names = [name for name in columns if "secret" in name or "signature" in name or "key_id" in name]
    assert secret_names == []
    unique_names = _unique_names(table)
    assert unique_names == {
        "uq_payment_transactions_gateway_order_id",
        "uq_payment_transactions_gateway_payment_id",
        "uq_payment_transactions_school_idempotency",
    }
    checks = [constraint for constraint in table.constraints if isinstance(constraint, CheckConstraint)]
    assert [constraint.name for constraint in checks] == [
        "ck_payment_transactions_amount_paise_non_negative"
    ]
    assert _fk_table(columns["bill_id"]) == "subscription_bills"
    assert _fk_table(columns["school_id"]) == "schools"


def test_webhook_event_idempotency_and_no_payload():
    table = PaymentWebhookEvent.__table__
    names = {column.name for column in table.columns}
    assert "event_id" in names
    assert "payload" not in names
    assert "signature" not in names
    assert _unique_names(table) == {"uq_payment_webhook_events_provider_event"}
    payment_id = table.columns["payment_transaction_id"]
    assert payment_id.nullable is True
    assert _fk_table(payment_id) == "payment_transactions"


def _fk_table(column) -> str:
    return next(iter(column.foreign_keys)).column.table.name


def _unique_names(table) -> set[str]:
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint) and not isinstance(constraint, PrimaryKeyConstraint)
    }


def test_existing_bill_money_column_unchanged():
    amount = SubscriptionBill.__table__.columns["amount"]
    assert amount.type.__class__ is Float
    assert "amount_paise" not in SubscriptionBill.__table__.columns


def test_migration_revises_current_head_and_downgrade_drops_children_first():
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    revision = script.get_revision("20261017_0013")
    assert revision is not None
    assert revision.down_revision == "6bfcc3198722"
    invoice = script.get_revision("20261017_0014")
    assert invoice is not None
    assert invoice.down_revision == "20261017_0013"
    source = inspect.getsource(revision.module.downgrade)
    assert source.index("payment_webhook_events") < source.index("payment_transactions")
    invoice_down = inspect.getsource(invoice.module.downgrade)
    assert invoice_down.index("subscription_invoices") < invoice_down.index("subscription_invoice_counters")


def test_invoice_snapshot_columns_and_constraints():
    from app.models.tables import Package, Subscription, SubscriptionInvoice, SubscriptionInvoiceCounter

    table = SubscriptionInvoice.__table__
    columns = {column.name: column for column in table.columns}
    assert columns["invoice_number"].nullable is False
    assert columns["tax_label"].nullable is True
    assert columns["tax_rate_percent"].nullable is True
    assert columns["tax_amount_paise"].nullable is True
    assert columns["amount_paise"].type.__class__ is BigInteger
    assert "gstin" not in columns
    assert "signature" not in columns
    assert _unique_names(table) == {
        "uq_subscription_invoices_number",
        "uq_subscription_invoices_payment",
    }
    assert _fk_table(columns["payment_transaction_id"]) == "payment_transactions"
    assert _fk_table(columns["bill_id"]) == "subscription_bills"
    assert _fk_table(columns["school_id"]) == "schools"
    assert _fk_table(columns["subscription_id"]) == "subscriptions"
    assert _fk_table(columns["package_id"]) == "packages"
    assert "amount_paise" not in Package.__table__.columns or Package.__table__.columns["monthly_price"].type.__class__ is Float
    assert "invoice_number" not in Subscription.__table__.columns
    assert {column.name for column in SubscriptionInvoiceCounter.__table__.columns} == {"year", "last_value"}


def test_one_open_transaction_per_bill_index_and_webhook_diagnostics():
    indexes = {index.name: index for index in PaymentTransaction.__table__.indexes if isinstance(index, Index)}
    guard = indexes["uq_payment_transactions_bill_open"]
    assert guard.unique is True
    assert [column.name for column in guard.columns] == ["bill_id"]
    assert str(guard.dialect_options["postgresql"]["where"]) == "status <> 4"
    columns = {column.name: column for column in PaymentWebhookEvent.__table__.columns}
    for name in ("gateway_order_id", "gateway_payment_id", "amount_paise", "currency", "outcome"):
        assert columns[name].nullable is True
    assert columns["amount_paise"].type.__class__ is BigInteger


def test_bill_guard_migration_is_the_single_head():
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    revision = script.get_revision("20261019_0015")
    assert revision is not None
    assert revision.down_revision == "20261017_0014"
    assert len(script.get_heads()) == 1, script.get_heads()
    upgrade = inspect.getsource(revision.module.upgrade)
    assert "uq_payment_transactions_bill_open" in upgrade
    assert "status <> 4" in upgrade
    downgrade = inspect.getsource(revision.module.downgrade)
    assert downgrade.index("drop_column") < downgrade.index("drop_index")
