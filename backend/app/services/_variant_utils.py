"""变体归一化与 fingerprint 公共工具。

购物车和询价单共用，保证 fingerprint 口径一致：
始终用 attr_key_en + attr_value_en 做规范化，再取 md5。
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product_attr import ProductAttr


async def normalize_variants_to_en(
    db: AsyncSession, product_id: int, selected_variants: list[dict],
) -> list[dict]:
    """将前端传入的变体选择（可能是任意语言）统一转为英文存储。

    匹配逻辑：用前端传入的 key+value 去 product_attrs 的各语言列匹配，
    找到就取 attr_key_en + attr_value_en。找不到就原样存入。
    """
    if not selected_variants:
        return []

    rows = await db.execute(
        select(ProductAttr).where(
            ProductAttr.product_id == product_id,
            ProductAttr.selectable.is_(True),
        )
    )
    attrs = rows.scalars().all()

    # 多语言索引：(key, value) → attr
    idx: dict[tuple[str, str], ProductAttr] = {}
    for a in attrs:
        for k_col, v_col in [
            (a.attr_key_en, a.attr_value_en),
            (a.attr_key_zh, a.attr_value_zh),
            (a.attr_key_sw, a.attr_value_sw),
        ]:
            if k_col and v_col:
                idx[(k_col, v_col)] = a

    result = []
    for sv in selected_variants:
        k = sv.get("attr_name") or sv.get("key", "")
        v = sv.get("value", "")
        matched = idx.get((k, v))
        if matched:
            result.append({
                "attr_name": matched.attr_key_en or k,
                "value": matched.attr_value_en or v,
            })
        else:
            result.append({"attr_name": k, "value": v})
    return sorted(result, key=lambda x: (x.get("attr_name", ""), x.get("value", "")))


def variant_snapshot_to_display(snapshot: list[dict], locale: str = "zh") -> str | None:
    """将 variant_snapshot 拼接为人类可读文本。

    只拼规格值、不带属性名前缀（attr_name 是内部英文键如 "spec"，不应展示给买家；
    展示语境都带「变体规格」列头，键名冗余）。多轴用 " / " 连接。
    """
    if not snapshot:
        return None
    parts = [str(s.get("value", "")) for s in snapshot if s.get("value")]
    return " / ".join(parts) or None


async def get_viewable_product(db: AsyncSession, product_id: int):
    """校验 SPU 是否 ACTIVE + 未软删，返回 Product 或 None。"""
    from app.db.models.product import Product, ProductStatus
    row = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.status == ProductStatus.ACTIVE,
            Product.deleted_at.is_(None),
        )
    )
    return row.scalar_one_or_none()


def variant_fingerprint(normalized_variants: list[dict]) -> str:
    """规范化排序后的 JSON 取 md5，作为变体行身份标识。

    空变体也产生确定性 hash（md5("[]")），保证所有行 fingerprint 非空。
    """
    payload = json.dumps(normalized_variants, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()
