"""spu_sku_restructure

把扁平 products 重构为 SPU + SKU 两层。
新建 product_skus、sku_price_tiers 表；
改造 product_images（加 sku_id）、product_suppliers（product_id → sku_id）；
products 移除下沉字段，新增 spu_code/selling_points。

Revision ID: 20260605_spu_sku
Revises: 3b4626a6aadd
Create Date: 2026-06-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260605_spu_sku"
down_revision: Union[str, None] = "3b4626a6aadd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. 新建 product_skus ──
    op.create_table(
        "product_skus",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("sku_code", sa.String(length=50), nullable=False),
        sa.Column("manufacturer_model", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("name_i18n", sa.JSON(), nullable=True),
        sa.Column("color", sa.String(length=50), nullable=True),
        sa.Column("color_i18n", sa.JSON(), nullable=True),
        sa.Column("material", sa.String(length=100), nullable=True),
        sa.Column("material_i18n", sa.JSON(), nullable=True),
        sa.Column("price_min", sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column("price_max", sa.DECIMAL(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="TZS"),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("moq", sa.Integer(), nullable=False),
        sa.Column("lead_time_min", sa.Integer(), nullable=True),
        sa.Column("lead_time_max", sa.Integer(), nullable=True),
        sa.Column("packing_quantity", sa.Integer(), nullable=True),
        sa.Column("gross_weight_kg", sa.DECIMAL(precision=8, scale=2), nullable=True),
        sa.Column("volume_cbm", sa.DECIMAL(precision=8, scale=4), nullable=True),
        sa.Column("can_consolidate", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("cargo_type", sa.String(length=20), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name="fk_product_skus_product_id", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku_code"),
    )
    op.create_index("ix_product_skus_product_id", "product_skus", ["product_id"])
    op.create_index("ix_product_skus_status", "product_skus", ["status"])
    # 部分唯一索引：每个 SPU 下最多 1 个默认 SKU
    op.execute(
        "CREATE UNIQUE INDEX ix_product_skus_default "
        "ON product_skus (product_id) WHERE is_default"
    )

    # ── 2. 新建 sku_price_tiers ──
    op.create_table(
        "sku_price_tiers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sku_id", sa.Integer(), nullable=False),
        sa.Column("min_qty", sa.Integer(), nullable=False),
        sa.Column("max_qty", sa.Integer(), nullable=True),
        sa.Column("unit_price", sa.DECIMAL(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="TZS"),
        sa.Column("label", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["sku_id"], ["product_skus.id"],
            name="fk_sku_price_tiers_sku_id", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku_id", "min_qty", name="uq_sku_price_tiers_sku_qty"),
    )
    op.create_index("ix_sku_price_tiers_sku_id", "sku_price_tiers", ["sku_id"])

    # ── 3. product_images 加 sku_id ──
    op.add_column(
        "product_images",
        sa.Column("sku_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_product_images_sku_id", "product_images",
        "product_skus", ["sku_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_product_images_sku_id", "product_images", ["sku_id"])

    # ── 4. product_suppliers 加新列（先加后迁再删旧） ──
    op.add_column(
        "product_suppliers",
        sa.Column("sku_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "product_suppliers",
        sa.Column("supplier_currency", sa.String(length=3), nullable=False, server_default="CNY"),
    )
    op.add_column(
        "product_suppliers",
        sa.Column("cif_price_usd", sa.DECIMAL(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        "product_suppliers",
        sa.Column("pvoc_status", sa.String(length=20), nullable=True),
    )

    # ── 5. products 加 SPU 新列（先加，数据迁移后再删旧列） ──
    op.add_column(
        "products",
        sa.Column("spu_code", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("selling_points", sa.Text(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("selling_points_i18n", sa.JSON(), nullable=True),
    )

    # ── 6. 数据迁移 ──
    # 6a. products.spu_code 从 sku_code 派生
    op.execute("UPDATE products SET spu_code = sku_code")

    # 6b. 为每条现有 product 创建 1 个默认 SKU
    op.execute("""
        INSERT INTO product_skus (
            product_id, sku_code, price_min, price_max, currency, unit, moq,
            lead_time_min, lead_time_max, is_default, status, created_at, updated_at
        )
        SELECT
            id, sku_code, price_min, price_max, currency, unit, moq,
            lead_time_days, lead_time_days, true, 'ACTIVE', now(), now()
        FROM products
    """)

    # 6c. product_suppliers.sku_id 指向新建的默认 SKU
    op.execute("""
        UPDATE product_suppliers ps
        SET sku_id = sk.id
        FROM product_skus sk
        WHERE sk.product_id = ps.product_id AND sk.is_default = true
    """)

    # 6d. has_pvoc → pvoc_status
    op.execute("""
        UPDATE product_suppliers
        SET pvoc_status = CASE WHEN has_pvoc = true THEN 'OBTAINED' ELSE NULL END
    """)

    # 6e. product_images.sku_id 保持 NULL（SPU 级）— 无需操作

    # ── 7. 收尾：加约束、删旧列 ──
    # products.spu_code → NOT NULL + UNIQUE
    op.alter_column("products", "spu_code", nullable=False)
    op.create_unique_constraint("uq_products_spu_code", "products", ["spu_code"])

    # product_suppliers.sku_id → NOT NULL + FK + 新唯一约束
    op.alter_column("product_suppliers", "sku_id", nullable=False)
    op.create_foreign_key(
        "fk_product_suppliers_sku_id", "product_suppliers",
        "product_skus", ["sku_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_product_suppliers_sku_id", "product_suppliers", ["sku_id"])

    # 删除旧约束和索引
    op.drop_constraint("uq_product_suppliers_product_supplier", "product_suppliers", type_="unique")
    op.drop_index("ix_product_suppliers_product_id", table_name="product_suppliers")

    # 新唯一约束
    op.create_unique_constraint(
        "uq_product_suppliers_sku_supplier", "product_suppliers", ["sku_id", "supplier_org_id"],
    )

    # supplier_price 精度 10,2 → 12,2
    op.alter_column(
        "product_suppliers", "supplier_price",
        existing_type=sa.DECIMAL(precision=10, scale=2),
        type_=sa.DECIMAL(precision=12, scale=2),
    )

    # 删除 product_suppliers 旧列
    op.drop_constraint("fk_product_suppliers_product_id", "product_suppliers", type_="foreignkey")
    op.drop_column("product_suppliers", "product_id")
    op.drop_column("product_suppliers", "has_pvoc")

    # 删除 products 下沉字段
    op.drop_constraint("products_sku_code_key", "products", type_="unique")
    op.drop_column("products", "sku_code")
    op.drop_column("products", "price_min")
    op.drop_column("products", "price_max")
    op.drop_column("products", "currency")
    op.drop_column("products", "unit")
    op.drop_column("products", "moq")
    op.drop_column("products", "lead_time_days")


def downgrade() -> None:
    # ── 1. products 恢复下沉字段 ──
    op.add_column("products", sa.Column("sku_code", sa.String(length=50), nullable=True))
    op.add_column("products", sa.Column("price_min", sa.DECIMAL(precision=10, scale=2), nullable=True))
    op.add_column("products", sa.Column("price_max", sa.DECIMAL(precision=10, scale=2), nullable=True))
    op.add_column("products", sa.Column("currency", sa.String(length=3), server_default="USD", nullable=True))
    op.add_column("products", sa.Column("unit", sa.String(length=20), nullable=True))
    op.add_column("products", sa.Column("moq", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("lead_time_days", sa.Integer(), nullable=True))

    # ── 2. 从默认 SKU 回填 products ──
    op.execute("""
        UPDATE products p
        SET sku_code = sk.sku_code,
            price_min = sk.price_min,
            price_max = sk.price_max,
            currency = sk.currency,
            unit = sk.unit,
            moq = sk.moq,
            lead_time_days = sk.lead_time_min
        FROM product_skus sk
        WHERE sk.product_id = p.id AND sk.is_default = true
    """)

    # 恢复 NOT NULL 和 UNIQUE
    op.alter_column("products", "sku_code", nullable=False)
    op.alter_column("products", "price_min", nullable=False)
    op.alter_column("products", "price_max", nullable=False)
    op.alter_column("products", "currency", nullable=False)
    op.alter_column("products", "unit", nullable=False)
    op.alter_column("products", "moq", nullable=False)
    op.create_unique_constraint("products_sku_code_key", "products", ["sku_code"])

    # ── 3. product_suppliers 恢复 product_id ──
    op.add_column("product_suppliers", sa.Column("product_id", sa.Integer(), nullable=True))
    op.add_column("product_suppliers", sa.Column("has_pvoc", sa.Boolean(), server_default="false", nullable=False))

    # 从 sku → product 回填 product_id
    op.execute("""
        UPDATE product_suppliers ps
        SET product_id = sk.product_id,
            has_pvoc = CASE WHEN pvoc_status = 'OBTAINED' THEN true ELSE false END
        FROM product_skus sk
        WHERE sk.id = ps.sku_id
    """)

    op.alter_column("product_suppliers", "product_id", nullable=False)
    op.create_foreign_key(
        "fk_product_suppliers_product_id", "product_suppliers",
        "products", ["product_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_product_suppliers_product_id", "product_suppliers", ["product_id"])

    # 删除新约束和列
    op.drop_constraint("uq_product_suppliers_sku_supplier", "product_suppliers", type_="unique")
    op.drop_index("ix_product_suppliers_sku_id", table_name="product_suppliers")
    op.drop_constraint("fk_product_suppliers_sku_id", "product_suppliers", type_="foreignkey")
    op.drop_column("product_suppliers", "sku_id")
    op.drop_column("product_suppliers", "supplier_currency")
    op.drop_column("product_suppliers", "cif_price_usd")
    op.drop_column("product_suppliers", "pvoc_status")

    # 恢复旧唯一约束
    op.create_unique_constraint(
        "uq_product_suppliers_product_supplier", "product_suppliers", ["product_id", "supplier_org_id"],
    )

    # supplier_price 精度恢复
    op.alter_column(
        "product_suppliers", "supplier_price",
        existing_type=sa.DECIMAL(precision=12, scale=2),
        type_=sa.DECIMAL(precision=10, scale=2),
    )

    # ── 4. product_images 删除 sku_id ──
    op.drop_index("ix_product_images_sku_id", table_name="product_images")
    op.drop_constraint("fk_product_images_sku_id", "product_images", type_="foreignkey")
    op.drop_column("product_images", "sku_id")

    # ── 5. 删除 products 新列 ──
    op.drop_constraint("uq_products_spu_code", "products", type_="unique")
    op.drop_column("products", "spu_code")
    op.drop_column("products", "selling_points")
    op.drop_column("products", "selling_points_i18n")

    # ── 6. 删除新表 ──
    op.drop_index("ix_sku_price_tiers_sku_id", table_name="sku_price_tiers")
    op.drop_table("sku_price_tiers")
    op.execute("DROP INDEX IF EXISTS ix_product_skus_default")
    op.drop_index("ix_product_skus_status", table_name="product_skus")
    op.drop_index("ix_product_skus_product_id", table_name="product_skus")
    op.drop_table("product_skus")
