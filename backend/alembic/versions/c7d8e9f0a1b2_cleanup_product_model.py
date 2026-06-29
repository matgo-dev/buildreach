"""删除 product_skus 的硬编码变体列和冗余策略列 + products.ref_price_tiers

product_skus 删除:
- color_zh/en/sw, material_zh/en/sw: 变体属性走 ProductAttr(selectable=True)
- can_consolidate, cargo_type: 拼柜策略在 SPU 级(products 表)已有

products 删除:
- ref_price_tiers: 阿里阶梯参考价,平台不抓/不展示价格,永远为空

Revision ID: c7d8e9f0a1b2
"""
from alembic import op


revision = "c7d8e9f0a1b2"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # product_skus: 删除硬编码变体列
    op.drop_column("product_skus", "color_zh")
    op.drop_column("product_skus", "color_en")
    op.drop_column("product_skus", "color_sw")
    op.drop_column("product_skus", "material_zh")
    op.drop_column("product_skus", "material_en")
    op.drop_column("product_skus", "material_sw")
    # product_skus: 删除与 SPU 重复的拼柜策略列
    op.drop_column("product_skus", "can_consolidate")
    op.drop_column("product_skus", "cargo_type")
    # products: 删除阿里阶梯参考价(永远为空)
    op.drop_column("products", "ref_price_tiers")


def downgrade() -> None:
    import sqlalchemy as sa

    op.add_column("products", sa.Column("ref_price_tiers", sa.JSON(), nullable=True))
    op.add_column("product_skus", sa.Column("cargo_type", sa.String(20), nullable=True))
    op.add_column("product_skus", sa.Column("can_consolidate", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("product_skus", sa.Column("material_sw", sa.String(100), nullable=True))
    op.add_column("product_skus", sa.Column("material_en", sa.String(100), nullable=True))
    op.add_column("product_skus", sa.Column("material_zh", sa.String(100), nullable=True))
    op.add_column("product_skus", sa.Column("color_sw", sa.String(50), nullable=True))
    op.add_column("product_skus", sa.Column("color_en", sa.String(50), nullable=True))
    op.add_column("product_skus", sa.Column("color_zh", sa.String(50), nullable=True))
