"""运营商品管理 API — SPU + SKU 两层化 + 审计日志。

SPU CRUD + SKU CRUD(含阶梯价) + 图片(SPU/SKU) + 供货关系(挂 SKU)。
全部写路径成功后写 audit_log；可预期校验错误不写审计。
"""
from __future__ import annotations

import math
from typing import List

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.constants import AuditAction, AuditResourceType
from app.audit.logger import write_audit
from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.core.exceptions import success
from app.core.i18n import get_localized
from app.db.models.product_image import ImageType
from app.db.models.product_sku import SkuStatus
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_permission
from app.schemas.product import (
    AttrTemplateSchema,
    PriceTierSchema,
    ProductAttrSchema,
    ProductCreate,
    ProductImageSchema,
    ProductOperator,
    ProductOperatorDetail,
    ProductStatusUpdate,
    ProductUpdate,
    SkuCreate,
    SkuOperator,
    SkuUpdate,
    SupplierRelationCreate,
    SupplierRelationDetail,
    SupplierRelationUpdate,
)
from app.services import product as product_svc

router = APIRouter(prefix="/operator/products", tags=["operator-products"])


# ── 序列化工具 ───────────────────────────────────────────

def _img_to_dict(img) -> dict:
    d = ProductImageSchema.model_validate(img).model_dump()
    d["full_url"] = f"{settings.IMAGE_BASE_URL}/{img.image_key}"
    return d


def _get_main_image_url(p) -> str | None:
    if not p.images:
        return None
    main = next((i for i in p.images if i.image_type == ImageType.MAIN), None)
    if not main:
        main = sorted(p.images, key=lambda i: i.sort_order)[0]
    return f"{settings.IMAGE_BASE_URL}/{main.image_key}"


def _default_sku(p):
    if not p.skus:
        return None
    default = next((s for s in p.skus if s.is_default), None)
    if not default:
        active = [s for s in p.skus if s.status == SkuStatus.ACTIVE]
        default = active[0] if active else (p.skus[0] if p.skus else None)
    return default


def _sku_to_operator(sku) -> dict:
    sku_images = [_img_to_dict(img) for img in (sku.images or [])]
    tiers = [PriceTierSchema.model_validate(t).model_dump() for t in (sku.price_tiers or [])]
    suppliers = []
    for sr in (sku.supplier_relations or []):
        suppliers.append(SupplierRelationDetail(
            id=sr.id,
            sku_id=sr.sku_id,
            supplier_org_id=sr.supplier_org_id,
            supplier_price=sr.supplier_price,
            supplier_currency=sr.supplier_currency,
            cif_price_usd=sr.cif_price_usd,
            supplier_moq=sr.supplier_moq,
            supplier_lead_time_days=sr.supplier_lead_time_days,
            pvoc_status=sr.pvoc_status,
            has_coc=sr.has_coc,
            is_preferred=sr.is_preferred,
            notes=sr.notes,
            created_at=sr.created_at,
            updated_at=sr.updated_at,
        ).model_dump())

    return SkuOperator(
        id=sku.id,
        sku_code=sku.sku_code,
        name=sku.name,
        name_i18n=sku.name_i18n,
        color=sku.color,
        color_i18n=sku.color_i18n,
        material=sku.material,
        material_i18n=sku.material_i18n,
        manufacturer_model=sku.manufacturer_model,
        price_min=sku.price_min,
        price_max=sku.price_max,
        currency=sku.currency,
        unit=sku.unit,
        moq=sku.moq,
        lead_time_min=sku.lead_time_min,
        lead_time_max=sku.lead_time_max,
        is_default=sku.is_default,
        status=sku.status,
        packing_quantity=sku.packing_quantity,
        gross_weight_kg=sku.gross_weight_kg,
        volume_cbm=sku.volume_cbm,
        can_consolidate=sku.can_consolidate,
        cargo_type=sku.cargo_type,
        price_tiers=tiers,
        images=sku_images,
        supplier_relations=suppliers,
        created_at=sku.created_at,
        updated_at=sku.updated_at,
    ).model_dump()


def _to_operator(p) -> dict:
    ds = _default_sku(p)
    active_count = sum(1 for s in p.skus if s.status == SkuStatus.ACTIVE) if p.skus else 0
    return ProductOperator(
        id=p.id,
        spu_code=p.spu_code,
        name=get_localized(p, "name"),
        name_i18n=p.name_i18n,
        category_code=p.category_code,
        origin=get_localized(p, "origin"),
        brand=get_localized(p, "brand") or None,
        is_featured=p.is_featured,
        main_image=_get_main_image_url(p),
        status=p.status,
        price_min=ds.price_min if ds else None,
        price_max=ds.price_max if ds else None,
        currency=ds.currency if ds else None,
        sku_count=active_count,
        created_at=p.created_at,
        updated_at=p.updated_at,
    ).model_dump()


# ── SPU CRUD ─────────────────────────────────────────────

