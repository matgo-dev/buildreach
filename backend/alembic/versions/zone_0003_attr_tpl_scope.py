"""attr_templates unique -> (category_code, attr_key, scope)"""
from alembic import op

revision = "zone_0003_attr_tpl_scope"
down_revision = "zone_0002_products_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_attr_templates_category_key", "attr_templates", type_="unique")
    op.create_unique_constraint(
        "uq_attr_templates_category_key_scope", "attr_templates",
        ["category_code", "attr_key", "scope"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_attr_templates_category_key_scope", "attr_templates", type_="unique")
    op.create_unique_constraint(
        "uq_attr_templates_category_key", "attr_templates",
        ["category_code", "attr_key"],
    )
