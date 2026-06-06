"""product_v2_i18n

Product/ProductSku 多语言从 JSON 模式迁移到 v2 分列模式:
- 删除 *_i18n JSON 列和原始单值列
- 添加 *_zh / *_en 分列
- 添加 source_lang + trans_meta (I18nMixin)

Revision ID: 20260606_v2_i18n
Revises: 20260605_spu_sku
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260606_v2_i18n"
down_revision: Union[str, None] = "20260605_spu_sku"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── products 表 ──────────────────────────────────────
    # 删除 JSON i18n 列
    op.drop_column("products", "name_i18n")
    op.drop_column("products", "description_i18n")
    op.drop_column("products", "brand_i18n")
    op.drop_column("products", "origin_i18n")
    op.drop_column("products", "selling_points_i18n")

    # 删除原始单值列
    op.drop_column("products", "name")
    op.drop_column("products", "description")
    op.drop_column("products", "brand")
    op.drop_column("products", "origin")
    op.drop_column("products", "selling_points")

    # 添加 v2 分列
    op.add_column("products", sa.Column("name_zh", sa.String(200), nullable=False, server_default=""))
    op.add_column("products", sa.Column("name_en", sa.String(200), nullable=True))
    op.add_column("products", sa.Column("description_zh", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("description_en", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("brand_zh", sa.String(100), nullable=True))
    op.add_column("products", sa.Column("brand_en", sa.String(100), nullable=True))
    op.add_column("products", sa.Column("origin_zh", sa.String(100), nullable=False, server_default="中国"))
    op.add_column("products", sa.Column("origin_en", sa.String(100), nullable=True, server_default="China"))
    op.add_column("products", sa.Column("selling_points_zh", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("selling_points_en", sa.Text(), nullable=True))

    # I18nMixin 列
    op.add_column("products", sa.Column("source_lang", sa.String(10), nullable=False, server_default="zh"))
    op.add_column("products", sa.Column("trans_meta", sa.JSON(), nullable=False, server_default="{}"))

    # 清理 server_default(仅迁移用,ORM default 接管)
    op.alter_column("products", "name_zh", server_default=None)

    # ── product_skus 表 ─────────────────────────────────
    # 删除 JSON i18n 列
    op.drop_column("product_skus", "name_i18n")
    op.drop_column("product_skus", "color_i18n")
    op.drop_column("product_skus", "material_i18n")

    # 删除原始单值列
    op.drop_column("product_skus", "name")
    op.drop_column("product_skus", "color")
    op.drop_column("product_skus", "material")

    # 添加 v2 分列
    op.add_column("product_skus", sa.Column("name_zh", sa.String(200), nullable=True))
    op.add_column("product_skus", sa.Column("name_en", sa.String(200), nullable=True))
    op.add_column("product_skus", sa.Column("color_zh", sa.String(50), nullable=True))
    op.add_column("product_skus", sa.Column("color_en", sa.String(50), nullable=True))
    op.add_column("product_skus", sa.Column("material_zh", sa.String(100), nullable=True))
    op.add_column("product_skus", sa.Column("material_en", sa.String(100), nullable=True))

    # I18nMixin 列
    op.add_column("product_skus", sa.Column("source_lang", sa.String(10), nullable=False, server_default="zh"))
    op.add_column("product_skus", sa.Column("trans_meta", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    # ── product_skus 表 ─────────────────────────────────
    op.drop_column("product_skus", "trans_meta")
    op.drop_column("product_skus", "source_lang")
    op.drop_column("product_skus", "material_en")
    op.drop_column("product_skus", "material_zh")
    op.drop_column("product_skus", "color_en")
    op.drop_column("product_skus", "color_zh")
    op.drop_column("product_skus", "name_en")
    op.drop_column("product_skus", "name_zh")

    # 恢复原始列
    op.add_column("product_skus", sa.Column("material", sa.String(100), nullable=True))
    op.add_column("product_skus", sa.Column("color", sa.String(50), nullable=True))
    op.add_column("product_skus", sa.Column("name", sa.String(200), nullable=True))
    op.add_column("product_skus", sa.Column("material_i18n", sa.JSON(), nullable=True))
    op.add_column("product_skus", sa.Column("color_i18n", sa.JSON(), nullable=True))
    op.add_column("product_skus", sa.Column("name_i18n", sa.JSON(), nullable=True))

    # ── products 表 ──────────────────────────────────────
    op.drop_column("products", "trans_meta")
    op.drop_column("products", "source_lang")
    op.drop_column("products", "selling_points_en")
    op.drop_column("products", "selling_points_zh")
    op.drop_column("products", "origin_en")
    op.drop_column("products", "origin_zh")
    op.drop_column("products", "brand_en")
    op.drop_column("products", "brand_zh")
    op.drop_column("products", "description_en")
    op.drop_column("products", "description_zh")
    op.drop_column("products", "name_en")
    op.drop_column("products", "name_zh")

    # 恢复原始列
    op.add_column("products", sa.Column("selling_points", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("origin", sa.String(100), nullable=False, server_default="China"))
    op.add_column("products", sa.Column("brand", sa.String(100), nullable=True))
    op.add_column("products", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("name", sa.String(200), nullable=False, server_default=""))
    op.add_column("products", sa.Column("selling_points_i18n", sa.JSON(), nullable=True))
    op.add_column("products", sa.Column("origin_i18n", sa.JSON(), nullable=True))
    op.add_column("products", sa.Column("brand_i18n", sa.JSON(), nullable=True))
    op.add_column("products", sa.Column("description_i18n", sa.JSON(), nullable=True))
    op.add_column("products", sa.Column("name_i18n", sa.JSON(), nullable=True))

    # 清理恢复列的 server_default
    op.alter_column("products", "name", server_default=None)
    op.alter_column("products", "origin", server_default=None)
