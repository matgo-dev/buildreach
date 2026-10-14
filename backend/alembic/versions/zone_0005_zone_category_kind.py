"""zone_categories.kind: CATEGORY | SCENE(应用场景轴)"""
from alembic import op
import sqlalchemy as sa

revision = "zone_0005_zone_category_kind"
down_revision = "user_0001_email_normalized"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "zone_categories",
        sa.Column("kind", sa.String(16), nullable=False, server_default="CATEGORY"),
    )


def downgrade() -> None:
    op.drop_column("zone_categories", "kind")
