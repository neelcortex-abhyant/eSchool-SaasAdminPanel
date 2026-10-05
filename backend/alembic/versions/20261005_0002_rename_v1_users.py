"""Rename V1 users table to v1_users to free legacy users name.

Revision ID: 20261005_0002
Revises: 20261005_0001
Create Date: 2026-10-05

Does not rewrite 20261005_0001. Preserves existing V1 rows and sessions.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0002"
down_revision: Union[str, None] = "20261005_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop FK from auth_sessions → users, rename table, recreate FK → v1_users.
    op.drop_constraint("auth_sessions_user_id_fkey", "auth_sessions", type_="foreignkey")
    op.rename_table("users", "v1_users")
    # Rename indexes created by 0001 if they still reference old names.
    # PostgreSQL keeps index names; recreate email unique index name for clarity.
    op.execute('ALTER INDEX IF EXISTS ix_users_email RENAME TO ix_v1_users_email')
    op.create_foreign_key(
        "auth_sessions_user_id_fkey",
        "auth_sessions",
        "v1_users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("auth_sessions_user_id_fkey", "auth_sessions", type_="foreignkey")
    op.execute('ALTER INDEX IF EXISTS ix_v1_users_email RENAME TO ix_users_email')
    op.rename_table("v1_users", "users")
    op.create_foreign_key(
        "auth_sessions_user_id_fkey",
        "auth_sessions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
