"""报价单 PDF 产物记录。

运营提交报价后异步预生成所有语言的 PDF 文件,
买方下载时直接返回已生成文件,避免现场渲染阻塞。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin


class QuoteDocument(Base, TimestampUpdateMixin):
    __tablename__ = "quote_documents"

    # 状态机：PENDING → GENERATING → READY / FAILED; FAILED → PENDING(重试)
    TRANSITIONS: dict[str, set[str]] = {
        "PENDING": {"GENERATING"},
        "GENERATING": {"READY", "FAILED"},
        "FAILED": {"PENDING"},
    }

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quote_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rfq_quotes.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "quote_id", "version", "locale",
            name="uq_quote_doc_version_locale",
        ),
        Index("ix_quote_documents_quote_id", "quote_id"),
    )

    def transition_to(self, new_status: str) -> None:
        """状态机校验 + 变更。不合法转换直接抛异常。"""
        allowed = self.TRANSITIONS.get(self.status)
        if allowed is None or new_status not in allowed:
            raise ValueError(
                f"QuoteDocument status transition {self.status} → {new_status} not allowed"
            )
        self.status = new_status
