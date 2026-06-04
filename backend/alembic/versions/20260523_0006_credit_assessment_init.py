"""credit assessment module — 13 tables init

Revision ID: 20260523_0006
Revises: 20260521_0005
Create Date: 2026-05-23

新增信用评估模块全部底层表(对齐 docs/architecture/信用评估模块技术方案设计-v0_1.md §二)。

表清单(共 14 张物理表 = §二定义的 13 张 + ai_message 拆出):

评分模型骨架(3):
- score_dimension      维度(4 维)
- score_subitem        子项(12 个)
- score_rule           规则(~35 条)

企业与数据快照(5):
- credit_company                  企业主表
- credit_company_basic_data       工商基础数据快照(只增不改)
- credit_company_finance_data     财务数据快照
- credit_company_legal_data       司法舆情数据快照
- credit_company_certification    证书

评分结果(3):
- score_snapshot       评分快照(含 is_current 部分唯一索引)
- score_detail         评分明细(每快照 12 条)
- score_audit_log      评分变动审计

用户交互(3):
- credit_search_history    搜索历史
- credit_ai_conversation   AI 会话
- credit_ai_message        AI 消息

非破坏性 migration:仅 create_table + create_index,不触发 CI 拦截。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260523_0006"
down_revision: Union[str, None] = "20260521_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # 1. score_dimension
    # =========================================================================
    op.create_table(
        "score_dimension",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("max_score", sa.SmallInteger(), nullable=False),
        sa.Column("display_order", sa.SmallInteger(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_score_dimension_code"),
    )

    # =========================================================================
    # 2. score_subitem
    # =========================================================================
    op.create_table(
        "score_subitem",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("dimension_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("max_score", sa.SmallInteger(), nullable=False),
        sa.Column("default_score", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("display_order", sa.SmallInteger(), nullable=False),
        sa.Column("data_source_hint", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_score_subitem_code"),
        sa.ForeignKeyConstraint(
            ["dimension_id"], ["score_dimension.id"], name="fk_score_subitem_dimension"
        ),
    )
    op.create_index(
        "ix_score_subitem_dimension_active",
        "score_subitem",
        ["dimension_id", "is_active", "display_order"],
    )

    # =========================================================================
    # 3. score_rule
    # =========================================================================
    op.create_table(
        "score_rule",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("subitem_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("evaluator_key", sa.String(length=100), nullable=False),
        sa.Column("condition_expr", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("priority", sa.SmallInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_score_rule_code"),
        sa.ForeignKeyConstraint(
            ["subitem_id"], ["score_subitem.id"], name="fk_score_rule_subitem"
        ),
    )
    op.create_index(
        "ix_score_rule_subitem_active_priority",
        "score_rule",
        ["subitem_id", "is_active", "priority"],
    )

    # =========================================================================
    # 4. credit_company
    # =========================================================================
    op.create_table(
        "credit_company",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("legal_name_en", sa.String(length=300), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("registration_no", sa.String(length=100), nullable=True),
        sa.Column("linked_supplier_org_id", sa.Integer(), nullable=True),
        sa.Column("data_status", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("country_code", "name", name="uq_credit_company_country_name"),
        sa.ForeignKeyConstraint(
            ["linked_supplier_org_id"],
            ["supplier_organizations.id"],
            name="fk_credit_company_supplier_org",
        ),
    )
    op.create_index(
        "ix_credit_company_country", "credit_company", ["country_code"]
    )

    # =========================================================================
    # 5. credit_company_basic_data
    # =========================================================================
    op.create_table(
        "credit_company_basic_data",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("established_date", sa.Date(), nullable=True),
        sa.Column("registered_capital", sa.String(length=100), nullable=True),
        sa.Column("business_scope", sa.Text(), nullable=True),
        sa.Column("legal_representative", sa.String(length=100), nullable=True),
        sa.Column("shareholders", sa.Text(), nullable=True),
        sa.Column("status_text", sa.String(length=50), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("website", sa.String(length=300), nullable=True),
        sa.Column("data_source", sa.String(length=20), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["company_id"], ["credit_company.id"], name="fk_credit_basic_company"
        ),
    )
    op.create_index(
        "ix_credit_basic_company_fetched",
        "credit_company_basic_data",
        ["company_id", "fetched_at"],
    )

    # =========================================================================
    # 6. credit_company_finance_data
    # =========================================================================
    op.create_table(
        "credit_company_finance_data",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("revenue_trend", sa.String(length=32), nullable=True),
        sa.Column("debt_ratio", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("cash_flow_status", sa.String(length=32), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("data_source", sa.String(length=20), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["company_id"], ["credit_company.id"], name="fk_credit_finance_company"
        ),
    )
    op.create_index(
        "ix_credit_finance_company_fetched",
        "credit_company_finance_data",
        ["company_id", "fetched_at"],
    )

    # =========================================================================
    # 7. credit_company_legal_data
    # =========================================================================
    op.create_table(
        "credit_company_legal_data",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("litigation_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("defaulter_unresolved_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("defaulter_resolved_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("negative_news_level", sa.String(length=20), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("data_source", sa.String(length=20), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["company_id"], ["credit_company.id"], name="fk_credit_legal_company"
        ),
    )
    op.create_index(
        "ix_credit_legal_company_fetched",
        "credit_company_legal_data",
        ["company_id", "fetched_at"],
    )

    # =========================================================================
    # 8. credit_company_certification
    # =========================================================================
    op.create_table(
        "credit_company_certification",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("cert_type", sa.String(length=50), nullable=False),
        sa.Column("cert_name", sa.String(length=200), nullable=False),
        sa.Column("target_country_code", sa.String(length=2), nullable=True),
        sa.Column("issuer", sa.String(length=200), nullable=True),
        sa.Column("issued_at", sa.Date(), nullable=True),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("data_source", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["company_id"], ["credit_company.id"], name="fk_credit_cert_company"
        ),
    )
    op.create_index(
        "ix_credit_cert_company_type",
        "credit_company_certification",
        ["company_id", "cert_type"],
    )

    # =========================================================================
    # 9. credit_search_history
    # =========================================================================
    op.create_table(
        "credit_search_history",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("searched_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["company_id"], ["credit_company.id"], name="fk_credit_search_company"
        ),
    )
    op.create_index(
        "ix_credit_search_user_searched_at",
        "credit_search_history",
        ["user_id", sa.text("searched_at DESC")],
    )

    # =========================================================================
    # 10. credit_ai_conversation
    # =========================================================================
    op.create_table(
        "credit_ai_conversation",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["company_id"], ["credit_company.id"], name="fk_credit_ai_conv_company"
        ),
    )
    op.create_index(
        "ix_credit_ai_conv_user_company",
        "credit_ai_conversation",
        ["user_id", "company_id"],
    )

    # =========================================================================
    # 11. credit_ai_message
    # =========================================================================
    op.create_table(
        "credit_ai_message",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id", "sequence", name="uq_credit_ai_message_conv_seq"
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["credit_ai_conversation.id"],
            name="fk_credit_ai_msg_conv",
        ),
    )

    # =========================================================================
    # 12. score_snapshot
    # =========================================================================
    op.create_table(
        "score_snapshot",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("total_score", sa.SmallInteger(), nullable=False),
        sa.Column("grade", sa.String(length=1), nullable=False),
        sa.Column("dimension_1_score", sa.SmallInteger(), nullable=False),
        sa.Column("dimension_2_score", sa.SmallInteger(), nullable=False),
        sa.Column("dimension_3_score", sa.SmallInteger(), nullable=False),
        sa.Column("dimension_4_score", sa.SmallInteger(), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("trigger_detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("basic_data_id", sa.Integer(), nullable=True),
        sa.Column("finance_data_id", sa.Integer(), nullable=True),
        sa.Column("legal_data_id", sa.Integer(), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("ai_summary_generated_at", sa.DateTime(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("calculated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["company_id"], ["credit_company.id"], name="fk_score_snapshot_company"
        ),
        sa.ForeignKeyConstraint(
            ["basic_data_id"],
            ["credit_company_basic_data.id"],
            name="fk_score_snapshot_basic_data",
        ),
        sa.ForeignKeyConstraint(
            ["finance_data_id"],
            ["credit_company_finance_data.id"],
            name="fk_score_snapshot_finance_data",
        ),
        sa.ForeignKeyConstraint(
            ["legal_data_id"],
            ["credit_company_legal_data.id"],
            name="fk_score_snapshot_legal_data",
        ),
    )
    # 部分唯一索引:每个 company 同时只能有一条 is_current=true 的快照
    op.create_index(
        "uq_score_snapshot_current",
        "score_snapshot",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )
    op.create_index(
        "ix_score_snapshot_company_calculated",
        "score_snapshot",
        ["company_id", sa.text("calculated_at DESC")],
    )
    op.create_index(
        "ix_score_snapshot_grade_current",
        "score_snapshot",
        ["grade", "is_current"],
    )

    # =========================================================================
    # 13. score_detail
    # =========================================================================
    op.create_table(
        "score_detail",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("dimension_code", sa.String(length=64), nullable=False),
        sa.Column("dimension_name", sa.String(length=100), nullable=False),
        sa.Column("subitem_code", sa.String(length=64), nullable=False),
        sa.Column("subitem_name", sa.String(length=200), nullable=False),
        sa.Column("hit_rule_code", sa.String(length=128), nullable=True),
        sa.Column("hit_rule_description", sa.String(length=500), nullable=True),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("max_score", sa.SmallInteger(), nullable=False),
        sa.Column("is_default_score", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("evaluation_context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id", "subitem_code", name="uq_score_detail_snapshot_subitem"
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["score_snapshot.id"], name="fk_score_detail_snapshot"
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["credit_company.id"], name="fk_score_detail_company"
        ),
    )

    # =========================================================================
    # 14. score_audit_log
    # =========================================================================
    op.create_table(
        "score_audit_log",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("previous_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("current_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("previous_total_score", sa.SmallInteger(), nullable=True),
        sa.Column("current_total_score", sa.SmallInteger(), nullable=False),
        sa.Column("score_delta", sa.SmallInteger(), nullable=False),
        sa.Column("previous_grade", sa.String(length=1), nullable=True),
        sa.Column("current_grade", sa.String(length=1), nullable=False),
        sa.Column("grade_changed", sa.Boolean(), nullable=False),
        sa.Column(
            "changed_subitems",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["company_id"], ["credit_company.id"], name="fk_score_audit_company"
        ),
        sa.ForeignKeyConstraint(
            ["previous_snapshot_id"],
            ["score_snapshot.id"],
            name="fk_score_audit_prev_snapshot",
        ),
        sa.ForeignKeyConstraint(
            ["current_snapshot_id"],
            ["score_snapshot.id"],
            name="fk_score_audit_curr_snapshot",
        ),
    )
    op.create_index(
        "ix_score_audit_company_created",
        "score_audit_log",
        ["company_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_score_audit_grade_changed",
        "score_audit_log",
        ["grade_changed", "created_at"],
    )


def downgrade() -> None:
    # 按建表反序 drop
    op.drop_index("ix_score_audit_grade_changed", table_name="score_audit_log")
    op.drop_index("ix_score_audit_company_created", table_name="score_audit_log")
    op.drop_table("score_audit_log")

    op.drop_table("score_detail")

    op.drop_index("ix_score_snapshot_grade_current", table_name="score_snapshot")
    op.drop_index("ix_score_snapshot_company_calculated", table_name="score_snapshot")
    op.drop_index("uq_score_snapshot_current", table_name="score_snapshot")
    op.drop_table("score_snapshot")

    op.drop_table("credit_ai_message")

    op.drop_index("ix_credit_ai_conv_user_company", table_name="credit_ai_conversation")
    op.drop_table("credit_ai_conversation")

    op.drop_index("ix_credit_search_user_searched_at", table_name="credit_search_history")
    op.drop_table("credit_search_history")

    op.drop_index("ix_credit_cert_company_type", table_name="credit_company_certification")
    op.drop_table("credit_company_certification")

    op.drop_index(
        "ix_credit_legal_company_fetched", table_name="credit_company_legal_data"
    )
    op.drop_table("credit_company_legal_data")

    op.drop_index(
        "ix_credit_finance_company_fetched", table_name="credit_company_finance_data"
    )
    op.drop_table("credit_company_finance_data")

    op.drop_index(
        "ix_credit_basic_company_fetched", table_name="credit_company_basic_data"
    )
    op.drop_table("credit_company_basic_data")

    op.drop_index("ix_credit_company_country", table_name="credit_company")
    op.drop_table("credit_company")

    op.drop_index(
        "ix_score_rule_subitem_active_priority", table_name="score_rule"
    )
    op.drop_table("score_rule")

    op.drop_index(
        "ix_score_subitem_dimension_active", table_name="score_subitem"
    )
    op.drop_table("score_subitem")

    op.drop_table("score_dimension")
