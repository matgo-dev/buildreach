"""add swatch_image column to product_attrs

Revision ID: bdf9c2192003
Revises: 9f809a16689c
Create Date: 2026-06-18 21:46:36.212293
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bdf9c2192003'
down_revision: Union[str, None] = '9f809a16689c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('product_attrs', sa.Column('swatch_image', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('product_attrs', 'swatch_image')
