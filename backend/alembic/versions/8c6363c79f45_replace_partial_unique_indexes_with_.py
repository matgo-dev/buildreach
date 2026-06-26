"""replace_partial_unique_indexes_with_full_unique

禁用账号不再释放邮箱/手机号/用户名,恢复走管理员启用流程。
迁移时自动清理重复数据:同一邮箱存在多条记录时,保留最早创建的,删除后创建的。

Revision ID: 8c6363c79f45
Revises: 6aa11955310e
Create Date: 2026-06-26 18:49:13.419546
"""
from typing import Sequence, Union

from alembic import op

revision: str = '8c6363c79f45'
down_revision: Union[str, None] = '6aa11955310e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 清理重复数据:同一 email/phone/username 存在多条时,保留 id 最小的,删除其余
    # 删除前先解除外键引用(buyer_members, user_roles 等级联删除会自动处理)
    for col in ('email', 'phone', 'username'):
        op.execute(f"""
            DELETE FROM user_roles WHERE user_id IN (
                SELECT u.id FROM users u
                WHERE u.{col} IS NOT NULL
                  AND u.id NOT IN (
                      SELECT MIN(id) FROM users WHERE {col} IS NOT NULL GROUP BY {col}
                  )
                  AND u.{col} IN (
                      SELECT {col} FROM users WHERE {col} IS NOT NULL GROUP BY {col} HAVING COUNT(*) > 1
                  )
            )
        """)
        op.execute(f"""
            DELETE FROM buyer_members WHERE user_id IN (
                SELECT u.id FROM users u
                WHERE u.{col} IS NOT NULL
                  AND u.id NOT IN (
                      SELECT MIN(id) FROM users WHERE {col} IS NOT NULL GROUP BY {col}
                  )
                  AND u.{col} IN (
                      SELECT {col} FROM users WHERE {col} IS NOT NULL GROUP BY {col} HAVING COUNT(*) > 1
                  )
            )
        """)
        op.execute(f"""
            DELETE FROM users
            WHERE {col} IS NOT NULL
              AND id NOT IN (
                  SELECT MIN(id) FROM users WHERE {col} IS NOT NULL GROUP BY {col}
              )
              AND {col} IN (
                  SELECT {col} FROM users WHERE {col} IS NOT NULL GROUP BY {col} HAVING COUNT(*) > 1
              )
        """)

    # 被保留的 DISABLED 用户恢复为 ACTIVE
    op.execute("UPDATE users SET status = 'ACTIVE' WHERE status = 'DISABLED'")

    # 替换 partial unique index 为全量 unique index
    op.drop_index('uq_users_email_active', table_name='users',
                  postgresql_where="((status)::text <> 'DISABLED'::text)")
    op.drop_index('uq_users_phone_active', table_name='users',
                  postgresql_where="((status)::text <> 'DISABLED'::text)")
    op.drop_index('uq_users_username_active', table_name='users',
                  postgresql_where="((status)::text <> 'DISABLED'::text)")
    op.create_index('uq_users_email', 'users', ['email'], unique=True)
    op.create_index('uq_users_phone', 'users', ['phone'], unique=True)
    op.create_index('uq_users_username', 'users', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index('uq_users_username', table_name='users')
    op.drop_index('uq_users_phone', table_name='users')
    op.drop_index('uq_users_email', table_name='users')
    op.create_index('uq_users_username_active', 'users', ['username'], unique=True,
                    postgresql_where="((status)::text <> 'DISABLED'::text)")
    op.create_index('uq_users_phone_active', 'users', ['phone'], unique=True,
                    postgresql_where="((status)::text <> 'DISABLED'::text)")
    op.create_index('uq_users_email_active', 'users', ['email'], unique=True,
                    postgresql_where="((status)::text <> 'DISABLED'::text)")
