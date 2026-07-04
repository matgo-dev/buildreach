"""央企专区(common-materials)商品图片导入。

材料表商品(ZSOE-* SPU)本身已由 import_zone_soe_materials.py 导入,但 v1 未带图,前端走占位图。
本脚本把预匹配好的 xfs / okorder 平台图片(已下载到本地)按**商品中文名**挂到对应 ZSOE 商品上:

- 数据源:预匹配结果 CSV `最终结果.csv`(1688 行,每行 = 一个材料名 → 来源/offer/主图/详情图路径)
  + 同目录 `categories_xfs/`、`categories_okorder/` 下的实际图片文件(9735 张,0 缺失)。
- 匹配键:CSV 的「输入中文名」硬归一化后 == 平台商品 name_zh(spu_code LIKE 'ZSOE-%')。
  同一中文名挂在多个大类下时(实测 12 例),同一批图挂到每个商品。
- 每商品图片(与 import_products_xfs 对齐):
    main_01  → MAIN   (sort 0)  + 生成 _thumb.webp 缩略图(仅主图有缩略图)
    main_02… → GALLERY(sort 1…)
    detail_* → DETAIL (sort 续) —— 详情页展示,不生成缩略图
  均为 SPU 级(sku_id=NULL)。缩略图走 _buyer_utils.thumb_url_from_image_key 的 _thumb.webp 约定。
- 图片落地:backend/uploads/products/<spu_code>/<文件名>,与平台商品同布局。

幂等(可重复执行):每个匹配到的商品先删其 SPU 级 product_images 再重挂;缩略图已存在且不旧则跳过。
  (只有本脚本给 ZSOE 商品挂图,删除范围安全。)

用法(本地/联调;生产严禁——脚本硬拦 OVH 生产库):
    cd backend
    python scripts/import_zone_soe_images.py --dry-run          # 干跑:只匹配统计,不拷图不落库
    python scripts/import_zone_soe_images.py --commit           # 落库:拷图 + 缩略图 + product_images
    # 源目录默认在桌面;生产上把整个文件夹拷过去后用 --source-dir 指定:
    python scripts/import_zone_soe_images.py --commit --source-dir /path/to/筛出目录
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import csv
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path, PurePosixPath

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))

from PIL import Image  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.db.models.product import Product  # noqa: E402
from app.db.models.product_image import ImageType, ProductImage  # noqa: E402
from app.db.models.zone import Zone, ZoneProduct  # noqa: E402

# 可信本地文件(非用户上传),放开 PIL 像素上限,避免大图触发解压炸弹保护。
Image.MAX_IMAGE_PIXELS = None

# 专区商品按"归属 common-materials 专区"圈定(code 已中性化为 MG-P,不能再靠 spu_code 前缀认)
ZONE_CODE = "common-materials"
UPLOADS_ROOT = _BACKEND_ROOT / "uploads"

# 缩略图参数(与 generate_product_thumbnails.py / thumb_url_from_image_key 的 _thumb.webp 约定一致)
THUMB_SIZE = (300, 300)
THUMB_WEBP_QUALITY = 80

# 预匹配结果目录默认位置(桌面);生产用 --source-dir 覆盖。
DEFAULT_SOURCE_DIR = Path(
    "/Users/liujingjing/Desktop/20260703筛出-基础校准拓展：材料名称中英文、规格、单位-按中英文名去重"
)
RESULT_CSV_NAME = "最终结果.csv"


# 低分复核前缀(flag_zone_soe_low_score.py 打的),匹配前先剥掉,避免打标后重跑丢图
_FLAG_RE = re.compile(r"^【低分\d+】")


def _hard(s: str) -> str:
    """硬归一化:剥低分前缀 + NFKC(全角→半角)+ 去所有空白。与材料导入脚本一致,保证名称 join 命中。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", _FLAG_RE.sub("", str(s))))


def _split_paths(cell: str | None) -> list[str]:
    """图片路径单元格 'images/main_01.jpg;images/main_02.jpg' → 相对路径列表(去空白/空项)。"""
    if not cell:
        return []
    return [p.strip() for p in cell.split(";") if p.strip()]


