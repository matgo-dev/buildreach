"""supplier register: country_code + registration_no + users.language_preference

Revision ID: 20260520_0004
Revises: 20260520_0003
Create Date: 2026-05-20

变更点(对齐 docs/PRD_供应商注册_v1.3.md §4.1):
- supplier_organizations:
  - 加列 country_code VARCHAR(2)(先 NULL → 回填 'CN' → SET NOT NULL,兼容已有数据)
  - 重命名 business_license_no → registration_no(数据保留)
  - 删除原 UNIQUE(business_license_no)
  - 新增 UNIQUE(country_code, registration_no)(复合唯一,不同国家可撞号)
- users:
  - 加列 language_preference VARCHAR(10) NULL(个人语言偏好,本轮仅 SUPPLIER 注册写入)

注意:本 migration 含 alter_column(new_column_name=...) 与 drop_constraint(unique),
不含 drop_column / drop_table,理论上不触发 CI 破坏性拦截。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260520_0004"
down_revision: Union[str, None] = "20260520_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- supplier_organizations ----
    # 1) 加 country_code(先 nullable),兜底回填存量数据,然后 SET NOT NULL
    op.add_column(
        "supplier_organizations",
        sa.Column("country_code", sa.String(length=2), nullable=True),
    )
    op.execute("UPDATE supplier_organizations SET country_code = 'CN' WHERE country_code IS NULL")
    op.alter_column("supplier_organizations", "country_code", nullable=False)

    # 2) 删除旧 UNIQUE(business_license_no)
    op.drop_constraint(
        "uq_supplier_org_license", "supplier_organizations", type_="unique"
    )

    # 3) 重命名 business_license_no → registration_no(数据保留)
    op.alter_column(
        "supplier_organizations",
        "business_license_no",
        new_column_name="registration_no",
        existing_type=sa.String(length=100),
        existing_nullable=True,
    )

    # 4) 新增复合 UNIQUE(country_code, registration_no)
    op.create_unique_constraint(
        "uq_supplier_org_country_regno",
        "supplier_organizations",
        ["country_code", "registration_no"],
    )

    # ---- users ----
    op.add_column(
        "users",
        sa.Column("language_preference", sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    # ---- users ----
    op.drop_column("users", "language_preference")

    # ---- supplier_organizations ----
    op.drop_constraint(
        "uq_supplier_org_country_regno", "supplier_organizations", type_="unique"
    )
    op.alter_column(
        "supplier_organizations",
        "registration_no",
        new_column_name="business_license_no",
        existing_type=sa.String(length=100),
        existing_nullable=True,
    )
    op.create_unique_constraint(
        "uq_supplier_org_license",
        "supplier_organizations",
        ["business_license_no"],
    )
    op.drop_column("supplier_organizations", "country_code")
