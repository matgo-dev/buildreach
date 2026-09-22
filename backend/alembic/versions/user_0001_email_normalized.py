"""users.email 归一化约束:只允许去首尾空格后的小写邮箱(身份比较不区分大小写)"""
from alembic import op

revision = "user_0001_email_normalized"
down_revision = "auth_0001_auth_sessions"
branch_labels = None
depends_on = None

# 显式列出 A-Z 而非 [A-Z] 区间:PG 正则区间依赖排序规则,显式列举与库 locale 无关。
# 只约束 ASCII 大写,避免 PG lower() 与 Python str.lower() 在非 ASCII 上的细微差异让合法写入失败。
_CHECK = "email = btrim(email) AND email !~ '[ABCDEFGHIJKLMNOPQRSTUVWXYZ]'"


def upgrade() -> None:
    # 存量归一化(单条集合式 UPDATE;生产实测 0 行命中)。若存在仅大小写不同的重复账号,
    # 这里会撞 uq_users_email 失败——需人工合并账号,不能自动选一个覆盖。
    op.execute("UPDATE users SET email = lower(btrim(email)) WHERE NOT (" + _CHECK + ")")
    # NOT VALID + VALIDATE:校验阶段只持 SHARE UPDATE EXCLUSIVE 锁,不阻塞读写
    op.execute(f"ALTER TABLE users ADD CONSTRAINT ck_users_email_normalized CHECK ({_CHECK}) NOT VALID")
    op.execute("ALTER TABLE users VALIDATE CONSTRAINT ck_users_email_normalized")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT ck_users_email_normalized")
