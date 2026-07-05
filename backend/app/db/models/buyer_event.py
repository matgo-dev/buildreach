"""买方行为事件 — 独立于 audit_logs 的轻量事件表。

用途：最近浏览、搜索历史、转化漏斗、热门商品统计、AI 客服训练语料。
设计决策见 docs/adr/ADR-0007-买方行为追踪方案决策.md
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, _utcnow


class BuyerEvent(Base):
    __tablename__ = "buyer_events"
    __table_args__ = (
        Index("ix_buyer_events_user_type_time", "user_id", "event_type", "created_at"),
        Index("ix_buyer_events_resource", "resource_type", "resource_id"),
        Index("ix_buyer_events_session", "session_id"),
        Index("ix_buyer_events_org_time", "buyer_org_id", "created_at"),
        Index("ix_buyer_events_created_at", "created_at"),  # 时间范围查询/漏斗统计
        Index("ix_buyer_events_user_time", "user_id", "created_at"),  # 去重窗口查询
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 游客事件无归属机构/用户，按 session_id 归属，故均可空
    buyer_org_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("buyer_organizations.id", name="fk_buyer_events_org_id"),
        nullable=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_buyer_events_user_id"),
        nullable=True,
    )
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    resource_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
