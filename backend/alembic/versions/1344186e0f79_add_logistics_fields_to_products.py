"""add logistics fields to products

Revision ID: 1344186e0f79
Revises: 0535dd9a4db5
Create Date: 2026-06-16 18:04:29.053748
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1344186e0f79'
down_revision: Union[str, None] = '0535dd9a4db5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('lead_time_min', sa.Integer(), nullable=True))
    op.add_column('products', sa.Column('lead_time_max', sa.Integer(), nullable=True))
    op.add_column('products', sa.Column('packing_quantity', sa.Integer(), nullable=True))
    op.add_column('products', sa.Column('gross_weight_kg', sa.DECIMAL(precision=8, scale=2), nullable=True))
    op.add_column('products', sa.Column('volume_cbm', sa.DECIMAL(precision=8, scale=4), nullable=True))
    op.add_column('products', sa.Column('can_consolidate', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('products', sa.Column('cargo_type', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'cargo_type')
    op.drop_column('products', 'can_consolidate')
    op.drop_column('products', 'volume_cbm')
    op.drop_column('products', 'gross_weight_kg')
    op.drop_column('products', 'packing_quantity')
    op.drop_column('products', 'lead_time_max')
    op.drop_column('products', 'lead_time_min')
