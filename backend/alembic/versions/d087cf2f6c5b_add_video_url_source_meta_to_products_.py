"""add video_url source_meta to products and source_url to product_images

Revision ID: d087cf2f6c5b
Revises: 1344186e0f79
Create Date: 2026-06-17 08:25:20.268905
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd087cf2f6c5b'
down_revision: Union[str, None] = '1344186e0f79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('product_images', sa.Column('source_url', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('video_url', sa.String(length=500), nullable=True))
    op.add_column('products', sa.Column('source_meta', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'source_meta')
    op.drop_column('products', 'video_url')
    op.drop_column('product_images', 'source_url')
