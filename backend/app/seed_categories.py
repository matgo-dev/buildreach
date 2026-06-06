"""品类 + 属性模板种子：以 CSV 为唯一数据源,upsert 模式。

数据源:
- data/categories.csv — 每行一个 L3,带所属 L1/L2 名,853 行
- data/attr_templates.csv — 每行一个 L1 下的属性,44 行

code 派生:按 CSV 首次出现顺序编号。
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

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _load_en_names() -> dict[str, str]:
    """加载中英文名称映射。"""
    path = _DATA_DIR / "category_names_en.json"
    if path.exists():
        return json.load(path.open(encoding="utf-8"))
    return {}


def _parse_categories_csv() -> list[dict]:
    """读取 categories.csv,派生 code / level / parent_code / sort_order,关联英文名。"""
    path = _DATA_DIR / "categories.csv"
    en_names = _load_en_names()
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
                    "name_en": en_names.get(l1_name),
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
                    "name_en": en_names.get(l2_name),
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
                "name_en": en_names.get(l3_name),
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

    # upsert 品类(L1→L2→L3,父先于子,JSON 已保证 FK 安全)
    cat_created, cat_updated = 0, 0
    for item in cat_rows:
        row = await db.execute(
            select(Category).where(Category.code == item["code"])
        )
        existing = row.scalar_one_or_none()
        if existing is not None:
            existing.name_zh = item["name_zh"]
            existing.name_en = item.get("name_en")
            existing.level = item["level"]
            existing.parent_code = item["parent_code"]
            existing.sort_order = item["sort_order"]
            existing.is_active = True
            cat_updated += 1
        else:
            db.add(Category(
                code=item["code"],
                name_zh=item["name_zh"],
                name_en=item.get("name_en"),
                level=item["level"],
                parent_code=item["parent_code"],
                sort_order=item["sort_order"],
                is_active=True,
            ))
            cat_created += 1

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
    logger.warning(
        "Seed: categories L1=%d L2=%d L3=%d (total %d, +%d/~%d), attr_templates=%d (+%d/~%d).",
        l1_count, l2_count, l3_count, len(cat_rows),
        cat_created, cat_updated, len(attr_rows), attr_created, attr_updated,
    )
