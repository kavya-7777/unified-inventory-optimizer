"""add_lane_capacity

Revision ID: c1a2e3f4b5d6
Revises: a5f5260489c9
Create Date: 2026-09-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a2e3f4b5d6'
down_revision: Union[str, None] = 'a5f5260489c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('lanes', sa.Column('capacity', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('lanes', 'capacity')
