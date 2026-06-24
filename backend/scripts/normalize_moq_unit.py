"""moq_unit 数据清洗脚本 — 将中英文混杂的单位值统一映射为标准 code。

用法
----
    # 预览（不写库）
    python scripts/normalize_moq_unit.py --dry-run

    # 执行清洗
    python scripts/normalize_moq_unit.py

    # 线上环境（进容器后执行）
    python scripts/normalize_moq_unit.py

映射规则
--------
源值（中文/英文/混写）→ 标准 code（与前端 unit_XXX 翻译 key 对齐）。
未识别的值不修改，打印警告人工处理。

⚠️ 幂等安全：已经是标准 code 的行不会被重复处理。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 让 scripts/ 下能 import app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from app.core.config import settings

# asyncpg URL → psycopg 同步 URL
_sync_url = str(settings.DATABASE_URL).replace("+asyncpg", "+psycopg")
sync_engine = create_engine(_sync_url)

# ── 映射表 ──────────────────────────────────────────
# 左侧 key 全部小写匹配，右侧为标准 code
UNIT_MAP: dict[str, str] = {
    # 中文 → code
    "个": "PCS",
    "件": "PCS",
    "只": "PCS",
    "把": "PCS",
    "根": "PCS",
    "片": "PCS",
    "块": "PCS",
    "条": "PCS",
    "支": "PCS",
    "枚": "PCS",
    "颗": "PCS",
    "套": "SET",
    "组": "SET",
    "双": "PAIR",
    "对": "PAIR",
    "米": "M",
    "平方米": "M2",
    "平米": "M2",
    "立方米": "M3",
    "方": "M3",
    "公斤": "KG",
    "千克": "KG",
    "吨": "TON",
    "卷": "ROLL",
    "张": "SHEET",
    "箱": "BOX",
    "盒": "BOX",
    "包": "BAG",
    "袋": "BAG",
    "桶": "BARREL",
    "升": "L",
    "捆": "BUNDLE",
    "扎": "BUNDLE",
    # 英文变体 → code
    "pcs": "PCS",
    "pc": "PCS",
    "piece": "PCS",
    "pieces": "PCS",
    "set": "SET",
    "sets": "SET",
    "pair": "PAIR",
    "pairs": "PAIR",
    "meter": "M",
    "meters": "M",
    "m": "M",
    "square meter": "M2",
    "square meters": "M2",
    "sqm": "M2",
    "cubic meter": "M3",
    "cubic meters": "M3",
    "cbm": "M3",
    "kg": "KG",
    "kilogram": "KG",
    "kilograms": "KG",
    "ton": "TON",
    "tons": "TON",
    "roll": "ROLL",
    "rolls": "ROLL",
    "sheet": "SHEET",
    "sheets": "SHEET",
    "box": "BOX",
    "boxes": "BOX",
    "bag": "BAG",
    "bags": "BAG",
    "barrel": "BARREL",
    "barrels": "BARREL",
    "l": "L",
    "liter": "L",
    "liters": "L",
    "bundle": "BUNDLE",
    "bundles": "BUNDLE",
}

# 已经是标准 code 的值（不需要处理）
STANDARD_CODES = {
    "PCS", "SET", "PAIR", "M", "M2", "M3", "KG", "TON",
    "ROLL", "SHEET", "BOX", "BAG", "BARREL", "L", "BUNDLE",
}


def normalize_unit(raw: str) -> str | None:
    """将原始单位值映射为标准 code，无法识别返回 None。"""
    stripped = raw.strip()
    if stripped.upper() in STANDARD_CODES:
        return stripped.upper()
    return UNIT_MAP.get(stripped.lower())


def main() -> None:
    parser = argparse.ArgumentParser(description="清洗 products.moq_unit 为标准 code")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写库")
    args = parser.parse_args()

    with sync_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT moq_unit FROM products WHERE moq_unit IS NOT NULL ORDER BY moq_unit")
        ).fetchall()

        updates: list[tuple[str, str]] = []  # (old_value, new_code)
        unknown: list[str] = []

        for (raw_unit,) in rows:
            code = normalize_unit(raw_unit)
            if code is None:
                unknown.append(raw_unit)
            elif code != raw_unit:
                updates.append((raw_unit, code))
            # else: 已经是标准 code，跳过

        # 汇报
        print(f"\n{'='*50}")
        print(f"moq_unit 清洗预览")
        print(f"{'='*50}")
        print(f"待清洗: {len(updates)} 种值")
        print(f"已标准: {len(rows) - len(updates) - len(unknown)} 种值")
        if unknown:
            print(f"⚠️  未识别: {unknown}")
        print()

        for old, new in updates:
            count = conn.execute(
                text("SELECT COUNT(*) FROM products WHERE moq_unit = :old"),
                {"old": old},
            ).scalar()
            print(f"  '{old}' → '{new}'  ({count} 条)")

        if args.dry_run:
            print(f"\n{'='*50}")
            print("DRY RUN — 未执行任何修改")
            return

        if not updates:
            print("\n没有需要清洗的数据。")
            return

        # 执行更新
        print(f"\n执行清洗...")
        total = 0
        for old, new in updates:
            result = conn.execute(
                text("UPDATE products SET moq_unit = :new WHERE moq_unit = :old"),
                {"old": old, "new": new},
            )
            total += result.rowcount
        conn.commit()

        print(f"✅ 清洗完成，共更新 {total} 条记录")

        # 同时清洗 unit 字段（如果也有脏数据）
        unit_rows = conn.execute(
            text("SELECT DISTINCT unit FROM products WHERE unit IS NOT NULL ORDER BY unit")
        ).fetchall()
        unit_updates = []
        for (raw_unit,) in unit_rows:
            code = normalize_unit(raw_unit)
            if code and code != raw_unit:
                unit_updates.append((raw_unit, code))
        if unit_updates:
            print(f"\n附带清洗 unit 字段:")
            unit_total = 0
            for old, new in unit_updates:
                result = conn.execute(
                    text("UPDATE products SET unit = :new WHERE unit = :old"),
                    {"old": old, "new": new},
                )
                unit_total += result.rowcount
                print(f"  '{old}' → '{new}'  ({result.rowcount} 条)")
            conn.commit()
            print(f"✅ unit 字段清洗完成，共更新 {unit_total} 条记录")


if __name__ == "__main__":
    main()
