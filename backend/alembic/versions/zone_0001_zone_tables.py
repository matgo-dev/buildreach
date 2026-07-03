"""zone tables

新增央企专区(Zone)四表:zones / zone_categories / zone_products / zone_grants。

Revision ID: zone_0001_zone_tables
Revises: 20260630_0010
Create Date: 2026-07-02
"""
from alembic import op
import sqlalchemy as sa

revision = "zone_0001_zone_tables"
down_revision = "20260630_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "zones",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name_zh", sa.String(128), nullable=False),
        sa.Column("name_en", sa.String(128)),
        sa.Column("name_sw", sa.String(128)),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("settings", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code", name="uq_zones_code"),
    )
    op.create_table(
        "zone_categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("zone_id", sa.Integer, sa.ForeignKey("zones.id"), nullable=False),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("name_zh", sa.String(128), nullable=False),
        sa.Column("name_en", sa.String(128)),
        sa.Column("name_sw", sa.String(128)),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("mapped_platform_codes", sa.JSON, nullable=False, server_default="[]"),
        # I18nMixin 列,与 categories 表迁移(20260614_i18n_category_attr_expansion)对齐
        sa.Column("source_lang", sa.String(10), nullable=False, server_default="zh"),
        sa.Column("trans_meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("i18n_pending_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("zone_id", "code", name="uq_zone_categories_zone_code"),
        sa.UniqueConstraint("zone_id", "id", name="uq_zone_categories_zone_id_id"),
    )
    op.create_index("ix_zone_categories_zone_id", "zone_categories", ["zone_id"])
    op.create_index("ix_zone_categories_i18n_pending_at", "zone_categories", ["i18n_pending_at"])
    op.create_table(
        "zone_products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("zone_id", sa.Integer, sa.ForeignKey("zones.id"), nullable=False),
        sa.Column("spu_id", sa.Integer, sa.ForeignKey("products.id"), nullable=False),
        sa.Column("zone_category_id", sa.Integer, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("zone_id", "spu_id", "zone_category_id", name="uq_zone_products_triplet"),
        sa.ForeignKeyConstraint(
            ["zone_id", "zone_category_id"],
            ["zone_categories.zone_id", "zone_categories.id"],
            name="fk_zone_products_category_same_zone",
        ),
    )
    op.create_index("ix_zone_products_zone_id", "zone_products", ["zone_id"])
    op.create_index("ix_zone_products_spu_id", "zone_products", ["spu_id"])
    op.create_table(
        "zone_grants",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("zone_id", sa.Integer, sa.ForeignKey("zones.id"), nullable=False),
        sa.Column("buyer_org_id", sa.Integer, sa.ForeignKey("buyer_organizations.id"), nullable=False),
        sa.Column("granted_by", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("zone_id", "buyer_org_id", name="uq_zone_grants_zone_org"),
    )
    op.create_index("ix_zone_grants_zone_id", "zone_grants", ["zone_id"])
    op.create_index("ix_zone_grants_buyer_org_id", "zone_grants", ["buyer_org_id"])


def downgrade() -> None:
    for t in ("zone_grants", "zone_products", "zone_categories", "zones"):
        op.drop_table(t)
