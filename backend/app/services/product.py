"""商品目录 Service — CRUD + 供货关系 + 图片 + 属性模板。"""
from __future__ import annotations

import math
import os
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessError, NotFoundError
from app.db.models.attr_template import AttrTemplate
from app.db.models.category import Category
from app.db.models.product import Product, ProductStatus
from app.db.models.product_attr import ProductAttr
from app.db.models.product_image import ProductImage
from app.db.models.product_supplier import ProductSupplier
from app.db.models.supplier_organization import SupplierOrganization
from app.schemas.product import (
    ProductAttrCreate,
    ProductCreate,
    ProductSupplierCreate,
    ProductSupplierUpdate,
    ProductUpdate,
)

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "products"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_IMAGES_PER_PRODUCT = 8


# ── 商品 CRUD ──────────────────────────────────────────────

async def _generate_sku_code(db: AsyncSession, category_code: str) -> str:
    """根据品类编码自动生成 SKU，格式：{品类前缀}-{序号}。

    如品类 01.001 → LT-001-001，品类 01 → LT-001。
    """
    # 品类代码到 SKU 前缀映射（对齐文档 §三）
    _PREFIX_MAP = {
        "01": "LT", "02": "EL", "03": "SB", "04": "TH", "05": "BP",
        "06": "PF", "07": "CD", "08": "SP", "09": "SC",
    }
    l1_code = category_code.split(".")[0]
    prefix = _PREFIX_MAP.get(l1_code, l1_code.upper())

    # 查该品类下已有产品数量，确定序号
    count_result = await db.execute(
        select(func.count()).select_from(Product).where(
            Product.category_code == category_code
        )
    )
    seq = (count_result.scalar() or 0) + 1
    sku = f"{prefix}-{category_code.replace('.', '-')}-{seq:03d}"

    # 防冲突（极端情况）
    exists = await db.execute(select(Product).where(Product.sku_code == sku))
    while exists.scalar_one_or_none():
        seq += 1
        sku = f"{prefix}-{category_code.replace('.', '-')}-{seq:03d}"
        exists = await db.execute(select(Product).where(Product.sku_code == sku))

    return sku


async def create_product(
    db: AsyncSession, data: ProductCreate, operator_id: int,
) -> Product:
    # 品类存在校验
    cat = await db.execute(
        select(Category).where(Category.code == data.category_code)
    )
    if not cat.scalar_one_or_none():
        raise NotFoundError("Category not found")

    # SKU 自动生成（如果前端未传）
    sku_code = data.sku_code if data.sku_code else await _generate_sku_code(db, data.category_code)

    # SKU 唯一校验
    exists = await db.execute(
        select(Product).where(Product.sku_code == sku_code)
    )
    if exists.scalar_one_or_none():
        raise BusinessError(400, 50003, "SKU code already exists")

    product = Product(
        category_code=data.category_code,
        sku_code=sku_code,
        name=data.name,
        name_i18n=data.name_i18n,
        description=data.description,
        description_i18n=data.description_i18n,
        price_min=data.price_min,
        price_max=data.price_max,
        currency=data.currency,
        unit=data.unit,
        moq=data.moq,
        lead_time_days=data.lead_time_days,
        origin=data.origin,
        origin_i18n=data.origin_i18n,
        hs_code=data.hs_code,
        brand=data.brand,
        brand_i18n=data.brand_i18n,
        certifications=data.certifications or [],
        is_featured=data.is_featured,
        status=data.status if data.status in ProductStatus.ALL else ProductStatus.DRAFT,
        created_by=operator_id,
    )
    db.add(product)
    await db.flush()

    # 品类属性
    if data.attributes:
        for attr in data.attributes:
            db.add(ProductAttr(
                product_id=product.id,
                attr_key=attr.attr_key,
                attr_value=attr.attr_value,
                attr_unit=attr.attr_unit,
                sort_order=attr.sort_order,
            ))

    await db.commit()
    await db.refresh(product)

    # 如果直接上架，更新品类计数
    if product.status == ProductStatus.ACTIVE:
        await _sync_category_product_count(db, product.category_code)

    return product


