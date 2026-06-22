"""feat: banner_slides table + category short_name i18n

Revision ID: 4c8cfbd92ad8
Revises: 99acbe5b00b2
Create Date: 2026-06-22 17:56:54.528677
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c8cfbd92ad8'
down_revision: Union[str, None] = '99acbe5b00b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- banner_slides 新表 ---
    op.create_table('banner_slides',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title_zh', sa.String(length=100), nullable=True),
        sa.Column('title_en', sa.String(length=100), nullable=True),
        sa.Column('title_sw', sa.String(length=100), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=False),
        sa.Column('link_url', sa.String(length=500), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('position', sa.String(length=50), server_default='home_carousel', nullable=False),
        sa.Column('start_at', sa.DateTime(), nullable=True),
        sa.Column('end_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('source_lang', sa.String(length=10), nullable=False),
        sa.Column('trans_meta', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('i18n_pending_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_banner_slides_i18n_pending_at'), 'banner_slides', ['i18n_pending_at'], unique=False)

    # --- categories: short_name → short_name_zh/en/sw ---
    op.add_column('categories', sa.Column('short_name_zh', sa.String(length=20), nullable=True))
    op.add_column('categories', sa.Column('short_name_en', sa.String(length=20), nullable=True))
    op.add_column('categories', sa.Column('short_name_sw', sa.String(length=20), nullable=True))
    # 数据迁移: 旧 short_name → short_name_zh
    op.execute("UPDATE categories SET short_name_zh = short_name WHERE short_name IS NOT NULL")
    op.drop_column('categories', 'short_name')


def downgrade() -> None:
    op.add_column('categories', sa.Column('short_name', sa.VARCHAR(length=20), autoincrement=False, nullable=True))
    op.execute("UPDATE categories SET short_name = short_name_zh WHERE short_name_zh IS NOT NULL")
    op.drop_column('categories', 'short_name_sw')
    op.drop_column('categories', 'short_name_en')
    op.drop_column('categories', 'short_name_zh')
    op.drop_index(op.f('ix_banner_slides_i18n_pending_at'), table_name='banner_slides')
    op.drop_table('banner_slides')
