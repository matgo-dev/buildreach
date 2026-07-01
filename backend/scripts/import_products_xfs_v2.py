"""鑫方盛抓数 v2（SPU+SKU 格式）→ 商品入库 CLI 脚本。

用法
----
    # 导入一个 raw 批次目录
    python scripts/import_products_xfs_v2.py --batch ../data/xfs_2026-06-28

    # 只跑校验 + 打印差异,不写库
    python scripts/import_products_xfs_v2.py --batch ../data/xfs_2026-06-28 --dry-run

与 v1 的关键差异
----------------
- offer.json 按 SPU+SKU 聚合（spuCode + skus[]），不再是扁平单品
- 每个 SKU 创建独立 ProductSku 记录
- spuBasicAttributes[] → ProductAttr(sku_id=NULL)
- SKU saleAttributes[] → ProductAttr(sku_id=具体 SKU, selectable=True)
- images[]/detailImages[] → ProductImage(MAIN/GALLERY/DETAIL)
- 不导入价格数据
- 品类匹配走 categoryPath 数组逐层匹配 DB 已有品类

⚠️ 本脚本**不在应用启动时自动跑**,只能本地人工执行。
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import sys
import uuid
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
    ProductSku,
    ProductStatus,
)
from app.db.models.audit_log import AuditLog, AuditStatus  # noqa: E402
from app.db.models.product_image import ImageType  # noqa: E402
from app.db.models.product_sku import SkuStatus  # noqa: E402
from app.db.url import prepare_sync_url  # noqa: E402
from app.services.product_code import xfs_product_code, xfs_sku_code  # noqa: E402
from scripts.normalize_moq_unit import normalize_unit  # noqa: E402

from scripts._log_setup import setup_logging  # noqa: E402
setup_logging("import_products_xfs_v2")
log = logging.getLogger("import_products_xfs_v2")

# ────────────────────── 常量 ──────────────────────

# 中文单位 → 标准 code（normalize_unit 已覆盖大部分,这里仅补充要求中明确列出的映射）
_UNIT_MAP_SUPPLEMENT: dict[str, str] = {
    "台": "PCS",
    "件": "PCS",
    "个": "PCS",
    "箱": "BOX",
    "米": "M",
    "卷": "ROLL",
    "套": "SET",
    "根": "PCS",
    "把": "PCS",
}


def _normalize_unit(raw: str | None) -> str:
    """中文单位转标准 code,无法识别时回退 PCS。"""
    if not raw:
        return "PCS"
    code = normalize_unit(raw)
    if code:
        return code
    return _UNIT_MAP_SUPPLEMENT.get(raw.strip(), "PCS")


# ────────────────────── 数据结构 ──────────────────────


@dataclass
class RunMeta:
    """run.json 元数据。"""
    source: str
    crawled_at: str | None = None
    operator: str | None = None


@dataclass
class OfferFile:
    """一个 offer.json 的定位信息。"""
    spu_code_raw: str           # 目录名 = spuCode
    offer_dir: Path             # 包含 offer.json 的目录
    offer_json_path: Path       # offer.json 完整路径
    data: dict | None = None    # 解析后的 JSON


@dataclass
class ValidationResult:
    """校验结果汇总。"""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    offers: list[OfferFile] = field(default_factory=list)
    offer_errors: dict[str, list[str]] = field(default_factory=dict)


# ────────────────────── Reader ──────────────────────


def read_run_json(batch_dir: Path) -> RunMeta:
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


def scan_offers(batch_dir: Path) -> list[OfferFile]:
    """递归扫描 categories/ 下所有 offers/{spuCode}/offer.json。"""
    offers: list[OfferFile] = []
    categories_dir = batch_dir / "categories"
    if not categories_dir.exists():
        log.error("categories/ 目录不存在: %s", categories_dir)
        sys.exit(1)

    for offer_json in sorted(categories_dir.rglob("offers/*/offer.json")):
        offer_dir = offer_json.parent
        spu_code_raw = offer_dir.name
        offers.append(OfferFile(
            spu_code_raw=spu_code_raw,
            offer_dir=offer_dir,
            offer_json_path=offer_json,
        ))
    return offers


# ────────────────────── 校验 ──────────────────────


def validate_batch(offers: list[OfferFile]) -> ValidationResult:
    """校验所有 offer.json 的基本结构完整性。"""
    result = ValidationResult(offers=offers)

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
            result.offer_errors[offer.spu_code_raw] = offer_errs
            continue

        data = offer.data

        # spuCode 与目录名一致性
        json_spu_code = str(data.get("spuCode", ""))
        if json_spu_code and json_spu_code != offer.spu_code_raw:
            offer_errs.append(
                f"spuCode 不一致: 目录名={offer.spu_code_raw}, JSON spuCode={json_spu_code}"
            )

        # 必须字段
        if not data.get("spuName"):
            offer_errs.append("缺少 spuName")
        if not data.get("categoryPath"):
            offer_errs.append("缺少 categoryPath")

        # skus 数组
        skus = data.get("skus", [])
        if not skus:
            offer_errs.append("skus 数组为空")
        else:
            for i, sku in enumerate(skus):
                if not sku.get("skuCode"):
                    offer_errs.append(f"skus[{i}] 缺少 skuCode")

        # 图片文件存在性
        for img in data.get("images", []):
            img_path = img.get("path", "")
            if img_path and not (offer.offer_dir / img_path).exists():
                offer_errs.append(f"images 图片不存在: {img_path}")

        for img in data.get("detailImages", []):
            img_path = img.get("path", "")
            if img_path and not (offer.offer_dir / img_path).exists():
                offer_errs.append(f"detailImages 图片不存在: {img_path}")

        if offer_errs:
            result.offer_errors[offer.spu_code_raw] = offer_errs

    return result


# ────────────────────── 品类匹配 ──────────────────────


def _load_category_index(db: Session) -> dict[tuple[str, str | None], Category]:
    """加载全量品类到内存索引,按 (name_zh, parent_code) 查找。调用方缓存结果。"""
    all_cats = db.execute(select(Category).where(Category.is_active.is_(True))).scalars().all()
    index: dict[tuple[str, str | None], Category] = {}
    for c in all_cats:
        index[(c.name_zh, c.parent_code)] = c
    return index


def match_category_by_path(
    category_path: list[str],
    cat_index: dict[tuple[str, str | None], Category],
) -> str | None:
    """按 categoryPath 数组逐层匹配已有品类,返回叶子节点 code。

    匹配逻辑:从第一级开始,按 (name_zh, parent_code) 逐层往下找。
    任何一层找不到就返回 None。
    """
    if not category_path:
        return None

    parent_code: str | None = None
    leaf_code: str | None = None

    for name_zh in category_path:
        cat = cat_index.get((name_zh, parent_code))
        if not cat:
            return None
        parent_code = cat.code
        leaf_code = cat.code

    return leaf_code


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
    run.status = status
    run.product_count = product_count
    run.imported_at = _utcnow()
    run.error_summary = error_summary
    run.updated_at = _utcnow()
    db.flush()


# ────────────────────── 图片工具 ──────────────────────


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


# ────────────────────── 审计 ──────────────────────


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
    entry = AuditLog(
        trace_id=str(uuid.uuid4()),
        user_id=None,
        user_email=None,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        action=action,
        method="CLI",
        path="scripts/import_products_xfs_v2.py",
        ip=None,
        user_agent=None,
        status=status,
        error_message=error_message,
        extra={**(extra or {}), "operator": operator or "system"},
    )
    db.add(entry)
    db.flush()


# ────────────────────── 商品导入 ──────────────────────


def import_offer(
    db: Session,
    offer: OfferFile,
    *,
    run: IngestRun,
    run_meta: RunMeta,
    static_root: Path,
    cat_index: dict[tuple[str, str | None], Category],
) -> None:
    """导入单个 SPU+SKU offer:幂等 upsert + 子行先清后插 + 图片拷贝 + 审计。

    事务边界:调用方负责 commit/rollback(一个 offer = 一个事务)。
    """
    data = offer.data
    assert data is not None

    raw_spu = str(data.get("spuCode", offer.spu_code_raw))
    spu_code = xfs_product_code(raw_spu)

    # ── 1. 品类匹配:categoryPath 逐层走 DB 已有品类 ──
    category_path: list[str] = data.get("categoryPath", [])
    category_code = match_category_by_path(category_path, cat_index)
    if not category_code:
        raise ValueError(
            f"品类路径匹配失败: {' > '.join(category_path)}，"
            f"请确认 DB 中已有对应品类链"
        )

    # ── 2. 来源溯源 ──
    meta_obj = data.get("_meta", {})
    source_meta: dict[str, Any] = {}
    if isinstance(meta_obj, dict):
        if meta_obj.get("sourceUrl"):
            source_meta["product_url"] = meta_obj["sourceUrl"]
        if meta_obj.get("scrapeTime"):
            source_meta["crawled_at"] = meta_obj["scrapeTime"]
    source_meta["spuCode"] = raw_spu
    # categoryName 存 source_meta,不丢弃(categoryPath 用于匹配,categoryName 用于溯源)
    cat_name = (data.get("categoryName") or "").strip()
    if cat_name:
        source_meta["categoryName"] = cat_name

    # ── 3. SPU 字段映射 ──
    name_zh = (data.get("spuName") or "").strip()
    brand_zh = (data.get("brandName") or "").strip() or None

    # SPU manufacturer_model:只在源站明确给了"系列/整款共用型号"时才填。
    # XFS 的"型号/规格型号"大多在 SKU 级(不同 SKU 型号不同),SPU 级不硬填。
    manufacturer_model = None

    # 单位:取第一个 SKU(默认 SKU)的 unitName
    skus_raw = data.get("skus", [])
    first_sku = skus_raw[0] if skus_raw else {}
    unit_raw = first_sku.get("unitName")
    unit = _normalize_unit(unit_raw)

    # MOQ:取第一个 SKU 的 moq
    moq_value = first_sku.get("moq")
    if moq_value is not None:
        try:
            moq_value = int(moq_value)
        except (TypeError, ValueError):
            moq_value = None

    # i18n:纯中文数据,所有 _en/_sw 标 pending
    _i18n_fields = ["name", "description", "brand", "origin",
                    "selling_points", "detail_description"]
    _trans_meta: dict[str, str] = {}
    for _f in _i18n_fields:
        _trans_meta[f"{_f}_zh"] = "src"
        _trans_meta[f"{_f}_en"] = "pending"
        _trans_meta[f"{_f}_sw"] = "pending"

    # ── 4. 幂等 upsert by spu_code ──
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
        product.moq_unit = unit
        product.unit = unit
        if manufacturer_model:
            product.manufacturer_model = manufacturer_model
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
            name_zh=name_zh or spu_code,
            name_en=None,
            description_zh=None,
            description_en=None,
            selling_points_zh=None,
            selling_points_en=None,
            certifications=[],
            brand_zh=brand_zh,
            brand_en=None,
            origin_zh=None,
            origin_en=None,
            detail_description_zh=None,
            detail_description_en=None,
            manufacturer_model=manufacturer_model,
            unit=unit,
            moq=moq_value,
            moq_unit=unit,
            source=run_meta.source,
            source_meta=source_meta or None,
            last_ingest_run_id=run.id,
            status=ProductStatus.ACTIVE,
            source_lang="zh",
            trans_meta=_trans_meta,
            i18n_pending_at=_utcnow(),
        )
        db.add(product)
        audit_action = AuditAction.IMPORT

    db.flush()  # 拿到 product.id

    # ── 5. 子行先清后插(防重导翻倍) ──
    # 清 SKU 级 attrs 和 images 需要先拿到旧 SKU id 列表
    old_sku_ids = [
        row[0] for row in db.execute(
            select(ProductSku.id).where(ProductSku.product_id == product.id)
        ).all()
    ]
    if old_sku_ids:
        db.execute(
            delete(ProductAttr).where(ProductAttr.sku_id.in_(old_sku_ids))
        )
        db.execute(
            delete(ProductImage).where(ProductImage.sku_id.in_(old_sku_ids))
        )
    # 清 SPU 级 attrs 和 images（sku_id=NULL 的）
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
    # 清旧 SKU
    db.execute(
        delete(ProductSku).where(ProductSku.product_id == product.id)
    )
    db.flush()

    # ── 6. SPU 公共属性:spuBasicAttributes[] → ProductAttr(sku_id=NULL) ──
    attr_sort = 0
    seen_attr_keys: set[str] = set()
    for attr_def in data.get("spuBasicAttributes", []):
        key = (attr_def.get("name") or "").strip()
        value = (attr_def.get("value") or "").strip()
        if not key or not value:
            continue
        # 跳过品牌相关(与顶层 brandName 重复)
        if "品牌" in key:
            continue
        if key in seen_attr_keys:
            continue
        seen_attr_keys.add(key)

        db.add(ProductAttr(
            product_id=product.id,
            sku_id=None,
            attr_key_zh=key[:50],
            attr_key_en=None,       # 纯中文数据源,英文由 i18n 管道补译
            attr_value_zh=value[:500],
            attr_value_en=None,
            attr_group=None,
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

    # ── 6.5 SPU 销售属性(变体轴定义):spuSaleAttributes → ProductAttr(sku_id=NULL, selectable=True) ──
    # 定义了 SPU 下有哪些变体维度及所有可选值,前端渲染变体选择器需要这些数据
    for sa_def in data.get("spuSaleAttributes", []):
        sa_name = (sa_def.get("name") or "").strip()
        if not sa_name:
            continue
        sa_values = sa_def.get("values", [])
        if isinstance(sa_values, str):
            sa_values = [v.strip() for v in sa_values.split(",") if v.strip()]
        for sa_val in sa_values:
            if not sa_val:
                continue
            dedup_key = (sa_name, str(sa_val))
            if dedup_key in seen_attr_keys:
                continue
            seen_attr_keys.add(dedup_key)
            db.add(ProductAttr(
                product_id=product.id,
                sku_id=None,
                attr_key_zh=sa_name[:50],
                attr_key_en=None,
                attr_value_zh=str(sa_val)[:500],
                attr_value_en=None,
                attr_group=None,
                value_type="text",
                sort_order=attr_sort,
                selectable=True,
                swatch_image=None,
                source_lang="zh",
                trans_meta={
                    "attr_key_zh": "src", "attr_key_en": "pending", "attr_key_sw": "pending",
                    "attr_value_zh": "src", "attr_value_en": "pending", "attr_value_sw": "pending",
                },
                i18n_pending_at=_utcnow(),
            ))
            attr_sort += 1

    # ── 7. SKU 创建 ──
    for sku_idx, sku_raw in enumerate(skus_raw):
        sku_code_raw = str(sku_raw.get("skuCode", ""))
        if not sku_code_raw:
            log.warning("  [%s] skus[%d] 缺少 skuCode,跳过", raw_spu, sku_idx)
            continue

        sku_code = xfs_sku_code(sku_code_raw)

        sku_name_zh = (sku_raw.get("skuName") or "").strip() or None
        sku_moq = sku_raw.get("moq")
        if sku_moq is not None:
            try:
                sku_moq = int(sku_moq)
            except (TypeError, ValueError):
                sku_moq = 1
        else:
            sku_moq = 1  # ProductSku.moq NOT NULL,给默认值

        # 从 skuRawFields 提取可映射到模型固定列的字段
        raw_fields = sku_raw.get("skuRawFields") or {}
        weight = _parse_decimal(raw_fields.get("weight"))
        volume = _parse_decimal(raw_fields.get("volume"))
        arrival_cycle = _parse_decimal(raw_fields.get("arrivalCycle"))
        lead_time_max = int(arrival_cycle) if arrival_cycle else None

        # SKU manufacturer_model:优先从 saleAttributes 提取,有 fallback 链
        # 同时该值仍保留在 ProductAttr(selectable=True),固定列用于检索/运营
        _MODEL_KEYS = ("型号", "规格型号", "厂家型号", "货号", "订货号")
        sku_model = None
        for sa in (sku_raw.get("saleAttributes") or []):
            if isinstance(sa, dict) and sa.get("name") in _MODEL_KEYS:
                sku_model = (sa.get("value") or "").strip() or None
                break
        # fallback: factoryCode → specificationProperties
        if not sku_model:
            sku_model = (raw_fields.get("factoryCode") or "").strip() or None
        if not sku_model:
            sku_model = (raw_fields.get("specificationProperties") or "").strip() or None

        # partsNumber → packing_quantity(件装数量,如"1台/件"→解析数字)
        packing_qty = None
        parts_num = raw_fields.get("partsNumber")
        if parts_num:
            m = re.search(r"(\d+)", str(parts_num))
            if m:
                packing_qty = int(m.group(1))

        sku = ProductSku(
            product_id=product.id,
            sku_code=sku_code,
            name_zh=sku_name_zh,
            name_en=None,
            manufacturer_model=sku_model,
            moq=sku_moq,
            packing_quantity=packing_qty,
            gross_weight_kg=weight,
            volume_cbm=volume,
            lead_time_max=lead_time_max,
            is_default=(sku_idx == 0),
            status=SkuStatus.ACTIVE,
            source_lang="zh",
            trans_meta={
                "name_zh": "src",
                "name_en": "pending",
                "name_sw": "pending",
            },
            i18n_pending_at=_utcnow(),
        )
        db.add(sku)
        db.flush()

        # ── 7.1 SKU 级 saleAttributes → ProductAttr(selectable=True) ──
        sku_attr_sort = 0
        seen_sku_attr_keys: set[tuple[str, str]] = set()
        for sa in (sku_raw.get("saleAttributes") or []):
            sa_name = (sa.get("name") or "").strip()
            sa_value = (sa.get("value") or "").strip()
            if not sa_name or not sa_value:
                continue
            dedup = (sa_name, sa_value)
            if dedup in seen_sku_attr_keys:
                continue
            seen_sku_attr_keys.add(dedup)

            db.add(ProductAttr(
                product_id=product.id,
                sku_id=sku.id,
                attr_key_zh=sa_name[:50],
                attr_key_en=None,
                attr_value_zh=sa_value[:500],
                attr_value_en=None,
                attr_group=None,
                value_type="text",
                sort_order=sku_attr_sort,
                selectable=True,
                swatch_image=None,
                source_lang="zh",
                trans_meta={
                    "attr_key_zh": "src", "attr_key_en": "pending", "attr_key_sw": "pending",
                    "attr_value_zh": "src", "attr_value_en": "pending", "attr_value_sw": "pending",
                },
                i18n_pending_at=_utcnow(),
            ))
            sku_attr_sort += 1

        # ── 7.2 skuRawFields 全量存为 ProductAttr ──
        # 已映射到模型固定列的字段不重复存属性表
        _MAPPED_TO_COLUMN = {"weight", "volume", "arrivalCycle"}
        for rf_key, rf_val in raw_fields.items():
            if rf_key in _MAPPED_TO_COLUMN:
                continue
            val_str = str(rf_val).strip() if rf_val is not None else ""
            if not val_str:
                continue
            db.add(ProductAttr(
                product_id=product.id,
                sku_id=sku.id,
                attr_key_zh=rf_key[:50],
                attr_key_en=None,
                attr_value_zh=val_str[:500],
                attr_value_en=None,
                attr_group=None,
                value_type="text",
                sort_order=sku_attr_sort,
                selectable=False,
                source_lang="zh",
                trans_meta={
                    "attr_key_zh": "src", "attr_key_en": "pending", "attr_key_sw": "pending",
                    "attr_value_zh": "src", "attr_value_en": "pending", "attr_value_sw": "pending",
                },
                i18n_pending_at=_utcnow(),
            ))
            sku_attr_sort += 1

    # ── 8. SPU 级图片:images[] + detailImages[] ──
    img_sort = 0
    for img_def in data.get("images", []):
        img_path = img_def.get("path", "")
        if not img_path:
            continue
        _copy_image(offer.offer_dir / img_path, static_root, spu_code)
        # 图片类型:尊重抓取数据的 imgType;没有则按排序推断(第一张 MAIN,其余 GALLERY)
        raw_type = (img_def.get("type") or "").upper()
        if raw_type == "MAIN":
            img_type = ImageType.MAIN
        elif raw_type == "GALLERY":
            img_type = ImageType.GALLERY
        elif img_sort == 0:
            img_type = ImageType.MAIN
        else:
            img_type = ImageType.GALLERY
        db.add(ProductImage(
            product_id=product.id,
            sku_id=None,
            image_key=_image_key(spu_code, img_path),
            image_type=img_type,
            sort_order=img_sort,
            source_url=img_def.get("sourceUrl") or None,
        ))
        img_sort += 1

    for img_def in data.get("detailImages", []):
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
            source_url=img_def.get("sourceUrl") or None,
        ))
        img_sort += 1

    db.flush()

    # ── 9. 审计 ──
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
            "spuCode": raw_spu,
            "sku_count": len(skus_raw),
        },
    )


def _parse_decimal(raw: Any) -> float | None:
    """安全解析数值,无效返回 None。"""
    if raw is None:
        return None
    try:
        val = float(raw)
        return val if val > 0 else None
    except (TypeError, ValueError):
        return None


# ────────────────────── CLI 入口 ──────────────────────


def _parse_crawled_at(raw: str | None) -> datetime | None:
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
    parser = argparse.ArgumentParser(description="鑫方盛抓数 v2（SPU+SKU 格式）→ 商品入库")
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

    # 2. 扫描 offers
    log.info("扫描 offers ...")
    offers = scan_offers(batch_dir)
    log.info("  找到 %d 个 offer(SPU)", len(offers))

    # 3. 校验
    log.info("执行校验 ...")
    vr = validate_batch(offers)

    if vr.warnings:
        log.warning("告警 (%d):", len(vr.warnings))
        for w in vr.warnings:
            log.warning("  %s", w)

    valid_offers = [o for o in offers if o.spu_code_raw not in vr.offer_errors]
    failed_offers = [o for o in offers if o.spu_code_raw in vr.offer_errors]

    if vr.offer_errors:
        log.error("失败的 offer (%d):", len(vr.offer_errors))
        for oid, errs in vr.offer_errors.items():
            for e in errs:
                log.error("  [%s] %s", oid, e)

    if vr.errors:
        log.error("批次级错误,整批拒绝:")
        for e in vr.errors:
            log.error("  %s", e)
        sys.exit(1)

    log.info("校验通过: %d 可导入, %d 校验失败", len(valid_offers), len(failed_offers))

    if args.dry_run:
        log.info("[DRY RUN] 将导入 %d 个 SPU(来源: %s),不写库。", len(valid_offers), run_meta.source)
        for o in valid_offers:
            spu_code = xfs_product_code(o.spu_code_raw)
            cat_path = o.data.get("categoryPath", []) if o.data else []
            sku_count = len(o.data.get("skus", [])) if o.data else 0
            name_zh = (o.data.get("spuName") or "") if o.data else ""
            log.info(
                "  %s → 品类=%s, SKU数=%d, name=%s",
                spu_code, " > ".join(cat_path), sku_count, name_zh[:60],
            )
        sys.exit(0)

    # ── 写库 ──
    sync_url = prepare_sync_url(settings.DATABASE_URL)
    engine = create_engine(sync_url)

    with Session(engine) as db:
        try:
            # 4. 开 run
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

            # 5. 导入商品(逐 offer 独立事务)
            static_root = _BACKEND_ROOT / "uploads"
            static_root.mkdir(exist_ok=True)

            # 品类索引只加载一次,所有 offer 共用
            cat_index = _load_category_index(db)
            log.info("  品类索引: %d 条", len(cat_index))

            success_count = 0
            import_errors: list[dict] = []

            for i, offer in enumerate(valid_offers, 1):
                try:
                    import_offer(
                        db, offer,
                        run=run,
                        run_meta=run_meta,
                        static_root=static_root,
                        cat_index=cat_index,
                    )
                    db.commit()
                    success_count += 1
                    if i % 50 == 0:
                        log.info("  进度: %d/%d", i, len(valid_offers))
                except Exception as exc:
                    db.rollback()
                    err_msg = str(exc)[:500]
                    log.error("  [%s] 导入失败: %s", offer.spu_code_raw, err_msg)
                    import_errors.append({
                        "spuCode": offer.spu_code_raw,
                        "error": err_msg,
                    })

            # 加上校验阶段失败的
            for oid, errs in vr.offer_errors.items():
                import_errors.append({
                    "spuCode": oid,
                    "error": "; ".join(errs),
                })

            # 6. 关闭 run
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
