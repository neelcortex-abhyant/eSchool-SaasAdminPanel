"""School branches + branch_id inventory B + v1_user_branch_access.

Revision ID: 20261105_0046
Revises: 20261030_0045
Create Date: 2026-11-05

Upgrade is idempotent for default Main branch creation and NULL branch_id
backfill. Downgrade drops branch_id columns and branch tables — Branch 2
operational separation is destroyed and is not recoverable without backup.
Do not apply to Neon without explicit approval. Downgrade is not for
production data.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "20261105_0046"
down_revision: Union[str, None] = "20261030_0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Inventory B — operational tables that receive branch_id.
# Keep in sync with docs/school-erp-branch-architecture.md and plan.
BRANCH_SCOPED_REQUIRED: tuple[str, ...] = (
    "class_sections",
    "class_subjects",
    "teacher_assignments",
    "class_timetable_entries",
    "students",
    "student_guardians",
    "student_electives",
    "student_transfers",
    "student_promotions",
    "attendances",
    "attendance_locks",
    "attendance_events",
    "homeworks",
    "homework_submissions",
    "study_materials",
    "online_assessments",
    "online_assessment_questions",
    "online_assessment_choices",
    "online_assessment_attempts",
    "online_assessment_answers",
    "exams",
    "offline_exam_schedules",
    "offline_exam_marks",
    "offline_exam_mark_audits",
    "offline_exam_results",
    "report_cards",
    "fee_structures",
    "fee_structure_amounts",
    "fee_installments",
    "fee_assignments",
    "fee_concessions",
    "fee_payments",
    "fee_payment_allocations",
    "fees",
    "announcements",
    "staff_attendance_records",
    "staff_qr_attendance_settings",
    "staff_tasks",
    "leaves",
    "expenses",
    "income_records",
    "salary_assignments",
    "payroll_runs",
    "payroll_items",
    "payroll_audit_events",
    "message_conversations",
    "conversation_messages",
    "conversation_reads",
    "transport_vehicles",
    "transport_routes",
    "transport_stops",
    "student_transport_assignments",
    "transport_trips",
    "transport_gps_points",
    "transport_attendance_events",
    "certificate_issues",
    "person_documents",
    "admission_inquiries",
    "online_classes",
    "syllabi",
    "diary_categories",
    "student_diary_entries",
    "support_tickets",
    "support_ticket_messages",
)

# school_id may be null — keep branch_id nullable after backfill.
BRANCH_SCOPED_OPTIONAL: tuple[str, ...] = (
    "notifications",
    "staffs",
)

BRANCH_SCOPED_TABLES: tuple[str, ...] = BRANCH_SCOPED_REQUIRED + BRANCH_SCOPED_OPTIONAL


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        text("SELECT to_regclass(:n) IS NOT NULL"),
        {"n": f"public.{name}"},
    ).scalar()
    return bool(row)


def _has_column(conn, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :t AND column_name = :c
            """
        ),
        {"t": table, "c": column},
    ).scalar()
    return row is not None


def build_default_main_branch_insert_sql(
    required_tables_with_school_id: Sequence[str],
) -> str:
    """SQL to create one Main branch per school that needs it.

    - Active schools (deleted_at IS NULL) always qualify when they have no live branch.
    - Soft-deleted schools qualify only when they still own rows in at least one
      required branch-scoped table (so historical rows can receive branch_id).
    - Soft-deleted schools with no required rows do not get a Main branch.
    - NOT EXISTS prevents duplicate live Main/default branches.

    ``required_tables_with_school_id`` must be a subset of BRANCH_SCOPED_REQUIRED
    that exist in the target database and have a school_id column.
    """
    safe_tables = [t for t in required_tables_with_school_id if t in BRANCH_SCOPED_REQUIRED]
    if safe_tables:
        orphan_exists = " OR ".join(
            f"EXISTS (SELECT 1 FROM {table} t WHERE t.school_id = s.id)" for table in safe_tables
        )
        school_predicate = f"(s.deleted_at IS NULL OR ({orphan_exists}))"
    else:
        school_predicate = "s.deleted_at IS NULL"

    return f"""
            INSERT INTO school_branches (school_id, name, code, address, status, is_default, created_at, updated_at)
            SELECT s.id, 'Main', 'MAIN', '', 1, 1, NOW(), NOW()
            FROM schools s
            WHERE {school_predicate}
              AND NOT EXISTS (
                SELECT 1 FROM school_branches b
                WHERE b.school_id = s.id AND b.deleted_at IS NULL
              )
            """


