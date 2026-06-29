"""鑫方盛抓数 → 商品入库 CLI 脚本。

用法
----
    # 导入一个 raw 批次目录
    python scripts/import_products_xfs.py --batch ../data/xfs_2026-06-20

    # 只跑校验 + 打印差异,不写库
    python scripts/import_products_xfs.py --batch ../data/xfs_2026-06-20 --dry-run

设计要点
--------
- 幂等:按 spu_code(BR-{hash8}) upsert,子行先清后插,重跑安全
- 事务边界 = 单个 offer:一个商品失败不连累其他
- 归类靠 categories_raw.json 数据树,不靠目录路径
- 与 import_products_1688.py(阿里版)同构,适配鑫方盛纯中文数据源

鑫方盛 vs 阿里关键差异:
  - 纯中文数据,无 _en 字段,所有 _en/_sw 标 pending 等翻译管道补译
  - source 用 product_id / product_url(非 offer_id / offer_url)
  - 属性扁平 {key, value, group},无 values[] 嵌套,无 selectable
  - 品牌为顶层 brand 字段,不从属性提取
  - 无阶梯价 / 无描述文本 / 无 selling_points / certifications / origin 提取

⚠️ 本脚本**不在应用启动时自动跑**,只能本地人工执行。
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from dataclasses import dataclass, field
import hashlib
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

from scripts._log_setup import setup_logging  # noqa: E402
setup_logging("import_products_xfs")
log = logging.getLogger("import_products_xfs")

# ────────────────────── 数据结构 ──────────────────────


@dataclass
class RunMeta:
    """run.json 元数据。"""
    source: str
    crawled_at: str | None = None
    operator: str | None = None


# L1 品类 short_name 三语映射(人工校对,不走机器翻译)
# key = short_name_zh, value = (en, sw)
_L1_SHORT_NAME_I18N: dict[str, tuple[str, str]] = {
    "劳保": ("Safety", "Kinga"),
    "手动": ("Hand Tools", "Zana"),
    "紧固": ("Fastener", "Bolta"),
    "安防": ("Security", "Ulinzi"),
    "粘胶": ("Adhesive", "Gundi"),
    "气动": ("Pneumatic", "Hewa"),
    "磨具": ("Abrasive", "Sanifu"),
    "机电": ("Electro", "Umeme"),
    "五金": ("Hardware", "Vifaa"),
    "电器": ("Appliance", "Kifaa"),
    "灯具": ("Lighting", "Taa"),
    "电缆": ("Cable", "Kebo"),
    "电力": ("Conduit", "Njia"),
    "工控": ("Automate", "Kiwanda"),
    "电辅": ("Wiring", "Nyaya"),
    "保温": ("Insulate", "Joto"),
    "防水": ("Waterproof", "Sifongo"),
    "涂料": ("Paint", "Rangi"),
    "装饰": ("Decor", "Mapambo"),
    "门窗": ("Door&Win", "Milango"),
    "土建": ("Civil", "Ujenzi"),
    "临建": ("Temp Build", "Kambi"),
    "装配": ("Precast", "Paneli"),
    "暖通": ("HVAC", "HVAC"),
    "水暖": ("Plumbing", "Paipu"),
    "消防": ("Fire", "Zimamoto"),
    "陶瓷": ("Sanitary", "Vyoo"),
    "管道": ("Piping", "Mirija"),
    "量具": ("Measure", "Kipimo"),
    "金属": ("Metal", "Metali"),
    "配电": ("Switchgear", "Gridi"),
}


@dataclass
class CategoryNode:
    """categories_raw.json 中的一个分类节点。

    鑫方盛约定:扁平数组 {level, name_zh, path_zh, parent_zh, short_name?}。
    path_zh 是品类唯一标识(从根到当前用 / 分隔),防止不同一级下同名子品类歧义。
    short_name 仅一级品类有(导航栏缩写,如"动力"对应"动力工具")。
    """
    name_zh: str
    level: int
    path_zh: str = ""               # 唯一标识:"动力工具/电动工具/电锤工具"
    short_name: str | None = None   # 仅一级品类:导航栏缩写
    parent_name_zh: str | None = None
    children: list["CategoryNode"] = field(default_factory=list)
    # 导入后填充的 DB code
    db_code: str | None = None


@dataclass
class OfferFile:
    """一个 offer.json 的定位信息。"""
    product_id: str
    offer_dir: Path          # 包含 offer.json 的目录
    offer_json_path: Path    # offer.json 完整路径
    data: dict | None = None  # 解析后的 JSON


@dataclass
class ValidationResult:
    """校验结果汇总。"""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    offers: list[OfferFile] = field(default_factory=list)
    # product_id → 失败原因(硬错误,该 offer 不导入)
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

    鑫方盛约定:扁平数组,每行 {level, name_zh, path_zh, parent_zh, short_name?}。
    path_zh 是唯一标识(从根到当前用 / 分隔),优先用 path_zh 推断父子关系。

    父子挂载策略(按优先级):
    1. path_zh 截取:从 path_zh 去掉最后一段得到父 path → 精确匹配,无歧义
    2. parent_zh + nodes_by_name:兼容无 path_zh 的数据(同名会取最后一个)
    3. level 栈式推断:兜底,当 parent_zh 全部缺失时
    """
    nodes_by_path: dict[str, CategoryNode] = {}
    nodes_by_name: dict[str, CategoryNode] = {}
    all_nodes: list[CategoryNode] = []

    for item in raw:
        name_zh = item.get("name_zh", "")
        path_zh = item.get("path_zh", "")
        node = CategoryNode(
            name_zh=name_zh,
            level=item.get("level", 1),
            path_zh=path_zh or name_zh,
            short_name=item.get("short_name"),
            parent_name_zh=item.get("parent_zh"),
        )
        if path_zh:
            nodes_by_path[path_zh] = node
        nodes_by_name[name_zh] = node
        all_nodes.append(node)

    # 自动检测 path_zh 分隔符:优先 ">"(新版),兼容 "/"(旧版)
    _sep = ">"
    if not any(">" in (n.path_zh or "") for n in all_nodes):
        _sep = "/"
    has_path_zh = any(n.path_zh and _sep in n.path_zh for n in all_nodes)
    has_parent_refs = any(n.parent_name_zh for n in all_nodes)

    roots: list[CategoryNode] = []

    if has_path_zh:
        # 优先策略:从 path_zh 截取父路径,精确匹配
        orphans: list[CategoryNode] = []
        for node in all_nodes:
            if _sep not in node.path_zh:
                roots.append(node)
            else:
                parent_path = node.path_zh.rsplit(_sep, 1)[0]
                parent = nodes_by_path.get(parent_path)
                if parent:
                    parent.children.append(node)
                else:
                    orphans.append(node)
        if orphans:
            log.error("以下 %d 个品类节点无法通过 path_zh 找到父节点(可能 name_zh 含 '/'):", len(orphans))
            for o in orphans[:20]:
                log.error("  path_zh=%s  name_zh=%s  parent_zh=%s", o.path_zh, o.name_zh, o.parent_name_zh)
            raise ValueError(
                f"{len(orphans)} 个品类 path_zh 解析失败,请检查数据中 name_zh 是否含 '/' 等歧义字符"
            )
    elif has_parent_refs:
        for node in all_nodes:
            if node.parent_name_zh and node.parent_name_zh in nodes_by_name:
                parent = nodes_by_name[node.parent_name_zh]
                parent.children.append(node)
            else:
                roots.append(node)
    else:
        # 兼容模式:按 level 顺序推断父子(栈式)
        stack: dict[int, CategoryNode] = {}
        for node in all_nodes:
            if node.level == 1:
                roots.append(node)
            else:
                parent = stack.get(node.level - 1)
                if parent:
                    parent.children.append(node)
                    node.parent_name_zh = parent.name_zh
                else:
                    roots.append(node)
            stack[node.level] = node

    return roots


