"""add visibility to products"""
from alembic import op
import sqlalchemy as sa

revision = "zone_0002_products_visibility"
down_revision = "zone_0001_zone_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("visibility", sa.String(16), server_default="PUBLIC", nullable=False))
    op.create_index("ix_products_visibility", "products", ["visibility"])


def downgrade() -> None:
    op.drop_index("ix_products_visibility", table_name="products")
    op.drop_column("products", "visibility")
