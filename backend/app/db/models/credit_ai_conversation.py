"""AI 会话(信用评估 §二)。

每次用户在某企业详情页打开"AI 评价"对话框时,创建一个会话;
会话内的多轮消息写入 credit_ai_message。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class CreditAiConversation(Base, TimestampMixin):
    __tablename__ = "credit_ai_conversation"
    __table_args__ = (
        Index(
            "ix_credit_ai_conv_user_company", "user_id", "company_id"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("credit_company.id", name="fk_credit_ai_conv_company"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
