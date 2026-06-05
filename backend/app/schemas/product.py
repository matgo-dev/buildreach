"""商品 Pydantic schemas — SPU + SKU 两层化。

断层隔离：Public(买方)系列不含供应商信息，Operator 系列含全量。
多语言：name/description/brand/origin 用 _i18n JSON 模式。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------- 图片 ----------

class ProductImageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    image_key: str
    full_url: str = ""
    image_type: str = "GALLERY"
    sort_order: int
    sku_id: int | None = None
    width: int | None = None
    height: int | None = None
    file_size: int | None = None


# ---------- 品类属性 ----------

class ProductAttrSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    attr_key: str
    attr_value: str
    attr_unit: str | None = None
    sort_order: int = 0


class ProductAttrCreate(BaseModel):
    attr_key: str
    attr_value: str
    attr_unit: str | None = None
    sort_order: int = 0


# ---------- 属性模板 ----------

class AttrTemplateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category_code: str
    attr_key: str
    display_name: str
    attr_type: str
    attr_unit: str | None = None
    options: dict | list | None = None
    is_required: bool = False
    sort_order: int = 0


# ---------- 阶梯价 ----------

class PriceTierCreate(BaseModel):
    min_qty: int = Field(gt=0)
    max_qty: int | None = Field(default=None, gt=0)
    unit_price: Decimal = Field(gt=0, decimal_places=2)
    currency: str = "TZS"
    label: str | None = Field(default=None, max_length=50)


class PriceTierSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    min_qty: int
    max_qty: int | None = None
    unit_price: Decimal
    currency: str
    label: str | None = None


# ---------- 供货关系（运营侧，挂 SKU） ----------

class SupplierRelationCreate(BaseModel):
    supplier_org_id: int
    supplier_price: Decimal = Field(ge=0, decimal_places=2)
    supplier_currency: str = "CNY"
    cif_price_usd: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    supplier_moq: int | None = Field(default=None, gt=0)
    supplier_lead_time_days: int | None = Field(default=None, gt=0)
    pvoc_status: Literal["OBTAINED", "CAN_ARRANGE", "UNAVAILABLE"] | None = None
    has_coc: bool = False
    is_preferred: bool = False
    notes: str | None = None


class SupplierRelationUpdate(BaseModel):
    supplier_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    supplier_currency: str | None = None
    cif_price_usd: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    supplier_moq: int | None = Field(default=None, gt=0)
    supplier_lead_time_days: int | None = Field(default=None, gt=0)
    pvoc_status: Literal["OBTAINED", "CAN_ARRANGE", "UNAVAILABLE"] | None = None
    has_coc: bool | None = None
    is_preferred: bool | None = None
    notes: str | None = None


class SupplierRelationDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sku_id: int
    supplier_org_id: int
    supplier_org_name: str = ""
    supplier_price: Decimal
    supplier_currency: str
    cif_price_usd: Decimal | None = None
    supplier_moq: int | None = None
    supplier_lead_time_days: int | None = None
    pvoc_status: str | None = None
    has_coc: bool
    is_preferred: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------- SKU ----------

class SkuCreate(BaseModel):
    sku_code: str | None = Field(default=None, max_length=50)
    manufacturer_model: str | None = Field(default=None, max_length=100)
    name: str | None = Field(default=None, max_length=200)
    name_i18n: dict | None = None
    color: str | None = Field(default=None, max_length=50)
    color_i18n: dict | None = None
    material: str | None = Field(default=None, max_length=100)
    material_i18n: dict | None = None
    price_min: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    price_max: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    currency: str = "TZS"
    unit: str = Field(max_length=20)
    moq: int = Field(gt=0)
    lead_time_min: int | None = Field(default=None, ge=0)
    lead_time_max: int | None = Field(default=None, ge=0)
    packing_quantity: int | None = Field(default=None, gt=0)
    gross_weight_kg: Decimal | None = Field(default=None, gt=0)
    volume_cbm: Decimal | None = Field(default=None, gt=0)
    can_consolidate: bool = True
    cargo_type: str | None = Field(default=None, max_length=20)
    is_default: bool = False
    status: str = "ACTIVE"
    price_tiers: List[PriceTierCreate] | None = None


class SkuUpdate(BaseModel):
    manufacturer_model: str | None = Field(default=None, max_length=100)
    name: str | None = Field(default=None, max_length=200)
    name_i18n: dict | None = None
    color: str | None = Field(default=None, max_length=50)
    color_i18n: dict | None = None
    material: str | None = Field(default=None, max_length=100)
    material_i18n: dict | None = None
    price_min: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    price_max: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    currency: str | None = None
    unit: str | None = Field(default=None, max_length=20)
    moq: int | None = Field(default=None, gt=0)
    lead_time_min: int | None = Field(default=None, ge=0)
    lead_time_max: int | None = Field(default=None, ge=0)
    packing_quantity: int | None = Field(default=None, gt=0)
    gross_weight_kg: Decimal | None = Field(default=None, gt=0)
    volume_cbm: Decimal | None = Field(default=None, gt=0)
    can_consolidate: bool | None = None
    cargo_type: str | None = Field(default=None, max_length=20)
    is_default: bool | None = None
    status: str | None = None
    price_tiers: List[PriceTierCreate] | None = None


# SKU 买方响应（不含供应商）
class SkuPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sku_code: str
    name: str | None = None
    color: str | None = None
    material: str | None = None
    manufacturer_model: str | None = None
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    currency: str
    unit: str
    moq: int
    lead_time_min: int | None = None
    lead_time_max: int | None = None
    is_default: bool
    status: str
    price_tiers: List[PriceTierSchema] = []
    images: List[ProductImageSchema] = []


# SKU 运营响应（含供应商 + 物流参数）
class SkuOperator(SkuPublic):
    name_i18n: dict | None = None
    color_i18n: dict | None = None
    material_i18n: dict | None = None
    packing_quantity: int | None = None
    gross_weight_kg: Decimal | None = None
    volume_cbm: Decimal | None = None
    can_consolidate: bool = True
    cargo_type: str | None = None
    supplier_relations: List[SupplierRelationDetail] = []
    created_at: datetime
    updated_at: datetime


# ---------- 商品(SPU) — 公开（买方，无供应商） ----------

class ProductPublic(BaseModel):
    """买方列表项：SPU 基本信息 + 默认 SKU 展示价"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    spu_code: str
    name: str
    category_code: str
    category_name: str = ""
    origin: str
    brand: str | None = None
    certifications: list | None = None
    is_featured: bool
    main_image: str | None = None
    # 默认 SKU 的展示价
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    currency: str | None = None
    sku_count: int = 0


