"""ingest: ingest_run table, products source/run_fk, attrs i18n/group/value_type, image spec_value, relax constraints

Revision ID: 04b3b5e32d7b
Revises: fe438ffd1696
Create Date: 2026-06-12 16:08:23.077103
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '04b3b5e32d7b'
down_revision: Union[str, None] = 'fe438ffd1696'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. ingest_run 表(先建,因 products FK 引用它) ──
    op.create_table(
        "ingest_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_key", sa.String(200), nullable=False, unique=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("operator", sa.String(100), nullable=True),
        sa.Column("crawled_at", sa.DateTime(), nullable=True),
        sa.Column("imported_at", sa.DateTime(), nullable=True),
        sa.Column("product_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="RUNNING"),
        sa.Column("raw_path", sa.String(500), nullable=False),
        sa.Column("error_summary", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False,
            server_default=sa.text("(now() at time zone 'utc')"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False,
            server_default=sa.text("(now() at time zone 'utc')"),
        ),
    )

    # ── 2. products 加列 ──
    op.add_column(
        "products",
        sa.Column("source", sa.String(50), nullable=False, server_default="MANUAL"),
    )
    op.create_index("ix_products_source", "products", ["source"])

    op.add_column(
        "products",
        sa.Column("last_ingest_run_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_products_last_ingest_run_id",
        "products", "ingest_runs",
        ["last_ingest_run_id"], ["id"],
    )

    # ── 3. product_attrs 加列 ──
    op.add_column(
        "product_attrs",
        sa.Column("value_type", sa.String(20), nullable=False, server_default="text"),
    )
    op.add_column(
        "product_attrs",
        sa.Column("attr_group", sa.String(100), nullable=True),
    )
    op.add_column(
        "product_attrs",
        sa.Column("attr_key_zh", sa.String(50), nullable=True),
    )
    op.add_column(
        "product_attrs",
        sa.Column("attr_value_zh", sa.String(500), nullable=True),
    )

    # ── 4. product_images 加列 ──
    op.add_column(
        "product_images",
        sa.Column("spec_value", sa.String(200), nullable=True),
    )

    # ── 5. product_attrs 唯一约束放宽 ──
    # 旧:(product_id, attr_key) → 新:(product_id, attr_key, attr_value)
    # 同一 attr_key 可以有多个 value(如"颜色"有红/蓝/绿)
    op.drop_index("uq_product_attrs_product_key", table_name="product_attrs")
    op.drop_index("uq_product_attrs_sku_key", table_name="product_attrs")

    op.create_index(
        "uq_product_attrs_product_key_val",
        "product_attrs",
        ["product_id", "attr_key", "attr_value"],
        unique=True,
        postgresql_where=sa.text("sku_id IS NULL"),
    )
    op.create_index(
        "uq_product_attrs_sku_key_val",
        "product_attrs",
        ["sku_id", "attr_key", "attr_value"],
        unique=True,
        postgresql_where=sa.text("sku_id IS NOT NULL"),
    )

    # ── 6. categories CHECK 约束放宽:level IN (1,2,3) → level >= 1 ──
    op.drop_constraint("ck_categories_level", "categories", type_="check")
    op.create_check_constraint(
        "ck_categories_level",
        "categories",
        sa.text("level >= 1"),
    )


def downgrade() -> None:
    # ── 6. 恢复 categories CHECK ──
    op.drop_constraint("ck_categories_level", "categories", type_="check")
    op.create_check_constraint(
        "ck_categories_level",
        "categories",
        sa.text("level IN (1, 2, 3)"),
    )

    # ── 5. 恢复旧唯一约束 ──
    op.drop_index("uq_product_attrs_sku_key_val", table_name="product_attrs")
    op.drop_index("uq_product_attrs_product_key_val", table_name="product_attrs")

    op.create_index(
        "uq_product_attrs_product_key",
        "product_attrs",
        ["product_id", "attr_key"],
        unique=True,
        postgresql_where=sa.text("sku_id IS NULL"),
    )
    op.create_index(
        "uq_product_attrs_sku_key",
        "product_attrs",
        ["sku_id", "attr_key"],
        unique=True,
        postgresql_where=sa.text("sku_id IS NOT NULL"),
    )

    # ── 4. product_images 删列 ──
    op.drop_column("product_images", "spec_value")

    # ── 3. product_attrs 删列 ──
    op.drop_column("product_attrs", "attr_value_zh")
    op.drop_column("product_attrs", "attr_key_zh")
    op.drop_column("product_attrs", "attr_group")
    op.drop_column("product_attrs", "value_type")

    # ── 2. products 删列 ──
    op.drop_constraint("fk_products_last_ingest_run_id", "products", type_="foreignkey")
    op.drop_column("products", "last_ingest_run_id")
    op.drop_index("ix_products_source", table_name="products")
    op.drop_column("products", "source")

    # ── 1. 删 ingest_runs 表 ──
    op.drop_table("ingest_runs")