def local_offer_dir(source_dir: Path, src: str, offer_path_win: str) -> Path:
    """把 CSV 里的 Windows offer.json 路径重映射到本地 offer 目录。

    XFS:     F:\\...\\categories\\<分类树>\\offers\\<id>\\offer.json → categories_xfs/<分类树>/offers/<id>
    OKorder: F:\\...\\categories\\okorder\\offers\\<name_id>\\offer.json → categories_okorder/offers/<name_id>
    """
    raw = str(offer_path_win).replace("\\", "/")
    marker = "/categories/"
    i = raw.find(marker)
    if i < 0:
        raise ValueError(f"offer 路径缺少 /categories/ 段:{offer_path_win!r}")
    sub = raw[i + len(marker):]
    sub = str(PurePosixPath(sub).parent)  # 去掉 offer.json
    if src.upper() == "XFS":
        return source_dir / "categories_xfs" / sub
    # OKorder:sub 形如 "okorder/offers/<name_id>",剥掉前导 okorder/
    if sub.startswith("okorder/"):
        sub = sub[len("okorder/"):]
    return source_dir / "categories_okorder" / sub


def _resolve_offer_dir(offer_dir: Path | None) -> Path | None:
    """把计算出的 offer 目录落到磁盘真实目录。

    okorder 目录名 `<seq>_<商品名>_<offerid>` 在 CSV 与磁盘间存在空白/连字符归一化差异
    (如 CSV `Pyrofix- 铝耐热漆` vs 磁盘 `Pyrofix - 铝耐热漆`),精确路径 exists() 失败。
    用「首段序号 + 尾段 offerid」(seq 唯一、offerid 可重复,组合唯一)glob 回落。
    xfs 目录是纯数字 id,精确命中,此函数为 no-op。
    """
    if offer_dir is None or offer_dir.exists():
        return offer_dir
    parent = offer_dir.parent
    if not parent.exists():
        return None
    parts = offer_dir.name.split("_")
    if len(parts) >= 3:
        seq, offerid = parts[0], parts[-1]
        hits = [p for p in parent.glob(f"{seq}_*_{offerid}") if p.is_dir()]
        if len(hits) == 1:
            return hits[0]
    return None


def _glob_images(offer_dir: Path) -> tuple[list[str], list[str]]:
    """从 offer 目录 images/ 直接扫图,回落 CSV 图片路径列缺失的行。返回 (mains, details) 相对路径。"""
    imgdir = offer_dir / "images"
    if not imgdir.exists():
        return [], []
    mains = sorted(f"images/{p.name}" for p in imgdir.glob("main_*") if p.is_file())
    details = sorted(f"images/{p.name}" for p in imgdir.glob("detail_*") if p.is_file())
    return mains, details


def _thumb_is_fresh(original_path: Path, thumb_path: Path) -> bool:
    try:
        return (
            thumb_path.exists()
            and thumb_path.stat().st_size > 0
            and thumb_path.stat().st_mtime >= original_path.stat().st_mtime
        )
    except OSError:
        return False


def make_thumbnail(original_path: Path) -> bool:
    """为主图原图生成 300px WebP 缩略图(<stem>_thumb.webp,原子写)。已存在且不旧则跳过。

    走裸 PIL(非 _buyer_utils.generate_thumbnail 的用户上传安全门:那会对大图抛 422)。
    这里的图是可信本地文件,只做尺寸压缩。失败返回 False,不中断整批。
    """
    thumb_path = original_path.with_name(original_path.stem + "_thumb.webp")
    if _thumb_is_fresh(original_path, thumb_path):
        return True
    tmp_name = None
    try:
        with Image.open(original_path) as opened:
            img = opened.convert("RGB")
        img.thumbnail(THUMB_SIZE, Image.LANCZOS)
        with tempfile.NamedTemporaryFile(
            dir=thumb_path.parent, prefix=f".{thumb_path.name}.", suffix=".tmp", delete=False
        ) as tmp:
            tmp_name = tmp.name
        img.save(tmp_name, format="WEBP", quality=THUMB_WEBP_QUALITY)
        Path(tmp_name).replace(thumb_path)
        return True
    except Exception as e:  # noqa: BLE001 —— 单张失败不中断
        if tmp_name:
            Path(tmp_name).unlink(missing_ok=True)
        print(f"  [WARN] 缩略图生成失败 {original_path}: {e}", file=sys.stderr)
        return False


def _image_key(spu_code: str, rel_path: str) -> str:
    """image_key:products/<spu_code>/<文件名>(与 import_products_xfs 对齐)。"""
    return f"products/{spu_code}/{Path(rel_path).name}"