class ProductPublicDetail(BaseModel):
    """买方详情：SPU + skus[] + 图片 + 属性"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    spu_code: str
    name: str
    description: str | None = None
    category_code: str
    category_name: str = ""
    origin: str
    brand: str | None = None
    hs_code: str | None = None
    certifications: list | None = None
    selling_points: str | None = None
    is_featured: bool
    skus: List[SkuPublic] = []
    images: List[ProductImageSchema] = []
    attributes: List[ProductAttrSchema] = []


# ---------- 商品(SPU) — 运营（含供应商 + i18n 原始数据） ----------

class ProductOperator(BaseModel):
    """运营列表项：SPU + 默认 SKU 展示价 + 状态/创建信息"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    spu_code: str
    name: str
    name_i18n: dict | None = None
    category_code: str
    category_name: str = ""
    origin: str
    brand: str | None = None
    is_featured: bool
    main_image: str | None = None
    status: str
    created_by_name: str = ""
    # 默认 SKU 的展示价
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    currency: str | None = None
    sku_count: int = 0
    created_at: datetime
    updated_at: datetime


class ProductOperatorDetail(BaseModel):
    """运营详情：SPU + skus[](含阶梯价/供货) + 图片 + 属性 + i18n"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    spu_code: str
    name: str
    name_i18n: dict | None = None
    description: str | None = None
    description_i18n: dict | None = None
    category_code: str
    category_name: str = ""
    origin: str
    origin_i18n: dict | None = None
    brand: str | None = None
    brand_i18n: dict | None = None
    hs_code: str | None = None
    certifications: list | None = None
    selling_points: str | None = None
    selling_points_i18n: dict | None = None
    is_featured: bool
    status: str
    created_by_name: str = ""
    skus: List[SkuOperator] = []
    images: List[ProductImageSchema] = []
    attributes: List[ProductAttrSchema] = []
    created_at: datetime
    updated_at: datetime


# ---------- SPU 创建 / 编辑（不含 SKU 级字段） ----------

class ProductCreate(BaseModel):
    category_code: str
    spu_code: str | None = Field(default=None, max_length=50)
    name: str = Field(max_length=200)
    name_i18n: dict | None = None
    description: str | None = None
    description_i18n: dict | None = None
    origin: str = "China"
    origin_i18n: dict | None = None
    hs_code: str | None = None
    brand: str | None = None
    brand_i18n: dict | None = None
    certifications: list | None = None
    selling_points: str | None = None
    selling_points_i18n: dict | None = None
    is_featured: bool = False
    status: str = "DRAFT"
    attributes: List[ProductAttrCreate] | None = None


class ProductUpdate(BaseModel):
    category_code: str | None = None
    name: str | None = Field(default=None, max_length=200)
    name_i18n: dict | None = None
    description: str | None = None
    description_i18n: dict | None = None
    origin: str | None = None
    origin_i18n: dict | None = None
    hs_code: str | None = None
    brand: str | None = None
    brand_i18n: dict | None = None
    certifications: list | None = None
    selling_points: str | None = None
    selling_points_i18n: dict | None = None
    is_featured: bool | None = None
    attributes: List[ProductAttrCreate] | None = None


class ProductStatusUpdate(BaseModel):
    status: str  # DRAFT / ACTIVE / INACTIVE


# ---------- 分页 ----------

class ProductPage(BaseModel):
    items: list
    total: int
    page: int
    size: int
    pages: int
