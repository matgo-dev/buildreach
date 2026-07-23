"""前台会话账本:每设备一行,支撑 refresh 轮换作废 + 单设备 logout。

设计:docs/specs/2026-07-22-前台refresh会话吊销-设计.md
不加 UA/IP/设备名字段——"设备管理页"是不存在的场景,不预留。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class AuthSession(Base, TimestampMixin):
    __tablename__ = "auth_sessions"

    # id 即 refresh JWT 里的 sid
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 当前有效 refresh 的指纹(uuid4 字符串)
    current_jti: Mapped[str] = mapped_column(String(36), nullable=False)
    # 上一代指纹:仅多 tab 并发的宽限判定用
    prev_jti: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # 最近一次轮换时间(naive UTC,全项目约定)
    rotated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 滑动过期:每次轮换重置为 now+REFRESH_TOKEN_EXPIRE_DAYS
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
