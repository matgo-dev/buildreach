"""商品目录 Service — SPU + SKU 两层化,v2 i18n 分列模式。

SPU CRUD / SKU CRUD(含阶梯价整体替换) / 供货关系(挂 SKU) / 图片(SPU+SKU) / 属性模板。
多语言写入经 i18n_write,读出经 get_localized。
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

from fastapi import UploadFile
from sqlalchemy import delete as sa_delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import (
    NotFoundError,
    ImageFormatInvalidError,
    ImageNotOwnedError,
    ImageTooLargeError,
    ImageTooSmallError,
    InvalidProductStatusError,
    MaxImagesExceededError,
    OnlyDraftDeletableError,
    IllegalTransitionError,
    ProductNotEditableError,
    PriceTierInvalidError,
    PublishValidationFailedError,
    SkuCodeExistsError,
    AttrKeyNotInTemplateError,
    AttrScopeMismatchError,
    CategoryNotLeafError,
    ProductRangeInvalidError,
    SpuCodeExistsError,
    SupplierAlreadyBoundError,
)
from app.core.message_keys import MessageKey
from app.core.i18n_write import apply_i18n_create, apply_i18n_edit
from app.core.i18n_registry import get_i18n_fields
from app.core.locale import SUPPORTED_LOCALES, get_current_locale
from app.db.models.attr_template import AttrTemplate
from app.db.models.category import Category
from app.db.models.product import Product, ProductStatus, SupplyMode
from app.db.models.product_attr import ProductAttr
from app.db.models.product_image import ProductImage, ImageType
from app.db.models.product_sku import ProductSku, SkuStatus
from app.db.models.product_supplier import ProductSupplier
from app.db.models.sku_price_tier import SkuPriceTier
from app.db.models.supplier_organization import SupplierOrganization
from app.db.base import _utcnow
from app.audit.constants import AuditAction, AuditResourceType
from app.audit.logger import write_audit
from app.schemas.product import (
    ProductAttrCreate,
    ProductCreate,
    ProductUpdate,
    SkuCreate,
    SkuUpdate,
    PriceTierCreate,
    SupplierRelationCreate,
    SupplierRelationUpdate,
)

MAX_IMAGES_PER_PRODUCT = 8

# 图片校验常量从公共模块导入
from app.services._buyer_utils import (
    ALLOWED_EXTENSIONS,
    MAX_IMAGE_SIZE,
    save_uploaded_image,
)

# i18n 字段声明:从注册表读取(单一来源)
from app.db.models.product import Product as _Product
from app.db.models.product_sku import ProductSku as _ProductSku
_PRODUCT_I18N_FIELDS = get_i18n_fields(_Product)
_SKU_I18N_FIELDS = get_i18n_fields(_ProductSku)


# ── 软删除工具 ──────────────────────────────────────────

def _not_deleted(model):
    """返回 model.deleted_at IS NULL 条件,所有查询统一用。"""
    return model.deleted_at.is_(None)


def _soft_delete_values(operator_id: int | None) -> dict:
    """软删赋值字典,供 update().values() 使用。"""
    return {"deleted_at": _utcnow(), "deleted_by": operator_id}


async def _soft_delete_obj(obj, operator_id: int | None) -> None:
    """单对象软删。"""
    obj.deleted_at = _utcnow()
    obj.deleted_by = operator_id


# ── SPU 编码生成 ─────────────────────────────────────────

_PREFIX_MAP = {
    "01": "LT", "02": "EL", "03": "SB", "04": "TH", "05": "BP",
    "06": "PF", "07": "CD", "08": "SP", "09": "SC",
    "10": "WT", "11": "AG", "12": "EN", "13": "SF",
}


async def _descendant_category_codes(
    db: AsyncSession, category_code: str,
) -> list[str]:
    """返回以 category_code 为根的整棵子树 code 集(含自身),逐层展开直到叶子。"""
    codes: list[str] = [category_code]
    current_layer = [category_code]
    while current_layer:
        rows = (await db.execute(
            select(Category.code).where(Category.parent_code.in_(current_layer))
        )).scalars().all()
        if not rows:
            break
        codes.extend(rows)
        current_layer = list(rows)
    return codes


async def _generate_spu_code(db: AsyncSession, category_code: str) -> str:
    l1_code = category_code.split(".")[0]
    prefix = _PREFIX_MAP.get(l1_code, l1_code.upper())

    count_result = await db.execute(
        select(func.count()).select_from(Product).where(
            Product.category_code == category_code
        )
    )
    seq = (count_result.scalar() or 0) + 1
    code = f"{prefix}-{category_code.replace('.', '-')}-{seq:03d}"

    while (await db.execute(
        select(Product.id).where(Product.spu_code == code, _not_deleted(Product))
    )).scalar_one_or_none():
        seq += 1
        code = f"{prefix}-{category_code.replace('.', '-')}-{seq:03d}"

    return code


async def _generate_sku_code(
    db: AsyncSession, spu_code: str, product_id: int,
) -> str:
    count_result = await db.execute(
        select(func.count()).select_from(ProductSku).where(
            ProductSku.product_id == product_id
        )
    )
    seq = (count_result.scalar() or 0) + 1
    code = f"{spu_code}-S{seq:02d}"

    while (await db.execute(
        select(ProductSku.id).where(ProductSku.sku_code == code, _not_deleted(ProductSku))
    )).scalar_one_or_none():
        seq += 1
        code = f"{spu_code}-S{seq:02d}"

    return code


# ── SPU CRUD ─────────────────────────────────────────────

async def create_product(
    db: AsyncSession, data: ProductCreate, operator_id: int,
) -> Product:
    # 品类存在 + 叶子校验(直接读 is_leaf 字段)
    cat = await db.execute(
        select(Category).where(Category.code == data.category_code)
    )
    category = cat.scalar_one_or_none()
    if not category:
        raise NotFoundError("Category not found")
    if not category.is_leaf:
        raise CategoryNotLeafError(data.category_code)

    spu_code = data.spu_code or await _generate_spu_code(db, data.category_code)

    if (await db.execute(
        select(Product.id).where(Product.spu_code == spu_code, _not_deleted(Product))
    )).scalar_one_or_none():
        raise SpuCodeExistsError()

    source_lang = data.source_lang or "zh"
    # 交期范围校验
    _validate_lead_time_range(
        getattr(data, "lead_time_min", None),
        getattr(data, "lead_time_max", None),
    )

    product = Product(
        category_code=data.category_code,
        spu_code=spu_code,
        source_lang=source_lang,
        name_zh="",  # 占位,由 i18n_write 覆写
        hs_code=data.hs_code,
        certifications=data.certifications or [],
        unit=data.unit,
        currency=data.currency,
        is_featured=data.is_featured,
        supply_mode=getattr(data, "supply_mode", SupplyMode.SUPPLIER_DIRECT) or SupplyMode.SUPPLIER_DIRECT,
        # 物流参数（SPU 级）
        lead_time_min=getattr(data, "lead_time_min", None),
        lead_time_max=getattr(data, "lead_time_max", None),
        packing_quantity=getattr(data, "packing_quantity", None),
        gross_weight_kg=getattr(data, "gross_weight_kg", None),
        volume_cbm=getattr(data, "volume_cbm", None),
        can_consolidate=getattr(data, "can_consolidate", True),
        cargo_type=getattr(data, "cargo_type", None),
        status=ProductStatus.DRAFT,
        created_by=operator_id,
    )

    # i18n 字段写入(flush 前设好,避免 NOT NULL 约束)
    i18n_values = {
        "name": data.name,
        "description": data.description,
        "brand": data.brand,
        "origin": data.origin,
        "selling_points": data.selling_points,
    }
    for field, value in i18n_values.items():
        if value is not None:
            await apply_i18n_create(product, field, value, source_lang, domain="product")

    db.add(product)
    await db.flush()

    # SPU 级属性
    if data.attributes:
        tpl_map = await _load_template_map(db, data.category_code)
        await _add_attrs(
            db, product.id, data.attributes,
            template_map=tpl_map,
            category_code=data.category_code,
            expected_scope="SPU",
        )

    await db.commit()
    await db.refresh(product)
    return product


async def update_product(
    db: AsyncSession, product_id: int, data: ProductUpdate,
    *, operator_id: int | None = None,
) -> Product:
    product = await _get_product_or_404(db, product_id)

    # 状态机：ACTIVE 不可编辑，需先下架
    if product.status not in ProductStatus.EDITABLE:
        raise ProductNotEditableError(product.status)

    # 交期范围校验（有值时）
    lead_min = data.lead_time_min if data.lead_time_min is not None else product.lead_time_min
    lead_max = data.lead_time_max if data.lead_time_max is not None else product.lead_time_max
    _validate_lead_time_range(lead_min, lead_max)

    source_lang = product.source_lang

    update_data = data.model_dump(exclude_unset=True, exclude={"attributes"})
    i18n_fields_to_update = {}

    # 分离 i18n 字段和普通字段
    for field in list(update_data.keys()):
        if field in _PRODUCT_I18N_FIELDS:
            i18n_fields_to_update[field] = update_data.pop(field)

    # 普通字段直接赋值
    for field, value in update_data.items():
        setattr(product, field, value)

    # i18n 字段走 apply_i18n_edit
    for field, value in i18n_fields_to_update.items():
        if value is not None:
            old_value = getattr(product, f"{field}_{source_lang}", None)
            await apply_i18n_edit(product, field, source_lang, value, old_value, domain="product")

    # SPU 级属性整体替换(硬删:属性随父级有效性过滤,编辑时可替换)
    if data.attributes is not None:
        await db.execute(
            sa_delete(ProductAttr).where(
                ProductAttr.product_id == product_id,
                ProductAttr.sku_id.is_(None),
            )
        )
        if data.attributes:
            tpl_map = await _load_template_map(db, product.category_code)
            await _add_attrs(
                db, product_id, data.attributes,
                template_map=tpl_map,
                category_code=product.category_code,
                expected_scope="SPU",
            )

    await db.commit()
    await db.refresh(product)
    return product


async def _load_template_map(
    db: AsyncSession, category_code: str,
) -> dict[str, "AttrTemplate"]:
    """加载品类(含祖先链)的属性模板,返回 {attr_key: template} 映射。"""
    templates = await get_attr_templates(db, category_code)
    return {t.attr_key: t for t in templates}


async def _add_attrs(
    db: AsyncSession,
    product_id: int,
    attrs: list,
    *,
    template_map: dict[str, "AttrTemplate"],
    category_code: str,
    expected_scope: str,
    sku_id: int | None = None,
) -> None:
    """添加属性,校验 attr_key ∈ 模板 + scope 一致性,unit/sort_order 从模板取。"""
    for attr in attrs:
        tpl = template_map.get(attr.attr_key)
        if tpl is None:
            if template_map:
                # 品类有模板定义,拒绝模板外的属性
                raise AttrKeyNotInTemplateError(attr.attr_key, category_code)
            # 品类无模板时仍保存属性,但无法填充 unit/sort_order/selectable
            logger.warning(
                "属性 '%s' 不在品类 '%s' 模板中(品类无模板),允许保存",
                attr.attr_key, category_code,
            )
            db.add(ProductAttr(
                product_id=product_id,
                sku_id=sku_id,
                attr_key_en=attr.attr_key,
                attr_value_en=attr.attr_value,
                source_lang="en",
                trans_meta={
                    "attr_key_en": "src",
                    "attr_key_zh": "pending",
                    "attr_key_sw": "pending",
                    "attr_value_en": "src",
                    "attr_value_zh": "pending",
                    "attr_value_sw": "pending",
                },
            ))
            continue
        if tpl.scope != expected_scope:
            raise AttrScopeMismatchError(attr.attr_key, tpl.scope)

        db.add(ProductAttr(
            product_id=product_id,
            sku_id=sku_id,
            attr_key_en=attr.attr_key,
            attr_value_en=attr.attr_value,
            attr_unit=tpl.attr_unit,
            sort_order=tpl.sort_order,
            selectable=tpl.selectable,
            source_lang="en",
            trans_meta={
                "attr_key_en": "src",
                "attr_key_zh": "pending",
                "attr_key_sw": "pending",
                "attr_value_en": "src",
                "attr_value_zh": "pending",
                "attr_value_sw": "pending",
            },
        ))


async def update_product_status(
    db: AsyncSession, product_id: int, new_status: str,
    *, skip_validation: bool = False,
) -> Product:
    if new_status not in ProductStatus.ALL:
        raise InvalidProductStatusError(new_status)

    product = await _get_product_or_404(db, product_id, load_relations=True)

    # 状态机校验：只允许合法转换
    if not ProductStatus.can_transition(product.status, new_status):
        raise IllegalTransitionError(product.status, new_status)

    # 上架校验(skip_validation=True 时跳过，用于批量测试)
    # errors 结构化：[{key, params}]，前端按 key 翻译
    if new_status == ProductStatus.ACTIVE and not skip_validation:
        errors: list[dict[str, object]] = []

        # ADR-0006 方案 C：不强制 SKU。上架只校验图片 + SPU 必填属性。
        # SKU 相关校验（价格/交期/SKU 必填属性）全部移除。
        # 如有 SKU 且数据不一致（如 price_min > price_max），由运营自行管理，不阻塞上架。

        # SPU 必填属性校验（仅 MANUAL 来源，爬虫数据不走模板）
        is_manual = (getattr(product, "source", "MANUAL") or "MANUAL") == "MANUAL"
        if is_manual:
            tpl_map = await _load_template_map(db, product.category_code)
            required_spu = [k for k, t in tpl_map.items() if t.is_required and t.scope == "SPU"]
            spu_attr_keys = {a.attr_key_en for a in product.attrs if a.sku_id is None}
            missing_spu = [k for k in required_spu if k not in spu_attr_keys]
            if missing_spu:
                errors.append({"key": "publish_missing_spu_attrs", "params": {"attrs": ", ".join(missing_spu)}})

        # ── 通用校验:所有来源都必须有图片 ──
        if not product.images:
            errors.append({"key": "publish_no_image"})

        if errors:
            raise PublishValidationFailedError(errors)

    product.status = new_status
    await db.commit()
    await db.refresh(product)
    return product


async def delete_product(db: AsyncSession, product_id: int, *, operator_id: int) -> None:
    product = await _get_product_or_404(db, product_id)
    if product.status not in ProductStatus.DELETABLE:
        raise OnlyDraftDeletableError()

    sd = _soft_delete_values(operator_id)

    # 级联删除子表
    sku_ids_q = select(ProductSku.id).where(
        ProductSku.product_id == product_id, _not_deleted(ProductSku),
    )
    # 阶梯价硬删(明细数据,随父级有效性)
    await db.execute(
        sa_delete(SkuPriceTier).where(SkuPriceTier.sku_id.in_(sku_ids_q))
    )
    # 供货关系软删
    await db.execute(
        update(ProductSupplier).where(
            ProductSupplier.sku_id.in_(sku_ids_q), _not_deleted(ProductSupplier),
        ).values(**sd)
    )
    # 属性硬删(明细数据,随父级有效性)
    await db.execute(
        sa_delete(ProductAttr).where(ProductAttr.product_id == product_id)
    )
    # SKU 本体软删
    await db.execute(
        update(ProductSku).where(
            ProductSku.product_id == product_id, _not_deleted(ProductSku),
        ).values(**sd)
    )
    # 图片软删
    await db.execute(
        update(ProductImage).where(
            ProductImage.product_id == product_id, _not_deleted(ProductImage),
        ).values(**sd)
    )
    # SPU 本体软删
    await _soft_delete_obj(product, operator_id)
    await db.commit()


async def get_product(db: AsyncSession, product_id: int) -> Product:
    return await _get_product_or_404(db, product_id, load_relations=True)


async def _batch_main_images(
    db: AsyncSession, product_ids: list[int],
) -> dict[int, str]:
    """批量查每个商品的主图 URL — DISTINCT ON 每个 product_id 只取一行。"""
    if not product_ids:
        return {}
    q = (
        select(ProductImage.product_id, ProductImage.image_key)
        .where(
            ProductImage.product_id.in_(product_ids),
            _not_deleted(ProductImage),
        )
        .order_by(
            ProductImage.product_id,
            (ProductImage.image_type != ImageType.MAIN).asc(),
            ProductImage.sort_order.asc(),
        )
        .distinct(ProductImage.product_id)
    )
    rows = (await db.execute(q)).all()
    base = settings.IMAGE_PATH_PREFIX
    return {pid: f"{base}/{key}" for pid, key in rows}


def _build_keyword_filter(keyword: str):
    """按当前请求 locale 构建 keyword 搜索过滤（名称 + 品牌 + SPU 编码）。"""
    kw = f"%{keyword}%"
    locale = get_current_locale()
    name_col = getattr(Product, f"name_{locale}", Product.name_en)
    return or_(
        name_col.ilike(kw),
        Product.brand_zh.ilike(kw),
        Product.spu_code.ilike(kw),
    )


async def list_products_operator(
    db: AsyncSession,
    *,
    category_code: str | None = None,
    status: str | None = None,
    supply_mode: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Product], int, dict[int, str]]:
    # 列表只需 SKU（价格汇总+计数），不加载全部图片（批量查主图）
    q = select(Product).options(
        selectinload(Product.skus.and_(_not_deleted(ProductSku))),
    ).where(_not_deleted(Product))
    count_q = select(func.count(Product.id)).where(_not_deleted(Product))

    if category_code:
        codes = await _descendant_category_codes(db, category_code)
        q = q.where(Product.category_code.in_(codes))
        count_q = count_q.where(Product.category_code.in_(codes))
    if status:
        q = q.where(Product.status == status)
        count_q = count_q.where(Product.status == status)
    if supply_mode:
        q = q.where(Product.supply_mode == supply_mode)
        count_q = count_q.where(Product.supply_mode == supply_mode)
    if keyword:
        kf = _build_keyword_filter(keyword)
        q = q.where(kf)
        count_q = count_q.where(kf)

    total = (await db.execute(count_q)).scalar() or 0
    q = q.order_by(Product.created_at.desc()).offset((page - 1) * size).limit(size)
    rows = (await db.execute(q)).scalars().all()
    products = list(rows)
    main_image_map = await _batch_main_images(db, [p.id for p in products])
    return products, total, main_image_map


async def list_products_public(
    db: AsyncSession,
    *,
    category_code: str | None = None,
    category_codes: list[str] | None = None,
    featured: bool | None = None,
    supply_mode: str | None = None,
    certification: str | None = None,
    brand: str | None = None,
    keyword: str | None = None,
    sort: str = "newest",
    page: int = 1,
    size: int = 20,
) -> tuple[list[Product], int, dict[int, str]]:
    # 列表不加载图片关系，主图由 _batch_main_images 批量查
    q = select(Product).where(Product.status == ProductStatus.ACTIVE, _not_deleted(Product))
    count_q = select(func.count(Product.id)).where(Product.status == ProductStatus.ACTIVE, _not_deleted(Product))

    if category_code:
        codes = await _descendant_category_codes(db, category_code)
        q = q.where(Product.category_code.in_(codes))
        count_q = count_q.where(Product.category_code.in_(codes))
    elif category_codes:
        # 浏览偏好:多个一级品类 → 展开全部后代
        all_desc: list[str] = []
        for cc in category_codes:
            all_desc.extend(await _descendant_category_codes(db, cc))
        if all_desc:
            q = q.where(Product.category_code.in_(all_desc))
            count_q = count_q.where(Product.category_code.in_(all_desc))
    if featured is not None:
        q = q.where(Product.is_featured == featured)
        count_q = count_q.where(Product.is_featured == featured)
    if supply_mode:
        q = q.where(Product.supply_mode == supply_mode)
        count_q = count_q.where(Product.supply_mode == supply_mode)
    if brand:
        brand_col = _brand_col_by_locale()
        brand_list = [b.strip() for b in brand.split(",") if b.strip()]
        if len(brand_list) == 1:
            brand_filter = brand_col == brand_list[0]
        else:
            brand_filter = brand_col.in_(brand_list)
        q = q.where(brand_filter)
        count_q = count_q.where(brand_filter)
    if certification:
        # certifications::jsonb @> jsonb_build_array('CE')
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import JSONB
        cert_filter = cast(Product.certifications, JSONB).op("@>")(
            func.jsonb_build_array(certification)
        )
        q = q.where(cert_filter)
        count_q = count_q.where(cert_filter)
    if keyword:
        kf = _build_keyword_filter(keyword)
        q = q.where(kf)
        count_q = count_q.where(kf)

    # 排序分支
    if sort in ("price_asc", "price_desc"):
        # 子查询：每个 SPU 的 active SKU 最低价
        price_sub = (
            select(
                ProductSku.product_id,
                func.min(ProductSku.price_min).label("min_price"),
            )
            .where(ProductSku.status == SkuStatus.ACTIVE, _not_deleted(ProductSku))
            .group_by(ProductSku.product_id)
            .subquery()
        )
        q = q.outerjoin(price_sub, Product.id == price_sub.c.product_id)
        if sort == "price_asc":
            q = q.order_by(price_sub.c.min_price.asc().nulls_last())
        else:
            q = q.order_by(price_sub.c.min_price.desc().nulls_last())
    else:
        q = q.order_by(Product.created_at.desc())

    total = (await db.execute(count_q)).scalar() or 0
    q = q.offset((page - 1) * size).limit(size)
    rows = (await db.execute(q)).scalars().all()
    products = list(rows)
    main_image_map = await _batch_main_images(db, [p.id for p in products])
    return products, total, main_image_map


async def sample_home_floor_products(
    db: AsyncSession,
    *,
    category_paths: list[list[str]],
    exclude_category_paths: list[list[str]] | None = None,
    size: int = 8,
) -> tuple[list[Product], dict[int, str], list[Category]]:
    """首页楼层选品:按分类中文路径解析当前环境 code,每个展示类目最多 1 个 SPU。"""
    if not category_paths or size <= 0:
        return [], {}, []

    display_categories = await _resolve_home_floor_display_categories(
        db,
        category_paths=category_paths,
        exclude_category_paths=exclude_category_paths or [],
    )

    if not display_categories:
        return [], {}, display_categories

    # 批量获取所有展示品类的后代 code（1 次查询合并所有品类）
    all_parent_codes = [c.code for c in display_categories]
    # 建立 L2 code → 后代 codes 的映射
    cat_to_descendants: dict[str, list[str]] = {c: [c] for c in all_parent_codes}
    current_layer = list(all_parent_codes)
    while current_layer:
        rows = (await db.execute(
            select(Category.code, Category.parent_code).where(
                Category.parent_code.in_(current_layer)
            )
        )).all()
        if not rows:
            break
        next_layer = []
        for child_code, parent_code in rows:
            # 找到这个 child 归属哪个顶层展示品类
            for top_code in all_parent_codes:
                if parent_code in cat_to_descendants.get(top_code, []):
                    cat_to_descendants[top_code].append(child_code)
                    break
            next_layer.append(child_code)
        current_layer = next_layer

    # 合并所有后代 code，一条 SQL 查出候选商品
    all_codes = []
    code_to_cat: dict[str, str] = {}  # product.category_code → 归属的展示品类 code
    for cat_code, descendants in cat_to_descendants.items():
        for d in descendants:
            all_codes.append(d)
            code_to_cat[d] = cat_code

    if not all_codes:
        return [], {}, display_categories

    # 一条 SQL 查出所有候选商品，按展示品类分组取最新
    all_candidates_stmt = (
        select(Product)
        .where(
            Product.status == ProductStatus.ACTIVE,
            _not_deleted(Product),
            Product.category_code.in_(all_codes),
        )
        .order_by(Product.created_at.desc(), Product.id.desc())
    )
    all_candidates = (await db.execute(all_candidates_stmt)).scalars().all()

    # 按展示品类分组，每个品类取第 1 个（最新的）
    selected: list[Product] = []
    seen_cats: set[str] = set()
    seen_ids: set[int] = set()
    for product in all_candidates:
        top_cat = code_to_cat.get(product.category_code)
        if not top_cat or top_cat in seen_cats or product.id in seen_ids:
            continue
        selected.append(product)
        seen_cats.add(top_cat)
        seen_ids.add(product.id)
        if len(selected) >= size:
            break

    main_image_map = await _batch_main_images(db, [p.id for p in selected])
    return selected, main_image_map, display_categories


async def _resolve_category_path(
    db: AsyncSession,
    path: list[str],
) -> Category | None:
    """按 name_zh 路径解析分类，避免跨环境硬编码 code。"""
    parent_code: str | None = None
    category: Category | None = None
    for level, raw_name in enumerate(path, start=1):
        name = raw_name.strip()
        if not name:
            return None
        stmt = select(Category).where(
            Category.level == level,
            Category.name_zh == name,
            Category.is_active.is_(True),
        )
        if parent_code is None:
            stmt = stmt.where(Category.parent_code.is_(None))
        else:
            stmt = stmt.where(Category.parent_code == parent_code)
        category = (await db.execute(stmt.limit(1))).scalar_one_or_none()
        if category is None:
            return None
        parent_code = category.code
    return category


async def _resolve_home_floor_display_categories(
    db: AsyncSession,
    *,
    category_paths: list[list[str]],
    exclude_category_paths: list[list[str]],
) -> list[Category]:
    """楼层左侧入口/商品采样桶:配置到 L1 时展开 L2，配置到 L2/L3 时使用该节点。"""
    exclude_codes: set[str] = set()
    for path in exclude_category_paths:
        category = await _resolve_category_path(db, path)
        if category is not None:
            exclude_codes.add(category.code)

    resolved_roots: list[Category] = []
    seen_root_codes: set[str] = set()
    for path in category_paths:
        category = await _resolve_category_path(db, path)
        if category is None or category.code in seen_root_codes:
            continue
        resolved_roots.append(category)
        seen_root_codes.add(category.code)

    display_categories: list[Category] = []
    seen_codes: set[str] = set()
    for root in resolved_roots:
        if root.level == 1:
            children = (await db.execute(
                select(Category)
                .where(
                    Category.parent_code == root.code,
                    Category.level == 2,
                    Category.is_active.is_(True),
                )
                .order_by(Category.sort_order.asc(), Category.code.asc())
            )).scalars().all()
            candidates = list(children)
        else:
            candidates = [root]

        for category in candidates:
            if category.code in seen_codes or category.code in exclude_codes:
                continue
            display_categories.append(category)
            seen_codes.add(category.code)

    return display_categories


async def list_certification_options(db: AsyncSession) -> list[str]:
    """聚合所有上架商品的认证值，去重排序，用于筛选下拉。"""
    from sqlalchemy import text
    result = await db.execute(text(
        "SELECT DISTINCT cert "
        "FROM products, jsonb_array_elements_text(certifications::jsonb) AS cert "
        "WHERE status = 'ACTIVE' AND deleted_at IS NULL "
        "AND certifications IS NOT NULL "
        "ORDER BY cert"
    ))
    return [row[0] for row in result]


def _brand_col_by_locale():
    """按当前 locale 选择品牌列，sw 回退 en。"""
    locale = get_current_locale()
    if locale == "en":
        return func.coalesce(func.nullif(Product.brand_en, ''), Product.brand_zh)
    if locale == "sw":
        return func.coalesce(func.nullif(Product.brand_sw, ''), func.nullif(Product.brand_en, ''), Product.brand_zh)
    return Product.brand_zh


async def list_brand_options(
    db: AsyncSession,
    *,
    category_code: str | None = None,
    limit: int = 50,
) -> list[str]:
    """按商品数量降序返回 Top N 品牌（按当前 locale），用于筛选下拉。"""
    from sqlalchemy import func

    brand_col = _brand_col_by_locale()
    cnt = func.count().label("cnt")
    q = (
        select(brand_col, cnt)
        .where(Product.status == ProductStatus.ACTIVE, _not_deleted(Product))
        .where(brand_col.isnot(None), brand_col != "")
        .group_by(brand_col)
        .order_by(cnt.desc())
        .limit(limit)
    )
    if category_code:
        codes = await _descendant_category_codes(db, category_code)
        q = q.where(Product.category_code.in_(codes))
    rows = await db.execute(q)
    return [row[0] for row in rows]


# ── SKU CRUD ─────────────────────────────────────────────

async def create_sku(
    db: AsyncSession, product_id: int, data: SkuCreate,
) -> ProductSku:
    product = await _get_product_or_404(db, product_id)
    if product.status not in ProductStatus.EDITABLE:
        raise ProductNotEditableError(product.status)
    _validate_sku_ranges(
        data.price_min, data.price_max,
        data.lead_time_min, data.lead_time_max,
    )

    sku_code = data.sku_code or await _generate_sku_code(db, product.spu_code, product_id)

    if (await db.execute(
        select(ProductSku.id).where(ProductSku.sku_code == sku_code, _not_deleted(ProductSku))
    )).scalar_one_or_none():
        raise SkuCodeExistsError()

    # 默认 SKU 唯一性处理
    if data.is_default:
        await db.execute(
            update(ProductSku)
            .where(ProductSku.product_id == product_id, ProductSku.is_default.is_(True))
            .values(is_default=False)
        )

    source_lang = data.source_lang or "zh"
    sku = ProductSku(
        product_id=product_id,
        sku_code=sku_code,
        manufacturer_model=data.manufacturer_model,
        source_lang=source_lang,
        price_min=data.price_min,
        price_max=data.price_max,
        moq=data.moq,
        lead_time_min=data.lead_time_min,
        lead_time_max=data.lead_time_max,
        packing_quantity=data.packing_quantity,
        gross_weight_kg=data.gross_weight_kg,
        volume_cbm=data.volume_cbm,
        can_consolidate=data.can_consolidate,
        cargo_type=data.cargo_type,
        is_default=data.is_default,
        status=SkuStatus.ACTIVE,
    )

    # i18n 字段写入(flush 前设好)
    i18n_values = {"name": data.name, "color": data.color, "material": data.material}
    for field, value in i18n_values.items():
        if value is not None:
            await apply_i18n_create(sku, field, value, source_lang, domain="product")

    db.add(sku)
    await db.flush()

    # SKU 级属性
    if data.attributes:
        tpl_map = await _load_template_map(db, product.category_code)
        await _add_attrs(
            db, product_id, data.attributes,
            template_map=tpl_map,
            category_code=product.category_code,
            expected_scope="SKU",
            sku_id=sku.id,
        )

    # 阶梯价
    if data.price_tiers:
        await _replace_price_tiers(db, sku, data.price_tiers)

    await db.commit()
    await db.refresh(sku, ["price_tiers"])
    return sku


async def update_sku(
    db: AsyncSession, product_id: int, sku_id: int, data: SkuUpdate,
    *, operator_id: int | None = None,
) -> ProductSku:
    product = await _get_product_or_404(db, product_id)
    if product.status not in ProductStatus.EDITABLE:
        raise ProductNotEditableError(product.status)
    sku = await _get_sku_under_product_or_404(db, product_id, sku_id)
    source_lang = sku.source_lang

    # 默认 SKU 唯一性处理
    if data.is_default is True and not sku.is_default:
        await db.execute(
            update(ProductSku)
            .where(ProductSku.product_id == sku.product_id, ProductSku.is_default.is_(True))
            .values(is_default=False)
        )

    update_data = data.model_dump(exclude_unset=True, exclude={"price_tiers", "attributes"})
    i18n_fields_to_update = {}

    for field in list(update_data.keys()):
        if field in _SKU_I18N_FIELDS:
            i18n_fields_to_update[field] = update_data.pop(field)

    for field, value in update_data.items():
        setattr(sku, field, value)

    _validate_sku_ranges(
        sku.price_min, sku.price_max,
        sku.lead_time_min, sku.lead_time_max,
    )

    for field, value in i18n_fields_to_update.items():
        if value is not None:
            old_value = getattr(sku, f"{field}_{source_lang}", None)
            await apply_i18n_edit(sku, field, source_lang, value, old_value, domain="product")

    # SKU 级属性整体替换(硬删)
    if data.attributes is not None:
        await db.execute(
            sa_delete(ProductAttr).where(ProductAttr.sku_id == sku_id)
        )
        if data.attributes:
            product = await _get_product_or_404(db, product_id)
            tpl_map = await _load_template_map(db, product.category_code)
            await _add_attrs(
                db, sku.product_id, data.attributes,
                template_map=tpl_map,
                category_code=product.category_code,
                expected_scope="SKU",
                sku_id=sku_id,
            )

    # 阶梯价整体替换
    if data.price_tiers is not None:
        await _replace_price_tiers(db, sku, data.price_tiers, operator_id=operator_id)

    await db.commit()
    await db.refresh(sku, ["price_tiers"])
    return sku


async def update_sku_status(
    db: AsyncSession, product_id: int, sku_id: int, new_status: str,
) -> dict:
    """SKU 状态切换是运营操作，ACTIVE 商品下也允许（如缺货停售）。
    SPU 状态只通过商品状态机显式变更，SKU 停用不连带下架 SPU。
    """
    if new_status not in SkuStatus.ALL:
        raise InvalidProductStatusError(new_status)
    product = await _get_product_or_404(db, product_id, load_relations=True)
    sku = await _get_sku_under_product_or_404(db, product_id, sku_id)
    if sku.status == new_status:
        return {"sku": sku}

    sku.status = new_status

    await db.commit()
    await db.refresh(sku)
    return {"sku": sku}


async def delete_sku(db: AsyncSession, product_id: int, sku_id: int, *, operator_id: int) -> None:
    product = await _get_product_or_404(db, product_id, load_relations=True)
    if product.status not in ProductStatus.EDITABLE:
        raise ProductNotEditableError(product.status)
    sku = await _get_sku_under_product_or_404(db, product_id, sku_id)

    sd = _soft_delete_values(operator_id)

    # 级联删除子表
    # 阶梯价/属性硬删(明细数据)
    await db.execute(
        sa_delete(SkuPriceTier).where(SkuPriceTier.sku_id == sku_id)
    )
    await db.execute(
        sa_delete(ProductAttr).where(ProductAttr.sku_id == sku_id)
    )
    # 供货关系软删
    await db.execute(
        update(ProductSupplier).where(
            ProductSupplier.sku_id == sku_id, _not_deleted(ProductSupplier),
        ).values(**sd)
    )
    await _soft_delete_obj(sku, operator_id)

    # 删除最后一个在售 SKU 时自动下架商品
    remaining_active = [
        s for s in product.skus
        if s.id != sku_id and s.status == SkuStatus.ACTIVE and s.deleted_at is None
    ]
    if not remaining_active and product.status == ProductStatus.ACTIVE:
        product.status = ProductStatus.INACTIVE

    await db.commit()


async def list_skus(
    db: AsyncSession, product_id: int,
) -> list[ProductSku]:
    await _get_product_or_404(db, product_id)
    q = (
        select(ProductSku)
        .options(
            selectinload(ProductSku.price_tiers),
            selectinload(ProductSku.images.and_(_not_deleted(ProductImage))),
            selectinload(ProductSku.supplier_relations.and_(_not_deleted(ProductSupplier))),
        )
        .where(ProductSku.product_id == product_id, _not_deleted(ProductSku))
        .order_by(ProductSku.is_default.desc(), ProductSku.created_at)
    )
    rows = (await db.execute(q)).scalars().all()
    return list(rows)


async def get_sku(db: AsyncSession, sku_id: int) -> ProductSku:
    return await _get_sku_or_404(db, sku_id, load_relations=True)


# ── 阶梯价校验 + 整体替换 ────────────────────────────────

def _validate_price_tiers(tiers: list[PriceTierCreate], moq: int) -> None:
    if not tiers:
        return

    sorted_tiers = sorted(tiers, key=lambda t: t.min_qty)

    if sorted_tiers[0].min_qty != moq:
        raise PriceTierInvalidError(
            f"First tier min_qty must equal SKU moq ({moq})",
            message_key=MessageKey.PRODUCT_PRICE_TIER_FIRST_MIN_QTY,
            message_params={"moq": moq},
        )

    for i, tier in enumerate(sorted_tiers):
        if i > 0:
            prev = sorted_tiers[i - 1]
            if prev.max_qty is None:
                raise PriceTierInvalidError(
                    "Only the last tier can have max_qty=null",
                    message_key=MessageKey.PRODUCT_PRICE_TIER_MAX_NULL_NOT_LAST,
                )
            if prev.max_qty + 1 != tier.min_qty:
                raise PriceTierInvalidError(
                    f"Tiers must be continuous: tier {i} min_qty should be "
                    f"{prev.max_qty + 1}, got {tier.min_qty}",
                    message_key=MessageKey.PRODUCT_PRICE_TIER_NOT_CONTINUOUS,
                    message_params={"tier": i, "expected": prev.max_qty + 1, "actual": tier.min_qty},
                )

        if i > 0:
            if tier.unit_price >= sorted_tiers[i - 1].unit_price:
                raise PriceTierInvalidError(
                    f"unit_price must decrease: tier {i} "
                    f"({tier.unit_price}) >= tier {i-1} "
                    f"({sorted_tiers[i-1].unit_price})",
                    message_key=MessageKey.PRODUCT_PRICE_TIER_PRICE_NOT_DECREASING,
                    message_params={"tier": i, "price": str(tier.unit_price), "prev_price": str(sorted_tiers[i-1].unit_price)},
                )

        if i < len(sorted_tiers) - 1 and tier.max_qty is None:
            raise PriceTierInvalidError(
                "Only the last tier can have max_qty=null",
                message_key=MessageKey.PRODUCT_PRICE_TIER_MAX_NULL_NOT_LAST,
            )


def _validate_lead_time_range(
    lead_time_min: int | None,
    lead_time_max: int | None,
) -> None:
    """校验交期区间: min <= max。"""
    if (
        lead_time_min is not None
        and lead_time_max is not None
        and lead_time_min > lead_time_max
    ):
        raise ProductRangeInvalidError("lead_time_min", "lead_time_max")


def _validate_sku_ranges(
    price_min,
    price_max,
    lead_time_min: int | None,
    lead_time_max: int | None,
) -> None:
    """校验 SKU 数值区间本身合法,不判断商业合理性。"""
    if price_min is not None and price_max is not None and price_min > price_max:
        raise ProductRangeInvalidError("price_min", "price_max")
    _validate_lead_time_range(lead_time_min, lead_time_max)


async def _replace_price_tiers(
    db: AsyncSession,
    sku: ProductSku,
    tiers: list[PriceTierCreate],
    *, operator_id: int | None = None,
) -> None:
    _validate_price_tiers(tiers, sku.moq)

    await db.execute(
        sa_delete(SkuPriceTier).where(SkuPriceTier.sku_id == sku.id)
    )
    for t in tiers:
        db.add(SkuPriceTier(
            sku_id=sku.id,
            min_qty=t.min_qty,
            max_qty=t.max_qty,
            unit_price=t.unit_price,
            currency=t.currency,
            label=t.label,
        ))


# ── 供货关系（挂 SKU）────────────────────────────────────

async def add_sku_supplier(
    db: AsyncSession, product_id: int, sku_id: int, data: SupplierRelationCreate,
) -> ProductSupplier:
    await _get_sku_under_product_or_404(db, product_id, sku_id)

    if (await db.execute(
        select(ProductSupplier.id).where(
            ProductSupplier.sku_id == sku_id,
            ProductSupplier.supplier_org_id == data.supplier_org_id,
            _not_deleted(ProductSupplier),
        )
    )).scalar_one_or_none():
        raise SupplierAlreadyBoundError()

    if not (await db.execute(
        select(SupplierOrganization.id).where(
            SupplierOrganization.id == data.supplier_org_id
        )
    )).scalar_one_or_none():
        raise NotFoundError("Supplier organization not found")

    ps = ProductSupplier(
        sku_id=sku_id,
        supplier_org_id=data.supplier_org_id,
        supplier_price=data.supplier_price,
        supplier_currency=data.supplier_currency,
        cif_price_usd=data.cif_price_usd,
        supplier_moq=data.supplier_moq,
        supplier_lead_time_days=data.supplier_lead_time_days,
        pvoc_status=data.pvoc_status,
        has_coc=data.has_coc,
        is_preferred=data.is_preferred,
        notes=data.notes,
    )
    db.add(ps)
    await db.commit()
    await db.refresh(ps)
    return ps


async def update_sku_supplier(
    db: AsyncSession, product_id: int, sku_id: int, ps_id: int, data: SupplierRelationUpdate,
) -> ProductSupplier:
    await _get_sku_under_product_or_404(db, product_id, sku_id)
    ps = await _get_supplier_relation_under_sku_or_404(db, sku_id, ps_id)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(ps, field, value)

    await db.commit()
    await db.refresh(ps)
    return ps


async def remove_sku_supplier(
    db: AsyncSession, product_id: int, sku_id: int, ps_id: int,
    *, operator_id: int,
) -> None:
    await _get_sku_under_product_or_404(db, product_id, sku_id)
    ps = await _get_supplier_relation_under_sku_or_404(db, sku_id, ps_id)
    await _soft_delete_obj(ps, operator_id)
    await db.commit()


async def list_sku_suppliers(
    db: AsyncSession, product_id: int, sku_id: int,
) -> list[dict]:
    await _get_sku_under_product_or_404(db, product_id, sku_id)
    q = (
        select(ProductSupplier, SupplierOrganization.name)
        .join(
            SupplierOrganization,
            ProductSupplier.supplier_org_id == SupplierOrganization.id,
            isouter=True,
        )
        .where(ProductSupplier.sku_id == sku_id, _not_deleted(ProductSupplier))
        .order_by(ProductSupplier.is_preferred.desc(), ProductSupplier.created_at)
    )
    rows = (await db.execute(q)).all()
    result = []
    for ps, org_name in rows:
        result.append({
            "id": ps.id,
            "sku_id": ps.sku_id,
            "supplier_org_id": ps.supplier_org_id,
            "supplier_org_name": org_name or "",
            "supplier_price": ps.supplier_price,
            "supplier_currency": ps.supplier_currency,
            "cif_price_usd": ps.cif_price_usd,
            "supplier_moq": ps.supplier_moq,
            "supplier_lead_time_days": ps.supplier_lead_time_days,
            "pvoc_status": ps.pvoc_status,
            "has_coc": ps.has_coc,
            "is_preferred": ps.is_preferred,
            "notes": ps.notes,
            "created_at": ps.created_at,
            "updated_at": ps.updated_at,
        })
    return result


# ── 图片（SPU + SKU 维度）────────────────────────────────



async def add_product_image(
    db: AsyncSession,
    product_id: int,
    file: UploadFile,
    image_type: str = "GALLERY",
    sku_id: int | None = None,
) -> ProductImage:
    product = await _get_product_or_404(db, product_id, load_relations=True)

    # 图片写操作受商品可编辑状态约束
    if product.status not in ProductStatus.EDITABLE:
        raise ProductNotEditableError(product.status)

    if sku_id is not None:
        sku_exists = any(s.id == sku_id for s in product.skus)
        if not sku_exists:
            raise NotFoundError("SKU not found under this product")

    if len(product.images) >= MAX_IMAGES_PER_PRODUCT:
        raise MaxImagesExceededError(MAX_IMAGES_PER_PRODUCT)

    # 前置校验用商品专属错误码,避免公共函数抛买方错误码
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ImageFormatInvalidError(", ".join(ALLOWED_EXTENSIONS))

    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise ImageTooLargeError()

    # 使用公共图片处理函数,square=True 保持商品图正方形裁剪行为
    image_key, img_w, img_h, file_size = save_uploaded_image(
        content, file.filename or "image.jpg", f"products/{product_id}", square=True,
    )

    actual_type = image_type if image_type in ImageType.ALL else ImageType.GALLERY
    if not product.images:
        actual_type = ImageType.MAIN

    next_sort = len(product.images)
    img = ProductImage(
        product_id=product_id,
        sku_id=sku_id,
        image_key=image_key,
        image_type=actual_type,
        sort_order=next_sort,
        width=img_w,
        height=img_h,
        file_size=file_size,
    )
    db.add(img)
    await db.commit()
    await db.refresh(img)
    return img


async def set_main_image(db: AsyncSession, product_id: int, image_id: int) -> None:
    product = await _get_product_or_404(db, product_id)

    if product.status not in ProductStatus.EDITABLE:
        raise ProductNotEditableError(product.status)

    await db.execute(
        update(ProductImage)
        .where(ProductImage.product_id == product_id, ProductImage.image_type == ImageType.MAIN, _not_deleted(ProductImage))
        .values(image_type=ImageType.GALLERY)
    )
    result = await db.execute(
        update(ProductImage)
        .where(ProductImage.id == image_id, ProductImage.product_id == product_id, _not_deleted(ProductImage))
        .values(image_type=ImageType.MAIN)
    )
    if result.rowcount == 0:
        raise NotFoundError("Image not found")
    await db.commit()


async def delete_product_image(db: AsyncSession, product_id: int, image_id: int, *, operator_id: int) -> None:
    # 校验商品可编辑状态
    product = await _get_product_or_404(db, product_id)
    if product.status not in ProductStatus.EDITABLE:
        raise ProductNotEditableError(product.status)

    # 同时校验图片归属
    row = await db.execute(
        select(ProductImage).where(
            ProductImage.id == image_id,
            ProductImage.product_id == product_id,
            _not_deleted(ProductImage),
        )
    )
    img = row.scalar_one_or_none()
    if not img:
        raise NotFoundError("Image not found")

    # TODO: 图片文件延迟清理任务待实现
    await _soft_delete_obj(img, operator_id)
    await db.commit()


async def update_image_sort(
    db: AsyncSession, product_id: int, image_ids: list[int],
) -> None:
    product = await _get_product_or_404(db, product_id)
    if product.status not in ProductStatus.EDITABLE:
        raise ProductNotEditableError(product.status)

    for idx, img_id in enumerate(image_ids):
        await db.execute(
            update(ProductImage)
            .where(ProductImage.id == img_id, ProductImage.product_id == product_id)
            .values(sort_order=idx)
        )
    await db.commit()


# ── 属性模板 ─────────────────────────────────────────────

async def _resolve_ancestor_codes(
    db: AsyncSession, category_code: str,
) -> list[tuple[str, int]]:
    """沿 parent_code 上溯,返回 [(code, level), ...],叶→根,最多 3 级。"""
    chain: list[tuple[str, int]] = []
    current_code: str | None = category_code
    for _ in range(3):
        if current_code is None:
            break
        row = (await db.execute(
            select(Category.code, Category.level, Category.parent_code)
            .where(Category.code == current_code)
        )).one_or_none()
        if row is None:
            break
        chain.append((row.code, row.level))
        current_code = row.parent_code
    return chain


async def get_attr_templates(
    db: AsyncSession, category_code: str,
) -> list[AttrTemplate]:
    chain = await _resolve_ancestor_codes(db, category_code)
    if not chain:
        return []

    ancestor_codes = [code for code, _ in chain]
    code_to_level = {code: level for code, level in chain}

    q = (
        select(AttrTemplate)
        .where(AttrTemplate.category_code.in_(ancestor_codes))
    )
    all_templates = (await db.execute(q)).scalars().all()

    # 按 attr_key 去重:同一 key 取最深(level 最大)的一条
    best: dict[str, AttrTemplate] = {}
    for t in all_templates:
        t_level = code_to_level.get(t.category_code, 0)
        existing = best.get(t.attr_key)
        if existing is None or t_level > code_to_level.get(existing.category_code, 0):
            best[t.attr_key] = t

    # 排序:按所属分类 level 升序(L1→L2→L3),同级按 sort_order 升序
    result = sorted(
        best.values(),
        key=lambda t: (code_to_level.get(t.category_code, 0), t.sort_order),
    )
    return result


# ── 聚合保存（单事务）────────────────────────────────────


async def create_product_aggregate(
    db: AsyncSession,
    data,  # ProductAggregateCreate schema
    *,
    actor_id: int,
    actor_email: str,
    request=None,
) -> Product:
    """单事务内建 SPU + 全部 SKU（含属性、阶梯价）+ 图片引用。

    service 持 commit；审计以 commit=False 写入，与业务写共用同一次 commit。
    """
    # 品类校验(直接读 is_leaf 字段,不再子查询)
    cat = (await db.execute(
        select(Category).where(Category.code == data.category_code)
    )).scalar_one_or_none()
    if not cat:
        raise NotFoundError("Category not found")
    if not cat.is_leaf:
        raise CategoryNotLeafError(data.category_code)

    spu_code = data.spu_code or await _generate_spu_code(db, data.category_code)
    if (await db.execute(
        select(Product.id).where(Product.spu_code == spu_code, _not_deleted(Product))
    )).scalar_one_or_none():
        raise SpuCodeExistsError()

    source_lang = data.source_lang or "zh"

    # 交期范围校验
    _validate_lead_time_range(
        getattr(data, "lead_time_min", None),
        getattr(data, "lead_time_max", None),
    )

    product = Product(
        category_code=data.category_code,
        spu_code=spu_code,
        source_lang=source_lang,
        name_zh="",
        hs_code=data.hs_code,
        certifications=data.certifications or [],
        unit=data.unit,
        currency=data.currency,
        is_featured=data.is_featured,
        supply_mode=getattr(data, "supply_mode", SupplyMode.SUPPLIER_DIRECT) or SupplyMode.SUPPLIER_DIRECT,
        # 物流参数（SPU 级）
        lead_time_min=getattr(data, "lead_time_min", None),
        lead_time_max=getattr(data, "lead_time_max", None),
        packing_quantity=getattr(data, "packing_quantity", None),
        gross_weight_kg=getattr(data, "gross_weight_kg", None),
        volume_cbm=getattr(data, "volume_cbm", None),
        can_consolidate=getattr(data, "can_consolidate", True),
        cargo_type=getattr(data, "cargo_type", None),
        status=ProductStatus.DRAFT,
        created_by=actor_id,
    )

    # i18n 字段
    for field in _PRODUCT_I18N_FIELDS:
        value = getattr(data, field, None)
        if value is not None:
            await apply_i18n_create(product, field, value, source_lang, domain="product")

    db.add(product)
    await db.flush()  # 拿 product.id

    # SPU 级属性
    tpl_map = await _load_template_map(db, data.category_code)
    if data.attributes:
        await _add_attrs(
            db, product.id, data.attributes,
            template_map=tpl_map,
            category_code=data.category_code,
            expected_scope="SPU",
        )

    # 批量建 SKU，收集 client_id → sku 映射
    sku_mappings: list[dict] = []
    for sku_data in (data.skus or []):
        sku = await _create_sku_in_aggregate(
            db, product, sku_data, tpl_map=tpl_map, source_lang=source_lang,
        )
        sku_mappings.append({
            "client_id": getattr(sku_data, "client_id", None),
            "id": sku.id,
            "sku_code": sku.sku_code,
        })

    # 图片引用
    if data.images:
        await _apply_image_refs(db, product.id, data.images)

    # 审计同事务
    await write_audit(
        db,
        resource_type=AuditResourceType.PRODUCT,
        action=AuditAction.CREATE,
        user_id=actor_id,
        user_email=actor_email,
        resource_id=product.id,
        request=request,
        extra={"sku_count": len(data.skus or [])},
        commit=False,
    )

    await db.commit()
    await db.refresh(product)
    return {"product": product, "sku_mappings": sku_mappings}


async def save_product_aggregate(
    db: AsyncSession,
    product_id: int,
    data,  # ProductAggregateSave schema
    *,
    actor_id: int,
    actor_email: str,
    request=None,
) -> Product:
    """单事务内更新 SPU + SKU diff（增/改/删）+ 图片引用。

    入参是「期望完整态」,服务端 diff 出变更并应用。
    """
    product = await _get_product_or_404(db, product_id, load_relations=True)
    if product.status not in ProductStatus.EDITABLE:
        raise ProductNotEditableError(product.status)

    source_lang = product.source_lang

    # ── 更新 SPU 字段 ──
    spu_update_fields = {}
    for field in _PRODUCT_I18N_FIELDS:
        value = getattr(data, field, None)
        if value is not None:
            old_value = getattr(product, f"{field}_{source_lang}", None)
            await apply_i18n_edit(product, field, source_lang, value, old_value, domain="product")

    _SPU_PLAIN_FIELDS = (
        "hs_code", "certifications", "is_featured", "supply_mode", "unit", "currency",
        "lead_time_min", "lead_time_max", "packing_quantity",
        "gross_weight_kg", "volume_cbm", "can_consolidate", "cargo_type",
    )
    for field in _SPU_PLAIN_FIELDS:
        value = getattr(data, field, None)
        if value is not None:
            setattr(product, field, value)

    # 交期范围校验（合并新旧值后校验）
    _validate_lead_time_range(product.lead_time_min, product.lead_time_max)

    # SPU 级属性整体替换(硬删)
    if data.attributes is not None:
        await db.execute(
            sa_delete(ProductAttr).where(
                ProductAttr.product_id == product_id,
                ProductAttr.sku_id.is_(None),
            )
        )
        tpl_map = await _load_template_map(db, product.category_code)
        if data.attributes:
            await _add_attrs(
                db, product_id, data.attributes,
                template_map=tpl_map,
                category_code=product.category_code,
                expected_scope="SPU",
            )
    else:
        tpl_map = await _load_template_map(db, product.category_code)

    # ── SKU diff ──
    # skus=None 表示不修改 SKU；skus=[] 表示删掉所有 SKU
    change_summary = {"added": 0, "updated": 0, "deleted": 0}

    if data.skus is not None:
        existing_skus = {s.id: s for s in product.skus}
        incoming_ids = set()

        for sku_data in data.skus:
            if sku_data.id is not None and sku_data.id in existing_skus:
                # 更新已有 SKU
                await _update_sku_in_aggregate(
                    db, product, existing_skus[sku_data.id], sku_data,
                    tpl_map=tpl_map, operator_id=actor_id,
                )
                incoming_ids.add(sku_data.id)
                change_summary["updated"] += 1
            elif sku_data.id is not None:
                # 带 id 但不属于本商品 → 拒绝（与逐实体 update_sku 行为一致）
                raise NotFoundError("SKU not found")
            else:
                # 不带 id → 新建 SKU
                await _create_sku_in_aggregate(
                    db, product, sku_data, tpl_map=tpl_map, source_lang=source_lang,
                )
                change_summary["added"] += 1

        # 删除不在入参中的 SKU（阶梯价/属性硬删,供货关系/SKU 软删）
        sd = _soft_delete_values(actor_id)
        for sku_id, sku in existing_skus.items():
            if sku_id not in incoming_ids:
                await db.execute(
                    sa_delete(SkuPriceTier).where(SkuPriceTier.sku_id == sku_id)
                )
                await db.execute(
                    sa_delete(ProductAttr).where(ProductAttr.sku_id == sku_id)
                )
                await db.execute(
                    update(ProductSupplier).where(
                        ProductSupplier.sku_id == sku_id, _not_deleted(ProductSupplier),
                    ).values(**sd)
                )
                await _soft_delete_obj(sku, actor_id)
                change_summary["deleted"] += 1

    # ── 图片引用 ──
    if data.images is not None:
        await _apply_image_refs(db, product_id, data.images)

    # 审计同事务
    await write_audit(
        db,
        resource_type=AuditResourceType.PRODUCT,
        action=AuditAction.UPDATE,
        user_id=actor_id,
        user_email=actor_email,
        resource_id=product_id,
        request=request,
        extra=change_summary,
        commit=False,
    )

    await db.commit()
    await db.refresh(product)
    return product


async def _create_sku_in_aggregate(
    db: AsyncSession,
    product: Product,
    sku_data,
    *,
    tpl_map: dict[str, "AttrTemplate"],
    source_lang: str,
) -> ProductSku:
    """聚合事务内创建单个 SKU（含属性、阶梯价），不 commit。"""
    _validate_sku_ranges(
        sku_data.price_min, sku_data.price_max,
        sku_data.lead_time_min, sku_data.lead_time_max,
    )

    sku_code = await _generate_sku_code(db, product.spu_code, product.id)

    sku_source_lang = getattr(sku_data, "source_lang", None) or source_lang
    sku = ProductSku(
        product_id=product.id,
        sku_code=sku_code,
        manufacturer_model=sku_data.manufacturer_model,
        source_lang=sku_source_lang,
        price_min=sku_data.price_min,
        price_max=sku_data.price_max,
        moq=sku_data.moq,
        lead_time_min=sku_data.lead_time_min,
        lead_time_max=sku_data.lead_time_max,
        packing_quantity=sku_data.packing_quantity,
        gross_weight_kg=sku_data.gross_weight_kg,
        volume_cbm=sku_data.volume_cbm,
        can_consolidate=sku_data.can_consolidate,
        cargo_type=sku_data.cargo_type,
        is_default=sku_data.is_default,
        status=SkuStatus.ACTIVE,
    )

    for field in _SKU_I18N_FIELDS:
        value = getattr(sku_data, field, None)
        if value is not None:
            await apply_i18n_create(sku, field, value, sku_source_lang, domain="product")

    # 默认 SKU 唯一性
    if sku_data.is_default:
        await db.execute(
            update(ProductSku)
            .where(ProductSku.product_id == product.id, ProductSku.is_default.is_(True))
            .values(is_default=False)
        )

    db.add(sku)
    await db.flush()  # 拿 sku.id

    if sku_data.attributes:
        await _add_attrs(
            db, product.id, sku_data.attributes,
            template_map=tpl_map,
            category_code=product.category_code,
            expected_scope="SKU",
            sku_id=sku.id,
        )

    if sku_data.price_tiers:
        await _replace_price_tiers(db, sku, sku_data.price_tiers)

    return sku


async def _update_sku_in_aggregate(
    db: AsyncSession,
    product: Product,
    sku: ProductSku,
    sku_data,
    *,
    tpl_map: dict[str, "AttrTemplate"],
    operator_id: int | None = None,
) -> ProductSku:
    """聚合事务内更新单个 SKU（含属性、阶梯价），不 commit。"""
    source_lang = sku.source_lang

    # 默认 SKU 唯一性
    if getattr(sku_data, "is_default", False) and not sku.is_default:
        await db.execute(
            update(ProductSku)
            .where(ProductSku.product_id == product.id, ProductSku.is_default.is_(True))
            .values(is_default=False)
        )

    # 普通字段
    plain_fields = (
        "manufacturer_model", "price_min", "price_max",
        "moq", "lead_time_min", "lead_time_max", "packing_quantity",
        "gross_weight_kg", "volume_cbm", "can_consolidate", "cargo_type",
        "is_default",
    )
    for field in plain_fields:
        value = getattr(sku_data, field, None)
        if value is not None:
            setattr(sku, field, value)

    _validate_sku_ranges(
        sku.price_min, sku.price_max,
        sku.lead_time_min, sku.lead_time_max,
    )

    # i18n 字段
    for field in _SKU_I18N_FIELDS:
        value = getattr(sku_data, field, None)
        if value is not None:
            old_value = getattr(sku, f"{field}_{source_lang}", None)
            await apply_i18n_edit(sku, field, source_lang, value, old_value, domain="product")

    # SKU 级属性整体替换(硬删)
    if sku_data.attributes is not None:
        await db.execute(
            sa_delete(ProductAttr).where(ProductAttr.sku_id == sku.id)
        )
        if sku_data.attributes:
            await _add_attrs(
                db, product.id, sku_data.attributes,
                template_map=tpl_map,
                category_code=product.category_code,
                expected_scope="SKU",
                sku_id=sku.id,
            )

    # 阶梯价整体替换
    if sku_data.price_tiers is not None:
        await _replace_price_tiers(db, sku, sku_data.price_tiers, operator_id=operator_id)

    return sku


async def _apply_image_refs(
    db: AsyncSession,
    product_id: int,
    image_refs: list,
) -> None:
    """根据入参图片引用列表，更新 image_type 和 sort_order。

    校验所有 image_id 属于本商品；将入参中标记为 MAIN 的设为主图。
    """
    if not image_refs:
        return

    image_ids = [ref.image_id for ref in image_refs]

    # 校验 image_id 都属于本商品
    rows = (await db.execute(
        select(ProductImage.id).where(
            ProductImage.id.in_(image_ids),
            ProductImage.product_id == product_id,
            _not_deleted(ProductImage),
        )
    )).scalars().all()
    owned_ids = set(rows)
    for img_id in image_ids:
        if img_id not in owned_ids:
            raise ImageNotOwnedError(img_id, product_id)

    # 先把本商品所有图片 type 重置为 GALLERY
    await db.execute(
        update(ProductImage)
        .where(ProductImage.product_id == product_id, _not_deleted(ProductImage))
        .values(image_type=ImageType.GALLERY)
    )

    # 按入参设置 type 和 sort_order
    for ref in image_refs:
        img_type = ref.image_type if ref.image_type in ImageType.ALL else ImageType.GALLERY
        await db.execute(
            update(ProductImage)
            .where(ProductImage.id == ref.image_id, ProductImage.product_id == product_id)
            .values(image_type=img_type, sort_order=ref.sort_order)
        )


# ── 公共序列化 helper（供 public / operator 路由复用）──────


def spu_price_range(p) -> dict:
    """SPU 级价格汇总：取所有 ACTIVE SKU 的 price_min/max 极值。currency 从 SPU 读。"""
    active = [s for s in p.skus if s.status == SkuStatus.ACTIVE]
    mins = [s.price_min for s in active if s.price_min is not None]
    maxs = [s.price_max for s in active if s.price_max is not None]
    return {
        "price_min": min(mins) if mins else None,
        "price_max": max(maxs) if maxs else None,
        "currency": p.currency,
    }


def default_sku_fields(p) -> dict:
    """从默认 SKU 取 moq/lead_time，unit 从 SPU 读。"""
    ds = _default_sku_pick(p)
    if not ds:
        return {"moq": None, "unit": p.unit, "lead_time_min": None, "lead_time_max": None}
    return {
        "moq": ds.moq,
        "unit": p.unit,
        "lead_time_min": ds.lead_time_min,
        "lead_time_max": ds.lead_time_max,
    }


def _default_sku_pick(p):
    """取默认 SKU：优先 is_default → 首个 active → 兜底首个。"""
    if not p.skus:
        return None
    default = next((s for s in p.skus if s.is_default), None)
    if not default:
        active = [s for s in p.skus if s.status == SkuStatus.ACTIVE]
        default = active[0] if active else p.skus[0]
    return default


# ── 可购口径(单一事实源)────────────────────────────────


async def get_purchasable_sku(
    db: AsyncSession, sku_id: int,
) -> ProductSku | None:
    """一次 JOIN 判断 SKU 可购:SKU ACTIVE + 未软删 + 父 SPU ACTIVE + 未软删。"""
    row = await db.execute(
        select(ProductSku)
        .join(Product, Product.id == ProductSku.product_id)
        .where(
            ProductSku.id == sku_id,
            ProductSku.status == SkuStatus.ACTIVE,
            _not_deleted(ProductSku),
            Product.status == ProductStatus.ACTIVE,
            _not_deleted(Product),
        )
    )
    return row.scalar_one_or_none()


# ── 内部工具 ─────────────────────────────────────────────

async def sync_parent_is_leaf(db: AsyncSession, parent_code: str | None) -> None:
    """根据 active 子节点数量同步父节点的 is_leaf 标记。

    品类增删/停启用时调用,保证 is_leaf 与实际子节点状态一致。
    """
    if parent_code is None:
        return
    parent = (await db.execute(
        select(Category).where(Category.code == parent_code)
    )).scalar_one_or_none()
    if parent is None:
        return
    has_active_child = (await db.execute(
        select(Category.code).where(
            Category.parent_code == parent_code,
            Category.is_active.is_(True),
        ).limit(1)
    )).scalar_one_or_none() is not None
    parent.is_leaf = not has_active_child


async def _get_product_or_404(
    db: AsyncSession, product_id: int, *, load_relations: bool = False,
) -> Product:
    q = select(Product).where(Product.id == product_id, _not_deleted(Product))
    if load_relations:
        q = q.options(
            selectinload(Product.images.and_(_not_deleted(ProductImage))),
            selectinload(Product.attrs),
            selectinload(Product.skus.and_(_not_deleted(ProductSku))).selectinload(ProductSku.price_tiers),
            selectinload(Product.skus.and_(_not_deleted(ProductSku))).selectinload(ProductSku.images.and_(_not_deleted(ProductImage))),
            selectinload(Product.skus.and_(_not_deleted(ProductSku))).selectinload(ProductSku.supplier_relations.and_(_not_deleted(ProductSupplier))),
        )
    row = await db.execute(q)
    product = row.scalar_one_or_none()
    if not product:
        raise NotFoundError("Product not found")
    return product


async def _get_sku_or_404(
    db: AsyncSession, sku_id: int, *, load_relations: bool = False,
) -> ProductSku:
    q = select(ProductSku).where(ProductSku.id == sku_id, _not_deleted(ProductSku))
    if load_relations:
        q = q.options(
            selectinload(ProductSku.price_tiers),
            selectinload(ProductSku.images.and_(_not_deleted(ProductImage))),
            selectinload(ProductSku.supplier_relations.and_(_not_deleted(ProductSupplier))),
        )
    row = await db.execute(q)
    sku = row.scalar_one_or_none()
    if not sku:
        raise NotFoundError("SKU not found")
    return sku


async def _get_sku_under_product_or_404(
    db: AsyncSession, product_id: int, sku_id: int, *, load_relations: bool = False,
) -> ProductSku:
    q = select(ProductSku).where(
        ProductSku.id == sku_id,
        ProductSku.product_id == product_id,
        _not_deleted(ProductSku),
    )
    if load_relations:
        q = q.options(
            selectinload(ProductSku.price_tiers),
            selectinload(ProductSku.images.and_(_not_deleted(ProductImage))),
            selectinload(ProductSku.supplier_relations.and_(_not_deleted(ProductSupplier))),
        )
    row = await db.execute(q)
    sku = row.scalar_one_or_none()
    if not sku:
        raise NotFoundError("SKU not found")
    return sku


async def _get_supplier_relation_under_sku_or_404(
    db: AsyncSession, sku_id: int, ps_id: int,
) -> ProductSupplier:
    row = await db.execute(
        select(ProductSupplier).where(
            ProductSupplier.id == ps_id,
            ProductSupplier.sku_id == sku_id,
            _not_deleted(ProductSupplier),
        )
    )
    ps = row.scalar_one_or_none()
    if not ps:
        raise NotFoundError("Supplier relation not found")
    return ps
