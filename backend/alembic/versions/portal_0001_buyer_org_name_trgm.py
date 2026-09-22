"""buyer_organizations.name 三元组索引:履约按名搜索前台组织(内部路由 ILIKE '%q%')走索引"""
from alembic import op

revision = "portal_0001_buyer_org_name_trgm"
down_revision = "user_0001_email_normalized"
branch_labels = None
depends_on = None

INDEX = "ix_buyer_organizations_name_trgm"


def upgrade() -> None:
    context = op.get_context()
    if context.dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")  # 20260630_0010 已建,幂等
    with context.autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX} "
            "ON buyer_organizations USING gin (name gin_trgm_ops)"
        )


def downgrade() -> None:
    context = op.get_context()
    if context.dialect.name != "postgresql":
        return
    with context.autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX}")
