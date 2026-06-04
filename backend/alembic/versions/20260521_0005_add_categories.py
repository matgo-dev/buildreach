"""add categories table

Revision ID: 20260521_0005
Revises: 20260520_0004
Create Date: 2026-05-21

新增 categories 表(对齐 docs/商品三级分类-PRD-v1.0.md §3.2):
- 单表自关联,3 层(level ∈ {1, 2, 3})
- code VARCHAR(16) UNIQUE NOT NULL,业务主键,永久不变契约(§3.4)
- parent_code 自关联 FK → categories.code(level=1 时为 NULL)
- 索引:UNIQUE(code) / INDEX(parent_code, level) / INDEX(level, is_active, sort_order)
- CHECK 约束:level ∈ {1, 2, 3}

非破坏性 migration:仅 create_table + create_index,不触发 CI 拦截。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260521_0005"
down_revision: Union[str, None] = "20260520_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name_zh", sa.String(length=128), nullable=False),
        sa.Column("name_en", sa.String(length=128), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("parent_code", sa.String(length=16), nullable=True),
        sa.Column(
            "sort_order", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_categories_code"),
        sa.CheckConstraint("level IN (1, 2, 3)", name="ck_categories_level"),
        sa.ForeignKeyConstraint(
            ["parent_code"],
            ["categories.code"],
            name="fk_categories_parent_code",
        ),
    )
    op.create_index(
        "ix_categories_parent_level",
        "categories",
        ["parent_code", "level"],
    )
    op.create_index(
        "ix_categories_level_active_sort",
        "categories",
        ["level", "is_active", "sort_order"],
    )


def downgrade() -> None:
    op.drop_index("ix_categories_level_active_sort", table_name="categories")
    op.drop_index("ix_categories_parent_level", table_name="categories")
    op.drop_table("categories")
