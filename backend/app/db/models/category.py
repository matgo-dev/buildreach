"""商品三级分类。

设计要点(详见 docs/商品三级分类-PRD-v1.0.md §3):
- 单表自关联,3 层(level ∈ {1, 2, 3})
- `code` 是业务主键,**永久不变契约**(§3.4):所有业务关联表外键引用 `code`,不引用 `id`
- code 格式:`XX.XXX.XXX` 纯数字点分(2-3-3),如 L1 "01" / L2 "01.005" / L3 "01.005.012"
- 删除走 `is_active=false`,永不物理删
"""
from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin


class CategoryLevel:
    """分类层级常量(对齐 PRD §3.2 CHECK 约束)。"""

    L1 = 1
    L2 = 2
    L3 = 3
    ALL = (L1, L2, L3)


class Category(Base, TimestampUpdateMixin):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("level IN (1, 2, 3)", name="ck_categories_level"),
        Index("ix_categories_parent_level", "parent_code", "level"),
        Index("ix_categories_level_active_sort", "level", "is_active", "sort_order"),
    )

    # 技术主键:ORM 内部用,不对外暴露作为关联键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 业务主键:对外关联键,永久不变(契约见 PRD §3.4)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name_zh: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(128), nullable=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    # 自关联:引用父节点的 code(不引用 id);L1 时为 NULL
    parent_code: Mapped[str | None] = mapped_column(
        String(16),
        ForeignKey("categories.code", name="fk_categories_parent_code"),
        nullable=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
