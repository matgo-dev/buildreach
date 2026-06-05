"""product_images_redesign

Revision ID: 3b4626a6aadd
Revises: c7551b74e9c7
Create Date: 2026-06-05 17:08:04.849788
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3b4626a6aadd'
down_revision: Union[str, None] = 'c7551b74e9c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 新增字段
    op.add_column('product_images', sa.Column('image_key', sa.String(length=300), server_default='', nullable=False))
    op.add_column('product_images', sa.Column('image_type', sa.String(length=20), server_default='GALLERY', nullable=False))
    op.add_column('product_images', sa.Column('width', sa.Integer(), nullable=True))
    op.add_column('product_images', sa.Column('height', sa.Integer(), nullable=True))
    op.add_column('product_images', sa.Column('file_size', sa.Integer(), nullable=True))
    op.create_index('ix_product_images_type', 'product_images', ['product_id', 'image_type'], unique=False)

    # 数据迁移：url → image_key（去掉 /uploads/ 前缀）
    op.execute("UPDATE product_images SET image_key = REPLACE(url, '/uploads/', '') WHERE url IS NOT NULL")
    # 第一张图（sort_order=0）设为 MAIN
    op.execute("UPDATE product_images SET image_type = 'MAIN' WHERE sort_order = 0")

    # 删除旧字段
    op.drop_column('product_images', 'url')


def downgrade() -> None:
    op.add_column('product_images', sa.Column('url', sa.VARCHAR(length=500), server_default='', nullable=False))
    op.execute("UPDATE product_images SET url = '/uploads/' || image_key")
    op.drop_index('ix_product_images_type', table_name='product_images')
    op.drop_column('product_images', 'file_size')
    op.drop_column('product_images', 'height')
    op.drop_column('product_images', 'width')
    op.drop_column('product_images', 'image_type')
    op.drop_column('product_images', 'image_key')