async def update_product(
    db: AsyncSession, product_id: int, data: ProductUpdate,
) -> Product:
    product = await _get_product_or_404(db, product_id)

    for field, value in data.model_dump(exclude_unset=True, exclude={"attributes"}).items():
        setattr(product, field, value)

    # 如果更新了属性，先删后建
    if data.attributes is not None:
        await db.execute(
            select(ProductAttr).where(ProductAttr.product_id == product_id)
        )
        # 删除旧属性
        from sqlalchemy import delete
        await db.execute(
            delete(ProductAttr).where(ProductAttr.product_id == product_id)
        )
        for attr in data.attributes:
            db.add(ProductAttr(
                product_id=product_id,
                attr_key=attr.attr_key,
                attr_value=attr.attr_value,
                attr_unit=attr.attr_unit,
                sort_order=attr.sort_order,
            ))

    await db.commit()
    await db.refresh(product)
    return product


async def update_product_status(
    db: AsyncSession, product_id: int, new_status: str,
) -> Product:
    if new_status not in ProductStatus.ALL:
        raise BusinessError(400, 50002, f"Invalid status: {new_status}")

    product = await _get_product_or_404(db, product_id, load_relations=True)
    old_status = product.status

    # 上架校验：必须有图片
    if new_status == ProductStatus.ACTIVE:
        if not product.images:
            raise BusinessError(400, 50004, "Cannot publish: at least 1 image required")

    product.status = new_status
    await db.commit()

    # 品类计数同步
    if old_status != new_status:
        await _sync_category_product_count(db, product.category_code)

    await db.refresh(product)
    return product


async def delete_product(db: AsyncSession, product_id: int) -> None:
    product = await _get_product_or_404(db, product_id)
    if product.status != ProductStatus.DRAFT:
        raise BusinessError(400, 50006, "Only DRAFT products can be deleted")
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
        selectinload(Product.supplier_relations),
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
        q = q.where(Product.name.ilike(kw) | Product.sku_code.ilike(kw))
        count_q = count_q.where(Product.name.ilike(kw) | Product.sku_code.ilike(kw))

    total = (await db.execute(count_q)).scalar() or 0
    q = q.order_by(Product.created_at.desc()).offset((page - 1) * size).limit(size)
    rows = (await db.execute(q)).scalars().all()
    return list(rows), total


async def list_products_public(
    db: AsyncSession,
    *,
    category_code: str | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    featured: bool | None = None,
    keyword: str | None = None,
    sort: str = "newest",
    page: int = 1,
    size: int = 20,
) -> tuple[list[Product], int]:
    """公开列表：只返回 ACTIVE 商品，不加载供货关系。"""
    q = select(Product).options(
        selectinload(Product.images),
    ).where(Product.status == ProductStatus.ACTIVE)
    count_q = select(func.count(Product.id)).where(Product.status == ProductStatus.ACTIVE)

    if category_code:
        q = q.where(Product.category_code == category_code)
        count_q = count_q.where(Product.category_code == category_code)
    if price_min is not None:
        q = q.where(Product.price_min >= price_min)
        count_q = count_q.where(Product.price_min >= price_min)
    if price_max is not None:
        q = q.where(Product.price_max <= price_max)
        count_q = count_q.where(Product.price_max <= price_max)
    if featured is not None:
        q = q.where(Product.is_featured == featured)
        count_q = count_q.where(Product.is_featured == featured)
    if keyword:
        kw = f"%{keyword}%"
        q = q.where(Product.name.ilike(kw) | Product.sku_code.ilike(kw))
        count_q = count_q.where(Product.name.ilike(kw) | Product.sku_code.ilike(kw))

    # 排序
    if sort == "price_asc":
        q = q.order_by(Product.price_min.asc())
    elif sort == "price_desc":
        q = q.order_by(Product.price_min.desc())
    else:
        q = q.order_by(Product.created_at.desc())

    total = (await db.execute(count_q)).scalar() or 0
    q = q.offset((page - 1) * size).limit(size)
    rows = (await db.execute(q)).scalars().all()
    return list(rows), total


