#!/usr/bin/env python3
"""手动执行：种入品类树 + 属性模板。

⚠️ DEPRECATED — 生产品类数据已切换为鑫方盛数据源,请使用 scripts/import_categories_xfs.py。
本脚本仅保留给测试/历史参考,线上不应再调用。

用法：
    cd backend
    python scripts/seed_categories.py           # 执行 upsert
    python scripts/seed_categories.py --dry-run  # 仅预览,不写库
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# 把 backend 目录加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.seed_categories import _parse_categories_csv, _parse_attr_templates_csv  # noqa: E402


def dry_run() -> None:
    """预览 CSV 解析结果,不连数据库。"""
    cat_rows = _parse_categories_csv()

    l1 = [r for r in cat_rows if r["level"] == 1]
    l2 = [r for r in cat_rows if r["level"] == 2]
    l3 = [r for r in cat_rows if r["level"] == 3]

    print("=" * 60)
    print("品类树预览 (dry-run, 不写库)")
    print("=" * 60)
    print(f"\n总计: L1={len(l1)}, L2={len(l2)}, L3={len(l3)}, 合计={len(cat_rows)}")

    print(f"\n── L1 一级分类 ({len(l1)}) ──")
    for c in l1:
        l2_count = sum(1 for r in l2 if r["parent_code"] == c["code"])
        l3_count = sum(1 for r in l3 if r["parent_code"] and r["parent_code"].startswith(c["code"] + "."))
        en = c.get("name_en") or "(无英文)"
        print(f"  {c['code']}  {c['name_zh']:10s}  {en:30s}  L2={l2_count}, L3={l3_count}")

    print(f"\n── L2 二级分类 (前 20 / {len(l2)}) ──")
    for c in l2[:20]:
        l3_count = sum(1 for r in l3 if r["parent_code"] == c["code"])
        en = c.get("name_en") or "(无英文)"
        print(f"  {c['code']:10s}  {c['name_zh']:12s}  {en:30s}  L3={l3_count}")
    if len(l2) > 20:
        print(f"  ... 省略 {len(l2) - 20} 条")

    print(f"\n── L3 三级分类 (前 10 / {len(l3)}) ──")
    for c in l3[:10]:
        en = c.get("name_en") or "(无英文)"
        print(f"  {c['code']:14s}  {c['name_zh']:14s}  {en}")
    if len(l3) > 10:
        print(f"  ... 省略 {len(l3) - 10} 条")

    # 属性模板
    l1_map = {r["name_zh"]: r["code"] for r in l1}
    attr_rows = _parse_attr_templates_csv(l1_map)
    l1_code_to_name = {r["code"]: r["name_zh"] for r in l1}

    print(f"\n── 属性模板 ({len(attr_rows)}) ──")
    by_l1: dict[str, list[str]] = {}
    for a in attr_rows:
        l1_name = l1_code_to_name.get(a["category_code"], a["category_code"])
        by_l1.setdefault(l1_name, []).append(a["attr_key"])
    for l1_name, keys in by_l1.items():
        print(f"  {l1_name}: {', '.join(keys)}")

    # 英文覆盖率
    with_en = sum(1 for r in cat_rows if r.get("name_en"))
    print(f"\n── 英文名覆盖: {with_en}/{len(cat_rows)} ({with_en*100//len(cat_rows)}%) ──")
    print()


async def execute() -> None:
    """连库执行 upsert。"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.core.config import settings
    from app.seed_categories import seed_categories

    engine = create_async_engine(settings.DATABASE_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        await seed_categories(db)
    await engine.dispose()
    print("Done.")


def main() -> None:
    parser = argparse.ArgumentParser(description="品类 + 属性模板种子")
    parser.add_argument("--dry-run", action="store_true", help="仅预览解析结果,不连数据库")
    args = parser.parse_args()

    if args.dry_run:
        dry_run()
    else:
        asyncio.run(execute())


if __name__ == "__main__":
    main()
