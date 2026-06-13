"""add sw columns to products product_skus categories

Revision ID: 5e90efe604ae
Revises: 9fa5741b1679
Create Date: 2026-06-13 15:21:14.771012
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e90efe604ae'
down_revision: Union[str, None] = '9fa5741b1679'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('categories', sa.Column('name_sw', sa.String(length=128), nullable=True))
    op.add_column('product_skus', sa.Column('name_sw', sa.String(length=200), nullable=True))
    op.add_column('product_skus', sa.Column('color_sw', sa.String(length=50), nullable=True))
    op.add_column('product_skus', sa.Column('material_sw', sa.String(length=100), nullable=True))
    op.add_column('products', sa.Column('name_sw', sa.String(length=200), nullable=True))
    op.add_column('products', sa.Column('description_sw', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('brand_sw', sa.String(length=100), nullable=True))
    op.add_column('products', sa.Column('origin_sw', sa.String(length=100), nullable=True))
    op.add_column('products', sa.Column('selling_points_sw', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'selling_points_sw')
    op.drop_column('products', 'origin_sw')
    op.drop_column('products', 'brand_sw')
    op.drop_column('products', 'description_sw')
    op.drop_column('products', 'name_sw')
    op.drop_column('product_skus', 'material_sw')
    op.drop_column('product_skus', 'color_sw')
    op.drop_column('product_skus', 'name_sw')
    op.drop_column('categories', 'name_sw')
