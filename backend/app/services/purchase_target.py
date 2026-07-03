"""交易目标解析器 — 购物车 / 询价单 / 结算等交易入口统一走这一个函数(v2 §6.3)。

职责:
1. 商品可交易性校验：ACTIVE + 未软删（不满足则一律 404 语义拒绝，不泄露存在性）。
2. 专区授权：ZONE_ONLY 商品要求 buyer_org 持有目标专区的有效 grant，
   商品在该专区白名单(zone_products)内，且专区自身处于 ACTIVE(停用专区拒绝交易)。
   PUBLIC 商品无需专区校验，但仍受 (1) 约束。
3. SKU 解析：多 ACTIVE SKU 的商品必须靠 selected_variants 唯一定位到一个 SKU；
   零匹配 / 多匹配一律拒绝，绝不静默挑一个（防止 orphan 绑定）。

variant_snapshot 落库口径沿用 app/services/_variant_utils.py 的既有约定：
[{"attr_name": ..., "value": ...}]（英文键值，供购物车/询价单直接落库/展示复用）。
selected_variants 入参兼容三种上游形状：{"attr_name","value"}(既有口径)、
{"attr_key_en","attr_value_en"}、{"key","value"}。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product, ProductStatus, ProductVisibility
from app.db.models.product_attr import ProductAttr
from app.db.models.product_sku import ProductSku, SkuStatus
from app.db.models.zone import Zone, ZoneGrant, ZoneProduct


class ZoneAccessDeniedError(Exception):
    """商品不存在 / 不可购买 / 专区未授权 — 对外一律呈现为 404 语义，不泄露存在性。"""


class VariantUnresolvableError(Exception):
    """selected_variants 无法唯一定位到一个 ACTIVE SKU（零匹配或多匹配）。"""


class SkuMismatchError(Exception):
    """显式传入的 sku_id 不属于/未激活该商品，或与 selected_variants 描述的规格不一致。"""


@dataclass
class PurchaseTarget:
    product: Product
    sku_id: int | None
    variant_snapshot: list[dict] = field(default_factory=list)


def _tuple_of(sku_attrs: list) -> dict:
    """SKU 级 selectable 属性 -> {attr_key_en: attr_value_en}。"""
    return {a.attr_key_en: a.attr_value_en for a in sku_attrs if getattr(a, "selectable", False)}


def _variants_to_map(selected_variants: list[dict] | None) -> dict:
    """归一化 selected_variants 为 {attr_key_en: attr_value_en}。

    兼容三种上游形状：{"attr_name","value"}(既有口径，见 _variant_utils.py)、
    {"attr_key_en","attr_value_en"}、{"key","value"}。
    """
    out: dict = {}
    for sv in selected_variants or []:
        if "attr_key_en" in sv:
            k, v = sv.get("attr_key_en"), sv.get("attr_value_en")
        elif "attr_name" in sv:
            k, v = sv.get("attr_name"), sv.get("value")
        else:
            k, v = sv.get("key"), sv.get("value")
        if k is not None:
            out[k] = v
    return out


def _snapshot_of(tuple_map: dict) -> list[dict]:
    """{attr_key_en: attr_value_en} -> 既有落库/展示形状 [{"attr_name","value"}]。"""
    return [{"attr_name": k, "value": v} for k, v in tuple_map.items()]


def _decide_target(
    product, active_skus: list, selected_variants: list[dict] | None, sku_id: int | None,
) -> tuple[int | None, list[dict]]:
    """纯逻辑：返回 (sku_id | None, variant_snapshot)。见 v2 §6.3。

    - 显式传 sku_id：必须命中 active_skus 中的一个；若同时传了 selected_variants，
      两者描述的规格必须一致，否则拒绝（防止前端传的展示信息与真实绑定的 SKU 对不上）。
    - 未传 sku_id 且 active SKU 数 <= 1：直接绑定该 SKU（或商品级 None，无 SKU 概念）。
    - 未传 sku_id 且多个 active SKU：必须靠 selected_variants 唯一定位到一个 SKU，
      零匹配 / 多匹配一律拒绝 —— 绝不默认挑一个（防 orphan）。
    """
    sel = _variants_to_map(selected_variants)

    if sku_id is not None:
        match = next((s for s in active_skus if s.id == sku_id), None)
        if match is None:
            raise SkuMismatchError(f"sku {sku_id} not active/does not belong to product")
        if sel and _tuple_of(match.attrs) != sel:
            raise SkuMismatchError("selected_variants inconsistent with sku_id")
        return match.id, _snapshot_of(_tuple_of(match.attrs))

    if len(active_skus) <= 1:
        default = next((s for s in active_skus if getattr(s, "is_default", False)), None)
        chosen = default or (active_skus[0] if active_skus else None)
        return (chosen.id if chosen else None), (selected_variants or [])

    if not sel:
        raise VariantUnresolvableError("multiple active skus require selected_variants")
    matches = [s for s in active_skus if _tuple_of(s.attrs) == sel]
    if len(matches) != 1:
        raise VariantUnresolvableError(f"selected_variants resolve to {len(matches)} skus")
    m = matches[0]
    return m.id, _snapshot_of(_tuple_of(m.attrs))


async def resolve_purchase_target(
    db: AsyncSession,
    *,
    product_id: int,
    buyer_org_id: int | None,
    selected_variants: list[dict] | None = None,
    sku_id: int | None = None,
) -> PurchaseTarget:
    """单一交易解析入口：授权 + SKU 解析。购物车/RFQ/结算都应调用此函数而非自行拼查询。"""
    product = (
        await db.execute(
            select(Product).where(
                Product.id == product_id,
                Product.deleted_at.is_(None),
                Product.status == ProductStatus.ACTIVE,
            )
        )
    ).scalar_one_or_none()
    if product is None:
        raise ZoneAccessDeniedError("product not available")

    if product.visibility == ProductVisibility.ZONE_ONLY:
        if buyer_org_id is None:
            raise ZoneAccessDeniedError("zone-only product requires a buyer organization")
        ok = (
            await db.execute(
                select(ZoneProduct.id)
                .join(ZoneGrant, ZoneGrant.zone_id == ZoneProduct.zone_id)
                .join(Zone, Zone.id == ZoneProduct.zone_id)
                .where(
                    ZoneProduct.spu_id == product_id,
                    ZoneGrant.buyer_org_id == buyer_org_id,
                    Zone.status == "ACTIVE",
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if ok is None:
            raise ZoneAccessDeniedError("no grant/whitelist/active-zone for zone-only product")

    active_skus = (
        await db.execute(
            select(ProductSku).where(
                ProductSku.product_id == product_id,
                ProductSku.status == SkuStatus.ACTIVE,
                ProductSku.deleted_at.is_(None),
            )
        )
    ).scalars().all()

    sku_ids = [s.id for s in active_skus]
    attrs = []
    if sku_ids:
        attrs = (
            await db.execute(select(ProductAttr).where(ProductAttr.sku_id.in_(sku_ids)))
        ).scalars().all()
    by_sku: dict[int, list] = {}
    for a in attrs:
        by_sku.setdefault(a.sku_id, []).append(a)
    for s in active_skus:
        s.attrs = by_sku.get(s.id, [])

    resolved_sku_id, snapshot = _decide_target(product, active_skus, selected_variants, sku_id)
    return PurchaseTarget(product=product, sku_id=resolved_sku_id, variant_snapshot=snapshot)
