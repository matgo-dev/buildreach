"""buyer_events: 允许游客事件(user_id / buyer_org_id 可空)

游客搜索/浏览按 session_id 归属，无 user_id / buyer_org_id。
"""
from alembic import op

revision = "evt_0001_guest_events"
down_revision = "zone_0004_zone_product_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("buyer_events", "user_id", nullable=True)
    op.alter_column("buyer_events", "buyer_org_id", nullable=True)


def downgrade() -> None:
    # 注意: 若已存在游客事件(user_id/org 为空)，回退前需先清理，否则约束失败。
    op.alter_column("buyer_events", "buyer_org_id", nullable=False)
    op.alter_column("buyer_events", "user_id", nullable=False)
