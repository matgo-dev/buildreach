"""zones 加 is_public:公开专区所有人(含未登录)可进,非公开专区仍走 zone_grants 授权

2026-10-15 业务定:常用材料(common-materials)、矿业勘探·开采(mining)两个专区对所有人开放。
mining 若尚未导入则 UPDATE 不命中,由导入脚本建专区时置 is_public=true。zones 表只有个位数行。
"""
import sqlalchemy as sa
from alembic import op

revision = "zone_0007_zone_is_public"
down_revision = "zone_0006_zone_cat_kind_check"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("zones", sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE zones SET is_public = true WHERE code IN ('common-materials', 'mining')")


def downgrade() -> None:
    op.drop_column("zones", "is_public")
