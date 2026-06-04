"""add users.username (optional, unique)

Revision ID: 20260518_0002
Revises: 20260517_0001
Create Date: 2026-05-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260518_0002"
down_revision: Union[str, None] = "20260517_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch_alter_table 兼容写法(PG/SQLite 都能跑)
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("username", sa.String(length=50), nullable=True))
        b.create_unique_constraint("uq_users_username", ["username"])
    op.create_index("ix_users_username", "users", ["username"])


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    with op.batch_alter_table("users") as b:
        b.drop_constraint("uq_users_username", type_="unique")
        b.drop_column("username")