def load_image_rows(source_dir: Path) -> list[dict]:
    """解析 最终结果.csv,产出每行的图片导入意图(含本地 offer 目录 + 主图/详情图相对路径)。"""
    csv_path = source_dir / RESULT_CSV_NAME
    if not csv_path.exists():
        raise FileNotFoundError(f"找不到预匹配结果 CSV:{csv_path}")
    rows: list[dict] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)  # 字段含逗号,必须走 csv 解析
        for r in reader:
            name_zh = (r.get("输入中文名") or "").strip()
            if not name_zh:
                continue
            src = (r.get("来源") or "").strip()
            offer_path = (r.get("offer文件路径") or "").strip()
            rows.append({
                "row_no": (r.get("表格行号") or "").strip(),
                "name_zh": name_zh,
                "src": src,
                "offer_dir": local_offer_dir(source_dir, src, offer_path) if offer_path else None,
                "mains": _split_paths(r.get("主图路径")),
                "details": _split_paths(r.get("详情图路径")),
                "link": (r.get("匹配商品链接") or "").strip() or None,
            })
    return rows


async def _product_index(db: AsyncSession) -> dict[str, list[Product]]:
    """common-materials 专区商品:硬归一化 name_zh → [商品](同名多商品挂同一批图)。"""
    zone_spu_ids = (
        select(ZoneProduct.spu_id)
        .join(Zone, Zone.id == ZoneProduct.zone_id)
        .where(Zone.code == ZONE_CODE)
    )
    products = (await db.execute(
        select(Product).where(Product.id.in_(zone_spu_ids), Product.deleted_at.is_(None))
    )).scalars().all()
    index: dict[str, list[Product]] = collections.defaultdict(list)
    for p in products:
        index[_hard(p.name_zh)].append(p)
    return index


def _plan_images(row: dict) -> list[dict]:
    """一行 → 有序图片计划:MAIN(0)+GALLERY(续) 来自 mains,DETAIL(续) 来自 details。

    仅 mains[0] 标记 thumb=True(只有主图生成缩略图)。返回按 sort_order 排好的列表。
    """
    plan: list[dict] = []
    sort_order = 0
    for i, rel in enumerate(row["mains"]):
        plan.append({
            "rel": rel,
            "image_type": ImageType.MAIN if i == 0 else ImageType.GALLERY,
            "sort_order": sort_order,
            "thumb": i == 0,
        })
        sort_order += 1
    for rel in row["details"]:
        plan.append({
            "rel": rel,
            "image_type": ImageType.DETAIL,
            "sort_order": sort_order,
            "thumb": False,
        })
        sort_order += 1
    return plan


async def run_import(db: AsyncSession, source_dir: Path, dry_run: bool) -> dict:
    stats = collections.Counter()
    rows = load_image_rows(source_dir)
    stats["csv_rows"] = len(rows)

    index = await _product_index(db)
    stats["zsoe_products"] = sum(len(v) for v in index.values())

    unmatched_names: list[str] = []
    missing_files: list[str] = []
    processed_product_ids: set[int] = set()

    for row in rows:
        products = index.get(_hard(row["name_zh"]))
        if not products:
            unmatched_names.append(row["name_zh"])
            stats["rows_unmatched"] += 1
            continue
        stats["rows_matched"] += 1

        offer_dir = _resolve_offer_dir(row["offer_dir"])
        mains, details = row["mains"], row["details"]
        # 数据修复:CSV 主图/详情图路径列全空但 offer 目录里有图(实测 26 行 okorder,
        # 主图数量>0 却漏填路径)→ 直接扫 offer 目录 images/ 回落。仅两列全空时触发,不误伤正常行。
        if offer_dir is not None and not mains and not details:
            g_mains, g_details = _glob_images(offer_dir)
            if g_mains or g_details:
                mains, details = g_mains, g_details
                stats["rows_recovered_by_glob"] += 1

        plan = _plan_images({"mains": mains, "details": details})
        if not plan:
            stats["rows_no_image"] += 1
            continue

        # 校验源文件存在(dry-run 也做,及时暴露缺图)
        valid_plan = []
        for item in plan:
            src_path = (offer_dir / item["rel"]) if offer_dir else None
            if src_path is None or not src_path.exists():
                missing_files.append(f"{row['name_zh']}::{item['rel']}")
                continue
            item["src_path"] = src_path
            valid_plan.append(item)
        if not valid_plan:
            stats["rows_all_missing"] += 1
            continue

        for product in products:
            if product.id in processed_product_ids:
                stats["products_skipped_dup_name"] += 1
                continue
            processed_product_ids.add(product.id)

            if not dry_run:
                # 幂等:先删该商品 SPU 级图片(只有本脚本给 ZSOE 挂图,范围安全),再重挂
                await db.execute(
                    delete(ProductImage).where(
                        ProductImage.product_id == product.id,
                        ProductImage.sku_id.is_(None),
                    )
                )
                dest_dir = UPLOADS_ROOT / "products" / product.spu_code
                dest_dir.mkdir(parents=True, exist_ok=True)

            for item in valid_plan:
                if not dry_run:
                    dest = UPLOADS_ROOT / "products" / product.spu_code / Path(item["rel"]).name
                    shutil.copy2(item["src_path"], dest)
                    db.add(ProductImage(
                        product_id=product.id,
                        sku_id=None,
                        image_key=_image_key(product.spu_code, item["rel"]),
                        image_type=item["image_type"],
                        sort_order=item["sort_order"],
                        source_url=row["link"],
                    ))
                    if item["thumb"]:
                        if make_thumbnail(dest):
                            stats["thumbs_generated"] += 1
                        else:
                            stats["thumbs_failed"] += 1
                stats[f"images_{item['image_type'].lower()}"] += 1
                stats["images_total"] += 1
            stats["products_imaged"] += 1

        if not dry_run:
            await db.flush()

    return {
        "stats": dict(stats),
        "unmatched_names": unmatched_names,
        "missing_files": missing_files,
    }


