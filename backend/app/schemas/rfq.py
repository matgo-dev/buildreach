"""询价单 DTO — 按角色分离(买方/运营)。

买方 DTO 不含 created_by_user_id / operator_assignee_id / buyer_org_id 等内部字段。
运营 DTO 全量。报价按角色层叠(买方 ACTIVE、运营全版本)。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


# ── 请求体 ──────────────────────────────────────────────

class RfqItemInput(BaseModel):
    """创建询价单行项。"""
    product_id: int
    selected_variants: list[dict[str, str]] = Field(default_factory=list)
    # 前端传当前 locale 的 key+value，后端转为英文后存入 variant_snapshot
    # 示例: [{"attr_name": "material_type", "value": "normal_white_with_film"}]
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=3)
    target_unit_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    remark: str | None = None


class RfqCreate(BaseModel):
    """创建询价单请求体。"""
    items: list[RfqItemInput]          # 统一入参，必填，≥1 条
    as_draft: bool = False             # True → 保存为草稿(DRAFT)，False → 直接提交(SUBMITTED)

    # 运营代客
    buyer_org_id: int | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None

    # 公共需求字段
    requested_delivery_place: str | None = None
    destination_port: str | None = None
    preferred_trade_term: str | None = None
    expected_delivery_date: datetime | None = None
    target_currency: str | None = None
    required_certifications: list[str] | None = None
    attachment_urls: list[str] | None = None
    remark: str | None = None


class RfqUpdate(BaseModel):
    """草稿态整单更新请求体。行项全量替换。"""
    items: list[RfqItemInput]          # 全量替换，≥1 条

    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None

    requested_delivery_place: str | None = None
    destination_port: str | None = None
    preferred_trade_term: str | None = None
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


class RfqItemEdit(BaseModel):
    """运营编辑行项：可改变体、数量、备注。None = 不改该字段。"""
    selected_variants: list[dict[str, str]] | None = None
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=3)
    target_unit_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    remark: str | None = None


class RfqListQuery(BaseModel):
    """列表查询参数。"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    status: str | None = None
    buyer_org_id: int | None = None
    mine: bool = False


# ── 响应体:行项目 ──────────────────────────────────────

class RfqItemPublic(BaseModel):
    """询价行项目(快照 + 读时 JOIN 增强)。"""
    id: int
    product_id: int
    variant_snapshot: list[dict] = []
    variant_display: str | None = None  # 序列化时动态拼接，非数据库列
    product_name_snapshot: str | None = None
    uom_snapshot: str | None = None
    quantity: Decimal
    target_unit_price: Decimal | None = None
    remark: str | None = None

    # 读时 JOIN 增强字段（详情页填充，列表页为 None）
    main_image: str | None = None
    spu_code: str | None = None
    brand: str | None = None
    origin: str | None = None
    category_name: str | None = None


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
    destination_port: str | None = None
    preferred_trade_term: str | None = None
    expected_delivery_date: datetime | None = None
    target_currency: str | None = None
    required_certifications: list[str] | None = None
    attachment_urls: list[str] | None = None

    # 时间
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # 列表缩略图:首个有效行项主图,读时 JOIN
    first_item_image: str | None = None

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
    destination_port: str | None = None
    preferred_trade_term: str | None = None
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
