"""央企专区显示名「常用材料」→「央企常用材料」(2026-10-15 业务定;专区对所有人开放后需标明来源)

导入脚本只在专区不存在时建名,已存在的专区靠本迁移改名。只动 code='common-materials' 一行。
"""
from alembic import op

revision = "zone_0008_soe_zone_name"
down_revision = "zone_0007_zone_is_public"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE zones SET name_zh = '央企常用材料' WHERE code = 'common-materials'")


def downgrade() -> None:
    op.execute("UPDATE zones SET name_zh = '常用材料' WHERE code = 'common-materials'")
