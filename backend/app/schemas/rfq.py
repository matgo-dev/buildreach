"""询价单 DTO — 按角色分离(买方/运营)。

买方 DTO 不含 created_by_user_id / operator_assignee_id / buyer_org_id 等内部字段。
运营 DTO 全量。报价按角色层叠(买方 ACTIVE、运营全版本)。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── 枚举(请求体用)──────────────────────────────────────

class SourceType(str, Enum):
    CART = "CART"
    DIRECT = "DIRECT"


# ── 请求体 ──────────────────────────────────────────────

class RfqDirectItem(BaseModel):
    """DIRECT 来源的行项目。"""
    sku_id: int
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=3)
    target_unit_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    remark: str | None = None


class RfqCreate(BaseModel):
    """创建询价单请求体。"""
    source_type: SourceType

    # CART 来源
    cart_item_ids: list[int] | None = None

    # DIRECT 来源
    items: list[RfqDirectItem] | None = None

    # 运营代客
    buyer_org_id: int | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None

    # 公共需求字段
    requested_delivery_place: str | None = None
    expected_delivery_date: datetime | None = None
    target_currency: str | None = None
    required_certifications: list[str] | None = None
    attachment_urls: list[str] | None = None
    remark: str | None = None


class RfqCancelRequest(BaseModel):
    """撤销询价单请求体。"""
    cancel_reason: str | None = None


class RfqItemUpdate(BaseModel):
    """草稿态编辑行项数量。"""
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=3)


class RfqListQuery(BaseModel):
    """列表查询参数。"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    status: str | None = None
    buyer_org_id: int | None = None
    mine: bool = False


# ── 响应体:行项目 ──────────────────────────────────────

class RfqItemPublic(BaseModel):
    """询价行项目(快照)。"""
    id: int
    sku_id: int
    product_name_snapshot: str | None = None
    sku_spec_snapshot: str | None = None
    uom_snapshot: str | None = None
    quantity: Decimal
    target_unit_price: Decimal | None = None
    remark: str | None = None


# ── 响应体:买方视角 ────────────────────────────────────

class RfqBuyerPublic(BaseModel):
    """买方可见询价单。不含 created_by_user_id / operator_assignee_id / buyer_org_id。"""
    id: int
    rfq_no: str
    status: str
    source: str

    # 联系方式
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    remark: str | None = None

    # 需求字段
    requested_delivery_place: str | None = None
    expected_delivery_date: datetime | None = None
    target_currency: str | None = None
    required_certifications: list[str] | None = None
    attachment_urls: list[str] | None = None

    # 时间
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # 行项目
    items: list[RfqItemPublic] = []

    # 报价层叠(买方仅 ACTIVE,无报价为 null)
    quote: Any | None = None


# ── 响应体:运营视角 ────────────────────────────────────

class RfqOperatorView(BaseModel):
    """运营全量视图。含内部字段。"""
    id: int
    rfq_no: str
    status: str
    source: str

    # 内部字段
    buyer_org_id: int
    buyer_user_id: int | None = None
    created_by_user_id: int
    operator_assignee_id: int | None = None

    # 联系方式
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    remark: str | None = None
    cancel_reason: str | None = None

    # 需求字段
    requested_delivery_place: str | None = None
    expected_delivery_date: datetime | None = None
    target_currency: str | None = None
    required_certifications: list[str] | None = None
    attachment_urls: list[str] | None = None

    # 时间
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # 行项目
    items: list[RfqItemPublic] = []

    # 报价层叠(运营全版本列表)
    quotes: list[Any] = []


# ── 分页包装 ────────────────────────────────────────────

class RfqListResponse(BaseModel):
    items: list[RfqBuyerPublic] | list[RfqOperatorView]
    total: int
    page: int
    page_size: int
