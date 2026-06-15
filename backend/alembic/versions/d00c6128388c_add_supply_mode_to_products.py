"""add supply_mode to products

Revision ID: d00c6128388c
Revises: a3f8e1b20614
Create Date: 2026-06-15 13:25:07.411573
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd00c6128388c'
down_revision: Union[str, None] = 'a3f8e1b20614'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('supply_mode', sa.String(length=30), server_default='SUPPLIER_DIRECT', nullable=False))
    op.create_index('ix_products_supply_mode', 'products', ['supply_mode'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_products_supply_mode', table_name='products')
    op.drop_column('products', 'supply_mode')
