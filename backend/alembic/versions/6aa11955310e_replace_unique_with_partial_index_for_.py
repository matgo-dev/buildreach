"""replace unique with partial index for disabled users

Revision ID: 6aa11955310e
Revises: 2ded69877815
Create Date: 2026-06-26
"""
from alembic import op

revision = "6aa11955310e"
down_revision = "2ded69877815"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 去掉旧的 unique index(SQLAlchemy unique=True 生成的是 ix_ 前缀的 unique index)
    op.drop_index("ix_users_email", "users")
    op.drop_index("ix_users_username", "users")
    op.drop_index("ix_users_phone", "users")

    # 创建 partial unique index:仅对非 DISABLED 用户生效,停用账号释放邮箱/用户名/手机号
    op.execute(
        "CREATE UNIQUE INDEX uq_users_email_active ON users (email) "
        "WHERE status != 'DISABLED'"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_users_username_active ON users (username) "
        "WHERE status != 'DISABLED'"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_users_phone_active ON users (phone) "
        "WHERE status != 'DISABLED'"
    )
    # 保留普通索引用于查询
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_phone", "users", ["phone"])


def downgrade() -> None:
    op.drop_index("ix_users_phone", "users")
    op.drop_index("ix_users_username", "users")
    op.drop_index("ix_users_email", "users")
    op.drop_index("uq_users_phone_active", "users")
    op.drop_index("uq_users_username_active", "users")
    op.drop_index("uq_users_email_active", "users")

    # 还原为 unique index
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)