# ── 供货关系 ──────────────────────────────────────────────

async def add_product_supplier(
    db: AsyncSession, product_id: int, data: ProductSupplierCreate,
) -> ProductSupplier:
    await _get_product_or_404(db, product_id)

    # 唯一校验
    exists = await db.execute(
        select(ProductSupplier).where(
            ProductSupplier.product_id == product_id,
            ProductSupplier.supplier_org_id == data.supplier_org_id,
        )
    )
    if exists.scalar_one_or_none():
        raise BusinessError(400, 50007, "Supplier already bound to this product")

    # 供应商存在校验
    sup = await db.execute(
        select(SupplierOrganization).where(SupplierOrganization.id == data.supplier_org_id)
    )
    if not sup.scalar_one_or_none():
        raise NotFoundError("Supplier organization not found")

    ps = ProductSupplier(
        product_id=product_id,
        supplier_org_id=data.supplier_org_id,
        supplier_price=data.supplier_price,
        supplier_moq=data.supplier_moq,
        supplier_lead_time_days=data.supplier_lead_time_days,
        has_pvoc=data.has_pvoc,
        has_coc=data.has_coc,
        is_preferred=data.is_preferred,
        notes=data.notes,
    )
    db.add(ps)
    await db.commit()
    await db.refresh(ps)
    return ps


