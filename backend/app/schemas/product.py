"""商品 Pydantic schemas — v2 i18n 分列模式。

断层隔离：Public(买方)系列不含供应商信息，Operator 系列含全量。
多语言：入参接单语言 + source_lang，出参经 get_localized 给当前语言值。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.constants.sku_unit import SkuUnitCode
from app.db.models.product import SupplyMode


# ---------- 图片 ----------

class ProductImageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    image_key: str
    full_url: str = ""
    thumbnail_url: str = ""
    image_type: str = "GALLERY"
    sort_order: int
    sku_id: int | None = None
    width: int | None = None
    height: int | None = None
    file_size: int | None = None


# ---------- 品类属性 ----------

class ProductAttrSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    attr_key: str = ""        # 本地化后的 key（由 service 层 get_localized 填充）
    attr_value: str = ""      # 本地化后的 value
    attr_unit: str | None = None
    sort_order: int = 0
    sku_id: int | None = None
    display_name: str | None = None


# ---------- 买方分组属性(广告牌模式) ----------

class AttrValue(BaseModel):
    """属性值 — 支持文本和色板图片两种类型。"""
    value: str
    value_type: str = "text"
    swatch_image: str | None = None


class AttrItem(BaseModel):
    """属性项 — 同 key 多值聚合。"""
    key: str
    unit: str | None = None
    selectable: bool = False
    values: List[AttrValue]


class AttrGroup(BaseModel):
    """属性分组 — 按 attr_group 归类。"""
    group: str
    items: List[AttrItem]


class ProductAttrCreate(BaseModel):
    attr_key: str
    attr_value: str


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
    scope: str = "SKU"
    selectable: bool = False


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
    color: str | None = Field(default=None, max_length=50)
    material: str | None = Field(default=None, max_length=100)
    source_lang: str = "zh"
    price_min: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    price_max: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    moq: int = Field(gt=0)
    lead_time_min: int | None = Field(default=None, ge=0)
    lead_time_max: int | None = Field(default=None, ge=0)
    packing_quantity: int | None = Field(default=None, gt=0)
    gross_weight_kg: Decimal | None = Field(default=None, gt=0)
    volume_cbm: Decimal | None = Field(default=None, gt=0)
    can_consolidate: bool = True
    cargo_type: str | None = Field(default=None, max_length=20)
    is_default: bool = False
    price_tiers: List[PriceTierCreate] | None = None
    attributes: List[ProductAttrCreate] | None = None


class SkuUpdate(BaseModel):
    manufacturer_model: str | None = Field(default=None, max_length=100)
    name: str | None = Field(default=None, max_length=200)
    color: str | None = Field(default=None, max_length=50)
    material: str | None = Field(default=None, max_length=100)
    price_min: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    price_max: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    moq: int | None = Field(default=None, gt=0)
    lead_time_min: int | None = Field(default=None, ge=0)
    lead_time_max: int | None = Field(default=None, ge=0)
    packing_quantity: int | None = Field(default=None, gt=0)
    gross_weight_kg: Decimal | None = Field(default=None, gt=0)
    volume_cbm: Decimal | None = Field(default=None, gt=0)
    can_consolidate: bool | None = None
    cargo_type: str | None = Field(default=None, max_length=20)
    is_default: bool | None = None
    price_tiers: List[PriceTierCreate] | None = None
    attributes: List[ProductAttrCreate] | None = None


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
    moq: int
    lead_time_min: int | None = None
    lead_time_max: int | None = None
    is_default: bool
    status: str
    price_tiers: List[PriceTierSchema] = []
    images: List[ProductImageSchema] = []
    attributes: List[ProductAttrSchema] = []


# SKU 运营响应（含供应商 + 物流参数 + i18n 分列原始值）
class SkuOperator(SkuPublic):
    name_zh: str | None = None
    name_en: str | None = None
    color_zh: str | None = None
    color_en: str | None = None
    material_zh: str | None = None
    material_en: str | None = None
    source_lang: str = "zh"
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
    """买方列表 — 广告牌模式,无价格/SKU。"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    spu_code: str
    name: str
    description: str | None = None
    category_code: str
    category_name: str = ""
    origin: str
    brand: str | None = None
    manufacturer_model: str | None = None
    certifications: list | None = None
    is_featured: bool
    supply_mode: str = SupplyMode.SUPPLIER_DIRECT
    main_image: str | None = None
    main_image_thumbnail: str | None = None
    unit: str | None = None
    moq: int | None = None
    moq_unit: str | None = None


