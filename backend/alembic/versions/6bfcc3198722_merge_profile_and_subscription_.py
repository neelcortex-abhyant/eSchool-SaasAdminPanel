"""merge profile and subscription migrations

Revision ID: 6bfcc3198722
Revises: 20261014_0011, 20261016_0012
Create Date: 2026-10-16 21:43:04.472376

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6bfcc3198722'
down_revision: Union[str, None] = ('20261014_0011', '20261016_0012')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
