"""add is_leaf to categories

Revision ID: 9f809a16689c
Revises: 73949f2ea14a
Create Date: 2026-06-18 10:40:16.700123
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f809a16689c'
down_revision: Union[str, None] = '73949f2ea14a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 加 is_leaf 列(参考阿里 B2B leaf 字段,避免每次查子节点)
    op.add_column(
        'categories',
        sa.Column('is_leaf', sa.Boolean(), nullable=False, server_default='true'),
    )

    # 数据回填:有 active 子节点的品类标记为 non-leaf
    op.execute("""
        UPDATE categories SET is_leaf = false
        WHERE code IN (
            SELECT DISTINCT parent_code
            FROM categories
            WHERE parent_code IS NOT NULL AND is_active = true
        )
    """)


def downgrade() -> None:
    op.drop_column('categories', 'is_leaf')
