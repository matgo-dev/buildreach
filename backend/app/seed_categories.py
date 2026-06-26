"""品类 + 属性模板种子：以 CSV 为唯一数据源,upsert 模式。

⚠️ DEPRECATED — 生产品类数据已切换为声明式治理,使用 scripts/import_categories.py。
本文件仅保留给测试 conftest 使用(测试需要品类数据初始化)。
线上/部署不应再调用此脚本。

数据源:
- data/categories.csv — 声明式品类表,每行一个品类(L1-L4),约 6391 行,code 已预定义
- data/attr_templates.csv — 每行一个 L1 下的属性,44 行

落库:按 code / (category_code, attr_key) 查重,存在则更新,不存在则插入。
不删除任何已有数据,商品等引用品类的业务数据不受影响。
幂等:重复运行结果一致。
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.attr_template import AttrTemplate
from app.db.models.category import Category
from app.core.i18n_write import apply_i18n_create

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _needs_translation(cat: "Category") -> bool:
    """判断品类是否缺少翻译(en 或 sw 为空)。"""
    return not cat.name_en or not cat.name_sw


async def _mark_i18n_pending(cat: "Category", name_zh: str) -> None:
    """为品类的 name 字段初始化 i18n 标记,让 sweeper 发现并翻译。"""
    await apply_i18n_create(cat, "name", name_zh, "zh", domain="category")


def _parse_categories_csv() -> list[dict]:
    """读取 categories.csv,code/level/parent_code 直接从 CSV 取,不再派生。"""
    path = _DATA_DIR / "categories.csv"
    rows: list[dict] = []

    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row["code"].strip()
            name_zh = row["name_zh"].strip()
            if not code or not name_zh:
                continue

            level = int(row["level"])
            parent_code = row.get("parent_code", "").strip() or None
            name_en = row.get("name_en", "").strip() or None
            name_sw = row.get("name_sw", "").strip() or None
            is_active = row.get("is_active", "t").strip().lower() in ("t", "true", "1", "yes")

            rows.append({
                "code": code,
                "name_zh": name_zh,
                "name_en": name_en,
                "name_sw": name_sw,
                "level": level,
                "parent_code": parent_code,
                "is_active": is_active,
                "sort_order": 0,
            })

    return rows


def _parse_attr_templates_csv(l1_map: dict[str, str]) -> list[dict]:
    """读取 attr_templates.csv,关联 L1 code。"""
    path = _DATA_DIR / "attr_templates.csv"
    rows: list[dict] = []
    l1_attr_counter: dict[str, int] = {}

    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            l1_name = row["一级分类"].strip()
            attr_name = row["属性名"].strip()
            if not l1_name or not attr_name:
                continue

            l1_code = l1_map.get(l1_name)
            if l1_code is None:
                logger.warning("attr_templates: L1 '%s' not found, skipping '%s'", l1_name, attr_name)
                continue

            scope = row.get("scope", "").strip().upper() or "SKU"
            if scope not in ("SPU", "SKU"):
                logger.warning("attr_templates: invalid scope '%s' for '%s', defaulting to SKU", scope, attr_name)
                scope = "SKU"

            l1_attr_counter.setdefault(l1_code, 0)
            l1_attr_counter[l1_code] += 1
            rows.append({
                "category_code": l1_code,
                "attr_key": attr_name,
                "display_name": attr_name,
                "attr_type": "text",
                "attr_unit": None,
                "options": None,
                "is_required": False,
                "sort_order": l1_attr_counter[l1_code] * 10,
                "scope": scope,
            })

    return rows


async def seed_categories(db: AsyncSession) -> None:
    """upsert 品类树 + 属性模板（按 code / 唯一键查重,存在则更新,不存在则插入）。

    不删除任何已有数据,商品等引用品类的业务数据不受影响。
    """
    cat_rows = _parse_categories_csv()

    # 提取 L1 name→code 映射给 attr_templates 用
    l1_map = {r["name_zh"]: r["code"] for r in cat_rows if r["level"] == 1}
    attr_rows = _parse_attr_templates_csv(l1_map)

    # upsert 品类(父先于子,CSV 按 code 排序保证 FK 安全)
    cat_created, cat_updated, cat_i18n_marked = 0, 0, 0
    for item in cat_rows:
        row = await db.execute(
            select(Category).where(Category.code == item["code"])
        )
        existing = row.scalar_one_or_none()
        if existing is not None:
            existing.name_zh = item["name_zh"]
            existing.name_en = item.get("name_en")
            existing.name_sw = item.get("name_sw")
            existing.level = item["level"]
            existing.parent_code = item["parent_code"]
            existing.sort_order = item["sort_order"]
            existing.is_active = item["is_active"]
            # 补标 i18n:已有记录如果缺翻译且未标 pending,补上标记
            if existing.i18n_pending_at is None and _needs_translation(existing):
                await _mark_i18n_pending(existing, item["name_zh"])
                cat_i18n_marked += 1
            cat_updated += 1
        else:
            cat = Category(
                code=item["code"],
                name_zh=item["name_zh"],
                name_en=item.get("name_en"),
                name_sw=item.get("name_sw"),
                level=item["level"],
                parent_code=item["parent_code"],
                sort_order=item["sort_order"],
                is_active=item["is_active"],
            )
            # 初始化 i18n 标记,让 sweeper 能发现并翻译
            await _mark_i18n_pending(cat, item["name_zh"])
            cat_i18n_marked += 1
            db.add(cat)
            cat_created += 1

    await db.flush()

    # 同步 is_leaf:有 active 子节点的品类为非叶子
    all_cats = (await db.execute(select(Category))).scalars().all()
    parent_codes_with_children: set[str] = set()
    for c in all_cats:
        if c.parent_code and c.is_active:
            parent_codes_with_children.add(c.parent_code)
    for c in all_cats:
        c.is_leaf = c.code not in parent_codes_with_children
    await db.flush()

    # upsert 属性模板(按唯一键 category_code + attr_key 查重)
    attr_created, attr_updated = 0, 0
    for item in attr_rows:
        row = await db.execute(
            select(AttrTemplate).where(
                AttrTemplate.category_code == item["category_code"],
                AttrTemplate.attr_key == item["attr_key"],
            )
        )
        existing = row.scalar_one_or_none()
        if existing is not None:
            existing.display_name = item["display_name"]
            existing.attr_type = item["attr_type"]
            existing.attr_unit = item["attr_unit"]
            existing.options = item["options"]
            existing.is_required = item["is_required"]
            existing.sort_order = item["sort_order"]
            existing.scope = item["scope"]
            attr_updated += 1
        else:
            db.add(AttrTemplate(
                category_code=item["category_code"],
                attr_key=item["attr_key"],
                display_name=item["display_name"],
                attr_type=item["attr_type"],
                attr_unit=item["attr_unit"],
                options=item["options"],
                is_required=item["is_required"],
                sort_order=item["sort_order"],
                scope=item["scope"],
            ))
            attr_created += 1

    await db.commit()

    l1_count = sum(1 for r in cat_rows if r["level"] == 1)
    l2_count = sum(1 for r in cat_rows if r["level"] == 2)
    l3_count = sum(1 for r in cat_rows if r["level"] == 3)
    l4_count = sum(1 for r in cat_rows if r["level"] == 4)
    logger.warning(
        "Seed: categories L1=%d L2=%d L3=%d L4=%d (total %d, +%d/~%d, i18n_marked=%d), attr_templates=%d (+%d/~%d).",
        l1_count, l2_count, l3_count, l4_count, len(cat_rows),
        cat_created, cat_updated, cat_i18n_marked, len(attr_rows), attr_created, attr_updated,
    )