async def _execute(dry_run: bool, source_dir: Path) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings

    if (
        not dry_run
        and "162.19.98.142" in (settings.DATABASE_URL or "")
        and os.environ.get("ALLOW_ZONE_SOE_IMAGES_PROD") != "1"
    ):
        raise SystemExit(
            "拒绝执行:DATABASE_URL 指向 OVH 生产库。生产落库前请先 dry-run 确认, "
            "并把图片源目录拷到生产机、用 --source-dir 指定,再设 ALLOW_ZONE_SOE_IMAGES_PROD=1 执行 --commit。"
        )

    if not source_dir.exists():
        raise SystemExit(f"图片源目录不存在:{source_dir}(生产用 --source-dir 指定)")

    engine = create_async_engine(settings.DATABASE_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        result = await run_import(db, source_dir, dry_run)
        if dry_run:
            await db.rollback()
        else:
            await db.commit()
    await engine.dispose()

    s = result["stats"]
    print("=" * 64)
    print(f"央企专区图片导入 {'[DRY-RUN 未落库/未拷图]' if dry_run else '[已落库 COMMIT]'}")
    print("=" * 64)
    print(f"CSV 行数:                 {s.get('csv_rows', 0)}")
    print(f"ZSOE 商品数:              {s.get('zsoe_products', 0)}")
    print(f"行匹配:                   命中 {s.get('rows_matched', 0)} / 未命中 {s.get('rows_unmatched', 0)}")
    print(f"商品挂图:                 {s.get('products_imaged', 0)}(同名去重跳过 {s.get('products_skipped_dup_name', 0)})")
    print(f"图片:                     MAIN {s.get('images_main', 0)} / GALLERY {s.get('images_gallery', 0)} / DETAIL {s.get('images_detail', 0)} = {s.get('images_total', 0)}")
    print(f"缩略图(仅主图):          生成 {s.get('thumbs_generated', 0)} / 失败 {s.get('thumbs_failed', 0)}")
    print(f"CSV 漏填路径按目录扫图回落: {s.get('rows_recovered_by_glob', 0)} 行")
    print(f"无图行:                   {s.get('rows_no_image', 0)} / 全缺文件行 {s.get('rows_all_missing', 0)}")
    if result["missing_files"]:
        print(f"缺失源文件:               {len(result['missing_files'])} 张(样例 {result['missing_files'][:3]})")
    if result["unmatched_names"]:
        u = result["unmatched_names"]
        print(f"未命中商品名:             {len(u)} 个(样例 {u[:8]})")
    if dry_run:
        print("\n这是干跑,数据库/文件系统未改动。确认无误后加 --commit 落库。")


def main() -> None:
    ap = argparse.ArgumentParser(description="央企专区商品图片导入(xfs/okorder 预匹配图 → ZSOE 商品)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="干跑:只匹配统计,不拷图不落库")
    g.add_argument("--commit", action="store_true", help="落库:拷图 + 缩略图 + product_images")
    ap.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR, help="预匹配结果目录(含 最终结果.csv + categories_xfs/okorder)")
    args = ap.parse_args()
    asyncio.run(_execute(dry_run=args.dry_run, source_dir=args.source_dir))


if __name__ == "__main__":
    main()
