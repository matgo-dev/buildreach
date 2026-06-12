"""add selectable column to product_attrs

Revision ID: 1c9a56723713
Revises: 04b3b5e32d7b
Create Date: 2026-06-12 20:17:34.989076
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c9a56723713'
down_revision: Union[str, None] = '04b3b5e32d7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('product_attrs', sa.Column('selectable', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('product_attrs', 'selectable')
