"""商品目录 Service — SPU + SKU 两层化,v2 i18n 分列模式。

SPU CRUD / SKU CRUD(含阶梯价整体替换) / 供货关系(挂 SKU) / 图片(SPU+SKU) / 属性模板。
多语言写入经 i18n_write,读出经 get_localized。
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import delete as sa_delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    NotFoundError,
    ImageFormatInvalidError,
    ImageTooLargeError,
    ImageTooSmallError,
    InvalidProductStatusError,
    MaxImagesExceededError,
    OnlyDraftDeletableError,
    PriceTierInvalidError,
    PublishValidationFailedError,
    SkuCodeExistsError,
    AttrKeyNotInTemplateError,
    AttrScopeMismatchError,
    SkuNotInProductError,
    SpuCodeExistsError,
    SupplierAlreadyBoundError,
)
from app.core.message_keys import MessageKey
from app.core.i18n_write import apply_i18n_create, apply_i18n_edit
from app.core.locale import SUPPORTED_LOCALES
from app.db.models.attr_template import AttrTemplate
from app.db.models.category import Category
from app.db.models.product import Product, ProductStatus
from app.db.models.product_attr import ProductAttr
from app.db.models.product_image import ProductImage, ImageType
from app.db.models.product_sku import ProductSku, SkuStatus
from app.db.models.product_supplier import ProductSupplier
from app.db.models.sku_price_tier import SkuPriceTier
from app.db.models.supplier_organization import SupplierOrganization
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

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "products"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_IMAGES_PER_PRODUCT = 8

# i18n 字段声明
_PRODUCT_I18N_FIELDS = ("name", "description", "brand", "origin", "selling_points")
_SKU_I18N_FIELDS = ("name", "color", "material")


# ── SPU 编码生成 ─────────────────────────────────────────

_PREFIX_MAP = {
    "01": "LT", "02": "EL", "03": "SB", "04": "TH", "05": "BP",
    "06": "PF", "07": "CD", "08": "SP", "09": "SC",
    "10": "WT", "11": "AG", "12": "EN", "13": "SF",
}


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
        select(Product.id).where(Product.spu_code == code)
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
        select(ProductSku.id).where(ProductSku.sku_code == code)
    )).scalar_one_or_none():
        seq += 1
        code = f"{spu_code}-S{seq:02d}"

    return code


# ── SPU CRUD ─────────────────────────────────────────────

async def create_product(
    db: AsyncSession, data: ProductCreate, operator_id: int,
) -> Product:
    # 品类存在校验
    cat = await db.execute(
        select(Category).where(Category.code == data.category_code)
    )
    if not cat.scalar_one_or_none():
        raise NotFoundError("Category not found")

    spu_code = data.spu_code or await _generate_spu_code(db, data.category_code)

    if (await db.execute(
        select(Product.id).where(Product.spu_code == spu_code)
    )).scalar_one_or_none():
        raise SpuCodeExistsError()

    source_lang = data.source_lang or "zh"
    product = Product(
        category_code=data.category_code,
        spu_code=spu_code,
        source_lang=source_lang,
        name_zh="",  # 占位,由 i18n_write 覆写
        hs_code=data.hs_code,
        certifications=data.certifications or [],
        is_featured=data.is_featured,
        status=data.status if data.status in ProductStatus.ALL else ProductStatus.DRAFT,
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
) -> Product:
    product = await _get_product_or_404(db, product_id)
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

    # SPU 级属性整体替换
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
            raise AttrKeyNotInTemplateError(attr.attr_key, category_code)
        if tpl.scope != expected_scope:
            raise AttrScopeMismatchError(attr.attr_key, tpl.scope)

        db.add(ProductAttr(
            product_id=product_id,
            sku_id=sku_id,
            attr_key=attr.attr_key,
            attr_value=attr.attr_value,
            attr_unit=tpl.attr_unit,
            sort_order=tpl.sort_order,
        ))


async def update_product_status(
    db: AsyncSession, product_id: int, new_status: str,
) -> Product:
    if new_status not in ProductStatus.ALL:
        raise InvalidProductStatusError(new_status)

    product = await _get_product_or_404(db, product_id, load_relations=True)

    # 上架校验
    if new_status == ProductStatus.ACTIVE:
        errors = []
        active_skus = [s for s in product.skus if s.status == SkuStatus.ACTIVE]
        if not active_skus:
            errors.append("At least 1 active SKU required")
        else:
            for sku in active_skus:
                if sku.price_min is None or sku.price_max is None:
                    errors.append(
                        f"SKU {sku.sku_code}: price_min and price_max must be set"
                    )
        if not product.images:
            errors.append("At least 1 image required")

        if errors:
            raise PublishValidationFailedError(errors)

    product.status = new_status
    await db.commit()
    await db.refresh(product)
    return product


async def delete_product(db: AsyncSession, product_id: int) -> None:
    product = await _get_product_or_404(db, product_id)
    if product.status != ProductStatus.DRAFT:
        raise OnlyDraftDeletableError()
    await db.delete(product)
    await db.commit()


async def get_product(db: AsyncSession, product_id: int) -> Product:
    return await _get_product_or_404(db, product_id, load_relations=True)


async def list_products_operator(
    db: AsyncSession,
    *,
    category_code: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Product], int]:
    q = select(Product).options(
        selectinload(Product.images),
        selectinload(Product.skus),
    )
    count_q = select(func.count(Product.id))

    if category_code:
        q = q.where(Product.category_code == category_code)
        count_q = count_q.where(Product.category_code == category_code)
    if status:
        q = q.where(Product.status == status)
        count_q = count_q.where(Product.status == status)
    if keyword:
        kw = f"%{keyword}%"
        # 搜索对各语言列做 OR 匹配
        keyword_filter = or_(
            Product.name_zh.ilike(kw),
            Product.name_en.ilike(kw),
            Product.spu_code.ilike(kw),
        )
        q = q.where(keyword_filter)
        count_q = count_q.where(keyword_filter)

    total = (await db.execute(count_q)).scalar() or 0
    q = q.order_by(Product.created_at.desc()).offset((page - 1) * size).limit(size)
    rows = (await db.execute(q)).scalars().all()
    return list(rows), total


async def list_products_public(
    db: AsyncSession,
    *,
    category_code: str | None = None,
    featured: bool | None = None,
    keyword: str | None = None,
    sort: str = "newest",
    page: int = 1,
    size: int = 20,
) -> tuple[list[Product], int]:
    q = select(Product).options(
        selectinload(Product.images),
        selectinload(Product.skus).selectinload(ProductSku.price_tiers),
    ).where(Product.status == ProductStatus.ACTIVE)
    count_q = select(func.count(Product.id)).where(Product.status == ProductStatus.ACTIVE)

    if category_code:
        q = q.where(Product.category_code == category_code)
        count_q = count_q.where(Product.category_code == category_code)
    if featured is not None:
        q = q.where(Product.is_featured == featured)
        count_q = count_q.where(Product.is_featured == featured)
    if keyword:
        kw = f"%{keyword}%"
        keyword_filter = or_(
            Product.name_zh.ilike(kw),
            Product.name_en.ilike(kw),
            Product.spu_code.ilike(kw),
        )
        q = q.where(keyword_filter)
        count_q = count_q.where(keyword_filter)

    q = q.order_by(Product.created_at.desc())

    total = (await db.execute(count_q)).scalar() or 0
    q = q.offset((page - 1) * size).limit(size)
    rows = (await db.execute(q)).scalars().all()
    return list(rows), total


# ── SKU CRUD ─────────────────────────────────────────────

async def create_sku(
    db: AsyncSession, product_id: int, data: SkuCreate,
) -> ProductSku:
    product = await _get_product_or_404(db, product_id)

    sku_code = data.sku_code or await _generate_sku_code(db, product.spu_code, product_id)

    if (await db.execute(
        select(ProductSku.id).where(ProductSku.sku_code == sku_code)
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
        currency=data.currency,
        unit=data.unit,
        moq=data.moq,
        lead_time_min=data.lead_time_min,
        lead_time_max=data.lead_time_max,
        packing_quantity=data.packing_quantity,
        gross_weight_kg=data.gross_weight_kg,
        volume_cbm=data.volume_cbm,
        can_consolidate=data.can_consolidate,
        cargo_type=data.cargo_type,
        is_default=data.is_default,
        status=data.status if data.status in SkuStatus.ALL else SkuStatus.ACTIVE,
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
    db: AsyncSession, sku_id: int, data: SkuUpdate,
) -> ProductSku:
    sku = await _get_sku_or_404(db, sku_id)
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

    for field, value in i18n_fields_to_update.items():
        if value is not None:
            old_value = getattr(sku, f"{field}_{source_lang}", None)
            await apply_i18n_edit(sku, field, source_lang, value, old_value, domain="product")

    # SKU 级属性整体替换
    if data.attributes is not None:
        await db.execute(
            sa_delete(ProductAttr).where(ProductAttr.sku_id == sku_id)
        )
        if data.attributes:
            product = await _get_product_or_404(db, sku.product_id)
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
        await _replace_price_tiers(db, sku, data.price_tiers)

    await db.commit()
    await db.refresh(sku, ["price_tiers"])
    return sku


async def delete_sku(db: AsyncSession, sku_id: int) -> None:
    sku = await _get_sku_or_404(db, sku_id)
    await db.delete(sku)
    await db.commit()


async def list_skus(
    db: AsyncSession, product_id: int,
) -> list[ProductSku]:
    await _get_product_or_404(db, product_id)
    q = (
        select(ProductSku)
        .options(
            selectinload(ProductSku.price_tiers),
            selectinload(ProductSku.images),
            selectinload(ProductSku.supplier_relations),
        )
        .where(ProductSku.product_id == product_id)
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


async def _replace_price_tiers(
    db: AsyncSession,
    sku: ProductSku,
    tiers: list[PriceTierCreate],
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
    db: AsyncSession, sku_id: int, data: SupplierRelationCreate,
) -> ProductSupplier:
    await _get_sku_or_404(db, sku_id)

    if (await db.execute(
        select(ProductSupplier.id).where(
            ProductSupplier.sku_id == sku_id,
            ProductSupplier.supplier_org_id == data.supplier_org_id,
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
    db: AsyncSession, ps_id: int, data: SupplierRelationUpdate,
) -> ProductSupplier:
    row = await db.execute(
        select(ProductSupplier).where(ProductSupplier.id == ps_id)
    )
    ps = row.scalar_one_or_none()
    if not ps:
        raise NotFoundError("Supplier relation not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(ps, field, value)

    await db.commit()
    await db.refresh(ps)
    return ps


async def remove_sku_supplier(db: AsyncSession, ps_id: int) -> None:
    row = await db.execute(
        select(ProductSupplier).where(ProductSupplier.id == ps_id)
    )
    ps = row.scalar_one_or_none()
    if not ps:
        raise NotFoundError("Supplier relation not found")
    await db.delete(ps)
    await db.commit()


async def list_sku_suppliers(
    db: AsyncSession, sku_id: int,
) -> list[dict]:
    await _get_sku_or_404(db, sku_id)
    q = (
        select(ProductSupplier, SupplierOrganization.name)
        .join(
            SupplierOrganization,
            ProductSupplier.supplier_org_id == SupplierOrganization.id,
            isouter=True,
        )
        .where(ProductSupplier.sku_id == sku_id)
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

TARGET_SIZE = (800, 800)
JPEG_QUALITY = 85


def _process_image(content: bytes) -> tuple[bytes, int, int]:
    from io import BytesIO
    from PIL import Image

    img = Image.open(BytesIO(content))
    img = img.convert("RGB")

    w, h = img.size
    if w < 200 or h < 200:
        raise ImageTooSmallError()

    img.thumbnail(TARGET_SIZE, Image.LANCZOS)

    w, h = img.size
    if w != h:
        side = max(w, h)
        bg = Image.new("RGB", (side, side), (255, 255, 255))
        bg.paste(img, ((side - w) // 2, (side - h) // 2))
        img = bg

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue(), img.size[0], img.size[1]


async def add_product_image(
    db: AsyncSession,
    product_id: int,
    file: UploadFile,
    image_type: str = "GALLERY",
    sku_id: int | None = None,
) -> ProductImage:
    product = await _get_product_or_404(db, product_id, load_relations=True)

    if sku_id is not None:
        sku_exists = any(s.id == sku_id for s in product.skus)
        if not sku_exists:
            raise NotFoundError("SKU not found under this product")

    if len(product.images) >= MAX_IMAGES_PER_PRODUCT:
        raise MaxImagesExceededError(MAX_IMAGES_PER_PRODUCT)

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ImageFormatInvalidError(", ".join(ALLOWED_EXTENSIONS))

    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise ImageTooLargeError()

    processed_bytes, img_w, img_h = _process_image(content)

    product_dir = UPLOAD_DIR / str(product_id)
    product_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    filepath = product_dir / filename
    filepath.write_bytes(processed_bytes)

    actual_type = image_type if image_type in ImageType.ALL else ImageType.GALLERY
    if not product.images:
        actual_type = ImageType.MAIN

    next_sort = len(product.images)
    image_key = f"products/{product_id}/{filename}"
    img = ProductImage(
        product_id=product_id,
        sku_id=sku_id,
        image_key=image_key,
        image_type=actual_type,
        sort_order=next_sort,
        width=img_w,
        height=img_h,
        file_size=len(processed_bytes),
    )
    db.add(img)
    await db.commit()
    await db.refresh(img)
    return img


async def set_main_image(db: AsyncSession, product_id: int, image_id: int) -> None:
    await _get_product_or_404(db, product_id)

    await db.execute(
        update(ProductImage)
        .where(ProductImage.product_id == product_id, ProductImage.image_type == ImageType.MAIN)
        .values(image_type=ImageType.GALLERY)
    )
    result = await db.execute(
        update(ProductImage)
        .where(ProductImage.id == image_id, ProductImage.product_id == product_id)
        .values(image_type=ImageType.MAIN)
    )
    if result.rowcount == 0:
        raise NotFoundError("Image not found")
    await db.commit()


async def delete_product_image(db: AsyncSession, image_id: int) -> None:
    row = await db.execute(
        select(ProductImage).where(ProductImage.id == image_id)
    )
    img = row.scalar_one_or_none()
    if not img:
        raise NotFoundError("Image not found")

    filepath = UPLOAD_DIR.parent / img.image_key
    if filepath.exists():
        filepath.unlink()

    await db.delete(img)
    await db.commit()


async def update_image_sort(
    db: AsyncSession, product_id: int, image_ids: list[int],
) -> None:
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


# ── 内部工具 ─────────────────────────────────────────────

async def _get_product_or_404(
    db: AsyncSession, product_id: int, *, load_relations: bool = False,
) -> Product:
    q = select(Product).where(Product.id == product_id)
    if load_relations:
        q = q.options(
            selectinload(Product.images),
            selectinload(Product.attrs),
            selectinload(Product.skus).selectinload(ProductSku.price_tiers),
            selectinload(Product.skus).selectinload(ProductSku.images),
            selectinload(Product.skus).selectinload(ProductSku.supplier_relations),
        )
    row = await db.execute(q)
    product = row.scalar_one_or_none()
    if not product:
        raise NotFoundError("Product not found")
    return product


async def _get_sku_or_404(
    db: AsyncSession, sku_id: int, *, load_relations: bool = False,
) -> ProductSku:
    q = select(ProductSku).where(ProductSku.id == sku_id)
    if load_relations:
        q = q.options(
            selectinload(ProductSku.price_tiers),
            selectinload(ProductSku.images),
            selectinload(ProductSku.supplier_relations),
        )
    row = await db.execute(q)
    sku = row.scalar_one_or_none()
    if not sku:
        raise NotFoundError("SKU not found")
    return sku