def flatten_tree(nodes: list[CategoryNode]) -> list[CategoryNode]:
    """深度优先展平分类树。"""
    result: list[CategoryNode] = []
    for node in nodes:
        result.append(node)
        result.extend(flatten_tree(node.children))
    return result


def build_leaf_lookup(nodes: list[CategoryNode]) -> dict[str, CategoryNode]:
    """构建叶子节点查找表:name_zh → CategoryNode(叶子 = 无子节点)。

    同时用 path_zh 建索引,优先用 path_zh 查(防同名歧义),name_zh 做兼容。
    """
    lookup: dict[str, CategoryNode] = {}
    for node in flatten_tree(nodes):
        if not node.children:
            lookup[node.name_zh] = node
            if node.path_zh:
                lookup[node.path_zh] = node
    return lookup


def build_name_lookup(nodes: list[CategoryNode]) -> dict[str, CategoryNode]:
    """构建全节点查找表:name_zh + path_zh → CategoryNode。"""
    result: dict[str, CategoryNode] = {}
    for n in flatten_tree(nodes):
        result[n.name_zh] = n
        if n.path_zh:
            result[n.path_zh] = n
    return result


def scan_offers(batch_dir: Path) -> list[OfferFile]:
    """递归扫描 categories/ 下所有 offers/<product_id>/offer.json。"""
    offers: list[OfferFile] = []
    categories_dir = batch_dir / "categories"
    if not categories_dir.exists():
        log.error("categories/ 目录不存在: %s", categories_dir)
        sys.exit(1)

    for offer_json in sorted(categories_dir.rglob("offers/*/offer.json")):
        offer_dir = offer_json.parent
        product_id = offer_dir.name
        offers.append(OfferFile(
            product_id=product_id,
            offer_dir=offer_dir,
            offer_json_path=offer_json,
        ))
    return offers


