"""阿里抓数 → 商品入库 CLI 脚本。

用法
----
    # 导入一个 raw 批次目录
    python scripts/import_products.py --batch ../data/alibaba_2026-06-10

    # 只跑校验 + 打印差异,不写库
    python scripts/import_products.py --batch ../data/alibaba_2026-06-10 --dry-run

设计要点
--------
- 幂等:按 spu_code upsert,子行先清后插,重跑安全
- 事务边界 = 单个 offer:一个商品失败不连累其他
- 归类靠 categories_raw.json 数据树,不靠目录路径
- 参照 import_categories.py 的 CLI 模式(--dry-run / fail-fast / 永不物理删)

⚠️ 本脚本**不在应用启动时自动跑**,只能本地人工执行。
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

# 让脚本能 import app.*
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))

from app.audit.constants import AuditAction, AuditResourceType  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.db.base import _utcnow  # noqa: E402
from app.db.models import (  # noqa: E402
    Category,
    IngestRun,
    IngestRunStatus,
    Product,
    ProductAttr,
    ProductImage,
    ProductStatus,
)
from app.db.models.audit_log import AuditLog, AuditStatus  # noqa: E402
from app.db.models.product_image import ImageType  # noqa: E402
from app.db.url import prepare_sync_url  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("import_products")

# ────────────────────── 数据结构 ──────────────────────


@dataclass
class RunMeta:
    """run.json 元数据。"""
    source: str
    crawled_at: str | None = None
    operator: str | None = None


@dataclass
class CategoryNode:
    """categories_raw.json 中的一个分类节点。

    约定格式:扁平数组 {level, name_en, name_zh, parent_en}。
    name_en 是节点唯一标识(同层同父下唯一),parent_en 引用父节点 name_en。
    """
    name_en: str
    name_zh: str
    level: int
    parent_name_en: str | None = None
    children: list["CategoryNode"] = field(default_factory=list)
    # 导入后填充的 DB code
    db_code: str | None = None


@dataclass
class OfferFile:
    """一个 offer.json 的定位信息。"""
    offer_id: str
    offer_dir: Path          # 包含 offer.json 的目录
    offer_json_path: Path    # offer.json 完整路径
    data: dict | None = None  # 解析后的 JSON


@dataclass
class ValidationResult:
    """校验结果汇总。"""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    offers: list[OfferFile] = field(default_factory=list)
    # offer_id → 失败原因(硬错误,该 offer 不导入)
    offer_errors: dict[str, list[str]] = field(default_factory=dict)


# ────────────────────── Reader ──────────────────────


def read_run_json(batch_dir: Path) -> RunMeta:
    """读取并校验 run.json。"""
    path = batch_dir / "run.json"
    if not path.exists():
        log.error("run.json 不存在: %s", path)
        sys.exit(1)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("source"):
        log.error("run.json 缺少 source 字段")
        sys.exit(1)
    return RunMeta(
        source=data["source"],
        crawled_at=data.get("crawled_at"),
        operator=data.get("operator"),
    )


def read_categories_raw(batch_dir: Path) -> dict[str, Any]:
    """读取 categories_raw.json,返回原始 dict。"""
    path = batch_dir / "categories_raw.json"
    if not path.exists():
        log.error("categories_raw.json 不存在: %s", path)
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def build_category_tree(raw: list) -> list[CategoryNode]:
    """从 categories_raw.json 构建分类树。

    约定格式(§4.1):扁平数组,每行 {level, name_en, name_zh, parent_en}。
    靠 parent_en(父节点的 name_en)挂父子。L1 的 parent_en 为 null。
    """
    # 先建全部节点
    nodes_by_name: dict[str, CategoryNode] = {}
    all_nodes: list[CategoryNode] = []

    for item in raw:
        name_en = item.get("name_en", "")
        node = CategoryNode(
            name_en=name_en,
            name_zh=item.get("name_zh", ""),
            level=item.get("level", 1),
            parent_name_en=item.get("parent_en"),
        )
        nodes_by_name[name_en] = node
        all_nodes.append(node)

    # 挂父子关系
    roots: list[CategoryNode] = []
    for node in all_nodes:
        if node.parent_name_en and node.parent_name_en in nodes_by_name:
            parent = nodes_by_name[node.parent_name_en]
            parent.children.append(node)
        else:
            roots.append(node)

    return roots


def flatten_tree(nodes: list[CategoryNode]) -> list[CategoryNode]:
    """深度优先展平分类树。"""
    result: list[CategoryNode] = []
    for node in nodes:
        result.append(node)
        result.extend(flatten_tree(node.children))
    return result


def build_leaf_lookup(nodes: list[CategoryNode]) -> dict[str, CategoryNode]:
    """构建叶子节点查找表:name_en → CategoryNode(叶子 = 无子节点)。"""
    lookup: dict[str, CategoryNode] = {}
    for node in flatten_tree(nodes):
        if not node.children:
            lookup[node.name_en] = node
    return lookup


def build_name_lookup(nodes: list[CategoryNode]) -> dict[str, CategoryNode]:
    """构建全节点查找表:name_en → CategoryNode。"""
    return {n.name_en: n for n in flatten_tree(nodes)}


def scan_offers(batch_dir: Path) -> list[OfferFile]:
    """递归扫描 categories/ 下所有 offers/<offer_id>/offer.json。"""
    offers: list[OfferFile] = []
    categories_dir = batch_dir / "categories"
    if not categories_dir.exists():
        log.error("categories/ 目录不存在: %s", categories_dir)
        sys.exit(1)

    for offer_json in sorted(categories_dir.rglob("offers/*/offer.json")):
        offer_dir = offer_json.parent
        offer_id = offer_dir.name
        offers.append(OfferFile(
            offer_id=offer_id,
            offer_dir=offer_dir,
            offer_json_path=offer_json,
        ))
    return offers


# ────────────────────── 校验 ──────────────────────


def _extract_leaf_name(source_category_path: list) -> str | None:
    """从 source_category_path 取叶子的 name_en。

    约定格式:[{name_en, name_zh}, ...]，取最后一个元素的 name_en。
    """
    if not source_category_path:
        return None
    last = source_category_path[-1]
    if isinstance(last, dict):
        return last.get("name_en")
    # 兼容纯字符串格式
    return str(last)


def _strip_level_prefix(dir_name: str) -> str:
    """剥掉 L<n>- 前缀,返回纯 slug 部分(去掉 __中文 后缀)。"""
    # L1-electrical-equipment__电气设备 → electrical-equipment
    import re
    name = re.sub(r"^L\d+-", "", dir_name)
    # 去掉 __中文名
    name = name.split("__")[0]
    return name


def _name_to_slug(name: str) -> str:
    """将分类 name_en 转为 slug 格式,用于与目录名比较。"""
    import re
    s = name.lower().strip()
    s = re.sub(r"[&]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


def validate_batch(
    batch_dir: Path,
    run_meta: RunMeta,
    cat_tree: list[CategoryNode],
    offers: list[OfferFile],
) -> ValidationResult:
    """执行全部交付前校验。失败的整批拒绝(errors 非空)或单 offer 失败(offer_errors)。"""
    result = ValidationResult(offers=offers)
    leaf_lookup = build_leaf_lookup(cat_tree)
    name_lookup = build_name_lookup(cat_tree)

    if not offers:
        result.errors.append("未找到任何 offer.json")
        return result

    for offer in offers:
        offer_errs: list[str] = []
        # 解析 JSON
        try:
            offer.data = json.loads(offer.offer_json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            offer_errs.append(f"offer.json 解析失败: {e}")
            result.offer_errors[offer.offer_id] = offer_errs
            continue

        data = offer.data
        # offer_id 与目录名一致性(约定:offer_id 在 source.offer_id)
        source_obj = data.get("source", {})
        json_offer_id = str(source_obj.get("offer_id", "")) if isinstance(source_obj, dict) else ""
        if json_offer_id and json_offer_id != offer.offer_id:
            offer_errs.append(
                f"offer_id 不一致: 目录名={offer.offer_id}, JSON source.offer_id={json_offer_id}"
            )

        # attributes 校验
        attributes = data.get("attributes", [])
        if not attributes:
            offer_errs.append("attributes 为空")
        for i, attr in enumerate(attributes):
            if not attr.get("group"):
                offer_errs.append(f"attributes[{i}] 缺少 group")
            if not attr.get("key_en"):
                offer_errs.append(f"attributes[{i}] 缺少 key_en")
            if not attr.get("values"):
                offer_errs.append(f"attributes[{i}] 缺少 values")

        # 图片文件存在性
        for img in data.get("gallery", []):
            img_path = img.get("path", "")
            if img_path and not (offer.offer_dir / img_path).exists():
                offer_errs.append(f"gallery 图片不存在: {img_path}")

        for img in data.get("description_images", []):
            img_path = img.get("path", "")
            if img_path and not (offer.offer_dir / img_path).exists():
                offer_errs.append(f"description_images 图片不存在: {img_path}")

        # 归类校验(硬):source_category_path 叶子的 name_en 匹配 categories_raw.json
        src_path = data.get("source_category_path", [])
        leaf_name = _extract_leaf_name(src_path)
        if not leaf_name:
            offer_errs.append("source_category_path 为空")
        elif leaf_name not in leaf_lookup:
            if leaf_name in name_lookup:
                # 在分类树中但不是叶子
                result.warnings.append(
                    f"[{offer.offer_id}] source_category_path 叶子 '{leaf_name}' "
                    f"在分类树中但不是叶子节点"
                )
            else:
                offer_errs.append(
                    f"source_category_path 叶子 '{leaf_name}' "
                    f"在 categories_raw.json 中未找到"
                )

        if offer_errs:
            result.offer_errors[offer.offer_id] = offer_errs

    # 目录交叉校验(报警)
    _cross_validate_directories(batch_dir, cat_tree, offers, result)

    return result


def _cross_validate_directories(
    batch_dir: Path,
    cat_tree: list[CategoryNode],
    offers: list[OfferFile],
    result: ValidationResult,
) -> None:
    """目录交叉校验:检测非叶子目录有 offers/,目录 slug 与 source_category_path 不一致。"""
    categories_dir = batch_dir / "categories"
    if not categories_dir.exists():
        return

    # 找出所有包含 offers/ 子目录的分类目录
    for offers_dir in categories_dir.rglob("offers"):
        if not offers_dir.is_dir():
            continue
        parent_cat_dir = offers_dir.parent
        # 检查该分类目录是否还有子分类目录(非 offers)
        subdirs = [
            d for d in parent_cat_dir.iterdir()
            if d.is_dir() and d.name != "offers"
        ]
        if subdirs:
            result.warnings.append(
                f"目录 {parent_cat_dir.relative_to(batch_dir)} "
                f"同时有子分类文件夹和 offers/(商品可能挂到了非叶子)"
            )

    # 每个 offer 的目录 slug vs source_category_path 叶子 name_en
    for offer in offers:
        if not offer.data:
            continue
        src_path = offer.data.get("source_category_path", [])
        leaf_name = _extract_leaf_name(src_path)
        if not leaf_name:
            continue

        # 从 offer 目录往上找分类目录名
        # 结构: categories/.../L<n>-<slug>__<中文>/offers/<offer_id>/
        cat_dir = offer.offer_dir.parent.parent  # offers/ 的父目录
        dir_slug = _strip_level_prefix(cat_dir.name)
        # 将 leaf_name 也转 slug 格式(小写、空格换连字符)来比较
        leaf_slug = _name_to_slug(leaf_name)
        if dir_slug and leaf_slug and dir_slug != leaf_slug:
            result.warnings.append(
                f"[{offer.offer_id}] 目录叶子 slug '{dir_slug}' "
                f"与 source_category_path 叶子 slug '{leaf_slug}' 不一致"
            )


# ────────────────────── run 生命周期 ──────────────────────


def open_run(db: Session, *, run_key: str, source: str,
             operator: str | None, raw_path: str,
             crawled_at: datetime | None) -> IngestRun:
    """创建 RUNNING 状态的 ingest_run 行。幂等:同 run_key 复用。"""
    existing = db.execute(
        select(IngestRun).where(IngestRun.run_key == run_key)
    ).scalar_one_or_none()
    if existing:
        # 复用:重置状态
        existing.status = IngestRunStatus.RUNNING
        existing.product_count = 0
        existing.error_summary = None
        existing.imported_at = None
        existing.updated_at = _utcnow()
        db.flush()
        return existing

    run = IngestRun(
        run_key=run_key,
        source=source,
        operator=operator,
        raw_path=raw_path,
        crawled_at=crawled_at,
        status=IngestRunStatus.RUNNING,
    )
    db.add(run)
    db.flush()
    return run


def close_run(
    db: Session,
    run: IngestRun,
    *,
    status: str,
    product_count: int,
    error_summary: list[dict] | None = None,
) -> None:
    """关闭 run:更新终态 + imported_at。"""
    run.status = status
    run.product_count = product_count
    run.imported_at = _utcnow()
    run.error_summary = error_summary
    run.updated_at = _utcnow()
    db.flush()


# ────────────────────── 分类导入(Phase 4 实现) ──────────────────────


def _split_seq(code: str) -> int:
    """从 code 末尾段取整数序号:'01'→1, '01.005'→5。"""
    return int(code.split(".")[-1])


def _next_seq(used: set[int]) -> int:
    seq = 1
    while seq in used:
        seq += 1
    return seq


def _make_code(parent_code: str | None, seq: int, level: int) -> str:
    """生成分类 code:L1 两位,L2+ 三位,父子用点分隔。"""
    if level == 1:
        return f"{seq:02d}"
    assert parent_code is not None
    return f"{parent_code}.{seq:03d}"


def import_categories(db: Session, cat_tree: list[CategoryNode]) -> dict[str, str]:
    """将 categories_raw.json 全层存入 categories 表,返回 name_en → code 映射。

    算法沿用 import_categories.py:按 (name_zh, parent_code) 匹配现有节点,
    沿用 code;新节点取空号生成稳定 code。append-only,永不物理删。
    """
    # 加载所有现有分类
    existing_by_natural: dict[tuple[str, str | None], Category] = {}
    used_seq_by_parent: dict[str | None, set[int]] = {}

    for c in db.execute(select(Category)).scalars().all():
        existing_by_natural[(c.name_zh, c.parent_code)] = c
        used_seq_by_parent.setdefault(c.parent_code, set()).add(_split_seq(c.code))

    slug_to_code: dict[str, str] = {}
    inserted = 0
    updated = 0

    def _upsert_node(node: CategoryNode, parent_code: str | None) -> str:
        nonlocal inserted, updated

        # name_en 也纳入匹配辅助,但 natural key 仍以 name_zh 为主
        natural_key = (node.name_zh, parent_code)
        existing = existing_by_natural.get(natural_key)

        if existing:
            code = existing.code
            # 更新 name_en(抓取可能比 Excel 更完整)
            changed = False
            if node.name_en and existing.name_en != node.name_en:
                existing.name_en = node.name_en
                changed = True
            if existing.level != node.level:
                existing.level = node.level
                changed = True
            if not existing.is_active:
                existing.is_active = True
                changed = True
            if changed:
                existing.updated_at = _utcnow()
                updated += 1
        else:
            # 也尝试用 name_en + parent 匹配(九云数据可能只有英文)
            en_key = (node.name_en, parent_code) if node.name_en else None
            existing_by_en = existing_by_natural.get(en_key) if en_key else None
            if existing_by_en:
                code = existing_by_en.code
                if node.name_zh and existing_by_en.name_zh != node.name_zh:
                    existing_by_en.name_zh = node.name_zh
                if node.name_en and existing_by_en.name_en != node.name_en:
                    existing_by_en.name_en = node.name_en
                existing_by_en.is_active = True
                existing_by_en.updated_at = _utcnow()
                updated += 1
            else:
                # 新建
                used = used_seq_by_parent.setdefault(parent_code, set())
                seq = _next_seq(used)
                used.add(seq)
                code = _make_code(parent_code, seq, node.level)

                now = _utcnow()
                cat = Category(
                    code=code,
                    name_zh=node.name_zh or node.name_en,
                    name_en=node.name_en or None,
                    level=node.level,
                    parent_code=parent_code,
                    sort_order=0,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
                db.add(cat)
                db.flush()  # 让后续子节点的 FK 可引用
                # 注册到 lookup 避免重复
                existing_by_natural[natural_key] = cat
                inserted += 1

        slug_to_code[node.name_en] = code
        node.db_code = code

        # 递归子节点
        for child in node.children:
            _upsert_node(child, code)

        return code

    for root in cat_tree:
        _upsert_node(root, None)

    log.info("  分类导入: 新增=%d, 更新=%d, 总映射=%d", inserted, updated, len(slug_to_code))
    return slug_to_code


# ────────────────────── 商品导入(Phase 5 实现) ──────────────────────


def import_offer(
    db: Session,
    offer: OfferFile,
    *,
    slug_to_code: dict[str, str],
    leaf_lookup: dict[str, CategoryNode],
    run: IngestRun,
    run_meta: RunMeta,
    static_root: Path,
) -> None:
    """导入单个 offer:幂等 upsert + 子行先清后插 + 图片拷贝 + 审计。

    事务边界:调用方负责 commit/rollback(一个 offer = 一个事务)。
    """
    data = offer.data
    assert data is not None

    offer_id = offer.offer_id
    spu_code = f"P-{offer_id}"

    # ── 1. 归类:source_category_path 叶子 name_en → DB code ──
    src_path = data.get("source_category_path", [])
    leaf_name = _extract_leaf_name(src_path)
    category_code = slug_to_code.get(leaf_name or "")
    if not category_code:
        raise ValueError(f"分类 '{leaf_name}' 无法映射到 DB code")

    # ── 2. SPU 字段映射 ──
    name_en = data.get("product_name_en") or data.get("listing_title_en", "")
    name_zh = data.get("product_name_zh") or data.get("listing_title_zh", "")
    desc_en = data.get("description_en") or ""
    desc_zh = data.get("description_zh") or ""

    # selling_points:从 attributes 里找 Feature/特性 那条
    sp_en, sp_zh = _extract_selling_points(data.get("attributes", []))

    # ── 3. 幂等 upsert by spu_code ──
    existing = db.execute(
        select(Product).where(Product.spu_code == spu_code)
    ).scalar_one_or_none()

    if existing:
        product = existing
        product.name_en = name_en or product.name_en
        product.name_zh = name_zh or product.name_zh
        product.description_en = desc_en or product.description_en
        product.description_zh = desc_zh or product.description_zh
        product.selling_points_en = sp_en or product.selling_points_en
        product.selling_points_zh = sp_zh or product.selling_points_zh
        product.category_code = category_code
        product.source = run_meta.source
        product.last_ingest_run_id = run.id
        product.updated_at = _utcnow()
        audit_action = AuditAction.UPDATE
    else:
        product = Product(
            spu_code=spu_code,
            category_code=category_code,
            name_en=name_en,
            name_zh=name_zh or name_en,  # name_zh NOT NULL,回退英文
            description_en=desc_en or None,
            description_zh=desc_zh or None,
            selling_points_en=sp_en or None,
            selling_points_zh=sp_zh or None,
            source=run_meta.source,
            last_ingest_run_id=run.id,
            status=ProductStatus.DRAFT,
        )
        db.add(product)
        audit_action = AuditAction.IMPORT

    db.flush()  # 拿到 product.id

    # ── 4. 子行先清后插(同事务,防重导翻倍) ──
    db.execute(
        delete(ProductAttr).where(
            ProductAttr.product_id == product.id,
            ProductAttr.sku_id.is_(None),
        )
    )
    db.execute(
        delete(ProductImage).where(
            ProductImage.product_id == product.id,
            ProductImage.sku_id.is_(None),
        )
    )

    # ── 5. product_attrs:values 有几个插几行 ──
    attr_sort = 0
    for attr_def in data.get("attributes", []):
        group = attr_def.get("group", "")
        key_en = attr_def.get("key_en", "")
        key_zh = attr_def.get("key_zh", "")

        for val in attr_def.get("values", []):
            label_en = val.get("label_en", "")
            label_zh = val.get("label_zh", "")
            swatch_raw = val.get("swatch_image")
            # swatch_image 约定为对象 {path, source_url} 或纯字符串 path
            swatch_path: str | None = None
            if isinstance(swatch_raw, dict):
                swatch_path = swatch_raw.get("path")
            elif isinstance(swatch_raw, str):
                swatch_path = swatch_raw

            # 确定 value_type
            if swatch_path and not label_en:
                value_type = "image"
                attr_value = swatch_path
            else:
                value_type = "text"
                attr_value = label_en

            if not attr_value:
                continue

            db.add(ProductAttr(
                product_id=product.id,
                sku_id=None,
                attr_key=key_en[:50] if key_en else (key_zh[:50] if key_zh else "unknown"),
                attr_value=attr_value[:200],
                attr_key_zh=key_zh[:50] if key_zh else None,
                attr_value_zh=label_zh[:500] if label_zh else None,
                attr_group=group[:100] if group else None,
                value_type=value_type,
                sort_order=attr_sort,
            ))
            attr_sort += 1

            # 色板图:label + swatch_image 同时有 → 额外写一张 spec_value 绑定图
            if swatch_path and label_en and value_type == "text":
                _copy_image(offer.offer_dir / swatch_path, static_root, spu_code)
                db.add(ProductImage(
                    product_id=product.id,
                    sku_id=None,
                    image_key=_image_key(spu_code, swatch_path),
                    image_type=ImageType.GALLERY,
                    sort_order=9000 + attr_sort,  # 色板图排后面
                    spec_value=f"颜色:{label_en}",
                ))

    # ── 6. product_images:gallery + description_images ──
    img_sort = 0
    for img_def in data.get("gallery", []):
        img_path = img_def.get("path", "")
        if not img_path:
            continue
        _copy_image(offer.offer_dir / img_path, static_root, spu_code)
        img_type = ImageType.MAIN if img_sort == 0 else ImageType.GALLERY
        db.add(ProductImage(
            product_id=product.id,
            sku_id=None,
            image_key=_image_key(spu_code, img_path),
            image_type=img_type,
            sort_order=img_sort,
        ))
        img_sort += 1

    for img_def in data.get("description_images", []):
        img_path = img_def.get("path", "")
        if not img_path:
            continue
        _copy_image(offer.offer_dir / img_path, static_root, spu_code)
        db.add(ProductImage(
            product_id=product.id,
            sku_id=None,
            image_key=_image_key(spu_code, img_path),
            image_type=ImageType.DETAIL,
            sort_order=img_sort,
        ))
        img_sort += 1

    db.flush()

    # ── 7. 审计(同事务) ──
    write_audit_sync(
        db,
        resource_type=AuditResourceType.PRODUCT.value,
        action=audit_action.value if isinstance(audit_action, AuditAction) else audit_action,
        resource_id=product.id,
        operator=run_meta.operator,
        extra={
            "spu_code": spu_code,
            "source": run_meta.source,
            "run_id": run.id,
            "offer_id": offer_id,
        },
    )


def _extract_selling_points(attributes: list[dict]) -> tuple[str, str]:
    """从 attributes 里提取 Feature/特性 那条的值拼接。"""
    sp_en_parts: list[str] = []
    sp_zh_parts: list[str] = []
    for attr in attributes:
        key_en = (attr.get("key_en") or "").lower()
        key_zh = attr.get("key_zh") or ""
        if "feature" in key_en or "特性" in key_zh or "特点" in key_zh:
            for val in attr.get("values", []):
                if val.get("label_en"):
                    sp_en_parts.append(val["label_en"])
                if val.get("label_zh"):
                    sp_zh_parts.append(val["label_zh"])
    return "; ".join(sp_en_parts), "; ".join(sp_zh_parts)


def _image_key(spu_code: str, rel_path: str) -> str:
    """生成 image_key:products/<spu_code>/<文件名>。"""
    filename = Path(rel_path).name
    return f"products/{spu_code}/{filename}"


def _copy_image(src: Path, static_root: Path, spu_code: str) -> None:
    """拷贝图片到 static 目录。路径按 spu_code 隔离,重跑覆盖同路径。"""
    if not src.exists():
        return
    dest_dir = static_root / "products" / spu_code
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)


# ────────────────────── 同步审计写入 ──────────────────────


def write_audit_sync(
    db: Session,
    *,
    resource_type: str,
    action: str,
    resource_id: str | int | None = None,
    operator: str | None = None,
    extra: dict | None = None,
    status: str = AuditStatus.SUCCESS,
    error_message: str | None = None,
) -> None:
    """同步版审计写入(CLI 脚本无 HTTP 请求,无 user_id)。"""
    import uuid
    entry = AuditLog(
        trace_id=str(uuid.uuid4()),
        user_id=None,
        user_email=None,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        action=action,
        method="CLI",
        path="scripts/import_products.py",
        ip=None,
        user_agent=None,
        status=status,
        error_message=error_message,
        extra={**(extra or {}), "operator": operator or "system"},
    )
    db.add(entry)
    db.flush()


# ────────────────────── CLI 入口 ──────────────────────


def _parse_crawled_at(raw: str | None) -> datetime | None:
    """将 run.json 的 crawled_at 转 naive UTC datetime。"""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        log.warning("crawled_at 格式无法解析: %s", raw)
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="阿里抓数 → 商品入库")
    parser.add_argument(
        "--batch", type=Path, required=True,
        help="raw 批次目录路径",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只跑校验 + 打印差异,不写库",
    )
    args = parser.parse_args()

    batch_dir = args.batch.resolve()
    if not batch_dir.is_dir():
        log.error("批次目录不存在: %s", batch_dir)
        sys.exit(1)

    # 1. 读取元数据
    log.info("读取 run.json ...")
    run_meta = read_run_json(batch_dir)
    log.info("  source=%s, operator=%s", run_meta.source, run_meta.operator)

    # 2. 读取分类树
    log.info("读取 categories_raw.json ...")
    raw_cats = read_categories_raw(batch_dir)
    cat_tree = build_category_tree(raw_cats)
    all_nodes = flatten_tree(cat_tree)
    leaf_nodes = [n for n in all_nodes if not n.children]
    log.info("  分类节点: %d (叶子: %d)", len(all_nodes), len(leaf_nodes))

    # 3. 扫描 offers
    log.info("扫描 offers ...")
    offers = scan_offers(batch_dir)
    log.info("  找到 %d 个 offer", len(offers))

    # 4. 校验
    log.info("执行校验 ...")
    vr = validate_batch(batch_dir, run_meta, cat_tree, offers)

    # 打印校验结果
    if vr.warnings:
        log.warning("⚠️  告警 (%d):", len(vr.warnings))
        for w in vr.warnings:
            log.warning("  %s", w)

    valid_offers = [o for o in offers if o.offer_id not in vr.offer_errors]
    failed_offers = [o for o in offers if o.offer_id in vr.offer_errors]

    if vr.offer_errors:
        log.error("❌ 失败的 offer (%d):", len(vr.offer_errors))
        for oid, errs in vr.offer_errors.items():
            for e in errs:
                log.error("  [%s] %s", oid, e)

    if vr.errors:
        log.error("❌ 批次级错误,整批拒绝:")
        for e in vr.errors:
            log.error("  %s", e)
        sys.exit(1)

    log.info("✅ 校验通过: %d 可导入, %d 校验失败", len(valid_offers), len(failed_offers))

    if args.dry_run:
        log.info("[DRY RUN] 将导入 %d 个商品(来源: %s),不写库。", len(valid_offers), run_meta.source)
        for o in valid_offers:
            spu_code = f"P-{o.offer_id}"
            src_path = o.data.get("source_category_path", []) if o.data else []
            leaf = _extract_leaf_name(src_path)
            name_en = ""
            if o.data:
                name_en = o.data.get("product_name_en") or o.data.get("listing_title_en", "")
            log.info("  %s → 分类叶子=%s, name=%s", spu_code, leaf, name_en[:60])
        sys.exit(0)

    # ── 写库 ──
    sync_url = prepare_sync_url(settings.DATABASE_URL)
    engine = create_engine(sync_url)

    with Session(engine) as db:
        try:
            # 5. 开 run
            crawled_at = _parse_crawled_at(run_meta.crawled_at)
            run_key = f"{run_meta.source}_{batch_dir.name}"
            run = open_run(
                db,
                run_key=run_key,
                source=run_meta.source,
                operator=run_meta.operator,
                raw_path=str(batch_dir),
                crawled_at=crawled_at,
            )
            db.commit()

            # 6. 导入分类
            log.info("导入分类 ...")
            slug_to_code = import_categories(db, cat_tree)
            db.commit()

            # 7. 导入商品(逐 offer 独立事务)
            leaf_lookup = build_leaf_lookup(cat_tree)
            # 图片存储目录:与 main.py 的 StaticFiles mount 一致
            static_root = _BACKEND_ROOT / "uploads"
            static_root.mkdir(exist_ok=True)

            success_count = 0
            import_errors: list[dict] = []

            for i, offer in enumerate(valid_offers, 1):
                try:
                    import_offer(
                        db, offer,
                        slug_to_code=slug_to_code,
                        leaf_lookup=leaf_lookup,
                        run=run,
                        run_meta=run_meta,
                        static_root=static_root,
                    )
                    db.commit()
                    success_count += 1
                    if i % 50 == 0:
                        log.info("  进度: %d/%d", i, len(valid_offers))
                except Exception as exc:
                    db.rollback()
                    err_msg = str(exc)[:500]
                    log.error("  [%s] 导入失败: %s", offer.offer_id, err_msg)
                    import_errors.append({
                        "offer_id": offer.offer_id,
                        "error": err_msg,
                    })

            # 加上校验阶段失败的
            for oid, errs in vr.offer_errors.items():
                import_errors.append({
                    "offer_id": oid,
                    "error": "; ".join(errs),
                })

            # 8. 关闭 run
            total_failed = len(import_errors)
            if total_failed == 0:
                final_status = IngestRunStatus.SUCCESS
            elif success_count == 0:
                final_status = IngestRunStatus.FAILED
            else:
                final_status = IngestRunStatus.PARTIAL

            close_run(
                db, run,
                status=final_status,
                product_count=success_count,
                error_summary=import_errors or None,
            )
            db.commit()

            log.info(
                "导入完成: status=%s, 成功=%d, 失败=%d",
                final_status, success_count, total_failed,
            )

        except Exception as exc:
            db.rollback()
            log.exception("导入过程异常终止: %s", exc)
            # 尝试标记 run 为 FAILED
            try:
                if "run" in locals():
                    close_run(
                        db, run,
                        status=IngestRunStatus.FAILED,
                        product_count=0,
                        error_summary=[{"error": str(exc)[:1000]}],
                    )
                    db.commit()
            except Exception:
                db.rollback()
            sys.exit(1)


if __name__ == "__main__":
    main()
