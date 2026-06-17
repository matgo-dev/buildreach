"""merge buyer_events and rfq_trade_terms heads

Revision ID: 73949f2ea14a
Revises: 2414bd043d08, 7cd4677d50fa
Create Date: 2026-06-17 12:35:32.541385
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '73949f2ea14a'
down_revision: Union[str, None] = ('2414bd043d08', '7cd4677d50fa')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