# ────────────────────── 校验 ──────────────────────


def _extract_leaf_name(source_category_path: list) -> str | None:
    """从 source_category_path 取叶子的 name_zh。

    鑫方盛约定:纯字符串数组 ["动力工具", "电动工具", "电锤工具"],取最后一个。
    """
    if not source_category_path:
        return None
    last = source_category_path[-1]
    if isinstance(last, dict):
        return last.get("name_zh")
    return str(last)


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
            result.offer_errors[offer.product_id] = offer_errs
            continue

        data = offer.data
        # product_id 与目录名一致性(约定:product_id 在 source.product_id)
        source_obj = data.get("source", {})
        json_product_id = str(source_obj.get("product_id", "")) if isinstance(source_obj, dict) else ""
        if json_product_id and json_product_id != offer.product_id:
            offer_errs.append(
                f"product_id 不一致: 目录名={offer.product_id}, JSON source.product_id={json_product_id}"
            )

        # attributes 校验(鑫方盛:扁平 {key, value, group})
        attributes = data.get("attributes", [])
        if not attributes:
            result.warnings.append(f"[{offer.product_id}] attributes 为空(规格参数缺失)")
        for i, attr in enumerate(attributes):
            if not attr.get("key"):
                offer_errs.append(f"attributes[{i}] 缺少 key")
            if not attr.get("group"):
                offer_errs.append(f"attributes[{i}] 缺少 group")

        # 图片文件存在性
        for img in data.get("gallery", []):
            img_path = img.get("path", "")
            if img_path and not (offer.offer_dir / img_path).exists():
                offer_errs.append(f"gallery 图片不存在: {img_path}")

        for img in data.get("description_images", []):
            img_path = img.get("path", "")
            if img_path and not (offer.offer_dir / img_path).exists():
                offer_errs.append(f"description_images 图片不存在: {img_path}")

        # 归类校验(硬):source_category_path 叶子的 name_zh 匹配 categories_raw.json
        src_path = data.get("source_category_path", [])
        leaf_name = _extract_leaf_name(src_path)
        if not leaf_name:
            offer_errs.append("source_category_path 为空")
        elif leaf_name not in leaf_lookup:
            if leaf_name in name_lookup:
                result.warnings.append(
                    f"[{offer.product_id}] source_category_path 叶子 '{leaf_name}' "
                    f"在分类树中但不是叶子节点"
                )
            else:
                # 品类不在 categories_raw.json 中，降级为警告（导入时会自动创建）
                result.warnings.append(
                    f"[{offer.product_id}] source_category_path 叶子 '{leaf_name}' "
                    f"在 categories_raw.json 中未找到，导入时将自动创建"
                )

        # 归类校验(软):source_category_path 逐层与 categories_raw.json 对比
        _validate_category_path(src_path, name_lookup, offer.product_id, result)

        if offer_errs:
            result.offer_errors[offer.product_id] = offer_errs

    return result


