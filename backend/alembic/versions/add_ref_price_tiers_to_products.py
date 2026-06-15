"""products 新增 ref_price_tiers JSONB 列（阿里阶梯参考价）

Revision ID: b3c4d5e6f7g8
Revises: 007df4ea498c
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa

revision = "b3c4d5e6f7g8"
down_revision = "007df4ea498c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("ref_price_tiers", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "ref_price_tiers")