async def update_product_supplier(
    db: AsyncSession, ps_id: int, data: ProductSupplierUpdate,
) -> ProductSupplier:
    row = await db.execute(
        select(ProductSupplier).where(ProductSupplier.id == ps_id)
    )
    ps = row.scalar_one_or_none()
    if not ps:
        raise NotFoundError("Product supplier relation not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(ps, field, value)

    await db.commit()
    await db.refresh(ps)
    return ps


async def remove_product_supplier(db: AsyncSession, ps_id: int) -> None:
    row = await db.execute(
        select(ProductSupplier).where(ProductSupplier.id == ps_id)
    )
    ps = row.scalar_one_or_none()
    if not ps:
        raise NotFoundError("Product supplier relation not found")
    await db.delete(ps)
    await db.commit()


async def list_product_suppliers(
    db: AsyncSession, product_id: int,
) -> list[dict]:
    """返回供货关系列表，含供应商名称。"""
    await _get_product_or_404(db, product_id)
    q = (
        select(ProductSupplier, SupplierOrganization.name)
        .join(
            SupplierOrganization,
            ProductSupplier.supplier_org_id == SupplierOrganization.id,
            isouter=True,
        )
        .where(ProductSupplier.product_id == product_id)
        .order_by(ProductSupplier.is_preferred.desc(), ProductSupplier.created_at)
    )
    rows = (await db.execute(q)).all()
    result = []
    for ps, org_name in rows:
        d = {
            "id": ps.id,
            "product_id": ps.product_id,
            "supplier_org_id": ps.supplier_org_id,
            "supplier_org_name": org_name or "",
            "supplier_price": ps.supplier_price,
            "supplier_moq": ps.supplier_moq,
            "supplier_lead_time_days": ps.supplier_lead_time_days,
            "has_pvoc": ps.has_pvoc,
            "has_coc": ps.has_coc,
            "is_preferred": ps.is_preferred,
            "notes": ps.notes,
            "created_at": ps.created_at,
            "updated_at": ps.updated_at,
        }
        result.append(d)
    return result


# ── 图片 ──────────────────────────────────────────────────

TARGET_SIZE = (800, 800)
JPEG_QUALITY = 85


def _process_image(content: bytes) -> tuple[bytes, int, int]:
    """Pillow 压缩：超 800x800 等比缩小，填充为正方形，输出 JPEG。"""
    from io import BytesIO
    from PIL import Image

    img = Image.open(BytesIO(content))
    img = img.convert("RGB")

    # 尺寸校验
    w, h = img.size
    if w < 200 or h < 200:
        raise BusinessError(400, 50011, "Image too small, minimum 200x200")

    # 等比缩小到 800x800 以内
    img.thumbnail(TARGET_SIZE, Image.LANCZOS)

    # 填充为正方形（白底居中）
    w, h = img.size
    if w != h:
        side = max(w, h)
        bg = Image.new("RGB", (side, side), (255, 255, 255))
        bg.paste(img, ((side - w) // 2, (side - h) // 2))
        img = bg

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    final_bytes = buf.getvalue()
    final_w, final_h = img.size
    return final_bytes, final_w, final_h


async def add_product_image(
    db: AsyncSession, product_id: int, file: UploadFile,
    image_type: str = "GALLERY",
) -> ProductImage:
    from app.db.models.product_image import ImageType
    product = await _get_product_or_404(db, product_id, load_relations=True)

    # 数量限制
    if len(product.images) >= MAX_IMAGES_PER_PRODUCT:
        raise BusinessError(400, 50008, f"Maximum {MAX_IMAGES_PER_PRODUCT} images per product")

    # 扩展名校验
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise BusinessError(400, 50009, f"Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}")

    # 读取并校验大小
    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise BusinessError(400, 50010, "Image size must be under 5MB")

    # Pillow 压缩到 800x800 正方形 JPEG
    processed_bytes, img_w, img_h = _process_image(content)

    # 保存文件（统一 .jpg）
    product_dir = UPLOAD_DIR / str(product_id)
    product_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    filepath = product_dir / filename
    filepath.write_bytes(processed_bytes)

    # 第一张图自动设为 MAIN
    actual_type = image_type if image_type in ImageType.ALL else ImageType.GALLERY
    if not product.images:
        actual_type = ImageType.MAIN

    # 写入数据库
    next_sort = len(product.images)
    image_key = f"products/{product_id}/{filename}"
    img = ProductImage(
        product_id=product_id,
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
    """设为主图：将原 MAIN 降为 GALLERY，目标图升为 MAIN。"""
    from app.db.models.product_image import ImageType
    await _get_product_or_404(db, product_id)

    # 原 MAIN → GALLERY
    await db.execute(
        update(ProductImage)
        .where(ProductImage.product_id == product_id, ProductImage.image_type == ImageType.MAIN)
        .values(image_type=ImageType.GALLERY)
    )
    # 目标 → MAIN
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

    # 删文件
    filepath = UPLOAD_DIR.parent / img.image_key
    if filepath.exists():
        filepath.unlink()

    await db.delete(img)
    await db.commit()


async def update_image_sort(
    db: AsyncSession, product_id: int, image_ids: list[int],
) -> None:
    """按传入的 image_ids 顺序重新排序。"""
    for idx, img_id in enumerate(image_ids):
        await db.execute(
            update(ProductImage)
            .where(ProductImage.id == img_id, ProductImage.product_id == product_id)
            .values(sort_order=idx)
        )
    await db.commit()


# ── 属性模板 ──────────────────────────────────────────────

async def get_attr_templates(
    db: AsyncSession, category_code: str,
) -> list[AttrTemplate]:
    q = (
        select(AttrTemplate)
        .where(AttrTemplate.category_code == category_code)
        .order_by(AttrTemplate.sort_order)
    )
    rows = (await db.execute(q)).scalars().all()
    return list(rows)


# ── 内部工具 ──────────────────────────────────────────────

async def _get_product_or_404(
    db: AsyncSession, product_id: int, *, load_relations: bool = False,
) -> Product:
    q = select(Product).where(Product.id == product_id)
    if load_relations:
        q = q.options(
            selectinload(Product.images),
            selectinload(Product.attrs),
            selectinload(Product.supplier_relations),
        )
    row = await db.execute(q)
    product = row.scalar_one_or_none()
    if not product:
        raise NotFoundError("Product not found")
    return product


async def _sync_category_product_count(
    db: AsyncSession, category_code: str,
) -> None:
    """同步品类的 ACTIVE 商品计数。"""
    cnt = (await db.execute(
        select(func.count(Product.id)).where(
            Product.category_code == category_code,
            Product.status == ProductStatus.ACTIVE,
        )
    )).scalar() or 0
    await db.execute(
        update(Category).where(Category.code == category_code).values(product_count=cnt)
    )
    await db.commit()
