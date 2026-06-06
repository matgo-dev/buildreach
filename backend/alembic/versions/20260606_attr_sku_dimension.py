"""attr_sku_dimension

product_attrs 加可空 sku_id,让属性既能挂商品维度也能挂 SKU 维度。
唯一约束从 (product_id, attr_key) 改为两条部分唯一索引。

Revision ID: 20260606_attr_sku
Revises: 20260606_v2_i18n
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260606_attr_sku"
down_revision: Union[str, None] = "20260606_v2_i18n"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 加 sku_id 列
    op.add_column(
        "product_attrs",
        sa.Column(
            "sku_id", sa.Integer(),
            sa.ForeignKey("product_skus.id", name="fk_product_attrs_sku_id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # 加 sku_id 普通索引
    op.create_index("ix_product_attrs_sku_id", "product_attrs", ["sku_id"])

    # 删除原唯一约束
    op.drop_constraint("uq_product_attrs_product_key", "product_attrs", type_="unique")

    # 商品级部分唯一索引(sku_id IS NULL)
    op.execute(
        "CREATE UNIQUE INDEX uq_product_attrs_product_key "
        "ON product_attrs (product_id, attr_key) WHERE sku_id IS NULL"
    )

    # SKU 级部分唯一索引(sku_id IS NOT NULL)
    op.execute(
        "CREATE UNIQUE INDEX uq_product_attrs_sku_key "
        "ON product_attrs (sku_id, attr_key) WHERE sku_id IS NOT NULL"
    )


def downgrade() -> None:
    # 删除部分唯一索引
    op.drop_index("uq_product_attrs_sku_key", table_name="product_attrs")
    op.drop_index("uq_product_attrs_product_key", table_name="product_attrs")

    # 恢复原唯一约束
    op.create_unique_constraint(
        "uq_product_attrs_product_key", "product_attrs", ["product_id", "attr_key"]
    )

    # 删除 sku_id 索引和列
    op.drop_index("ix_product_attrs_sku_id", table_name="product_attrs")
    op.drop_column("product_attrs", "sku_id")