def _validate_category_path(
    src_path: list,
    name_lookup: dict[str, "CategoryNode"],
    product_id: str,
    result: "ValidationResult",
) -> None:
    """逐层校验 offer 的 source_category_path 与 categories_raw.json 是否一致。

    鑫方盛的 source_category_path 是纯字符串数组。
    检查每一层的 name_zh 是否存在于分类树,以及父子关系是否对得上。
    不匹配时报 warning,不阻断导入。
    """
    if not src_path or len(src_path) < 2:
        return

    for i, level in enumerate(src_path):
        name_zh = level if isinstance(level, str) else str(level)
        if not name_zh:
            continue

        node = name_lookup.get(name_zh)
        if not node:
            result.warnings.append(
                f"[{product_id}] source_category_path 第{i + 1}层 '{name_zh}' "
                f"在 categories_raw.json 中未找到"
            )
            return

        # 校验父子关系:第 1 层(i=0)应该无 parent,后续层的 parent 应该是上一层
        if i > 0:
            expected_parent = src_path[i - 1] if isinstance(src_path[i - 1], str) else str(src_path[i - 1])
            if node.parent_name_zh and node.parent_name_zh != expected_parent:
                result.warnings.append(
                    f"[{product_id}] source_category_path 第{i + 1}层 '{name_zh}' "
                    f"的父节点应该是 '{node.parent_name_zh}',"
                    f"但 offer 路径中上一层是 '{expected_parent}'"
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


# ────────────────────── 分类导入 ──────────────────────


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
    """将 categories_raw.json 全层存入 categories 表,返回 path_zh → code 映射。

    算法:按 (name_zh, parent_code) 匹配现有节点,沿用 code;
    新节点取空号生成稳定 code。append-only,永不物理删。

    返回值优先用 path_zh 做 key(防同名歧义),name_zh 仅在无冲突时写入做兼容。
    """
    existing_by_natural: dict[tuple[str, str | None], Category] = {}
    used_seq_by_parent: dict[str | None, set[int]] = {}

    for c in db.execute(select(Category)).scalars().all():
        existing_by_natural[(c.name_zh, c.parent_code)] = c
        used_seq_by_parent.setdefault(c.parent_code, set()).add(_split_seq(c.code))

    path_to_code: dict[str, str] = {}
    # name_zh → code 兼容映射,同名时标记为冲突不写入
    _name_codes: dict[str, str | None] = {}  # None = 冲突,不可用
    inserted = 0
    updated = 0

    def _upsert_node(node: CategoryNode, parent_code: str | None) -> str:
        nonlocal inserted, updated

        natural_key = (node.name_zh, parent_code)
        existing = existing_by_natural.get(natural_key)

        if existing:
            code = existing.code
            changed = False
            if existing.level != node.level:
                existing.level = node.level
                changed = True
            if not existing.is_active:
                existing.is_active = True
                changed = True
            if node.short_name and existing.short_name_zh != node.short_name:
                existing.short_name_zh = node.short_name
                changed = True
            # 补齐 L1 short_name en/sw(人工映射表）
            if node.short_name and node.short_name in _L1_SHORT_NAME_I18N:
                sn_en, sn_sw = _L1_SHORT_NAME_I18N[node.short_name]
                if existing.short_name_en != sn_en:
                    existing.short_name_en = sn_en
                    changed = True
                if existing.short_name_sw != sn_sw:
                    existing.short_name_sw = sn_sw
                    changed = True
                # 标记为 manual,翻译器不会覆盖
                meta = dict(existing.trans_meta or {})
                if meta.get("short_name_en") != "manual" or meta.get("short_name_sw") != "manual":
                    meta["short_name_en"] = "manual"
                    meta["short_name_sw"] = "manual"
                    existing.trans_meta = meta
                    changed = True
            if changed:
                existing.updated_at = _utcnow()
                updated += 1
        else:
            # 新建
            used = used_seq_by_parent.setdefault(parent_code, set())
            seq = _next_seq(used)
            used.add(seq)
            code = _make_code(parent_code, seq, node.level)

            now = _utcnow()
            # L1 short_name 从人工映射表取,不走机器翻译
            sn_en, sn_sw = None, None
            sn_en_status, sn_sw_status = "pending", "pending"
            if node.short_name and node.short_name in _L1_SHORT_NAME_I18N:
                sn_en, sn_sw = _L1_SHORT_NAME_I18N[node.short_name]
                sn_en_status, sn_sw_status = "manual", "manual"

            cat = Category(
                code=code,
                name_zh=node.name_zh,
                name_en=None,  # 鑫方盛无英文,等翻译管道补译
                short_name_zh=node.short_name,
                short_name_en=sn_en,
                short_name_sw=sn_sw,
                level=node.level,
                parent_code=parent_code,
                sort_order=0,
                is_active=True,
                created_at=now,
                updated_at=now,
                source_lang="zh",
                trans_meta={
                    "name_zh": "src",
                    "name_en": "pending",
                    "name_sw": "pending",
                    "short_name_zh": "src" if node.short_name else None,
                    "short_name_en": sn_en_status if node.short_name else None,
                    "short_name_sw": sn_sw_status if node.short_name else None,
                },
                i18n_pending_at=now,
            )
            db.add(cat)
            db.flush()
            existing_by_natural[natural_key] = cat
            inserted += 1

        # path_zh 做主 key(唯一,无歧义)
        if node.path_zh:
            path_to_code[node.path_zh] = code
        # name_zh 做兼容 key:首次写入;再遇同名标记冲突
        if node.name_zh in _name_codes:
            if _name_codes[node.name_zh] != code:
                _name_codes[node.name_zh] = None  # 冲突
        else:
            _name_codes[node.name_zh] = code
        node.db_code = code

        for child in node.children:
            _upsert_node(child, code)

        return code

    for root in cat_tree:
        _upsert_node(root, None)

    # 把无冲突的 name_zh 也写入 path_to_code,方便兼容查找
    for name, code in _name_codes.items():
        if code is not None and name not in path_to_code:
            path_to_code[name] = code

    # 全量刷新 is_leaf:有 active 子节点的品类为非叶子
    all_cats = db.execute(select(Category)).scalars().all()
    parent_codes_with_active_children: set[str] = set()
    for c in all_cats:
        if c.parent_code and c.is_active:
            parent_codes_with_active_children.add(c.parent_code)
    for c in all_cats:
        c.is_leaf = c.code not in parent_codes_with_active_children

    log.info("  分类导入: 新增=%d, 更新=%d, 总映射=%d (path_zh)", inserted, updated, len(path_to_code))
    return path_to_code


# ────────────────────── 商品导入 ──────────────────────


def ensure_category_chain(
    db: Session,
    src_path: list,
    name_to_code: dict[str, str],
) -> str:
    """按 source_category_path 逐层查找/创建品类，返回叶子节点的 code。

    如果路径中某一层在 DB 里不存在，就自动创建。
    复用 _make_code / _next_seq 生成稳定 code。
    """
    # 加载已有品类的 (name_zh, parent_code) → Category 映射和已用序号
    existing_by_natural: dict[tuple[str, str | None], Category] = {}
    used_seq_by_parent: dict[str | None, set[int]] = {}
    for c in db.execute(select(Category)).scalars().all():
        existing_by_natural[(c.name_zh, c.parent_code)] = c
        used_seq_by_parent.setdefault(c.parent_code, set()).add(_split_seq(c.code))

    parent_code: str | None = None
    leaf_code: str | None = None
    path_parts = [str(s) for s in src_path]

    for i, name_zh in enumerate(path_parts):
        level = i + 1
        natural_key = (name_zh, parent_code)
        existing = existing_by_natural.get(natural_key)

        if existing:
            parent_code = existing.code
            leaf_code = existing.code
        else:
            # 自动创建
            used = used_seq_by_parent.setdefault(parent_code, set())
            seq = _next_seq(used)
            used.add(seq)
            code = _make_code(parent_code, seq, level)
            now = _utcnow()

            cat = Category(
                code=code,
                name_zh=name_zh,
                name_en=None,
                level=level,
                parent_code=parent_code,
                sort_order=0,
                is_active=True,
                created_at=now,
                updated_at=now,
                source_lang="zh",
                trans_meta={
                    "name_zh": "src",
                    "name_en": "pending",
                    "name_sw": "pending",
                },
                i18n_pending_at=now,
            )
            db.add(cat)
            db.flush()
            existing_by_natural[natural_key] = cat
            log.info("  自动创建品类: L%d %s → code=%s (parent=%s)", level, name_zh, code, parent_code)

            parent_code = code
            leaf_code = code

        # 更新 name_to_code 映射，后续 offer 可直接命中
        # 用 > 分隔的路径做 key
        partial_path = ">".join(path_parts[:i + 1])
        name_to_code[partial_path] = leaf_code  # type: ignore[assignment]
        # 叶子节点的 name_zh 也写入（无冲突时）
        if name_zh not in name_to_code:
            name_to_code[name_zh] = leaf_code  # type: ignore[assignment]

    assert leaf_code is not None, f"ensure_category_chain 失败: {src_path}"
    return leaf_code


def import_offer(
    db: Session,
    offer: OfferFile,
    *,
    name_to_code: dict[str, str],
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

    product_id = offer.product_id
    spu_code = "BR-" + hashlib.md5(f"P-XFS-{product_id}".encode()).hexdigest()[:8].upper()

    # ── 1. 归类:source_category_path → DB code ──
    # 优先用 path_zh(全路径,无歧义),回退到叶子 name_zh
    # path_to_code 的 key 分隔符取决于 categories_raw.json(可能是 ">" 或 "/"),两种都试
    src_path = data.get("source_category_path", [])
    leaf_name = _extract_leaf_name(src_path)
    category_code = None
    if src_path:
        parts = [str(s) for s in src_path]
        category_code = (
            name_to_code.get(">".join(parts))
            or name_to_code.get("/".join(parts))
        )
    if not category_code:
        category_code = name_to_code.get(leaf_name or "")
    if not category_code:
        # 品类路径在 DB 中不存在，按路径逐层自动创建
        if src_path:
            category_code = ensure_category_chain(db, src_path, name_to_code)
            log.info("  品类自动创建完成: %s → code=%s", " > ".join(str(s) for s in src_path), category_code)
        else:
            raise ValueError(f"分类路径为空，无法归类")

    # ── 1.5 来源溯源 ──
    source_obj = data.get("source", {})
    source_meta = {}
    if isinstance(source_obj, dict):
        if source_obj.get("product_url"):
            source_meta["product_url"] = source_obj["product_url"]
        if source_obj.get("crawled_at"):
            source_meta["crawled_at"] = source_obj["crawled_at"]
    video_url = data.get("video_url") or None

    # ── 2. SPU 字段映射(鑫方盛:纯中文,无英文字段) ──
    name_zh = data.get("product_name_zh") or ""
    # 品牌:顶层 brand 字段
    brand_zh = (data.get("brand") or "").strip() or None

    # 型号:从 attributes 列表中提取"型号"字段
    manufacturer_model = None
    for attr in (data.get("attributes") or []):
        if isinstance(attr, dict) and attr.get("name") == "型号":
            manufacturer_model = (attr.get("value") or "").strip() or None
            break

    # 描述/selling_points/certifications/origin:鑫方盛商品描述全是图片,文本字段留空
    desc_zh = None
    detail_desc_zh = None

    # MOQ
    moq_obj = data.get("moq") or {}
    moq_value = moq_obj.get("value")
    moq_unit_raw = moq_obj.get("unit") or None
    # 标准化单位（中文/英文混杂 → 统一 code）
    from scripts.normalize_moq_unit import normalize_unit
    moq_unit = normalize_unit(moq_unit_raw) if moq_unit_raw else None
    if moq_value is not None:
        try:
            moq_value = int(moq_value)
        except (TypeError, ValueError):
            moq_value = None

    # packing_qty
    packing_qty_obj = data.get("packing_qty") or {}
    packing_quantity = None
    packing_qty_raw = packing_qty_obj.get("value")
    if packing_qty_raw is not None:
        try:
            packing_quantity = int(packing_qty_raw)
        except (TypeError, ValueError):
            packing_quantity = None

    # 物流参数
    packing_obj = data.get("packing") or {}
    gross_weight_kg = _parse_decimal(packing_obj.get("gross_weight_kg"))
    volume_cbm = _parse_package_size_to_cbm(packing_obj.get("package_size"))

    # i18n:纯中文数据,所有 _en/_sw 标 pending
    _i18n_fields = ["name", "description", "brand", "origin",
                    "selling_points", "detail_description"]
    _trans_meta: dict[str, str] = {}
    for _f in _i18n_fields:
        _trans_meta[f"{_f}_zh"] = "src"
        _trans_meta[f"{_f}_en"] = "pending"
        _trans_meta[f"{_f}_sw"] = "pending"

    # ── 3. 幂等 upsert by spu_code ──
    existing = db.execute(
        select(Product).where(Product.spu_code == spu_code)
    ).scalar_one_or_none()

    if existing:
        product = existing
        if name_zh:
            product.name_zh = name_zh
        product.category_code = category_code
        if brand_zh:
            product.brand_zh = brand_zh
        if moq_value is not None:
            product.moq = moq_value
        if moq_unit:
            product.moq_unit = moq_unit
        if packing_quantity is not None:
            product.packing_quantity = packing_quantity
        if gross_weight_kg is not None:
            product.gross_weight_kg = gross_weight_kg
        if volume_cbm is not None:
            product.volume_cbm = volume_cbm
        if manufacturer_model:
            product.manufacturer_model = manufacturer_model
        if video_url:
            product.video_url = video_url
        if source_meta:
            product.source_meta = source_meta
        product.trans_meta = _trans_meta
        product.i18n_pending_at = _utcnow()
        product.source = run_meta.source
        product.last_ingest_run_id = run.id
        product.updated_at = _utcnow()
        audit_action = AuditAction.UPDATE
    else:
        product = Product(
            spu_code=spu_code,
            category_code=category_code,
            name_en=None,  # 等翻译管道补译
            name_zh=name_zh or spu_code,  # name_zh NOT NULL,回退 spu_code
            description_en=None,
            description_zh=desc_zh,
            selling_points_en=None,
            selling_points_zh=None,
            certifications=[],
            brand_en=None,
            brand_zh=brand_zh,
            origin_en=None,
            origin_zh=None,
            detail_description_en=None,
            detail_description_zh=detail_desc_zh,
            moq=moq_value,
            moq_unit=moq_unit,
            packing_quantity=packing_quantity,
            gross_weight_kg=gross_weight_kg,
            volume_cbm=volume_cbm,
            manufacturer_model=manufacturer_model,
            video_url=video_url,
            source=run_meta.source,
            source_meta=source_meta or None,
            last_ingest_run_id=run.id,
            status=ProductStatus.ACTIVE,  # 爬虫数据已人工审核,直接上架
            source_lang="zh",
            trans_meta=_trans_meta,
            i18n_pending_at=_utcnow(),
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

    # ── 5. product_attrs:鑫方盛扁平属性,每个 {key, value, group} 一行 ──
    attr_sort = 0
    seen_attr_keys: set[str] = set()
    for attr_def in data.get("attributes", []):
        key = (attr_def.get("key") or "").strip()
        value = (attr_def.get("value") or "").strip()
        group = (attr_def.get("group") or "").strip()

        if not key or not value:
            continue

        # 跳过品牌属性(与顶层 brand 字段重复)
        if key == "品牌":
            continue

        # 去重:同 key 只保留第一个
        if key in seen_attr_keys:
            continue
        seen_attr_keys.add(key)

        db.add(ProductAttr(
            product_id=product.id,
            sku_id=None,
            attr_key_zh=key[:50],
            attr_key_en=key[:50],  # NOT NULL + 唯一约束,先用中文填充,等翻译管道补译
            attr_value_zh=value[:500],
            attr_value_en=value[:500],  # NOT NULL + 唯一约束,先用中文填充,等翻译管道补译
            attr_group=group[:100] if group else None,
            value_type="text",
            sort_order=attr_sort,
            selectable=False,
            swatch_image=None,
            source_lang="zh",
            trans_meta={
                "attr_key_zh": "src",
                "attr_key_en": "pending",
                "attr_key_sw": "pending",
                "attr_value_zh": "src",
                "attr_value_en": "pending",
                "attr_value_sw": "pending",
            },
            i18n_pending_at=_utcnow(),
        ))
        attr_sort += 1

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
            source_url=img_def.get("source_url") or None,
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
            source_url=img_def.get("source_url") or None,
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
            "product_id": product_id,
        },
    )


def _parse_decimal(raw: str | None) -> float | None:
    """安全解析数值字符串,无效返回 None。"""
    if not raw:
        return None
    try:
        val = float(raw)
        return val if val > 0 else None
    except (TypeError, ValueError):
        return None


def _parse_package_size_to_cbm(raw: str | None) -> float | None:
    """从 "116X76X16厘米" 格式解析体积,返回 CBM。

    支持格式:
    - "116X76X16厘米" / "116x76x16cm" → 长x宽x高(厘米) → CBM
    - 数值间可有空格,单位可有可无(默认厘米)
    """
    if not raw:
        return None
    import re
    cleaned = re.sub(r"(厘米|cm|CM|毫米|mm|MM)\s*$", "", raw.strip(), flags=re.IGNORECASE)
    is_mm = bool(re.search(r"(毫米|mm)", raw, re.IGNORECASE))
    parts = re.split(r"[xX×*]\s*", cleaned.strip())
    if len(parts) != 3:
        return None
    try:
        dims = [float(p.strip()) for p in parts]
    except (TypeError, ValueError):
        return None
    if any(d <= 0 for d in dims):
        return None
    divisor = 1000.0 if is_mm else 100.0
    cbm = (dims[0] / divisor) * (dims[1] / divisor) * (dims[2] / divisor)
    return round(cbm, 4) if cbm > 0 else None


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
        path="scripts/import_products_xfs.py",
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
    parser = argparse.ArgumentParser(description="鑫方盛抓数 → 商品入库")
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

    if vr.warnings:
        log.warning("⚠️  告警 (%d):", len(vr.warnings))
        for w in vr.warnings:
            log.warning("  %s", w)

    valid_offers = [o for o in offers if o.product_id not in vr.offer_errors]
    failed_offers = [o for o in offers if o.product_id in vr.offer_errors]

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
            spu_code = "BR-" + hashlib.md5(f"P-XFS-{o.product_id}".encode()).hexdigest()[:8].upper()
            src_path = o.data.get("source_category_path", []) if o.data else []
            leaf = _extract_leaf_name(src_path)
            name_zh = ""
            if o.data:
                name_zh = o.data.get("product_name_zh", "")
            log.info("  %s → 分类叶子=%s, name=%s", spu_code, leaf, name_zh[:60])
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
            name_to_code = import_categories(db, cat_tree)
            db.commit()

            # 7. 导入商品(逐 offer 独立事务)
            leaf_lookup = build_leaf_lookup(cat_tree)
            static_root = _BACKEND_ROOT / "uploads"
            static_root.mkdir(exist_ok=True)

            success_count = 0
            import_errors: list[dict] = []

            for i, offer in enumerate(valid_offers, 1):
                try:
                    import_offer(
                        db, offer,
                        name_to_code=name_to_code,
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
                    log.error("  [%s] 导入失败: %s", offer.product_id, err_msg)
                    import_errors.append({
                        "product_id": offer.product_id,
                        "error": err_msg,
                    })

            # 加上校验阶段失败的
            for oid, errs in vr.offer_errors.items():
                import_errors.append({
                    "product_id": oid,
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
