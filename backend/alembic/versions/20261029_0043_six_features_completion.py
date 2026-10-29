"""Six School Admin features: leave types, announcements lifecycle, staff certs,
payroll structures, messaging.

Revision ID: 20261029_0043
Revises: 20261029_0042
Create Date: 2026-10-29

Do not apply to Neon from this delivery without explicit approval.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_0043"
down_revision: Union[str, None] = "20261029_0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- Leave types ----
    op.create_table(
        "leave_types",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_paid", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("days_per_year", sa.Integer(), nullable=True),
        sa.Column("applies_to", sa.String(length=64), nullable=True),  # all|students|staff|teachers
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_leave_types_school_id", "leave_types", ["school_id"])
    op.create_index(
        "uq_leave_types_school_code_active",
        "leave_types",
        ["school_id", "code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.add_column(
        "leaves",
        sa.Column("leave_type_id", sa.Integer(), sa.ForeignKey("leave_types.id"), nullable=True),
    )
    op.create_index("ix_leaves_leave_type_id", "leaves", ["leave_type_id"])

    # ---- Announcements lifecycle ----
    op.add_column(
        "announcements",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="published"),
    )
    op.add_column("announcements", sa.Column("audience_json", sa.Text(), nullable=True))
    op.add_column("announcements", sa.Column("publish_at", sa.DateTime(), nullable=True))
    op.add_column("announcements", sa.Column("published_at", sa.DateTime(), nullable=True))
    op.add_column("announcements", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_index("ix_announcements_school_status", "announcements", ["school_id", "status"])

    # ---- Notifications audience / delivery tracking (no push) ----
    op.add_column("notifications", sa.Column("audience_json", sa.Text(), nullable=True))
    op.add_column(
        "notifications",
        sa.Column("delivery", sa.String(length=32), nullable=False, server_default="queued"),
    )
    op.add_column("notifications", sa.Column("recipients", sa.Integer(), nullable=True))
    op.add_column("notifications", sa.Column("delivered", sa.Integer(), nullable=True))
    op.add_column("notifications", sa.Column("failed", sa.Integer(), nullable=True))
    op.add_column("notifications", sa.Column("failure_reason", sa.Text(), nullable=True))

    # ---- Certificate issues: staff + verify ----
    op.alter_column("certificate_issues", "student_id", existing_type=sa.Integer(), nullable=True)
    op.add_column(
        "certificate_issues",
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=True),
    )
    op.add_column(
        "certificate_issues",
        sa.Column("verification_token", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "certificate_issues",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="issued"),
    )
    op.add_column("certificate_issues", sa.Column("revoked_at", sa.DateTime(), nullable=True))
    op.add_column(
        "certificate_issues",
        sa.Column("pdf_storage_key", sa.String(length=512), nullable=True),
    )
    op.create_index("ix_certificate_issues_staff_id", "certificate_issues", ["staff_id"])
    op.create_index(
        "uq_certificate_issues_verification_token",
        "certificate_issues",
        ["verification_token"],
        unique=True,
        postgresql_where=sa.text("verification_token IS NOT NULL"),
    )
    op.create_check_constraint(
        "ck_certificate_issues_subject",
        "certificate_issues",
        "(student_id IS NOT NULL AND staff_id IS NULL) OR (student_id IS NULL AND staff_id IS NOT NULL)",
    )

    # ---- Payroll structures / assignments / payslip fields ----
    op.create_table(
        "salary_structures",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("basic", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_salary_structures_school_id", "salary_structures", ["school_id"])

    op.create_table(
        "salary_structure_lines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column(
            "structure_id",
            sa.Integer(),
            sa.ForeignKey("salary_structures.id"),
            nullable=False,
        ),
        sa.Column(
            "component_id",
            sa.Integer(),
            sa.ForeignKey("salary_components.id"),
            nullable=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),  # earning|deduction
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_salary_structure_lines_structure",
        "salary_structure_lines",
        ["school_id", "structure_id"],
    )

    op.create_table(
        "salary_assignments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=False),
        sa.Column(
            "structure_id",
            sa.Integer(),
            sa.ForeignKey("salary_structures.id"),
            nullable=False,
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_salary_assignments_school_id", "salary_assignments", ["school_id"])
    op.create_index(
        "uq_salary_assignments_staff_active",
        "salary_assignments",
        ["school_id", "staff_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.add_column("payroll_runs", sa.Column("processed_at", sa.DateTime(), nullable=True))
    op.add_column(
        "payroll_runs",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "uq_payroll_runs_school_period_active",
        "payroll_runs",
        ["school_id", "period_label"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND status = 'processed'"),
    )
    op.create_index(
        "uq_payroll_runs_idempotency",
        "payroll_runs",
        ["school_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.add_column("payroll_items", sa.Column("breakdown_json", sa.Text(), nullable=True))
    op.add_column(
        "payroll_items",
        sa.Column("payslip_ref", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "payroll_items",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="processed"),
    )
    op.add_column("payroll_items", sa.Column("failure_reason", sa.Text(), nullable=True))
    op.create_index(
        "uq_payroll_items_payslip_ref",
        "payroll_items",
        ["payslip_ref"],
        unique=True,
        postgresql_where=sa.text("payslip_ref IS NOT NULL"),
    )

    op.create_table(
        "payroll_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("payroll_runs.id"), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("detail_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_payroll_audit_events_school", "payroll_audit_events", ["school_id"])

    # ---- Messaging ----
    op.create_table(
        "messaging_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("can_view", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("can_send", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("can_moderate", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("poll_seconds", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "uq_messaging_policies_school_active",
        "messaging_policies",
        ["school_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "message_conversations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("teacher_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("parent_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("flagged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("last_message_preview", sa.String(length=255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_message_conversations_school", "message_conversations", ["school_id"])
    op.create_index(
        "uq_message_conversations_parties",
        "message_conversations",
        ["school_id", "student_id", "teacher_user_id", "parent_user_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("message_conversations.id"),
            nullable=False,
        ),
        sa.Column("sender_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("hidden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_conversation_messages_conversation",
        "conversation_messages",
        ["school_id", "conversation_id"],
    )

    op.create_table(
        "conversation_reads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("message_conversations.id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("last_read_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "uq_conversation_reads_user",
        "conversation_reads",
        ["conversation_id", "user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("conversation_reads")
    op.drop_table("conversation_messages")
    op.drop_table("message_conversations")
    op.drop_table("messaging_policies")
    op.drop_table("payroll_audit_events")
    op.drop_index("uq_payroll_items_payslip_ref", table_name="payroll_items")
    op.drop_column("payroll_items", "failure_reason")
    op.drop_column("payroll_items", "status")
    op.drop_column("payroll_items", "payslip_ref")
    op.drop_column("payroll_items", "breakdown_json")
    op.drop_index("uq_payroll_runs_idempotency", table_name="payroll_runs")
    op.drop_index("uq_payroll_runs_school_period_active", table_name="payroll_runs")
    op.drop_column("payroll_runs", "idempotency_key")
    op.drop_column("payroll_runs", "processed_at")
    op.drop_table("salary_assignments")
    op.drop_table("salary_structure_lines")
    op.drop_table("salary_structures")
    op.drop_constraint("ck_certificate_issues_subject", "certificate_issues", type_="check")
    op.drop_index("uq_certificate_issues_verification_token", table_name="certificate_issues")
    op.drop_index("ix_certificate_issues_staff_id", table_name="certificate_issues")
    op.drop_column("certificate_issues", "pdf_storage_key")
    op.drop_column("certificate_issues", "revoked_at")
    op.drop_column("certificate_issues", "status")
    op.drop_column("certificate_issues", "verification_token")
    op.drop_column("certificate_issues", "staff_id")
    op.alter_column("certificate_issues", "student_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("notifications", "failure_reason")
    op.drop_column("notifications", "failed")
    op.drop_column("notifications", "delivered")
    op.drop_column("notifications", "recipients")
    op.drop_column("notifications", "delivery")
    op.drop_column("notifications", "audience_json")
    op.drop_index("ix_announcements_school_status", table_name="announcements")
    op.drop_column("announcements", "deleted_at")
    op.drop_column("announcements", "published_at")
    op.drop_column("announcements", "publish_at")
    op.drop_column("announcements", "audience_json")
    op.drop_column("announcements", "status")
    op.drop_index("ix_leaves_leave_type_id", table_name="leaves")
    op.drop_column("leaves", "leave_type_id")
    op.drop_index("uq_leave_types_school_code_active", table_name="leave_types")
    op.drop_index("ix_leave_types_school_id", table_name="leave_types")
    op.drop_table("leave_types")
