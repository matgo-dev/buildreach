"""add short_name to categories

Revision ID: 99acbe5b00b2
Revises: a00ab037065f
Create Date: 2026-06-22 16:48:43.700187
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '99acbe5b00b2'
down_revision: Union[str, None] = 'a00ab037065f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('categories', sa.Column('short_name', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('categories', 'short_name')
