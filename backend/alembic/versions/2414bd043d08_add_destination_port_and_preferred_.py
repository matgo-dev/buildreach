"""add destination_port and preferred_trade_term to rfqs

Revision ID: 2414bd043d08
Revises: d087cf2f6c5b
Create Date: 2026-06-17 11:13:12.331834
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2414bd043d08'
down_revision: Union[str, None] = 'd087cf2f6c5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rfqs', sa.Column('destination_port', sa.String(100), nullable=True))
    op.add_column('rfqs', sa.Column('preferred_trade_term', sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column('rfqs', 'preferred_trade_term')
    op.drop_column('rfqs', 'destination_port')
