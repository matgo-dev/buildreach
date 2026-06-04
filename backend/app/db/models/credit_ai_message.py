"""AI 消息(信用评估 §二)。

每条消息属于一个 conversation,sequence 从 1 开始递增。
(conversation_id, sequence) UNIQUE 保证同会话内消息序号不重复。
流式响应在前端逐字渲染,流完后整体落库一条 assistant 消息。
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class MessageRole:
    USER = "user"
    ASSISTANT = "assistant"


class CreditAiMessage(Base, TimestampMixin):
    __tablename__ = "credit_ai_message"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "sequence", name="uq_credit_ai_message_conv_seq"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("credit_ai_conversation.id", name="fk_credit_ai_msg_conv"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
