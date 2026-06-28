"""add_published_at_to_products

Revision ID: 5d30666e77ed
Revises: c9d4e5f6a7b8
Create Date: 2026-06-28 11:04:57.280910
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '5d30666e77ed'
down_revision: Union[str, None] = 'c9d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('published_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_products_published_at'), 'products', ['published_at'], unique=False)
    # 回填：已上架商品用 updated_at 作为上架时间
    op.execute("UPDATE products SET published_at = updated_at WHERE status = 'ACTIVE' AND deleted_at IS NULL")


def downgrade() -> None:
    op.drop_index(op.f('ix_products_published_at'), table_name='products')
    op.drop_column('products', 'published_at')
