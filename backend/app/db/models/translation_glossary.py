"""行业术语表 — 翻译 API 调用时强制替换。"""
from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class TranslationGlossary(Base, TimestampMixin):
    __tablename__ = "translation_glossary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_locale: Mapped[str] = mapped_column(String(10), nullable=False)
    target_locale: Mapped[str] = mapped_column(String(10), nullable=False)
    source_term: Mapped[str] = mapped_column(String(200), nullable=False)
    target_term: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