class ProductPublicDetail(BaseModel):
    """买方详情 — 广告牌模式,去价去 SKU,属性按 group 聚合。"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    spu_code: str
    name: str
    description: str | None = None
    detail_description: str | None = None
    category_code: str
    category_name: str = ""
    origin: str
    brand: str | None = None
    manufacturer_model: str | None = None
    hs_code: str | None = None
    certifications: list | None = None
    selling_points: str | None = None
    is_featured: bool
    supply_mode: str = SupplyMode.SUPPLIER_DIRECT
    unit: str = "PCS"
    moq: int | None = None
    moq_unit: str | None = None
    lead_time_min: int | None = None
    lead_time_max: int | None = None
    gross_weight_kg: Decimal | None = None
    volume_cbm: Decimal | None = None
    attribute_groups: List[AttrGroup] = []
    images: List[ProductImageSchema] = []


# ---------- 商品(SPU) — 运营（含供应商 + i18n 分列原始数据） ----------

class ProductOperator(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    spu_code: str
    name: str
    name_zh: str | None = None
    name_en: str | None = None
    category_code: str
    category_name: str = ""
    origin: str
    brand: str | None = None
    is_featured: bool
    supply_mode: str = SupplyMode.SUPPLIER_DIRECT
    main_image: str | None = None
    main_image_thumbnail: str | None = None
    status: str
    created_by_name: str = ""
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    currency: str | None = None
    sku_count: int = 0
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ProductOperatorDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    spu_code: str
    name: str
    name_zh: str | None = None
    name_en: str | None = None
    description: str | None = None
    description_zh: str | None = None
    description_en: str | None = None
    category_code: str
    category_name: str = ""
    origin: str
    origin_zh: str | None = None
    origin_en: str | None = None
    brand: str | None = None
    brand_zh: str | None = None
    brand_en: str | None = None
    hs_code: str | None = None
    certifications: list | None = None
    selling_points: str | None = None
    selling_points_zh: str | None = None
    selling_points_en: str | None = None
    source_lang: str = "zh"
    is_featured: bool
    supply_mode: str = SupplyMode.SUPPLIER_DIRECT
    unit: str = "PCS"
    currency: str = "TZS"
    moq: int | None = None
    moq_unit: str | None = None
    ref_price_tiers: list | None = None
    # 物流参数（SPU 级）
    lead_time_min: int | None = None
    lead_time_max: int | None = None
    packing_quantity: int | None = None
    gross_weight_kg: Decimal | None = None
    volume_cbm: Decimal | None = None
    can_consolidate: bool = True
    cargo_type: str | None = None
    status: str
    created_by_name: str = ""
    skus: List[SkuOperator] = []
    images: List[ProductImageSchema] = []
    attributes: List[ProductAttrSchema] = []
    created_at: datetime
    updated_at: datetime


# ---------- SPU 创建 / 编辑（v2 i18n: 单语言值 + source_lang） ----------

class ProductCreate(BaseModel):
    category_code: str
    spu_code: str | None = Field(default=None, max_length=50)
    name: str = Field(max_length=200)
    description: str | None = None
    origin: str = "中国"
    hs_code: str | None = None
    brand: str | None = None
    certifications: list | None = None
    selling_points: str | None = None
    source_lang: str = "zh"
    is_featured: bool = False
    supply_mode: str = SupplyMode.SUPPLIER_DIRECT
    unit: SkuUnitCode = "PCS"
    currency: str = "TZS"
    # 物流参数（SPU 级）
    lead_time_min: int | None = Field(default=None, ge=0)
    lead_time_max: int | None = Field(default=None, ge=0)
    packing_quantity: int | None = Field(default=None, gt=0)
    gross_weight_kg: Decimal | None = Field(default=None, gt=0)
    volume_cbm: Decimal | None = Field(default=None, gt=0)
    can_consolidate: bool = True
    cargo_type: str | None = Field(default=None, max_length=20)
    attributes: List[ProductAttrCreate] | None = None


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    origin: str | None = None
    hs_code: str | None = None
    brand: str | None = None
    certifications: list | None = None
    selling_points: str | None = None
    is_featured: bool | None = None
    supply_mode: str | None = None
    unit: SkuUnitCode | None = None
    currency: str | None = None
    # 物流参数（SPU 级）
    lead_time_min: int | None = Field(default=None, ge=0)
    lead_time_max: int | None = Field(default=None, ge=0)
    packing_quantity: int | None = Field(default=None, gt=0)
    gross_weight_kg: Decimal | None = Field(default=None, gt=0)
    volume_cbm: Decimal | None = Field(default=None, gt=0)
    can_consolidate: bool | None = None
    cargo_type: str | None = Field(default=None, max_length=20)
    attributes: List[ProductAttrCreate] | None = None


class ProductStatusUpdate(BaseModel):
    status: str  # DRAFT / ACTIVE / INACTIVE


class SkuStatusUpdate(BaseModel):
    status: str  # ACTIVE / INACTIVE


# ---------- 聚合保存 ----------

class ImageRefInput(BaseModel):
    """图片引用（先传后引用，保存时按 ID 关联）。"""
    image_id: int
    image_type: Literal["MAIN", "GALLERY", "DETAIL"] = "GALLERY"
    sort_order: int = 0


class AggregateSkuCreate(BaseModel):
    """聚合创建时的 SKU 子项（无 id，服务端生成 sku_code）。"""
    model_config = ConfigDict(extra="forbid")

    client_id: str | None = Field(default=None, max_length=64, description="前端临时 UUID，用于建壳后映射 SKU 图片上传")
    manufacturer_model: str | None = Field(default=None, max_length=100)
    name: str | None = Field(default=None, max_length=200)
    color: str | None = Field(default=None, max_length=50)
    material: str | None = Field(default=None, max_length=100)
    source_lang: str = "zh"
    price_min: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    price_max: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    moq: int = Field(gt=0)
    lead_time_min: int | None = Field(default=None, ge=0)
    lead_time_max: int | None = Field(default=None, ge=0)
    packing_quantity: int | None = Field(default=None, gt=0)
    gross_weight_kg: Decimal | None = Field(default=None, gt=0)
    volume_cbm: Decimal | None = Field(default=None, gt=0)
    can_consolidate: bool = True
    cargo_type: str | None = Field(default=None, max_length=20)
    is_default: bool = False
    price_tiers: List[PriceTierCreate] | None = None
    attributes: List[ProductAttrCreate] | None = None


class AggregateSkuSave(AggregateSkuCreate):
    """聚合保存时的 SKU 子项（带可选 id：有 id=更新，无 id=新建）。"""
    id: int | None = None


class ProductAggregateCreate(BaseModel):
    """聚合创建：一次事务建 SPU + 全部 SKU + 图片引用。"""
    model_config = ConfigDict(extra="forbid")

    category_code: str
    spu_code: str | None = Field(default=None, max_length=50)
    name: str = Field(max_length=200)
    description: str | None = None
    origin: str = "中国"
    hs_code: str | None = None
    brand: str | None = None
    certifications: list | None = None
    selling_points: str | None = None
    source_lang: str = "zh"
    is_featured: bool = False
    supply_mode: str = SupplyMode.SUPPLIER_DIRECT
    unit: SkuUnitCode = "PCS"
    currency: str = "TZS"
    # 物流参数（SPU 级）
    lead_time_min: int | None = Field(default=None, ge=0)
    lead_time_max: int | None = Field(default=None, ge=0)
    packing_quantity: int | None = Field(default=None, gt=0)
    gross_weight_kg: Decimal | None = Field(default=None, gt=0)
    volume_cbm: Decimal | None = Field(default=None, gt=0)
    can_consolidate: bool = True
    cargo_type: str | None = Field(default=None, max_length=20)
    attributes: List[ProductAttrCreate] | None = None
    skus: List[AggregateSkuCreate] = []
    images: List[ImageRefInput] | None = None


class ProductAggregateSave(BaseModel):
    """聚合保存：一次事务更新 SPU + SKU diff + 图片引用。"""
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    origin: str | None = None
    hs_code: str | None = None
    brand: str | None = None
    certifications: list | None = None
    selling_points: str | None = None
    is_featured: bool | None = None
    supply_mode: str | None = None
    unit: SkuUnitCode | None = None
    currency: str | None = None
    # 物流参数（SPU 级）
    lead_time_min: int | None = Field(default=None, ge=0)
    lead_time_max: int | None = Field(default=None, ge=0)
    packing_quantity: int | None = Field(default=None, gt=0)
    gross_weight_kg: Decimal | None = Field(default=None, gt=0)
    volume_cbm: Decimal | None = Field(default=None, gt=0)
    can_consolidate: bool | None = None
    cargo_type: str | None = Field(default=None, max_length=20)
    attributes: List[ProductAttrCreate] | None = None
    skus: List[AggregateSkuSave] | None = None
    images: List[ImageRefInput] | None = None


# ---------- 分页 ----------

class ProductPage(BaseModel):
    items: list
    total: int
    page: int
    size: int
    pages: int
