"""add i18n_pending_at to products and product_skus

Revision ID: 1220b76561ab
Revises: df20b9804b9e
Create Date: 2026-06-13 23:59:07.337377
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1220b76561ab'
down_revision: Union[str, None] = 'df20b9804b9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('i18n_pending_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_products_i18n_pending_at'), 'products', ['i18n_pending_at'], unique=False)
    op.add_column('product_skus', sa.Column('i18n_pending_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_product_skus_i18n_pending_at'), 'product_skus', ['i18n_pending_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_product_skus_i18n_pending_at'), table_name='product_skus')
    op.drop_column('product_skus', 'i18n_pending_at')
    op.drop_index(op.f('ix_products_i18n_pending_at'), table_name='products')
    op.drop_column('products', 'i18n_pending_at')
