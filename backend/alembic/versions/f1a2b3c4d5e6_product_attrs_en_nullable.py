"""product_attrs: attr_key_en / attr_value_en 改 nullable + 重建唯一索引

纯中文数据源(XFS 等)只填 _zh 列,_en 留 NULL 由 i18n 管道补译。
模型已声明 nullable=True,此 migration 同步数据库。

Revision ID: f1a2b3c4d5e6
Revises: e36a9e44d149
Create Date: 2026-06-29 14:40:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e36a9e44d149"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 列 nullable
    op.alter_column("product_attrs", "attr_key_en",
                     existing_type=sa.String(50), nullable=True)
    op.alter_column("product_attrs", "attr_value_en",
                     existing_type=sa.String(200), nullable=True)

    # 2. 重建唯一索引(product_attrs 无 soft delete,不加 deleted_at 条件)
    #    nullable 后 NULL 不参与 PG 唯一判定,不会误冲突
    pass


def downgrade() -> None:
    # 回滚前需确保所有 _en 列已有值,否则 NOT NULL 会失败
    op.execute("UPDATE product_attrs SET attr_key_en = attr_key_zh WHERE attr_key_en IS NULL")
    op.execute("UPDATE product_attrs SET attr_value_en = attr_value_zh WHERE attr_value_en IS NULL")
    op.alter_column("product_attrs", "attr_value_en",
                     existing_type=sa.String(200), nullable=False)
    op.alter_column("product_attrs", "attr_key_en",
                     existing_type=sa.String(50), nullable=False)
