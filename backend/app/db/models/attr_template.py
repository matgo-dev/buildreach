"""品类属性模板定义。运营上架时按模板渲染表单。"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AttrTemplate(Base):
    __tablename__ = "attr_templates"
    __table_args__ = (
        Index("ix_attr_templates_category_code", "category_code"),
        UniqueConstraint(
            "category_code", "attr_key", "scope",
            name="uq_attr_templates_category_key_scope",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_code: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("categories.code", name="fk_attr_templates_category_code"),
        nullable=False,
    )
    attr_key: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    attr_type: Mapped[str] = mapped_column(String(20), nullable=False)
    attr_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    options: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scope: Mapped[str] = mapped_column(String(3), nullable=False, server_default="SKU")
    selectable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
