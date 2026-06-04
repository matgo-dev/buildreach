"""dimension-level override refactor

Revision ID: 20260523_0007
Revises: 20260523_0006
Create Date: 2026-05-23

把维度级 override 从 score_rule 表里剥离,单独建模为 score_dimension_override 表。

新增:
- score_dimension_override 表(每维度 1 条 override,共 3 条)
- score_snapshot 5 个新列:
  · dimension_1_natural_score / dimension_2_natural_score
  · dimension_3_natural_score / dimension_4_natural_score
  · dimension_overrides (JSONB,记录命中明细)

清理:
- 删除 9 条 priority=0 的旧 score_rule(都是子项级 override 占位规则)

注:DELETE 不可逆,downgrade 通过重新 INSERT 恢复(请从 git 历史拿到原始 seed 代码)。
对齐 docs/prompts/信用评估模块_工单prompt_v0_2.md §3 Step 1。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260523_0007"
down_revision: Union[str, None] = "20260523_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 待删除的 9 条 priority=0 旧 override rule code(精确枚举,避免误删)
_OBSOLETE_RULE_CODES = (
    "R_CERT_CRITICAL_MANDATORY",
    "R_CERT_CRITICAL_SYSTEM",
    "R_CERT_CRITICAL_INDUSTRY",
    "R_FIN_REV_MISSING",
    "R_FIN_DEBT_MISSING",
    "R_FIN_CASH_MISSING",
    "R_LEG_VETO_LITIGATION",
    "R_LEG_VETO_DEFAULTER",
    "R_LEG_VETO_NEWS",
)


def upgrade() -> None:
    # 1) 新建 score_dimension_override 表
    op.create_table(
        "score_dimension_override",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("dimension_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("override_score", sa.SmallInteger(), nullable=False),
        sa.Column("evaluator_key", sa.String(length=100), nullable=False),
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_score_dimension_override_code"),
        sa.ForeignKeyConstraint(
            ["dimension_id"],
            ["score_dimension.id"],
            name="fk_score_dim_override_dimension",
        ),
    )
    op.create_index(
        "ix_score_dim_override_dim_active_priority",
        "score_dimension_override",
        ["dimension_id", "is_active", "priority"],
    )

    # 2) score_snapshot 扩 5 列(全部 nullable=True,不强制对历史快照回填)
    op.add_column(
        "score_snapshot",
        sa.Column("dimension_1_natural_score", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "score_snapshot",
        sa.Column("dimension_2_natural_score", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "score_snapshot",
        sa.Column("dimension_3_natural_score", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "score_snapshot",
        sa.Column("dimension_4_natural_score", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "score_snapshot",
        sa.Column(
            "dimension_overrides",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    # 3) 删 9 条旧 priority=0 子项 override rule(精确枚举)
    code_list = ", ".join(f"'{c}'" for c in _OBSOLETE_RULE_CODES)
    op.execute(f"DELETE FROM score_rule WHERE code IN ({code_list})")


def downgrade() -> None:
    # 1) 反向:不重建 9 条 rule(seed 自启时会创建,这里不假设状态)
    #    DELETE 不可逆,如需精确回滚可在 downgrade 后重 seed 一次

    # 2) score_snapshot 删 5 列
    op.drop_column("score_snapshot", "dimension_overrides")
    op.drop_column("score_snapshot", "dimension_4_natural_score")
    op.drop_column("score_snapshot", "dimension_3_natural_score")
    op.drop_column("score_snapshot", "dimension_2_natural_score")
    op.drop_column("score_snapshot", "dimension_1_natural_score")

    # 3) drop 表
    op.drop_index(
        "ix_score_dim_override_dim_active_priority",
        table_name="score_dimension_override",
    )
    op.drop_table("score_dimension_override")
