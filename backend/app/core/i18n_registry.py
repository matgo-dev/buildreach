"""i18n 字段注册表 — 翻译字段的单一声明来源。

所有写路径(create/edit/aggregate)和 CLI(补译/扫描重译)共读此处。
新增/删减翻译字段只改这里,不散落到业务代码。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class I18nSpec:
    """单个实体的 i18n 字段声明。"""
    fields: tuple[str, ...]
    domain: str = "general"


# 全局注册表:model class → I18nSpec
_REGISTRY: dict[type, I18nSpec] = {}


def register_i18n(model: type, spec: I18nSpec) -> None:
    """注册实体的 i18n 字段声明。"""
    _REGISTRY[model] = spec


def get_i18n_spec(model: type) -> I18nSpec | None:
    """查询实体的 i18n 字段声明。"""
    return _REGISTRY.get(model)


def get_i18n_fields(model: type) -> tuple[str, ...]:
    """快捷获取字段列表,未注册返回空元组。"""
    spec = _REGISTRY.get(model)
    return spec.fields if spec else ()


def get_i18n_domain(model: type) -> str:
    """快捷获取 domain,未注册返回 general。"""
    spec = _REGISTRY.get(model)
    return spec.domain if spec else "general"


def all_registered() -> dict[type, I18nSpec]:
    """返回全部注册项(CLI 扫描用)。"""
    return dict(_REGISTRY)


# ── 商品域注册 ──

def _register_product_domain() -> None:
    """延迟导入避免循环依赖。"""
    from app.db.models.product import Product
    from app.db.models.product_sku import ProductSku
    from app.db.models.category import Category
    from app.db.models.product_attr import ProductAttr

    register_i18n(Product, I18nSpec(
        fields=("name", "description", "brand", "origin", "selling_points", "detail_description"),
        domain="product",
    ))
    register_i18n(ProductSku, I18nSpec(
        fields=("name", "color", "material"),
        domain="product",
    ))
    register_i18n(Category, I18nSpec(
        fields=("name", "short_name"),
        domain="category",
    ))
    register_i18n(ProductAttr, I18nSpec(
        fields=("attr_key", "attr_value"),
        domain="product",
    ))


# 模块加载时注册
_register_product_domain()
