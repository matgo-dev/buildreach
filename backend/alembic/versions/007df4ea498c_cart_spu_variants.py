"""cart_items 从 sku_id 改为 product_id + selected_variants（购物车 SPU 化）

- 新增 product_id (FK → products) + selected_variants (JSON)
- 回填 product_id（从 sku → product 关系）
- sku_id 改可空
- 唯一约束从 (cart_id, sku_id) 改为 (cart_id, product_id)

Revision ID: 007df4ea498c
Revises: a1b2c3d4e5f6
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa

revision = "007df4ea498c"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 新增 product_id 列（先 nullable，回填后收紧）
    op.add_column("cart_items", sa.Column(
        "product_id", sa.Integer(), nullable=True,
    ))
    op.create_foreign_key(
        "fk_cart_items_product_id", "cart_items", "products",
        ["product_id"], ["id"],
    )

    # 2. 新增 selected_variants JSON 列
    op.add_column("cart_items", sa.Column(
        "selected_variants", sa.JSON(), nullable=False, server_default="[]",
    ))

    # 3. sku_id 改可空
    op.alter_column("cart_items", "sku_id", nullable=True)

    # 4. 回填 product_id（从 product_skus 关联取）
    op.execute("""
        UPDATE cart_items
        SET product_id = ps.product_id
        FROM product_skus ps
        WHERE cart_items.sku_id = ps.id
          AND cart_items.product_id IS NULL
    """)

    # 5. 回填后收紧为 NOT NULL
    op.alter_column("cart_items", "product_id", nullable=False)

    # 6. 替换唯一约束
    op.drop_constraint("uq_cart_items_cart_sku", "cart_items", type_="unique")
    op.create_unique_constraint(
        "uq_cart_items_cart_product", "cart_items", ["cart_id", "product_id"],
    )


def downgrade() -> None:
    # 恢复唯一约束
    op.drop_constraint("uq_cart_items_cart_product", "cart_items", type_="unique")
    op.create_unique_constraint(
        "uq_cart_items_cart_sku", "cart_items", ["cart_id", "sku_id"],
    )

    # sku_id 恢复 NOT NULL
    op.alter_column("cart_items", "sku_id", nullable=False)

    # 移除新列
    op.drop_column("cart_items", "selected_variants")
    op.drop_constraint("fk_cart_items_product_id", "cart_items", type_="foreignkey")
    op.drop_column("cart_items", "product_id")
