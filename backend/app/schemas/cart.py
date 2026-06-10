"""购物车 DTO — 买方可见字段,断层隔离(不含供应商/成本/报价)。"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


# ── 请求体 ──────────────────────────────────────────────

class CartItemAdd(BaseModel):
    sku_id: int
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=3)


class CartItemUpdate(BaseModel):
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=3)


# ── 响应体 ──────────────────────────────────────────────

class CartItemPublic(BaseModel):
    item_id: int
    sku_id: int
    product_id: int
    quantity: Decimal

    # SKU 信息
    sku_code: str
    sku_name: str | None = None
    product_name: str | None = None
    manufacturer_model: str | None = None
    color: str | None = None
    material: str | None = None

    # SPU 级
    unit: str | None = None
    moq: int | None = None

    # 可购状态
    is_purchasable: bool = True
    unavailable_reason: str | None = None

    # 主图
    main_image: str | None = None


class CartPublic(BaseModel):
    id: int | None = None
    items: list[CartItemPublic] = []
