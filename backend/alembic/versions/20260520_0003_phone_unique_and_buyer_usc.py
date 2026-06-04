"""phone 唯一约束 + buyer_organizations.unified_social_credit_code(18 位国标)

Revision ID: 20260520_0003
Revises: 20260518_0002
Create Date: 2026-05-20

变更点(对齐 docs/RBAC_v4.md T1):
- users.phone:加 UNIQUE 约束(uq_users_phone)+ INDEX(ix_users_phone)。
  PG 默认 NULL 不参与唯一约束,允许多个用户 phone=NULL,符合预期。
- buyer_organizations:新增 unified_social_credit_code VARCHAR(18) NULL
  + UNIQUE(uq_buyer_org_usc)+ INDEX(ix_buyer_org_usc)。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260520_0003"
down_revision: Union[str, None] = "20260518_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.create_unique_constraint("uq_users_phone", ["phone"])
    op.create_index("ix_users_phone", "users", ["phone"])

    with op.batch_alter_table("buyer_organizations") as b:
        b.add_column(
            sa.Column("unified_social_credit_code", sa.String(length=18), nullable=True)
        )
        b.create_unique_constraint("uq_buyer_org_usc", ["unified_social_credit_code"])
    op.create_index(
        "ix_buyer_org_usc",
        "buyer_organizations",
        ["unified_social_credit_code"],
    )


def downgrade() -> None:
    op.drop_index("ix_buyer_org_usc", table_name="buyer_organizations")
    with op.batch_alter_table("buyer_organizations") as b:
        b.drop_constraint("uq_buyer_org_usc", type_="unique")
        b.drop_column("unified_social_credit_code")

    op.drop_index("ix_users_phone", table_name="users")
    with op.batch_alter_table("users") as b:
        b.drop_constraint("uq_users_phone", type_="unique")