@router.get("", summary="运营商品列表")
async def list_products(
    category_code: str | None = Query(None),
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_READ)),
    db: AsyncSession = Depends(get_db),
):
    items, total = await product_svc.list_products_operator(
        db, category_code=category_code, status=status,
        keyword=keyword, page=page, size=size,
    )
    return success({
        "items": [_to_operator(p) for p in items],
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if size else 0,
    })


@router.post("", summary="创建商品(SPU)")
async def create_product(
    request: Request,
    data: ProductCreate,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    product = await product_svc.create_product(db, data, current.id)
    await write_audit(
        db, resource_type=AuditResourceType.PRODUCT, action=AuditAction.CREATE,
        user_id=current.id, user_email=current.email,
        resource_id=product.id, request=request,
    )
    return success({"id": product.id, "spu_code": product.spu_code})


@router.put("/{product_id}", summary="编辑商品(SPU)")
async def update_product(
    product_id: int,
    request: Request,
    data: ProductUpdate,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    product = await product_svc.update_product(db, product_id, data)
    await write_audit(
        db, resource_type=AuditResourceType.PRODUCT, action=AuditAction.UPDATE,
        user_id=current.id, user_email=current.email,
        resource_id=product.id, request=request,
    )
    return success({"id": product.id})


@router.patch("/{product_id}/status", summary="上架/下架")
async def update_status(
    product_id: int,
    request: Request,
    data: ProductStatusUpdate,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_APPROVE)),
    db: AsyncSession = Depends(get_db),
):
    product = await product_svc.update_product_status(db, product_id, data.status)
    await write_audit(
        db, resource_type=AuditResourceType.PRODUCT, action=AuditAction.STATUS_CHANGE,
        user_id=current.id, user_email=current.email,
        resource_id=product.id, request=request,
        extra={"new_status": product.status},
    )
    return success({"id": product.id, "status": product.status})


@router.delete("/{product_id}", summary="删除草稿商品(SPU)")
async def delete_product(
    product_id: int,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    await product_svc.delete_product(db, product_id)
    await write_audit(
        db, resource_type=AuditResourceType.PRODUCT, action=AuditAction.DELETE,
        user_id=current.id, user_email=current.email,
        resource_id=product_id, request=request,
    )
    return success()


@router.get("/{product_id}", summary="运营商品详情(SPU)")
async def get_product(
    product_id: int,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_READ)),
    db: AsyncSession = Depends(get_db),
):
    p = await product_svc.get_product(db, product_id)

    data = ProductOperatorDetail(
        id=p.id,
        spu_code=p.spu_code,
        name=get_localized(p, "name"),
        name_i18n=p.name_i18n,
        description=get_localized(p, "description"),
        description_i18n=p.description_i18n,
        category_code=p.category_code,
        origin=get_localized(p, "origin"),
        origin_i18n=p.origin_i18n,
        brand=get_localized(p, "brand") or None,
        brand_i18n=p.brand_i18n,
        hs_code=p.hs_code,
        certifications=p.certifications,
        selling_points=get_localized(p, "selling_points"),
        selling_points_i18n=p.selling_points_i18n,
        is_featured=p.is_featured,
        status=p.status,
        skus=[_sku_to_operator(s) for s in p.skus],
        images=[_img_to_dict(img) for img in p.images],
        attributes=[ProductAttrSchema.model_validate(attr) for attr in p.attrs],
        created_at=p.created_at,
        updated_at=p.updated_at,
    ).model_dump()
    return success(data)


# ── SKU CRUD ─────────────────────────────────────────────

@router.get("/{product_id}/skus", summary="SKU 列表")
async def list_skus(
    product_id: int,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_READ)),
    db: AsyncSession = Depends(get_db),
):
    skus = await product_svc.list_skus(db, product_id)
    return success([_sku_to_operator(s) for s in skus])


