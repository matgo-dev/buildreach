"""products_i18n_fields

Revision ID: c7551b74e9c7
Revises: b826c151c8cc
Create Date: 2026-06-04 23:29:14.312556
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7551b74e9c7'
down_revision: Union[str, None] = 'b826c151c8cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 新增 i18n 字段
    op.add_column('products', sa.Column('name', sa.String(length=200), server_default='', nullable=False))
    op.add_column('products', sa.Column('name_i18n', sa.JSON(), nullable=True))
    op.add_column('products', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('description_i18n', sa.JSON(), nullable=True))
    op.add_column('products', sa.Column('brand_i18n', sa.JSON(), nullable=True))
    op.add_column('products', sa.Column('origin_i18n', sa.JSON(), nullable=True))

    # 数据迁移：name_en → name, description_en → description
    op.execute("UPDATE products SET name = name_en WHERE name_en IS NOT NULL")
    op.execute("UPDATE products SET description = description_en WHERE description_en IS NOT NULL")
    # name_zh 写入 name_i18n
    op.execute("""
        UPDATE products SET name_i18n = jsonb_build_object('zh', name_zh, 'en', name_en)
        WHERE name_zh IS NOT NULL OR name_en IS NOT NULL
    """)

    # 删除旧字段
    op.drop_column('products', 'name_en')
    op.drop_column('products', 'name_zh')
    op.drop_column('products', 'description_en')

    # origin 列宽从 50 → 100（支持更长的地名）
    op.alter_column('products', 'origin',
               existing_type=sa.VARCHAR(length=50),
               type_=sa.String(length=100),
               existing_nullable=False)


def downgrade() -> None:
    # 恢复旧字段
    op.add_column('products', sa.Column('description_en', sa.TEXT(), nullable=True))
    op.add_column('products', sa.Column('name_zh', sa.VARCHAR(length=200), nullable=True))
    op.add_column('products', sa.Column('name_en', sa.VARCHAR(length=200), server_default='', nullable=False))

    # 数据回迁
    op.execute("UPDATE products SET name_en = name")
    op.execute("UPDATE products SET description_en = description")
    op.execute("UPDATE products SET name_zh = name_i18n->>'zh' WHERE name_i18n IS NOT NULL")

    op.alter_column('products', 'origin',
               existing_type=sa.String(length=100),
               type_=sa.VARCHAR(length=50),
               existing_nullable=False)

    op.drop_column('products', 'origin_i18n')
    op.drop_column('products', 'brand_i18n')
    op.drop_column('products', 'description_i18n')
    op.drop_column('products', 'description')
    op.drop_column('products', 'name_i18n')
    op.drop_column('products', 'name')