def _required_tables_present_with_school_id(conn) -> list[str]:
    present: list[str] = []
    for table in BRANCH_SCOPED_REQUIRED:
        if _table_exists(conn, table) and _has_column(conn, table, "school_id"):
            present.append(table)
    return present


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "school_branches"):
        op.create_table(
            "school_branches",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=True),
            sa.Column("address", sa.String(length=512), nullable=False, server_default=""),
            sa.Column("status", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_default", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_school_branches_school_id", "school_branches", ["school_id"])
        op.create_index(
            "uq_school_branches_school_name_active",
            "school_branches",
            ["school_id", sa.text("lower(btrim(name))")],
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
        )

    if not _table_exists(conn, "v1_user_branch_access"):
        op.create_table(
            "v1_user_branch_access",
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("v1_users.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("branch_id", sa.Integer(), sa.ForeignKey("school_branches.id"), primary_key=True),
            sa.Column("access_role", sa.String(length=32), nullable=False, server_default="branch_admin"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        op.create_index("ix_v1_user_branch_access_branch_id", "v1_user_branch_access", ["branch_id"])

    # Idempotent Main for active schools + soft-deleted schools that still have
    # required operational rows (preserves history; does not undelete the school).
    conn.execute(
        text(
            build_default_main_branch_insert_sql(
                _required_tables_present_with_school_id(conn)
            )
        )
    )

    for table in BRANCH_SCOPED_TABLES:
        if not _table_exists(conn, table):
            continue
        if not _has_column(conn, table, "branch_id"):
            op.add_column(table, sa.Column("branch_id", sa.Integer(), nullable=True))
            op.create_index(f"ix_{table}_branch_id", table, ["branch_id"])

        # Backfill from default branch of same school (no-op when already set).
        if _has_column(conn, table, "school_id"):
            conn.execute(
                text(
                    f"""
                    UPDATE {table} t
                    SET branch_id = d.id
                    FROM school_branches d
                    WHERE d.school_id = t.school_id
                      AND d.is_default = 1
                      AND d.deleted_at IS NULL
                      AND t.branch_id IS NULL
                      AND t.school_id IS NOT NULL
                    """
                )
            )

    # Verify required tables have no NULL branch_id (when school_id present / all rows).
    for table in BRANCH_SCOPED_REQUIRED:
        if not _table_exists(conn, table) or not _has_column(conn, table, "branch_id"):
            continue
        nulls = conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE branch_id IS NULL")).scalar()
        if nulls and int(nulls) > 0:
            raise RuntimeError(
                f"Migration 0046 verification failed: {table} has {nulls} rows with NULL branch_id"
            )
        mismatch = conn.execute(
            text(
                f"""
                SELECT COUNT(*) FROM {table} t
                JOIN school_branches b ON b.id = t.branch_id
                WHERE t.school_id IS NOT NULL AND b.school_id <> t.school_id
                """
            )
        ).scalar()
        if mismatch and int(mismatch) > 0:
            raise RuntimeError(
                f"Migration 0046 verification failed: {table} has {mismatch} school/branch mismatches"
            )

        # FK + NOT NULL for required tables.
        fk_name = f"fk_{table}_branch_id_school_branches"
        try:
            op.create_foreign_key(fk_name, table, "school_branches", ["branch_id"], ["id"])
        except Exception:
            pass
        op.alter_column(table, "branch_id", nullable=False)

    for table in BRANCH_SCOPED_OPTIONAL:
        if not _table_exists(conn, table) or not _has_column(conn, table, "branch_id"):
            continue
        fk_name = f"fk_{table}_branch_id_school_branches"
        try:
            op.create_foreign_key(fk_name, table, "school_branches", ["branch_id"], ["id"])
        except Exception:
            pass


def downgrade() -> None:
    """DESTROYS Branch 2 separation. Dev/empty DBs only — not for production."""
    conn = op.get_bind()
    for table in reversed(BRANCH_SCOPED_TABLES):
        if not _table_exists(conn, table) or not _has_column(conn, table, "branch_id"):
            continue
        fk_name = f"fk_{table}_branch_id_school_branches"
        try:
            op.drop_constraint(fk_name, table, type_="foreignkey")
        except Exception:
            pass
        try:
            op.drop_index(f"ix_{table}_branch_id", table_name=table)
        except Exception:
            pass
        op.drop_column(table, "branch_id")

    if _table_exists(conn, "v1_user_branch_access"):
        op.drop_table("v1_user_branch_access")
    if _table_exists(conn, "school_branches"):
        try:
            op.drop_index("uq_school_branches_school_name_active", table_name="school_branches")
        except Exception:
            pass
        try:
            op.drop_index("ix_school_branches_school_id", table_name="school_branches")
        except Exception:
            pass
        op.drop_table("school_branches")
