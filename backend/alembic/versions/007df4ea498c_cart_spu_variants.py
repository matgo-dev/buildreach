"""cart_items SPU 化 + variant_fingerprint 三元组唯一约束

- 新增 product_id (FK → products) + selected_variants (JSON) + variant_fingerprint (VARCHAR(32))
- 回填 product_id（从 sku → product 关系）
- 回填 variant_fingerprint（历史行统一为 md5("[]")）
- sku_id 改可空
- 唯一约束从 (cart_id, sku_id) 改为 (cart_id, product_id, variant_fingerprint)

Revision ID: 007df4ea498c
Revises: a1b2c3d4e5f6
Create Date: 2026-06-15
"""
import hashlib
import json

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

    # 3. 新增 variant_fingerprint 列
    op.add_column("cart_items", sa.Column(
        "variant_fingerprint", sa.String(length=32), nullable=False, server_default="",
    ))

    # 4. sku_id 改可空
    op.alter_column("cart_items", "sku_id", nullable=True)

    # 5. 回填 product_id（从 product_skus 关联取）
    op.execute("""
        UPDATE cart_items
        SET product_id = ps.product_id
        FROM product_skus ps
        WHERE cart_items.sku_id = ps.id
          AND cart_items.product_id IS NULL
    """)

    # 6. 回填 variant_fingerprint：历史行项无 selected_variants（空数组），
    # 统一为空变体的确定性 hash，保证与应用层口径一致
    empty_fp = hashlib.md5(
        json.dumps([], sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    op.execute(f"""
        UPDATE cart_items
        SET variant_fingerprint = '{empty_fp}'
        WHERE variant_fingerprint = ''
    """)

    # 7. 回填后收紧 product_id 为 NOT NULL
    op.alter_column("cart_items", "product_id", nullable=False)

    # 8. 替换唯一约束：从 (cart_id, sku_id) 改为三元组
    op.drop_constraint("uq_cart_items_cart_sku", "cart_items", type_="unique")
    op.create_unique_constraint(
        "uq_cart_items_cart_product_variant", "cart_items",
        ["cart_id", "product_id", "variant_fingerprint"],
    )


def downgrade() -> None:
    # 恢复唯一约束
    op.drop_constraint("uq_cart_items_cart_product_variant", "cart_items", type_="unique")
    op.create_unique_constraint(
        "uq_cart_items_cart_sku", "cart_items", ["cart_id", "sku_id"],
    )

    # sku_id 恢复 NOT NULL
    op.alter_column("cart_items", "sku_id", nullable=False)

    # 移除新列
    op.drop_column("cart_items", "variant_fingerprint")
    op.drop_column("cart_items", "selected_variants")
    op.drop_constraint("fk_cart_items_product_id", "cart_items", type_="foreignkey")
    op.drop_column("cart_items", "product_id")
