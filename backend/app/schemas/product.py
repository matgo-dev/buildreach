"""商品 Pydantic schemas。

断层隔离：Public 系列不含供应商信息，Operator 系列含全量。
多语言：name/description/brand/origin 用 _i18n JSON 模式。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List

from pydantic import BaseModel, ConfigDict, Field


# ---------- 图片 ----------

class ProductImageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    image_key: str
    full_url: str = ""
    image_type: str = "GALLERY"
    sort_order: int
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


# ---------- 供货关系 ----------

class ProductSupplierCreate(BaseModel):
    supplier_org_id: int
    supplier_price: Decimal = Field(default=Decimal("0"), ge=0)
    supplier_moq: int | None = None
    supplier_lead_time_days: int | None = None
    has_pvoc: bool = False
    has_coc: bool = False
    is_preferred: bool = False
    notes: str | None = None


class ProductSupplierUpdate(BaseModel):
    supplier_price: Decimal | None = Field(default=None, gt=0)
    supplier_moq: int | None = None
    supplier_lead_time_days: int | None = None
    has_pvoc: bool | None = None
    has_coc: bool | None = None
    is_preferred: bool | None = None
    notes: str | None = None


class ProductSupplierDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    supplier_org_id: int
    supplier_org_name: str = ""
    supplier_price: Decimal
    supplier_moq: int | None = None
    supplier_lead_time_days: int | None = None
    has_pvoc: bool
    has_coc: bool
    is_preferred: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------- 商品 — 公开（买方，无供应商） ----------

class ProductPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sku_code: str
    name: str  # get_localized 后的本地化名称
    category_code: str
    category_name: str = ""
    price_min: Decimal
    price_max: Decimal
    currency: str
    unit: str
    moq: int
    lead_time_days: int | None = None
    origin: str  # get_localized 后的本地化产地
    brand: str | None = None  # get_localized 后的本地化品牌
    certifications: list | None = None
    is_featured: bool
    main_image: str | None = None


class ProductPublicDetail(ProductPublic):
    description: str | None = None  # get_localized 后
    hs_code: str | None = None
    images: List[ProductImageSchema] = []
    attributes: List[ProductAttrSchema] = []


# ---------- 商品 — 运营（含供应商 + i18n 原始数据） ----------

class ProductOperator(ProductPublic):
    name_i18n: dict | None = None
    status: str
    created_by_name: str = ""
    supplier_count: int = 0
    created_at: datetime
    updated_at: datetime


class ProductOperatorDetail(ProductPublicDetail):
    name_i18n: dict | None = None
    description_i18n: dict | None = None
    brand_i18n: dict | None = None
    origin_i18n: dict | None = None
    status: str
    created_by_name: str = ""
    suppliers: List[ProductSupplierDetail] = []
    created_at: datetime
    updated_at: datetime


# ---------- 创建 / 编辑 ----------

class ProductCreate(BaseModel):
    category_code: str
    sku_code: str | None = Field(default=None, max_length=50)
    name: str = Field(max_length=200)
    name_i18n: dict | None = None  # {"zh": "...", "en": "...", "sw": "..."}
    description: str | None = None
    description_i18n: dict | None = None
    price_min: Decimal = Field(gt=0)
    price_max: Decimal = Field(gt=0)
    currency: str = "USD"
    unit: str = Field(max_length=20)
    moq: int = Field(gt=0)
    lead_time_days: int | None = None
    origin: str = "China"
    origin_i18n: dict | None = None
    hs_code: str | None = None
    brand: str | None = None
    brand_i18n: dict | None = None
    certifications: list | None = None
    is_featured: bool = False
    status: str = "DRAFT"
    attributes: List[ProductAttrCreate] | None = None


class ProductUpdate(BaseModel):
    category_code: str | None = None
    name: str | None = Field(default=None, max_length=200)
    name_i18n: dict | None = None
    description: str | None = None
    description_i18n: dict | None = None
    price_min: Decimal | None = Field(default=None, gt=0)
    price_max: Decimal | None = Field(default=None, gt=0)
    currency: str | None = None
    unit: str | None = None
    moq: int | None = Field(default=None, gt=0)
    lead_time_days: int | None = None
    origin: str | None = None
    origin_i18n: dict | None = None
    hs_code: str | None = None
    brand: str | None = None
    brand_i18n: dict | None = None
    certifications: list | None = None
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