@router.post("/{product_id}/skus", summary="创建 SKU")
async def create_sku(
    product_id: int,
    request: Request,
    data: SkuCreate,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    sku = await product_svc.create_sku(db, product_id, data)
    await write_audit(
        db, resource_type=AuditResourceType.PRODUCT_SKU, action=AuditAction.CREATE,
        user_id=current.id, user_email=current.email,
        resource_id=sku.id, request=request,
    )
    return success({"id": sku.id, "sku_code": sku.sku_code})


@router.put("/{product_id}/skus/{sku_id}", summary="编辑 SKU")
async def update_sku(
    product_id: int,
    sku_id: int,
    request: Request,
    data: SkuUpdate,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    sku = await product_svc.update_sku(db, sku_id, data)
    await write_audit(
        db, resource_type=AuditResourceType.PRODUCT_SKU, action=AuditAction.UPDATE,
        user_id=current.id, user_email=current.email,
        resource_id=sku.id, request=request,
    )
    return success({"id": sku.id})


@router.delete("/{product_id}/skus/{sku_id}", summary="删除 SKU")
async def delete_sku(
    product_id: int,
    sku_id: int,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    await product_svc.delete_sku(db, sku_id)
    await write_audit(
        db, resource_type=AuditResourceType.PRODUCT_SKU, action=AuditAction.DELETE,
        user_id=current.id, user_email=current.email,
        resource_id=sku_id, request=request,
    )
    return success()


# ── 图片（SPU + SKU 维度）────────────────────────────────

@router.post("/{product_id}/images", summary="上传商品图片")
async def upload_image(
    product_id: int,
    request: Request,
    file: UploadFile = File(...),
    sku_id: int | None = Query(None),
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    img = await product_svc.add_product_image(db, product_id, file, sku_id=sku_id)
    await write_audit(
        db, resource_type=AuditResourceType.PRODUCT, action=AuditAction.CREATE,
        user_id=current.id, user_email=current.email,
        resource_id=product_id, request=request,
        extra={"sub_resource": "image", "image_id": img.id},
    )
    return success(_img_to_dict(img))


@router.delete("/{product_id}/images/{image_id}", summary="删除商品图片")
async def delete_image(
    product_id: int,
    image_id: int,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    await product_svc.delete_product_image(db, image_id)
    await write_audit(
        db, resource_type=AuditResourceType.PRODUCT, action=AuditAction.DELETE,
        user_id=current.id, user_email=current.email,
        resource_id=product_id, request=request,
        extra={"sub_resource": "image", "image_id": image_id},
    )
    return success()


@router.patch("/{product_id}/images/{image_id}/set-main", summary="设为主图")
async def set_main_image(
    product_id: int,
    image_id: int,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    await product_svc.set_main_image(db, product_id, image_id)
    await write_audit(
        db, resource_type=AuditResourceType.PRODUCT, action=AuditAction.UPDATE,
        user_id=current.id, user_email=current.email,
        resource_id=product_id, request=request,
        extra={"sub_resource": "image", "image_id": image_id, "action": "set_main"},
    )
    return success()


@router.patch("/{product_id}/images/sort", summary="图片排序")
async def sort_images(
    product_id: int,
    request: Request,
    image_ids: List[int],
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    await product_svc.update_image_sort(db, product_id, image_ids)
    await write_audit(
        db, resource_type=AuditResourceType.PRODUCT, action=AuditAction.UPDATE,
        user_id=current.id, user_email=current.email,
        resource_id=product_id, request=request,
        extra={"sub_resource": "image", "action": "sort"},
    )
    return success()


# ── 供货关系（挂 SKU）────────────────────────────────────

@router.get("/{product_id}/skus/{sku_id}/suppliers", summary="SKU 供货关系列表")
async def list_sku_suppliers(
    product_id: int,
    sku_id: int,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_READ)),
    db: AsyncSession = Depends(get_db),
):
    items = await product_svc.list_sku_suppliers(db, sku_id)
    return success(items)


@router.post("/{product_id}/skus/{sku_id}/suppliers", summary="绑定供应商到 SKU")
async def add_sku_supplier(
    product_id: int,
    sku_id: int,
    request: Request,
    data: SupplierRelationCreate,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    ps = await product_svc.add_sku_supplier(db, sku_id, data)
    await write_audit(
        db, resource_type=AuditResourceType.PRODUCT_SKU, action=AuditAction.CREATE,
        user_id=current.id, user_email=current.email,
        resource_id=sku_id, request=request,
        extra={"sub_resource": "supplier", "supplier_relation_id": ps.id},
    )
    return success({"id": ps.id})


@router.put("/{product_id}/skus/{sku_id}/suppliers/{ps_id}", summary="编辑供货关系")
async def update_sku_supplier(
    product_id: int,
    sku_id: int,
    ps_id: int,
    request: Request,
    data: SupplierRelationUpdate,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    ps = await product_svc.update_sku_supplier(db, ps_id, data)
    await write_audit(
        db, resource_type=AuditResourceType.PRODUCT_SKU, action=AuditAction.UPDATE,
        user_id=current.id, user_email=current.email,
        resource_id=sku_id, request=request,
        extra={"sub_resource": "supplier", "supplier_relation_id": ps.id},
    )
    return success({"id": ps.id})


@router.delete("/{product_id}/skus/{sku_id}/suppliers/{ps_id}", summary="移除供货关系")
async def remove_sku_supplier(
    product_id: int,
    sku_id: int,
    ps_id: int,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    await product_svc.remove_sku_supplier(db, ps_id)
    await write_audit(
        db, resource_type=AuditResourceType.PRODUCT_SKU, action=AuditAction.DELETE,
        user_id=current.id, user_email=current.email,
        resource_id=sku_id, request=request,
        extra={"sub_resource": "supplier", "supplier_relation_id": ps_id},
    )
    return success()


# ── 属性模板 ─────────────────────────────────────────────

@router.get("/attr-templates/{category_code}", summary="品类属性模板")
async def get_attr_templates(
    category_code: str,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_READ)),
    db: AsyncSession = Depends(get_db),
):
    templates = await product_svc.get_attr_templates(db, category_code)
    return success([AttrTemplateSchema.model_validate(t).model_dump() for t in templates])
