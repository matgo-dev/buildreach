"""move unit currency from sku to spu

Revision ID: 1c6db231a44b
Revises: 4a153ef93f20
Create Date: 2026-06-09 16:04:24.301360
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c6db231a44b'
down_revision: Union[str, None] = '4a153ef93f20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SPU 表加 unit / currency
    op.add_column('products', sa.Column('unit', sa.String(length=20), nullable=False, server_default='PCS'))
    op.add_column('products', sa.Column('currency', sa.String(length=3), nullable=False, server_default='TZS'))

    # SKU 表删 unit / currency
    op.drop_column('product_skus', 'unit')
    op.drop_column('product_skus', 'currency')


def downgrade() -> None:
    # SKU 表恢复 unit / currency
    op.add_column('product_skus', sa.Column('currency', sa.VARCHAR(length=3), server_default=sa.text("'TZS'::character varying"), autoincrement=False, nullable=False))
    op.add_column('product_skus', sa.Column('unit', sa.VARCHAR(length=20), autoincrement=False, nullable=False))

    # SPU 表删 unit / currency
    op.drop_column('products', 'currency')
    op.drop_column('products', 'unit')
