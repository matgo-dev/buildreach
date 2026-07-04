"""央企专区低分匹配商品——名称打标(复核辅助,不删图)。

图片是按商品名模糊匹配 xfs/okorder 拿的,低分匹配常配错图(如"高压静电电容器柜"→工作服图)。
本脚本**不删图**,只把低分商品的 `name_zh` 前面加 `【低分<分数>】` 前缀,方便在专区搜"低分"一次性捞出复核。

- 数据源:预匹配结果 CSV `最终结果.csv` 的「匹配分数」列(按「输入中文名」join 到平台 name_zh)。
- 阈值:分数 < --below(默认 180)的算低分。前缀带分数(取整)便于判轻重。
- 幂等 + 可逆:每次先剥掉已有 `【低分\\d+】` 前缀再按当前阈值重打;`--unflag` 一键去掉所有前缀。
- 只改商品标题 name_zh(搜索 ilike 命中它),不动 SKU / 图片 / category。

⚠️ 与图片导入的关系:图片导入按 name_zh 匹配。本脚本改了 name_zh 后,
   import_zone_soe_images 已做兼容(匹配前先剥 `【低分…】` 前缀),重跑图片脚本仍能命中、不丢图。

用法(本地/联调;生产严禁——脚本硬拦 OVH 生产库):
    cd backend
    python scripts/flag_zone_soe_low_score.py --dry-run            # 干跑看会打/去多少标
    python scripts/flag_zone_soe_low_score.py --commit             # 落库:按 <180 打标
    python scripts/flag_zone_soe_low_score.py --commit --below 150 # 改阈值(会自动纠正已有标)
    python scripts/flag_zone_soe_low_score.py --commit --unflag    # 去掉所有低分前缀
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import csv
import os
import re
import sys
import unicodedata
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.db.models.product import Product  # noqa: E402

ZSOE_SPU_PREFIX = "ZSOE-"
DEFAULT_THRESHOLD = 180.0

DEFAULT_SOURCE_DIR = Path(
    "/Users/liujingjing/Desktop/20260703筛出-基础校准拓展：材料名称中英文、规格、单位-按中英文名去重"
)
RESULT_CSV_NAME = "最终结果.csv"

# 低分前缀:【低分<整数分数>】,可逆/幂等靠它识别
FLAG_RE = re.compile(r"^【低分\d+】")


def _hard(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(s)))


def strip_flag(name: str) -> str:
    """剥掉开头的 【低分\\d+】 前缀(没有则原样返回)。"""
    return FLAG_RE.sub("", name)


def desired_name(base_name: str, score: float | None, threshold: float, unflag: bool) -> str:
    """目标名:低分且未 unflag → 打前缀;否则裸名。base_name 须是已剥前缀的裸名。"""
    if unflag or score is None or score >= threshold:
        return base_name
    return f"【低分{int(score)}】{base_name}"


def load_score_by_name(source_dir: Path) -> dict[str, float]:
    """最终结果.csv → 硬归一化(输入中文名) → 匹配分数(同名取最低分=最可疑)。"""
    csv_path = source_dir / RESULT_CSV_NAME
    if not csv_path.exists():
        raise FileNotFoundError(f"找不到预匹配结果 CSV:{csv_path}")
    out: dict[str, float] = {}
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            name = (r.get("输入中文名") or "").strip()
            if not name:
                continue
            try:
                sc = float(r.get("匹配分数") or "")
            except ValueError:
                continue
            k = _hard(name)
            if k not in out or sc < out[k]:
                out[k] = sc
    return out


async def run_flag(db: AsyncSession, source_dir: Path, threshold: float, unflag: bool) -> dict:
    stats = collections.Counter()
    score_by_name = load_score_by_name(source_dir)

    products = (await db.execute(
        select(Product).where(
            Product.spu_code.like(f"{ZSOE_SPU_PREFIX}%"),
            Product.deleted_at.is_(None),
        )
    )).scalars().all()
    stats["zsoe_products"] = len(products)

    samples: list[str] = []
    for p in products:
        base = strip_flag(p.name_zh)
        score = score_by_name.get(_hard(base))
        want = desired_name(base, score, threshold, unflag)
        if p.name_zh == want:
            continue
        had_flag = FLAG_RE.match(p.name_zh) is not None
        now_flag = FLAG_RE.match(want) is not None
        if now_flag and not had_flag:
            stats["flagged"] += 1
            if len(samples) < 10:
                samples.append(f"{p.spu_code}  {want}")
        elif had_flag and not now_flag:
            stats["unflagged"] += 1
        else:  # 前缀分数变了(阈值调整/分数刷新)
            stats["reflagged"] += 1
        p.name_zh = want

    return {"stats": dict(stats), "samples": samples}


async def _execute(dry_run: bool, source_dir: Path, threshold: float, unflag: bool) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings

    if (
        not dry_run
        and "162.19.98.142" in (settings.DATABASE_URL or "")
        and os.environ.get("ALLOW_ZONE_SOE_FLAG_PROD") != "1"
    ):
        raise SystemExit(
            "拒绝执行:DATABASE_URL 指向 OVH 生产库。生产落库前请先 dry-run 确认, "
            "再设 ALLOW_ZONE_SOE_FLAG_PROD=1 执行 --commit。"
        )
    if not unflag and not source_dir.exists():
        raise SystemExit(f"图片源目录不存在:{source_dir}(生产用 --source-dir 指定;--unflag 不需要)")

    engine = create_async_engine(settings.DATABASE_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        result = await run_flag(db, source_dir, threshold, unflag)
        if dry_run:
            await db.rollback()
        else:
            await db.commit()
    await engine.dispose()

    s = result["stats"]
    mode = "去标 UNFLAG" if unflag else f"打标(<{threshold:g})"
    print("=" * 60)
    print(f"央企专区低分名称{mode} {'[DRY-RUN 未落库]' if dry_run else '[已落库 COMMIT]'}")
    print("=" * 60)
    print(f"ZSOE 商品数:   {s.get('zsoe_products', 0)}")
    print(f"新打标:        {s.get('flagged', 0)}")
    print(f"去标:          {s.get('unflagged', 0)}")
    print(f"改标(换分数):  {s.get('reflagged', 0)}")
    if result["samples"]:
        print("样例:")
        for line in result["samples"]:
            print(f"  {line}")
    if dry_run:
        print("\n这是干跑,数据库未改动。确认后加 --commit 落库。")


def main() -> None:
    ap = argparse.ArgumentParser(description="央企专区低分匹配商品名称打标(复核辅助,不删图)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="干跑:算但不落库")
    g.add_argument("--commit", action="store_true", help="落库")
    ap.add_argument("--below", type=float, default=DEFAULT_THRESHOLD, help=f"低分阈值(默认 {DEFAULT_THRESHOLD:g};分数 < 此值打标)")
    ap.add_argument("--unflag", action="store_true", help="去掉所有 【低分…】 前缀(忽略阈值)")
    ap.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR, help="含 最终结果.csv 的目录")
    args = ap.parse_args()
    asyncio.run(_execute(dry_run=args.dry_run, source_dir=args.source_dir, threshold=args.below, unflag=args.unflag))


if __name__ == "__main__":
    main()
