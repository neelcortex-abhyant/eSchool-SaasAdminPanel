"""Phase 3: school_id/status on v1_users; v1_admin_id + provisioned_at on schools.

Revision ID: 20261007_0005
Revises: 20261007_0004
Create Date: 2026-10-07

Additive only. Does not drop or rewrite prior revisions.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0005"
down_revision: Union[str, None] = "20261007_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("v1_users", sa.Column("school_id", sa.Integer(), nullable=True))
    op.create_index("ix_v1_users_school_id", "v1_users", ["school_id"], unique=False)
    op.create_foreign_key(
        "fk_v1_users_school_id_schools",
        "v1_users",
        "schools",
        ["school_id"],
        ["id"],
    )
    op.add_column(
        "v1_users",
        sa.Column("status", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_v1_users_status", "v1_users", ["status"], unique=False)

    op.add_column("schools", sa.Column("v1_admin_id", sa.String(length=36), nullable=True))
    op.create_index("ix_schools_v1_admin_id", "schools", ["v1_admin_id"], unique=False)
    op.add_column("schools", sa.Column("provisioned_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("schools", "provisioned_at")
    op.drop_index("ix_schools_v1_admin_id", table_name="schools")
    op.drop_column("schools", "v1_admin_id")
    op.drop_index("ix_v1_users_status", table_name="v1_users")
    op.drop_column("v1_users", "status")
    op.drop_constraint("fk_v1_users_school_id_schools", "v1_users", type_="foreignkey")
    op.drop_index("ix_v1_users_school_id", table_name="v1_users")
    op.drop_column("v1_users", "school_id")
