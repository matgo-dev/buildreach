"""attr_templates 加 selectable + rfq_items SPU 化（ADR-0006）

- attr_templates: 新增 selectable 列
- rfq_items: 新增 product_id + variant_snapshot，sku_id 改可空
- rfq_items: sku_spec_snapshot_zh/en 改名 variant_snapshot_zh/en
- rfq_items: 替换唯一约束

Revision ID: a1b2c3d4e5f6
Revises: d00c6128388c
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "d00c6128388c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Part 1: attr_templates 加 selectable ──
    op.add_column(
        "attr_templates",
        sa.Column("selectable", sa.Boolean(), nullable=False, server_default="false"),
    )

    # ── Part 2: rfq_items SPU 化 ──

    # 2a. 新增 product_id（先 nullable，回填后收紧）
    op.add_column(
        "rfq_items",
        sa.Column("product_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_rfq_items_product_id",
        "rfq_items",
        "products",
        ["product_id"],
        ["id"],
    )

    # 2b. 新增 variant_snapshot (JSON)
    op.add_column(
        "rfq_items",
        sa.Column("variant_snapshot", sa.JSON(), nullable=False, server_default="[]"),
    )

    # 2c. sku_id 改可空
    op.alter_column("rfq_items", "sku_id", existing_type=sa.Integer(), nullable=True)

    # 2d. sku_spec_snapshot_zh/en 改名
    op.alter_column(
        "rfq_items",
        "sku_spec_snapshot_zh",
        new_column_name="variant_snapshot_zh",
    )
    op.alter_column(
        "rfq_items",
        "sku_spec_snapshot_en",
        new_column_name="variant_snapshot_en",
    )

    # 2e. 回填历史数据：从 sku_id 反查 product_id
    op.execute("""
        UPDATE rfq_items
        SET product_id = ps.product_id
        FROM product_skus ps
        WHERE rfq_items.sku_id = ps.id
          AND rfq_items.product_id IS NULL
    """)

    # 2f. 收紧 product_id 为 NOT NULL
    # 注意：如果有 rfq_items 的 sku_id 指向已删除的 product_skus，回填会漏掉
    # 这些孤儿行需要手动处理或先删除，否则此步会失败
    op.alter_column("rfq_items", "product_id", existing_type=sa.Integer(), nullable=False)

    # 2g. 替换唯一约束
    op.drop_index("uq_rfq_items_rfq_sku_active", table_name="rfq_items")
    op.create_index(
        "ix_rfq_items_rfq_product",
        "rfq_items",
        ["rfq_id", "product_id"],
    )


def downgrade() -> None:
    # 回滚索引
    op.drop_index("ix_rfq_items_rfq_product", table_name="rfq_items")
    op.create_index(
        "uq_rfq_items_rfq_sku_active",
        "rfq_items",
        ["rfq_id", "sku_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # 恢复列名
    op.alter_column("rfq_items", "variant_snapshot_en", new_column_name="sku_spec_snapshot_en")
    op.alter_column("rfq_items", "variant_snapshot_zh", new_column_name="sku_spec_snapshot_zh")

    # sku_id 恢复 NOT NULL
    op.alter_column("rfq_items", "sku_id", existing_type=sa.Integer(), nullable=False)

    # 删除新增列
    op.drop_column("rfq_items", "variant_snapshot")
    op.drop_constraint("fk_rfq_items_product_id", "rfq_items", type_="foreignkey")
    op.drop_column("rfq_items", "product_id")

    # Part 1 回滚
    op.drop_column("attr_templates", "selectable")
