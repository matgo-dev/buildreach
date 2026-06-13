"""add detail_description columns to products

Revision ID: df20b9804b9e
Revises: 5e90efe604ae
Create Date: 2026-06-13 19:14:25.516439
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df20b9804b9e'
down_revision: Union[str, None] = '5e90efe604ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('detail_description_zh', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('detail_description_en', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('detail_description_sw', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'detail_description_sw')
    op.drop_column('products', 'detail_description_en')
    op.drop_column('products', 'detail_description_zh')
