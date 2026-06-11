"""quote_item_add_skipped

Revision ID: fe438ffd1696
Revises: 47664fb17683
Create Date: 2026-06-11 18:05:18.943285
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe438ffd1696'
down_revision: Union[str, None] = '47664fb17683'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rfq_quote_items', sa.Column('skipped', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('rfq_quote_items', sa.Column('skip_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('rfq_quote_items', 'skip_reason')
    op.drop_column('rfq_quote_items', 'skipped')
