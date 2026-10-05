"""Create legacy school-scoped schema on shared Neon database.

Revision ID: 20261005_0003
Revises: 20261005_0002
Create Date: 2026-10-05

Maps the FastAPI-backed Laravel-compatible tables into one PostgreSQL database.
Physical database-per-school is replaced by school_id isolation.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0003"
down_revision: Union[str, None] = "20261005_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schools",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("support_phone", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("support_email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("tagline", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("logo", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("admin_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("code", sa.String(length=255), nullable=True),
        sa.Column("database_name", sa.String(length=255), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("installed", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_schools_code", "schools", ["code"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("first_name", sa.String(length=128), nullable=False),
        sa.Column("last_name", sa.String(length=128), nullable=False),
        sa.Column("mobile", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column("gender", sa.String(length=16), nullable=True),
        sa.Column("image", sa.String(length=512), nullable=True),
        sa.Column("dob", sa.Date(), nullable=True),
        sa.Column("country_code", sa.String(length=32), nullable=True),
        sa.Column("current_address", sa.String(length=512), nullable=True),
        sa.Column("permanent_address", sa.String(length=512), nullable=True),
        sa.Column("occupation", sa.String(length=255), nullable=True),
        sa.Column("status", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reset_request", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fcm_id", sa.String(length=1024), nullable=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=True),
        sa.Column("email_verified_at", sa.DateTime(), nullable=True),
        sa.Column("two_factor_enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("two_factor_secret", sa.String(length=255), nullable=True),
        sa.Column("two_factor_expires_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("school_id", "email", name="uq_users_school_email"),
    )
    op.create_index("ix_users_school_id", "users", ["school_id"])

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("guard_name", sa.String(length=255), nullable=False, server_default="web"),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("school_id", "name", "guard_name", name="uq_roles_school_name_guard"),
    )
    op.create_index("ix_roles_school_id", "roles", ["school_id"])

    op.create_table(
        "model_has_roles",
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), primary_key=True),
        sa.Column("model_type", sa.String(length=255), primary_key=True),
        sa.Column("model_id", sa.Integer(), primary_key=True),
        sa.UniqueConstraint("role_id", "model_id", "model_type"),
    )

    op.create_table(
        "personal_access_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tokenable_type", sa.String(length=255), nullable=False),
        sa.Column("tokenable_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False, unique=True),
        sa.Column("abilities", sa.Text(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "packages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("status", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("data", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=255), nullable=True),
    )

    op.create_table(
        "session_years",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("default", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_session_years_school_id", "session_years", ["school_id"])

    op.create_table(
        "mediums",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_mediums_school_id", "mediums", ["school_id"])

    op.create_table(
        "sections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sections_school_id", "sections", ["school_id"])

    op.create_table(
        "classes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("include_semesters", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("medium_id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_classes_school_id", "classes", ["school_id"])

    op.create_table(
        "class_sections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("medium_id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_class_sections_school_id", "class_sections", ["school_id"])

    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("bg_color", sa.String(length=32), nullable=False, server_default="#ffffff"),
        sa.Column("image", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("medium_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False, server_default="Theory"),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_subjects_school_id", "subjects", ["school_id"])

    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("class_section_id", sa.Integer(), nullable=False),
        sa.Column("admission_no", sa.String(length=512), nullable=False),
        sa.Column("roll_number", sa.Integer(), nullable=True),
        sa.Column("admission_date", sa.Date(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("guardian_id", sa.Integer(), nullable=False),
        sa.Column("session_year_id", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_students_school_id", "students", ["school_id"])

    op.create_table(
        "attendances",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("class_section_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("session_year_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("remark", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_attendances_school_id", "attendances", ["school_id"])

    op.create_table(
        "exams",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("session_year_id", sa.Integer(), nullable=False),
        sa.Column("publish", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_exams_school_id", "exams", ["school_id"])

    op.create_table(
        "fees",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("due_charges", sa.Float(), nullable=False, server_default="0"),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("session_year_id", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_fees_school_id", "fees", ["school_id"])

    op.create_table(
        "staffs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=True),
        sa.Column("qualification", sa.String(length=512), nullable=True),
        sa.Column("salary", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_staffs_school_id", "staffs", ["school_id"])

    op.create_table(
        "leaves",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("from_date", sa.Date(), nullable=False),
        sa.Column("to_date", sa.Date(), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("session_year_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_leaves_school_id", "leaves", ["school_id"])

    op.create_table(
        "announcements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("session_year_id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_announcements_school_id", "announcements", ["school_id"])

    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("session_year_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_expenses_school_id", "expenses", ["school_id"])


def downgrade() -> None:
    for table in (
        "expenses",
        "announcements",
        "leaves",
        "staffs",
        "fees",
        "exams",
        "attendances",
        "students",
        "subjects",
        "class_sections",
        "classes",
        "sections",
        "mediums",
        "session_years",
        "system_settings",
        "packages",
        "personal_access_tokens",
        "model_has_roles",
        "roles",
        "users",
        "schools",
    ):
        op.drop_table(table)
