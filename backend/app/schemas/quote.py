"""报价 DTO — 按角色分离(买方/运营)。

买方 DTO 不含 cost/supplier_*/quoted_by/版本历史。
运营 DTO 全量(含成本层、全版本)。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.constants.quote_terms import CurrencyCode, TradeTermCode
from app.schemas.attachment import AttachmentPublic


# ── 请求体 ──────────────────────────────────────────────


class QuoteTierInput(BaseModel):
    """阶梯价输入。"""
    min_qty: Decimal = Field(gt=0, max_digits=18, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=4)


class QuoteCostInput(BaseModel):
    """行内部成本输入(运营内部)。"""
    supplier_org_id: int | None = None
    supplier_unit_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    freight_cost_alloc: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    insurance_cost: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    export_clearance_cost: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    consolidation_cost: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    gross_margin: Decimal | None = Field(default=None, max_digits=18, decimal_places=4)


class QuoteLineInput(BaseModel):
    """报价行输入 — PRODUCT(商品) 或 FEE(费用)。"""
    source_rfq_item_id: int | None = None
    line_type: str = "PRODUCT"

    # 商品信息（PRODUCT 行必填 product_id）
    product_id: int | None = None
    product_name: str | None = None
    selected_variants: list[dict[str, str]] | None = None
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=3)
    uom: str | None = None

    # 报价信息
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    moq: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=3)
    cbm_per_unit: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=4)
    gross_weight_per_unit: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    remark: str | None = None
    tiers: list[QuoteTierInput] | None = None
    cost: QuoteCostInput | None = None


class QuoteHeaderInput(BaseModel):
    """报价表头输入。"""
    trade_term: TradeTermCode | None = None
    named_place: str | None = None
    currency: CurrencyCode | None = None
    valid_until: datetime | None = None
    lead_time_days: int | None = Field(default=None, ge=0)
    eta_days: int | None = Field(default=None, ge=0)


class QuoteCreatePayload(BaseModel):
    """创建/重报报价请求体。"""
    header: QuoteHeaderInput = QuoteHeaderInput()
    lines: list[QuoteLineInput]
    attachment_ids: list[int] | None = None


# ── 响应体:阶梯价(公共)──────────────────────────────────


class QuoteTierPublic(BaseModel):
    min_qty: Decimal
    unit_price: Decimal


# ── 响应体:成本层(运营)──────────────────────────────────


class QuoteCostView(BaseModel):
    supplier_org_id: int | None = None
    supplier_unit_price: Decimal | None = None
    freight_cost_alloc: Decimal | None = None
    insurance_cost: Decimal | None = None
    export_clearance_cost: Decimal | None = None
    consolidation_cost: Decimal | None = None
    gross_margin: Decimal | None = None


# ── 响应体:买方报价行 ────────────────────────────────────


class QuoteItemBuyerPublic(BaseModel):
    """买方可见报价行。无 cost/supplier。"""
    id: int
    source_rfq_item_id: int | None = None
    line_type: str = "PRODUCT"

    # 商品快照
    product_id: int | None = None
    product_name_snapshot: str | None = None
    quoted_variants: list[dict] | None = None
    variant_display: str | None = None
    quantity: Decimal | None = None
    uom: str | None = None

    # 报价信息
    unit_price: Decimal | None = None
    moq: Decimal | None = None
    cbm_per_unit: Decimal | None = None
    gross_weight_per_unit: Decimal | None = None
    line_amount: Decimal | None = None
    remark: str | None = None
    tiers: list[QuoteTierPublic] = []


# ── 响应体:运营报价行 ────────────────────────────────────


class QuoteItemOperatorView(QuoteItemBuyerPublic):
    """运营全量报价行,含成本层。"""
    cost: QuoteCostView | None = None


# ── 响应体:买方报价(仅 ACTIVE)────────────────────────────


class RfqQuoteBuyerPublic(BaseModel):
    """买方可见报价。无 cost/supplier_*/quoted_by/版本历史。"""
    id: int
    quote_no: str
    trade_term: str | None = None
    named_place: str | None = None
    currency: str | None = None
    valid_until: datetime | None = None
    lead_time_days: int | None = None
    eta_days: int | None = None
    total_amount: Decimal | None = None
    items: list[QuoteItemBuyerPublic] = []
    attachments: list[AttachmentPublic] = []


# ── 响应体:运营报价(全版本)────────────────────────────────


class RfqQuoteOperatorView(BaseModel):
    """运营全量报价(含版本历史 + 成本层)。"""
    id: int
    quote_no: str
    version: int
    quote_status: str
    quoted_by_user_id: int | None = None
    quoted_at: datetime | None = None
    trade_term: str | None = None
    named_place: str | None = None
    currency: str | None = None
    valid_until: datetime | None = None
    lead_time_days: int | None = None
    eta_days: int | None = None
    total_amount: Decimal | None = None
    created_at: datetime | None = None
    items: list[QuoteItemOperatorView] = []
    attachments: list[AttachmentPublic] = []
