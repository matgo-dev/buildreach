"""购物车 DTO — 买方可见字段,断层隔离(不含供应商/成本/报价)。"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


# ── 请求体 ──────────────────────────────────────────────

class CartItemAdd(BaseModel):
    product_id: int
    selected_variants: list[dict[str, str]] = Field(default_factory=list)
    # 示例: [{"attr_name": "material_type", "value": "normal_white_with_film"}]
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=3)


class CartItemUpdate(BaseModel):
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=3)
    selected_variants: list[dict[str, str]] | None = None

    @model_validator(mode="after")
    def at_least_one(self) -> "CartItemUpdate":
        if self.quantity is None and self.selected_variants is None:
            raise ValueError("quantity or selected_variants required")
        return self


# ── 响应体 ──────────────────────────────────────────────

class CartItemPublic(BaseModel):
    item_id: int
    product_id: int
    sku_id: int | None = None           # 保留，历史数据兼容
    selected_variants: list[dict] = []
    quantity: Decimal

    # 商品信息
    product_name: str | None = None
    variant_display: str | None = None  # 动态拼接，同 RFQ
    description: str | None = None      # 商品短描述
    brand: str | None = None
    origin: str | None = None           # 产地
    unit: str | None = None
    moq: int | None = None
    supply_mode: str | None = None      # PLATFORM_STOCK / SUPPLIER_DIRECT
    certifications: list[str] = []
    lead_time_min: int | None = None
    lead_time_max: int | None = None
    category_name: str | None = None    # 所属品类名

    # 可购状态
    is_purchasable: bool = True
    unavailable_reason: str | None = None
    # 可能的值: PRODUCT_DELETED | PRODUCT_INACTIVE | VARIANT_UNAVAILABLE

    # 主图
    main_image: str | None = None


class CartPublic(BaseModel):
    id: int | None = None
    items: list[CartItemPublic] = []
