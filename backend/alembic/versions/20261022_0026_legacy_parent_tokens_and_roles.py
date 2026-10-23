"""Legacy parent password tokens + Guardian role backfill for linked parents.

Revision ID: 20261022_0026
Revises: 20261022_0025
Create Date: 2026-10-22

Additive only.
1) Creates legacy_user_password_tokens for integer ``users`` (not v1_users).
2) Ensures school-scoped Guardian roles and assigns them to users who appear as
   students.guardian_id (or student_guardians.guardian_user_id) on non-deleted
   students and do not already hold Guardian for that school.

Does not assign Guardian to staff, students, or unrelated users.
Does not delete or modify passwords.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0026"
down_revision: Union[str, None] = "20261022_0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

USER_MODEL = "App\\Models\\User"


def upgrade() -> None:
    op.create_table(
        "legacy_user_password_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_legacy_user_password_tokens_user_id",
        "legacy_user_password_tokens",
        ["user_id"],
    )
    op.create_index(
        "ix_legacy_user_password_tokens_token_hash",
        "legacy_user_password_tokens",
        ["token_hash"],
        unique=True,
    )
    op.execute(
        sa.text(
            """
            INSERT INTO roles (name, guard_name, school_id, created_at, updated_at)
            SELECT 'Guardian', 'web', s.school_id, NOW(), NOW()
            FROM (
                SELECT DISTINCT school_id FROM students
                WHERE deleted_at IS NULL AND guardian_id IS NOT NULL
                UNION
                SELECT DISTINCT school_id FROM student_guardians
                WHERE deleted_at IS NULL
            ) s
            WHERE NOT EXISTS (
                SELECT 1 FROM roles r
                WHERE r.name = 'Guardian'
                  AND r.guard_name = 'web'
                  AND r.school_id = s.school_id
            )
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            INSERT INTO model_has_roles (role_id, model_id, model_type)
            SELECT DISTINCT r.id, u.id, '{USER_MODEL}'
            FROM users u
            JOIN (
                SELECT school_id, guardian_id AS guardian_user_id
                FROM students
                WHERE deleted_at IS NULL AND guardian_id IS NOT NULL
                UNION
                SELECT school_id, guardian_user_id
                FROM student_guardians
                WHERE deleted_at IS NULL
            ) g ON g.guardian_user_id = u.id AND g.school_id = u.school_id
            JOIN roles r
              ON r.school_id = u.school_id
             AND r.name = 'Guardian'
             AND r.guard_name = 'web'
            WHERE u.deleted_at IS NULL
              AND NOT EXISTS (
                SELECT 1 FROM model_has_roles m
                WHERE m.role_id = r.id
                  AND m.model_id = u.id
                  AND m.model_type = '{USER_MODEL}'
              )
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_legacy_user_password_tokens_token_hash",
        table_name="legacy_user_password_tokens",
    )
    op.drop_index(
        "ix_legacy_user_password_tokens_user_id",
        table_name="legacy_user_password_tokens",
    )
    op.drop_table("legacy_user_password_tokens")
