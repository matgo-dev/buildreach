"""credit harvest infrastructure — Δ7 抓取审计表 + 4 张快照表加字段

Revision ID: 20260525_0008
Revises: 20260523_0007
Create Date: 2026-05-25

新增:
- credit_data_harvest_run    抓取过程审计表(§4.7)
4 张快照表加字段:
- credit_company_basic_data        + raw_data + harvest_run_id
- credit_company_certification     + raw_data + harvest_run_id
- credit_company_finance_data      + harvest_run_id(raw_data 已有)
- credit_company_legal_data        + harvest_run_id(raw_data 已有)

迁移顺序:先建 credit_data_harvest_run,4 张快照表的 harvest_run_id 外键才能引用。

非破坏性 upgrade:仅 create_table + add_column + create_index + create_foreign_key,
不触发 CI 破坏性拦截(downgrade 的 drop 仅回滚用)。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260525_0008"
down_revision: Union[str, None] = "20260523_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 4 张快照表统一加 harvest_run_id 外键(name → table)
_SNAPSHOT_FK = {
    "fk_credit_basic_harvest_run": "credit_company_basic_data",
    "fk_credit_cert_harvest_run": "credit_company_certification",
    "fk_credit_finance_harvest_run": "credit_company_finance_data",
    "fk_credit_legal_harvest_run": "credit_company_legal_data",
}


def upgrade() -> None:
    # =========================================================================
    # 1. 抓取审计表(先建,后面快照表外键才能引用)
    # =========================================================================
    op.create_table(
        "credit_data_harvest_run",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("triggered_by", sa.String(length=50), nullable=False),
        sa.Column("operator_user_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column(
            "dimensions_status",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("cache_source_run_id", sa.Integer(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("tavily_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["company_id"], ["credit_company.id"], name="fk_harvest_run_company"
        ),
        sa.ForeignKeyConstraint(
            ["operator_user_id"], ["users.id"], name="fk_harvest_run_operator"
        ),
        sa.ForeignKeyConstraint(
            ["cache_source_run_id"],
            ["credit_data_harvest_run.id"],
            name="fk_harvest_run_cache_source",
        ),
    )
    op.create_index(
        "ix_harvest_run_company_started",
        "credit_data_harvest_run",
        ["company_id", sa.text("started_at DESC")],
    )
    op.create_index(
        "ix_harvest_run_status_started",
        "credit_data_harvest_run",
        ["status", sa.text("started_at DESC")],
    )

    # =========================================================================
    # 2. basic / certification:首次新增 raw_data + harvest_run_id
    # =========================================================================
    op.add_column(
        "credit_company_basic_data",
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "credit_company_certification",
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # =========================================================================
    # 3. 4 张快照表统一加 harvest_run_id + 外键
    # =========================================================================
    for fk_name, table in _SNAPSHOT_FK.items():
        op.add_column(table, sa.Column("harvest_run_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            fk_name, table, "credit_data_harvest_run", ["harvest_run_id"], ["id"]
        )


def downgrade() -> None:
    for fk_name, table in _SNAPSHOT_FK.items():
        op.drop_constraint(fk_name, table, type_="foreignkey")
        op.drop_column(table, "harvest_run_id")
    op.drop_column("credit_company_certification", "raw_data")
    op.drop_column("credit_company_basic_data", "raw_data")
    op.drop_index("ix_harvest_run_status_started", table_name="credit_data_harvest_run")
    op.drop_index("ix_harvest_run_company_started", table_name="credit_data_harvest_run")
    op.drop_table("credit_data_harvest_run")
