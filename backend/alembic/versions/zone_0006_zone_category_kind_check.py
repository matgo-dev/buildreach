"""zone_categories.kind 加 CHECK(CATEGORY | SCENE):枚举约束落 DB 层"""
from alembic import op

revision = "zone_0006_zone_category_kind_check"
down_revision = "zone_0005_zone_category_kind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_zone_categories_kind", "zone_categories", "kind IN ('CATEGORY', 'SCENE')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_zone_categories_kind", "zone_categories", type_="check")
