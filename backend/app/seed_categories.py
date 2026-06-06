"""品类 + 属性模板种子：以 CSV 为唯一数据源,全量覆盖。

数据源:
- data/categories.csv — 每行一个 L3,带所属 L1/L2 名,853 行
- data/attr_templates.csv — 每行一个 L1 下的属性,44 行

code 派生:按 CSV 首次出现顺序编号。
落库:先清空 attr_templates → categories,再按 L1→L2→L3 插入,最后插入 attr_templates。
幂等:全量覆盖,重复运行结果一致。
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.attr_template import AttrTemplate
from app.db.models.category import Category

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _parse_categories_csv() -> list[dict]:
    """读取 categories.csv,派生 code / level / parent_code / sort_order。"""
    path = _DATA_DIR / "categories.csv"
    rows: list[dict] = []

    # 跟踪首次出现顺序,派生编号
    l1_map: dict[str, str] = {}   # name_zh → code
    l1_seq = 0
    l2_map: dict[str, str] = {}   # "L1_name|L2_name" → code
    l2_counter: dict[str, int] = {}  # l1_code → next seq
    l3_counter: dict[str, int] = {}  # l2_code → next seq

    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            l1_name = row["一级分类"].strip()
            l2_name = row["二级分类"].strip()
            l3_name = row["三级分类"].strip()

            if not l1_name or not l2_name or not l3_name:
                continue

            # L1
            if l1_name not in l1_map:
                l1_seq += 1
                l1_code = f"{l1_seq:02d}"
                l1_map[l1_name] = l1_code
                l2_counter[l1_code] = 0
                rows.append({
                    "code": l1_code,
                    "name_zh": l1_name,
                    "level": 1,
                    "parent_code": None,
                    "sort_order": l1_seq * 10,
                })
            l1_code = l1_map[l1_name]

            # L2
            l2_key = f"{l1_name}|{l2_name}"
            if l2_key not in l2_map:
                l2_counter[l1_code] += 1
                l2_code = f"{l1_code}.{l2_counter[l1_code]:03d}"
                l2_map[l2_key] = l2_code
                l3_counter[l2_code] = 0
                rows.append({
                    "code": l2_code,
                    "name_zh": l2_name,
                    "level": 2,
                    "parent_code": l1_code,
                    "sort_order": l2_counter[l1_code] * 10,
                })
            l2_code = l2_map[l2_key]

            # L3
            l3_counter[l2_code] += 1
            l3_code = f"{l2_code}.{l3_counter[l2_code]:03d}"
            rows.append({
                "code": l3_code,
                "name_zh": l3_name,
                "level": 3,
                "parent_code": l2_code,
                "sort_order": l3_counter[l2_code] * 10,
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
            })

    return rows


async def seed_categories(db: AsyncSession) -> None:
    """全量覆盖品类树 + 属性模板。"""
    cat_rows = _parse_categories_csv()

    # 提取 L1 name→code 映射给 attr_templates 用
    l1_map = {r["name_zh"]: r["code"] for r in cat_rows if r["level"] == 1}
    attr_rows = _parse_attr_templates_csv(l1_map)

    # 清空(按 FK 依赖顺序:先删引用方,再删被引用方)
    # products 引用 categories.code,需先清商品相关表
    await db.execute(text("DELETE FROM product_suppliers"))
    await db.execute(text("DELETE FROM sku_price_tiers"))
    await db.execute(text("DELETE FROM product_images"))
    await db.execute(text("DELETE FROM product_attrs"))
    await db.execute(text("DELETE FROM product_skus"))
    await db.execute(text("DELETE FROM products"))
    await db.execute(text("DELETE FROM attr_templates"))
    await db.execute(text("DELETE FROM categories WHERE level = 3"))
    await db.execute(text("DELETE FROM categories WHERE level = 2"))
    await db.execute(text("DELETE FROM categories WHERE level = 1"))

    # 插入品类(L1→L2→L3,父先于子)
    for item in cat_rows:
        db.add(Category(
            code=item["code"],
            name_zh=item["name_zh"],
            level=item["level"],
            parent_code=item["parent_code"],
            sort_order=item["sort_order"],
            is_active=True,
        ))
    await db.flush()

    # 插入属性模板
    for item in attr_rows:
        db.add(AttrTemplate(
            category_code=item["category_code"],
            attr_key=item["attr_key"],
            display_name=item["display_name"],
            attr_type=item["attr_type"],
            attr_unit=item["attr_unit"],
            options=item["options"],
            is_required=item["is_required"],
            sort_order=item["sort_order"],
        ))

    await db.commit()

    l1_count = sum(1 for r in cat_rows if r["level"] == 1)
    l2_count = sum(1 for r in cat_rows if r["level"] == 2)
    l3_count = sum(1 for r in cat_rows if r["level"] == 3)
    logger.warning(
        "Seed: categories L1=%d L2=%d L3=%d (total %d), attr_templates=%d.",
        l1_count, l2_count, l3_count, len(cat_rows), len(attr_rows),
    )
