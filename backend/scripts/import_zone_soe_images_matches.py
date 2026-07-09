"""央企专区图片+分类更新脚本:读取九云 matches.json / XFS offer 目录树。

推荐的交付目录:

    run_YYYYMMDD_HHMMSS/
      run.json
      matches.json
      images/
        19396354/
          main_01.jpg
          detail_01.jpg

matches.json 为数组,每条至少包含:

    {
      "material_category_code": "02",
      "material_category_name": "水泥类",
      "material_name": "水泥",
      "material_name_en": "cement",
      "offer_id": "19396354",
      "offer_url": "https://www.xfs.com/productsku/19396354.html",
      "listing_title": "洪双竹 PC325/PF325水泥 50kg",
      "matched_category_path": ["涂料化工", "墙地面", "砂石水泥", "水泥"],
      "images": {
        "main": ["images/19396354/main_01.jpg"],
        "detail": ["images/19396354/detail_01.jpg"]
      }
    }

也兼容九云当前目录树(小陶拿数结构):

    run_YYYYMMDD_HHMMSS/
      categories/L1-.../L2-.../L3-.../L4-.../offers/<offer_id>/offer.json
      categories/**/offers/<offer_id>/images/main_01.jpg

其中 offer.json 里的 product_name_zh 作为 material_name、source_category_path 作为
matched_category_path。若 material_name 在央企材料表里重名,必须补 material_category_code
或 spu_code,脚本不会靠 XFS 类目猜。

本脚本做三件事(相对旧版新增分类与台账):
1. 图片全替换:删该 SPU 原有 SPU 级 product_images,拷新图;封面按分辨率选,主图生缩略图。
   - 分辨率:同 offer 的主图按 min(宽,高) 降序排,最清那张当封面(sort_order=0);
     若最佳主图仍 < --min-cover-side(默认 600)→ 判低清、**整条 hold 不替换**、记台账待人工复核。
2. 分类以 XFS 为准:matched_category_path 按名逐级解析到主 categories 树叶子 → 回写
   Product.category_code。缺叶子**只在已有父节点下自动建**并记录;**L1 都不存在则不动分类**、
   记 category_unresolved 待人工决定是否扩目录(绝不自动建一级大类)。
3. 执行台账:每次 --commit 按 spu_code upsert 到 data/zone_import/soe_image_refresh_ledger.csv,
   记录本条基于哪一版(run.crawled_at)、图数、old→new 分类、新建叶子、状态。
   --report:拿专区全部材料 join 台账,打印已更新 / 待更新,回答"哪些材料已基于这版更新"。

执行:

    cd backend
    python scripts/import_zone_soe_images_matches.py --source-dir /path/to/run --dry-run
    python scripts/import_zone_soe_images_matches.py --source-dir /path/to/run --commit
    python scripts/import_zone_soe_images_matches.py --report
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import csv
import dataclasses
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))
_REPO_ROOT = _BACKEND_ROOT.parent

from PIL import Image  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.db.models.category import Category  # noqa: E402
from app.db.models.product import Product  # noqa: E402
from app.db.models.product_image import ImageType, ProductImage  # noqa: E402
from app.db.models.zone import Zone, ZoneProduct  # noqa: E402
from app.services.product_code import platform_spu_code  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

ZONE_CODE = "common-materials"
ZSOE_SOURCE = "ZSOE"
UPLOADS_ROOT = _BACKEND_ROOT / "uploads"
MASTER_FINAL = _REPO_ROOT / "data" / "zone_import" / "prepared" / "master_final.json"
LEDGER_PATH = _REPO_ROOT / "data" / "zone_import" / "soe_image_refresh_ledger.csv"
THUMB_SIZE = (300, 300)
THUMB_WEBP_QUALITY = 80
MIN_COVER_SIDE = 600  # 最佳主图 min(宽,高) 低于此 → 判低清、hold 不替换

LEDGER_FIELDS = [
    "spu_code", "material_name", "offer_id", "run_crawled_at", "updated_at",
    "n_main", "n_gallery", "n_detail", "best_main_min_side",
    "old_category_code", "new_category_code", "created_leaf_codes",
    "cat_status", "status",
]

ZONE_CATEGORIES = [
    ("01", "钢筋类", "Rebar"),
    ("02", "水泥类", "Cement"),
    ("03", "钢材类", "Steel"),
    ("04", "木材类", "Timber"),
    ("05", "成品砼类", "Ready-mix Concrete"),
    ("06", "砂石料类", "Aggregates"),
    ("07", "油漆涂料", "Paints & Coatings"),
    ("08", "电动工具", "Power Tools"),
    ("09", "平立面装修类", "Finishing Materials"),
    ("10", "五金耗材类", "Hardware & Consumables"),
    ("11", "给排水类", "Water Supply & Drainage"),
    ("12", "强弱电类", "Electrical"),
    ("13", "暖通气动类", "HVAC & Pneumatic"),
    ("14", "消防类", "Fire Protection"),
    ("15", "家具家电类", "Furniture & Appliances"),
    ("16", "周转料", "Reusable Materials"),
    ("17", "临时设施", "Temporary Facilities"),
]
_CAT_NAME_TO_CODE = {name_zh: code for code, name_zh, _ in ZONE_CATEGORIES}


def _hard(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(s or "")))


def _raw_url(url: str | None) -> str | None:
    if not url:
        return None
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path, "", ""))


def _safe_offer_id(offer_id: str | None) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", str(offer_id or "unknown")).strip("_")
    return safe or "unknown"


def zsoe_spu_code(cat_code: str, material_name: str) -> str:
    return platform_spu_code(ZSOE_SOURCE, f"{cat_code}:{_hard(material_name)}")


@dataclasses.dataclass(frozen=True)
class ImageIn:
    kind: str
    rel_path: str
    source_url: str | None = None


@dataclasses.dataclass(frozen=True)
class MatchIn:
    material_name: str
    material_category_code: str | None
    material_category_name: str | None
    spu_code: str | None
    offer_id: str
    offer_url: str | None
    listing_title: str | None
    matched_category_path: list[str]
    images: list[ImageIn]
    base_dir: Path


def _normalize_image_item(kind: str, item: object) -> ImageIn:
    if isinstance(item, str):
        return ImageIn(kind=kind, rel_path=item)
    if isinstance(item, dict):
        rel = item.get("path") or item.get("local_path") or item.get("file")
        if not rel:
            raise ValueError(f"图片项缺少 path/local_path/file:{item!r}")
        source_url = item.get("source_url_raw") or item.get("source_url") or item.get("source_url_processed")
        return ImageIn(kind=kind, rel_path=str(rel), source_url=_raw_url(str(source_url)) if source_url else None)
    raise ValueError(f"不支持的图片项:{item!r}")


def _images_from_matches(images: dict) -> list[ImageIn]:
    out: list[ImageIn] = []
    for kind, image_type in (("main", ImageType.MAIN), ("gallery", ImageType.GALLERY), ("detail", ImageType.DETAIL)):
        for item in images.get(kind) or []:
            out.append(_normalize_image_item(image_type, item))
    return out


def load_matches_json(source_dir: Path) -> list[MatchIn]:
    path = source_dir / "matches.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("matches.json 必须是数组")

    rows: list[MatchIn] = []
    for i, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"matches.json 第 {i} 项不是对象")
        material_name = str(item.get("material_name") or "").strip()
        offer_id = str(item.get("offer_id") or "").strip()
        images = item.get("images") or {}
        if not material_name:
            raise ValueError(f"matches.json 第 {i} 项缺少 material_name")
        if not offer_id:
            raise ValueError(f"matches.json 第 {i} 项缺少 offer_id")
        if not isinstance(images, dict):
            raise ValueError(f"matches.json 第 {i} 项 images 必须是对象")
        matched_category_path = item.get("matched_category_path") or []
        rows.append(MatchIn(
            material_name=material_name,
            material_category_code=(str(item.get("material_category_code")).strip() if item.get("material_category_code") else None),
            material_category_name=(str(item.get("material_category_name")).strip() if item.get("material_category_name") else None),
            spu_code=(str(item.get("spu_code")).strip() if item.get("spu_code") else None),
            offer_id=offer_id,
            offer_url=(str(item.get("offer_url")).strip() if item.get("offer_url") else None),
            listing_title=(str(item.get("listing_title")).strip() if item.get("listing_title") else None),
            matched_category_path=[str(x) for x in matched_category_path],
            images=_images_from_matches(images),
            base_dir=source_dir,
        ))
    return rows


def load_offer_tree(source_dir: Path) -> list[MatchIn]:
    rows: list[MatchIn] = []
    for offer_json in sorted(source_dir.glob("categories/**/offers/*/offer.json")):
        data = json.loads(offer_json.read_text(encoding="utf-8"))
        source = data.get("source") or {}
        offer_id = str(source.get("offer_id") or offer_json.parent.name)
        category_path = [
            str(x.get("name_zh") or x.get("name_en") or "")
            for x in (data.get("source_category_path") or [])
            if x.get("name_zh") or x.get("name_en")
        ]

        images: list[ImageIn] = []
        for i, item in enumerate(data.get("gallery") or []):
            kind = ImageType.MAIN if i == 0 else ImageType.GALLERY
            images.append(_normalize_image_item(kind, item))
        for item in data.get("description_images") or []:
            images.append(_normalize_image_item(ImageType.DETAIL, item))

        rows.append(MatchIn(
            material_name=str(data.get("product_name_zh") or "").strip(),
            material_category_code=None,
            material_category_name=None,
            spu_code=None,
            offer_id=offer_id,
            offer_url=(str(source.get("offer_url")).strip() if source.get("offer_url") else None),
            listing_title=(str(data.get("listing_title_zh")).strip() if data.get("listing_title_zh") else None),
            matched_category_path=category_path,
            images=images,
            base_dir=offer_json.parent,
        ))
    return rows


def load_input_rows(source_dir: Path) -> list[MatchIn]:
    rows = load_matches_json(source_dir)
    if rows:
        return rows
    return load_offer_tree(source_dir)


def load_material_index() -> dict[str, list[dict]]:
    master = json.loads(MASTER_FINAL.read_text(encoding="utf-8"))
    index: dict[str, list[dict]] = collections.defaultdict(list)
    for item in master:
        cat_name = item["大类"]
        cat_code = _CAT_NAME_TO_CODE.get(cat_name)
        if not cat_code:
            continue
        name = item["zh"]
        index[_hard(name)].append({
            "cat_code": cat_code,
            "cat_name": cat_name,
            "name": name,
            "spu_code": zsoe_spu_code(cat_code, name),
        })
    return index


def _run_crawled_at(source_dir: Path) -> str:
    path = source_dir / "run.json"
    if not path.exists():
        return ""
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("crawled_at") or "")
    except Exception:  # noqa: BLE001
        return ""


async def _zone_product_codes(db: AsyncSession, zone_code: str) -> set[str]:
    rows = (await db.execute(
        select(Product.spu_code)
        .join(ZoneProduct, ZoneProduct.spu_id == Product.id)
        .join(Zone, Zone.id == ZoneProduct.zone_id)
        .where(
            Zone.code == zone_code,
            Product.deleted_at.is_(None),
        )
    )).scalars().all()
    return set(rows)


async def _zone_products_named(db: AsyncSession, zone_code: str) -> dict[str, str]:
    rows = (await db.execute(
        select(Product.spu_code, Product.name_zh)
        .join(ZoneProduct, ZoneProduct.spu_id == Product.id)
        .join(Zone, Zone.id == ZoneProduct.zone_id)
        .where(Zone.code == zone_code, Product.deleted_at.is_(None))
    )).all()
    return {code: (name or "") for code, name in rows}


def resolve_spu_code(row: MatchIn, material_index: dict[str, list[dict]]) -> tuple[str | None, str | None]:
    if row.spu_code:
        return row.spu_code, None

    if row.material_category_code:
        return zsoe_spu_code(row.material_category_code, row.material_name), None

    candidates = material_index.get(_hard(row.material_name), [])
    if len(candidates) == 1:
        return candidates[0]["spu_code"], None
    if len(candidates) > 1:
        detail = ", ".join(f"{c['cat_code']}/{c['cat_name']}/{c['name']}" for c in candidates)
        return None, f"材料名重名,需提供 material_category_code 或 spu_code:{row.material_name} -> {detail}"
    return None, f"材料名不在央企材料表:{row.material_name}"


# ----------------------------- 分类解析/建叶 -----------------------------

class CategoryState:
    """主 categories 树的内存态,供按名解析 + 在已有父下自动建叶。"""

    def __init__(self, categories: list[Category]) -> None:
        self.by_parent_name: dict[tuple[str, str], Category] = {}
        self.children: dict[str, list[Category]] = collections.defaultdict(list)
        for c in categories:
            self.by_parent_name[(c.parent_code or "", _hard(c.name_zh))] = c
            self.children[c.parent_code or ""].append(c)


async def load_category_state(db: AsyncSession) -> CategoryState:
    cats = (await db.execute(
        select(Category).where(Category.is_active.is_(True))
    )).scalars().all()
    return CategoryState(cats)


def _next_child_code(parent_code: str, child_codes: list[str]) -> str:
    prefix = f"{parent_code}."
    max_seg = 0
    for code in child_codes:
        if not code.startswith(prefix):
            continue
        rest = code[len(prefix):]
        if "." in rest or not rest.isdigit():
            continue
        max_seg = max(max_seg, int(rest))
    next_seg = max_seg + 1
    if next_seg > 999:
        raise RuntimeError(f"parent {parent_code} 子 code 已超过 999,无法自动建叶")
    code = f"{prefix}{next_seg:03d}"
    if len(code) > 16:
        raise RuntimeError(f"生成 code 超长({len(code)}): {code}")
    return code


def _resolve_path(path: list[str], ts: CategoryState) -> tuple[Category | None, int]:
    """按名从 L1 逐级下钻,返回(最后命中的节点, 命中深度)。"""
    parent = ""
    last: Category | None = None
    depth = 0
    for name in path:
        hit = ts.by_parent_name.get((parent, _hard(name)))
        if hit is None:
            break
        last = hit
        depth += 1
        parent = hit.code
    return last, depth


def _create_leaf(db: AsyncSession, parent: Category, name_zh: str, ts: CategoryState) -> Category:
    siblings = ts.children[parent.code]
    child = Category(
        code=_next_child_code(parent.code, [c.code for c in siblings]),
        name_zh=name_zh,
        name_en=None,
        level=parent.level + 1,
        parent_code=parent.code,
        sort_order=max([c.sort_order for c in siblings] or [0]) + 1,
        is_active=True,
        is_leaf=True,
        source_lang="zh",
        trans_meta={"name_zh": "src", "name_en": "pending"},
    )
    db.add(child)
    if parent.is_leaf:
        parent.is_leaf = False
    ts.children[parent.code].append(child)
    ts.by_parent_name[(parent.code, _hard(name_zh))] = child
    return child


async def apply_category(
    db: AsyncSession, product: Product, path: list[str], ts: CategoryState, dry_run: bool, stats: collections.Counter
) -> tuple[str | None, list[str], str]:
    """把 XFS 路径解析/建叶后回写 product.category_code。

    返回 (new_code, created_leaf_codes, cat_status)。cat_status:
      no_path / no_L1 / resolved_nonleaf / create_leaf / changed / unchanged
    """
    if not path:
        return None, [], "no_path"
    last, depth = _resolve_path(path, ts)
    if depth == 0:
        stats["cat_no_L1"] += 1
        return None, [], "no_L1"

    created: list[str] = []
    if depth < len(path):
        # 差几级:只在已有父下建叶(绝不建 L1,depth>=1 保证父存在)
        if dry_run:
            stats["cat_would_create_leaf"] += 1
            target_code = "(would-create-leaf)"
            new_code = target_code
            if product.category_code != new_code:
                stats["cat_changed"] += 1
            return new_code, [f"<{n}>" for n in path[depth:]], "create_leaf"
        node = last
        for name in path[depth:]:
            node = _create_leaf(db, node, name, ts)
            created.append(node.code)
            stats["cat_leaf_created"] += 1
        target = node
    else:
        target = last
        if not target.is_leaf:
            # XFS 路径比主树浅,落在非叶子上 → 不挂(避免商品挂到中间节点)
            stats["cat_resolved_nonleaf"] += 1
            return None, [], "resolved_nonleaf"

    if product.category_code == target.code:
        stats["cat_unchanged"] += 1
        return target.code, created, "unchanged"
    stats["cat_changed"] += 1
    if not dry_run:
        product.category_code = target.code
    return target.code, created, "changed"


# ----------------------------- 图片 -----------------------------

def _src_path(row: MatchIn, image: ImageIn) -> Path:
    rel = Path(image.rel_path)
    if rel.is_absolute():
        return rel
    return row.base_dir / rel


def _dest_name(row: MatchIn, image: ImageIn) -> str:
    return f"{_safe_offer_id(row.offer_id)}_{Path(image.rel_path).name}"


def _image_key(spu_code: str, filename: str) -> str:
    return f"products/{spu_code}/{filename}"


def _image_min_side(path: Path) -> int:
    try:
        with Image.open(path) as im:
            w, h = im.size
        return min(int(w), int(h))
    except Exception:  # noqa: BLE001
        return 0


def _rank_images(row: MatchIn, images: list[ImageIn]) -> tuple[list[ImageIn], int]:
    """主图(MAIN/GALLERY)按 min(宽,高) 降序,最清当封面;detail 保持原序。

    返回 (排好序的图列表, 最佳主图 min-side)。
    """
    gallery = [im for im in images if im.kind in (ImageType.MAIN, ImageType.GALLERY)]
    detail = [im for im in images if im.kind == ImageType.DETAIL]
    scored = sorted(
        ((_image_min_side(_src_path(row, im)), im) for im in gallery),
        key=lambda x: -x[0],
    )
    best = scored[0][0] if scored else 0
    ranked: list[ImageIn] = []
    for i, (_ms, im) in enumerate(scored):
        kind = ImageType.MAIN if i == 0 else ImageType.GALLERY
        ranked.append(dataclasses.replace(im, kind=kind))
    ranked.extend(detail)
    return ranked, best


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
    thumb_path = original_path.with_name(original_path.stem + "_thumb.webp")
    if _thumb_is_fresh(original_path, thumb_path):
        return True
    tmp_name = None
    try:
        with Image.open(original_path) as opened:
            img = opened.convert("RGB")
            width, height = img.size
        if width <= 0 or height <= 0:
            return False
        img.thumbnail(THUMB_SIZE, Image.LANCZOS)
        with tempfile.NamedTemporaryFile(
            dir=thumb_path.parent, prefix=f".{thumb_path.name}.", suffix=".tmp", delete=False
        ) as tmp:
            tmp_name = tmp.name
        img.save(tmp_name, format="WEBP", quality=THUMB_WEBP_QUALITY)
        Path(tmp_name).replace(thumb_path)
        return True
    except Exception as e:  # noqa: BLE001
        if tmp_name:
            Path(tmp_name).unlink(missing_ok=True)
        print(f"  [WARN] 缩略图生成失败 {original_path}: {e}", file=sys.stderr)
        return False


# ----------------------------- 台账 -----------------------------

def _load_ledger() -> dict[str, dict]:
    if not LEDGER_PATH.exists():
        return {}
    with LEDGER_PATH.open(encoding="utf-8", newline="") as f:
        return {r["spu_code"]: r for r in csv.DictReader(f) if r.get("spu_code")}


def _upsert_ledger(new_rows: list[dict]) -> None:
    ledger = _load_ledger()
    for r in new_rows:
        ledger[r["spu_code"]] = r
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
        w.writeheader()
        for spu in sorted(ledger):
            w.writerow({k: ledger[spu].get(k, "") for k in LEDGER_FIELDS})


# ----------------------------- 主流程 -----------------------------

async def run_import(
    db: AsyncSession, source_dir: Path, zone_code: str, dry_run: bool, min_cover_side: int
) -> dict:
    stats: collections.Counter = collections.Counter()
    rows = load_input_rows(source_dir)
    stats["input_rows"] = len(rows)
    material_index = load_material_index()
    zone_codes = await _zone_product_codes(db, zone_code)
    stats["zone_products"] = len(zone_codes)
    ts = await load_category_state(db)
    run_crawled_at = _run_crawled_at(source_dir)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    unresolved: list[str] = []
    missing_files: list[str] = []
    low_res: list[str] = []
    row_plans: list[tuple[MatchIn, str, list[ImageIn]]] = []

    for row in rows:
        if not row.material_name:
            unresolved.append(f"{row.offer_id}: 缺少 material_name/product_name_zh")
            stats["rows_unresolved"] += 1
            continue
        spu_code, reason = resolve_spu_code(row, material_index)
        if reason:
            unresolved.append(f"{row.offer_id}: {reason}")
            stats["rows_unresolved"] += 1
            continue
        assert spu_code is not None
        if spu_code not in zone_codes:
            unresolved.append(f"{row.offer_id}: spu_code 不属于专区 {zone_code}: {spu_code}")
            stats["rows_unresolved"] += 1
            continue
        valid_images = []
        for image in row.images:
            path = _src_path(row, image)
            if not path.exists():
                missing_files.append(f"{row.offer_id}/{row.material_name}: {image.rel_path}")
                continue
            valid_images.append(image)
        if not valid_images:
            stats["rows_no_valid_image"] += 1
            continue
        row_plans.append((row, spu_code, valid_images))
        stats["rows_planned"] += 1

    products_by_spu = {
        p.spu_code: p
        for p in (await db.execute(
            select(Product).where(
                Product.spu_code.in_([spu for _, spu, _ in row_plans] or ["__none__"]),
                Product.deleted_at.is_(None),
            )
        )).scalars().all()
    }

    ledger_rows: list[dict] = []
    processed: set[str] = set()
    for row, spu_code, images in row_plans:
        product = products_by_spu.get(spu_code)
        if product is None:
            unresolved.append(f"{row.offer_id}: product 不存在:{spu_code}")
            stats["rows_unresolved"] += 1
            continue
        if spu_code in processed:
            unresolved.append(f"{row.offer_id}: 同一 SPU 在输入中重复,已跳过:{spu_code}")
            stats["rows_duplicate_spu_skipped"] += 1
            continue
        processed.add(spu_code)

        ranked, best_main = _rank_images(row, images)

        # 低清 hold:最佳主图 < 门槛 → 整条不替换,记台账待复核
        if best_main < min_cover_side:
            low_res.append(f"{spu_code} {row.material_name} best={best_main}px offer={row.offer_id}")
            stats["rows_low_res_held"] += 1
            ledger_rows.append({
                "spu_code": spu_code, "material_name": row.material_name, "offer_id": row.offer_id,
                "run_crawled_at": run_crawled_at, "updated_at": now,
                "n_main": 0, "n_gallery": 0, "n_detail": 0, "best_main_min_side": best_main,
                "old_category_code": product.category_code, "new_category_code": product.category_code,
                "created_leaf_codes": "", "cat_status": "held", "status": "low_res_no_cover",
            })
            continue

        old_code = product.category_code
        new_code, created, cat_status = await apply_category(db, product, row.matched_category_path, ts, dry_run, stats)

        if not dry_run:
            await db.execute(
                delete(ProductImage).where(
                    ProductImage.product_id == product.id,
                    ProductImage.sku_id.is_(None),
                )
            )
            dest_dir = UPLOADS_ROOT / "products" / product.spu_code
            dest_dir.mkdir(parents=True, exist_ok=True)

        n = collections.Counter()
        sort_order = 0
        for image in ranked:
            src = _src_path(row, image)
            filename = _dest_name(row, image)
            if not dry_run:
                dest = UPLOADS_ROOT / "products" / product.spu_code / filename
                shutil.copy2(src, dest)
                db.add(ProductImage(
                    product_id=product.id,
                    sku_id=None,
                    image_key=_image_key(product.spu_code, filename),
                    image_type=image.kind,
                    sort_order=sort_order,
                    source_url=image.source_url,
                ))
                if image.kind == ImageType.MAIN:
                    if make_thumbnail(dest):
                        stats["thumbs_generated"] += 1
                    else:
                        stats["thumbs_failed"] += 1
            n[image.kind] += 1
            stats[f"images_{image.kind.lower()}"] += 1
            stats["images_total"] += 1
            sort_order += 1

        if cat_status == "no_L1":
            stats["rows_category_unresolved"] += 1
        ledger_rows.append({
            "spu_code": spu_code, "material_name": row.material_name, "offer_id": row.offer_id,
            "run_crawled_at": run_crawled_at, "updated_at": now,
            "n_main": n[ImageType.MAIN], "n_gallery": n[ImageType.GALLERY], "n_detail": n[ImageType.DETAIL],
            "best_main_min_side": best_main,
            "old_category_code": old_code or "", "new_category_code": (new_code if new_code and cat_status in ("changed", "create_leaf") else (old_code or "")),
            "created_leaf_codes": ";".join(created), "cat_status": cat_status, "status": "updated",
        })
        stats["products_updated"] += 1

    if not dry_run:
        await db.flush()
        _upsert_ledger(ledger_rows)

    return {
        "stats": dict(stats),
        "unresolved": unresolved,
        "missing_files": missing_files,
        "low_res": low_res,
        "ledger_rows": ledger_rows,
    }


async def run_report(db: AsyncSession, zone_code: str) -> dict:
    zone_products = await _zone_products_named(db, zone_code)
    ledger = _load_ledger()
    updated, held, pending = [], [], []
    for spu, name in sorted(zone_products.items()):
        row = ledger.get(spu)
        if row is None:
            pending.append((spu, name))
        elif row.get("status") == "updated":
            updated.append((spu, name))
        else:  # low_res_no_cover 等 → 视为待处理
            held.append((spu, name, row.get("status")))
    # 台账里有、但已不在专区的(材料被移除?)
    stray = [s for s in ledger if s not in zone_products]
    return {
        "zone_total": len(zone_products),
        "updated": updated,
        "held": held,
        "pending": pending,
        "stray": stray,
    }


def _print_import(source_dir: Path, zone_code: str, dry_run: bool, min_cover_side: int, result: dict) -> None:
    s = result["stats"]
    print("=" * 72)
    print(f"央企专区图片+分类更新 {'[DRY-RUN 未落库/未拷图/未写台账]' if dry_run else '[已落库 COMMIT]'}")
    print("=" * 72)
    print(f"source_dir:               {source_dir}")
    print(f"zone_code:                {zone_code}")
    print(f"低清门槛(min-side):       {min_cover_side}")
    print(f"输入行:                   {s.get('input_rows', 0)}")
    print(f"专区商品数:               {s.get('zone_products', 0)}")
    print(f"计划更新行:               {s.get('rows_planned', 0)}")
    print(f"未解析行:                 {s.get('rows_unresolved', 0)}")
    print(f"无有效图片行:             {s.get('rows_no_valid_image', 0)}")
    print(f"低清 hold(不替换):        {s.get('rows_low_res_held', 0)}")
    print(f"重复 SPU 跳过:            {s.get('rows_duplicate_spu_skipped', 0)}")
    print(f"商品更新:                 {s.get('products_updated', 0)}")
    print(f"图片:                     MAIN {s.get('images_main', 0)} / GALLERY {s.get('images_gallery', 0)} / DETAIL {s.get('images_detail', 0)} = {s.get('images_total', 0)}")
    print(f"缩略图(仅主图):           生成 {s.get('thumbs_generated', 0)} / 失败 {s.get('thumbs_failed', 0)}")
    print("-" * 72)
    print("分类(以 XFS 为准):")
    print(f"  改动:                   {s.get('cat_changed', 0)}(其中新建叶子 {s.get('cat_leaf_created', 0)} 个)")
    print(f"  未变:                   {s.get('cat_unchanged', 0)}")
    print(f"  L1 缺失·不动分类:       {s.get('cat_no_L1', 0)}(待人工决定是否扩目录)")
    print(f"  落非叶子·跳过:          {s.get('cat_resolved_nonleaf', 0)}")
    if dry_run and s.get('cat_would_create_leaf'):
        print(f"  待建叶子(dry-run):      {s.get('cat_would_create_leaf', 0)} 行")
    if result["missing_files"]:
        print(f"缺失源文件:               {len(result['missing_files'])} 张(样例 {result['missing_files'][:3]})")
    if result["low_res"]:
        print(f"\n低清待复核({len(result['low_res'])}):")
        for item in result["low_res"][:20]:
            print(f"  - {item}")
    if result["unresolved"]:
        print(f"\n未解析({len(result['unresolved'])}):")
        for item in result["unresolved"][:20]:
            print(f"  - {item}")
    if dry_run:
        print("\n这是干跑,数据库/文件系统/台账未改动。确认无误后用 --commit 落库。")
    else:
        print(f"\n台账已更新:               {LEDGER_PATH}")


def _print_report(zone_code: str, rep: dict) -> None:
    print("=" * 72)
    print(f"央企专区图片+分类更新台账报告  zone={zone_code}")
    print("=" * 72)
    print(f"专区材料总数:             {rep['zone_total']}")
    print(f"已更新(本版):             {len(rep['updated'])}")
    print(f"低清待复核:               {len(rep['held'])}")
    print(f"待更新(未做):             {len(rep['pending'])}")
    if rep["held"]:
        print(f"\n低清待复核({len(rep['held'])},样例):")
        for spu, name, st in rep["held"][:15]:
            print(f"  - {spu}  {name}  [{st}]")
    if rep["pending"]:
        print(f"\n待更新({len(rep['pending'])},样例):")
        for spu, name in rep["pending"][:15]:
            print(f"  - {spu}  {name}")
    if rep["stray"]:
        print(f"\n⚠️ 台账有但已不在专区({len(rep['stray'])}):{rep['stray'][:5]}")
    print(f"\n台账文件:                 {LEDGER_PATH}")


async def _execute(mode: str, source_dir: Path | None, zone_code: str, min_cover_side: int) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings

    dry_run = mode == "dry-run"
    if (
        mode == "commit"
        and "162.19.98.142" in (settings.DATABASE_URL or "")
        and os.environ.get("ALLOW_ZONE_SOE_IMAGES_PROD") != "1"
    ):
        raise SystemExit(
            "拒绝执行:DATABASE_URL 指向 OVH 生产库。生产落库前请先 dry-run 确认, "
            "并把图片源目录拷到生产机、用 --source-dir 指定,再设 ALLOW_ZONE_SOE_IMAGES_PROD=1 执行 --commit。"
        )

    if mode != "report":
        assert source_dir is not None
        if not source_dir.exists():
            raise SystemExit(f"图片源目录不存在:{source_dir}")

    engine = create_async_engine(settings.DATABASE_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        if mode == "report":
            rep = await run_report(db, zone_code)
            _print_report(zone_code, rep)
        else:
            assert source_dir is not None
            result = await run_import(db, source_dir, zone_code, dry_run, min_cover_side)
            if dry_run:
                await db.rollback()
            else:
                await db.commit()
            _print_import(source_dir, zone_code, dry_run, min_cover_side, result)
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, help="九云图片 run 目录(--report 时可省)")
    parser.add_argument("--zone-code", default=ZONE_CODE)
    parser.add_argument("--min-cover-side", type=int, default=MIN_COVER_SIDE, help="最佳主图 min(宽,高) 低于此判低清并 hold")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--commit", action="store_true")
    group.add_argument("--report", action="store_true", help="只读:打印已更新/待更新台账报告")
    args = parser.parse_args()

    mode = "report" if args.report else ("commit" if args.commit else "dry-run")
    if mode != "report" and args.source_dir is None:
        parser.error("--dry-run/--commit 需要 --source-dir")
    asyncio.run(_execute(mode, args.source_dir, args.zone_code, args.min_cover_side))


if __name__ == "__main__":
    main()
