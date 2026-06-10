"""询价单主表 + 枚举。

单边模型：买方提交或运营代创询价，运营填报价（独立实体 rfq_quotes）。
软删除——被订单引用，需审计追溯。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime, ForeignKey, Index, Integer, Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampUpdateMixin
from app.db.soft_delete_mixin import SoftDeleteMixin


# ── 枚举 ────────────────────────────────────────────────

class RfqStatus:
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    QUOTED = "QUOTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    ALL = (DRAFT, SUBMITTED, QUOTED, ACCEPTED, REJECTED, EXPIRED, CANCELLED)

    # 状态机：合法转换路径
    # 重报为 QUOTED 态内修订（version+1），不作为跨态迁移
    TRANSITIONS: dict[str, tuple[str, ...]] = {
        DRAFT: (SUBMITTED, CANCELLED),
        SUBMITTED: (QUOTED, CANCELLED),
        QUOTED: (ACCEPTED, REJECTED, EXPIRED, CANCELLED),
    }

    @classmethod
    def can_transition(cls, current: str, target: str) -> bool:
        return target in cls.TRANSITIONS.get(current, ())


class RfqSource:
    BUYER_SELF = "BUYER_SELF"
    OPERATOR_PROXY = "OPERATOR_PROXY"
    ALL = (BUYER_SELF, OPERATOR_PROXY)


class QuoteStatus:
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    ALL = (ACTIVE, SUPERSEDED)


class TradeTerm:
    FOB = "FOB"
    CFR = "CFR"
    CIF = "CIF"
    # 预留
    DAP = "DAP"
    DDP = "DDP"
    ALL = (FOB, CFR, CIF, DAP, DDP)


# ── 模型 ────────────────────────────────────────────────

class Rfq(Base, TimestampUpdateMixin, SoftDeleteMixin):
    __tablename__ = "rfqs"
    __table_args__ = (
        Index("ix_rfqs_status", "status"),
        Index("ix_rfqs_buyer_org_id", "buyer_org_id"),
        Index(
            "uq_rfqs_rfq_no_active",
            "rfq_no",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    rfq_no: Mapped[str] = mapped_column(String(40), nullable=False)
    buyer_org_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("buyer_organizations.id", name="fk_rfqs_buyer_org_id"),
        nullable=False,
    )
    buyer_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_rfqs_buyer_user_id"),
        nullable=True,
    )
    created_by_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_rfqs_created_by_user_id"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RfqStatus.DRAFT,
    )
    operator_assignee_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", name="fk_rfqs_operator_assignee_id"),
        nullable=True,
    )
    # 循环 FK：use_alter 避免建表顺序死锁
    accepted_quote_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "rfq_quotes.id",
            name="fk_rfqs_accepted_quote_id",
            use_alter=True,
        ),
        nullable=True,
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 联系方式
    contact_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 买方需求字段（Δ1 并入）
    requested_delivery_place: Mapped[str | None] = mapped_column(
        String(120), nullable=True,
    )
    expected_delivery_date: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
    )
    target_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    required_certifications: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_urls: Mapped[str | None] = mapped_column(Text, nullable=True)

    # relationships
    items: Mapped[list["RfqItem"]] = relationship(
        "RfqItem", back_populates="rfq", cascade="all, delete-orphan",
    )
    quotes: Mapped[list["RfqQuote"]] = relationship(
        "RfqQuote",
        back_populates="rfq",
        cascade="all, delete-orphan",
        foreign_keys="RfqQuote.rfq_id",
    )
