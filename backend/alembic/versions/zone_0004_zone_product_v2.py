"""zone_product v2: source fields + composite indexes"""
from alembic import op
import sqlalchemy as sa

revision = "zone_0004_zone_product_v2"
down_revision = "zone_0003_attr_tpl_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("zone_products", sa.Column("source", sa.String(16), nullable=False, server_default="MANUAL"))
    op.add_column("zone_products", sa.Column("source_batch_id", sa.String(64)))
    op.add_column("zone_products", sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id")))
    op.create_index("ix_zone_product_zone_category_sort", "zone_products",
                    ["zone_id", "zone_category_id", "sort_order", "id"])
    op.create_index("ix_zone_product_zone_spu", "zone_products", ["zone_id", "spu_id"])


def downgrade() -> None:
    op.drop_index("ix_zone_product_zone_spu", table_name="zone_products")
    op.drop_index("ix_zone_product_zone_category_sort", table_name="zone_products")
    op.drop_column("zone_products", "created_by")
    op.drop_column("zone_products", "source_batch_id")
    op.drop_column("zone_products", "source")
