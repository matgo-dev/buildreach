"""运营商品管理 API — v2 i18n 分列模式 + 审计日志。

SPU CRUD + SKU CRUD(含阶梯价) + 图片(SPU/SKU) + 供货关系(挂 SKU)。
全部写路径成功后写 audit_log；可预期校验错误不写审计。
"""
from __future__ import annotations

import math
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.audit.constants import AuditAction, AuditResourceType
from app.audit.logger import write_audit
from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.core.exceptions import success
from app.core.i18n import get_localized
from app.db.models.product_image import ImageType
from app.db.models.product_sku import SkuStatus
from app.db.models.user import User
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_any_role, require_permission
from app.schemas.product import (
    AttrTemplateSchema,
    PriceTierSchema,
    ProductAggregateCreate,
    ProductAggregateSave,
    ProductAttrSchema,
    ProductCreate,
    ProductImageSchema,
    ProductOperator,
    ProductOperatorDetail,
    ProductStatusUpdate,
    ProductUpdate,
    SkuStatusUpdate,
    SkuCreate,
    SkuOperator,
    SkuUpdate,
    SupplierRelationCreate,
    SupplierRelationDetail,
    SupplierRelationUpdate,
)
from app.services import product as product_svc
from app.services.product import spu_price_range

router = APIRouter(
    prefix="/operator/products",
    tags=["operator-products"],
    dependencies=[Depends(require_any_role("OPERATOR"))],
)


# ── 序列化工具 ───────────────────────────────────────────

def _enrich_attrs(attrs, template_map: dict) -> list[dict]:
    """属性序列化：attr_unit/sort_order/display_name 从模板取,key/value 本地化。"""
    from app.core.i18n import get_localized
    result = []
    for attr in attrs:
        tpl = template_map.get(attr.attr_key_en)
        result.append({
            "attr_key": get_localized(attr, "attr_key"),
            "attr_value": get_localized(attr, "attr_value"),
            "attr_unit": tpl.attr_unit if tpl else attr.attr_unit,
            "sort_order": tpl.sort_order if tpl else attr.sort_order,
            "sku_id": attr.sku_id,
            "display_name": tpl.display_name if tpl else attr.attr_key_en,
        })
    result.sort(key=lambda x: x["sort_order"])
    return result


def _img_to_dict(img) -> dict:
    d = ProductImageSchema.model_validate(img).model_dump()
    d["full_url"] = f"{settings.IMAGE_PATH_PREFIX}/{img.image_key}"
    return d


def _alive_images(images):
    """过滤软删图片"""
    return [i for i in images if not getattr(i, "deleted_at", None)]


def _get_main_image_url(p) -> str | None:
    imgs = _alive_images(p.images) if p.images else []
    if not imgs:
        return None
    main = next((i for i in imgs if i.image_type == ImageType.MAIN), None)
    if not main:
        main = sorted(imgs, key=lambda i: i.sort_order)[0]
    return f"{settings.IMAGE_PATH_PREFIX}/{main.image_key}"


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
        name=get_localized(sku, "name") or None,
        name_zh=sku.name_zh,
        name_en=sku.name_en,
        source_lang=sku.source_lang,
        manufacturer_model=sku.manufacturer_model,
        price_min=sku.price_min,
        price_max=sku.price_max,
        moq=sku.moq,
        lead_time_min=sku.lead_time_min,
        lead_time_max=sku.lead_time_max,
        is_default=sku.is_default,
        status=sku.status,
        packing_quantity=sku.packing_quantity,
        gross_weight_kg=sku.gross_weight_kg,
        volume_cbm=sku.volume_cbm,
        price_tiers=tiers,
        images=sku_images,
        supplier_relations=suppliers,
        created_at=sku.created_at,
        updated_at=sku.updated_at,
    ).model_dump()


def _to_operator(p, creator_name_map: dict | None = None, main_image_url: str | None = None) -> dict:
    prices = spu_price_range(p)
    active_count = sum(1 for s in p.skus if s.status == SkuStatus.ACTIVE) if p.skus else 0
    created_by_name = ""
    if creator_name_map and p.created_by:
        created_by_name = creator_name_map.get(p.created_by, "")
    return ProductOperator(
        id=p.id,
        spu_code=p.spu_code,
        name=get_localized(p, "name"),
        name_zh=p.name_zh,
        name_en=p.name_en,
        category_code=p.category_code,
        origin=get_localized(p, "origin"),
        brand=get_localized(p, "brand") or None,
        is_featured=p.is_featured,
        supply_mode=p.supply_mode,
        main_image=main_image_url,
        status=p.status,
        created_by_name=created_by_name,
        price_min=prices["price_min"],
        price_max=prices["price_max"],
        currency=prices["currency"],
        sku_count=active_count,
        published_at=getattr(p, "published_at", None),
        created_at=p.created_at,
        updated_at=p.updated_at,
    ).model_dump()


# ── SPU CRUD ─────────────────────────────────────────────

@router.get("", summary="运营商品列表")
async def list_products(
    category_code: str | None = Query(None),
    status: str | None = Query(None),
    supply_mode: str | None = Query(None),
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_READ)),
    db: AsyncSession = Depends(get_db),
):
    items, total, img_map = await product_svc.list_products_operator(
        db, category_code=category_code, status=status,
        supply_mode=supply_mode, keyword=keyword,
        page=page, size=size,
    )

    # 批量查创建人名称，避免 N+1
    creator_ids = {p.created_by for p in items if p.created_by}
    creator_name_map: dict[int, str] = {}
    if creator_ids:
        rows = (await db.execute(
            select(User.id, User.name).where(User.id.in_(creator_ids))
        )).all()
        creator_name_map = {r.id: r.name for r in rows}

    return success({
        "items": [_to_operator(p, creator_name_map, main_image_url=img_map.get(p.id)) for p in items],
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if size else 0,
    })


@router.post("", summary="创建商品(SPU)")
async def create_product(
    request: Request,
    background_tasks: BackgroundTasks,
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
    from app.db.models.product import Product
    from app.services.i18n_sweeper import enqueue_translation
    enqueue_translation(background_tasks, Product, product.id)
    return success({"id": product.id, "spu_code": product.spu_code})


@router.put("/{product_id}", summary="编辑商品(SPU)")
async def update_product(
    product_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
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
    from app.db.models.product import Product
    from app.services.i18n_sweeper import enqueue_translation
    enqueue_translation(background_tasks, Product, product.id)
    return success({"id": product.id})


@router.patch("/{product_id}/status", summary="上架/下架")
async def update_status(
    product_id: int,
    request: Request,
    data: ProductStatusUpdate,
    force: bool = Query(False, description="跳过上架校验(测试用)"),
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_APPROVE)),
    db: AsyncSession = Depends(get_db),
):
    # force 仅在 ENABLE_DEBUG_API=True 时生效，生产环境硬拦截
    effective_force = force and settings.ENABLE_DEBUG_API
    product = await product_svc.update_product_status(
        db, product_id, data.status, skip_validation=effective_force,
    )
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
    await product_svc.delete_product(db, product_id, operator_id=current.id)
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
    tpl_map = {t.attr_key: t for t in await product_svc.get_attr_templates(db, p.category_code)}

    # 查创建人名称
    created_by_name = ""
    if p.created_by:
        row = (await db.execute(
            select(User.name).where(User.id == p.created_by)
        )).scalar_one_or_none()
        created_by_name = row or ""

    # SPU 级属性
    spu_attrs = [a for a in p.attrs if a.sku_id is None]

    # SKU 级属性按 sku_id 分组
    sku_attr_groups: dict[int, list] = {}
    for a in p.attrs:
        if a.sku_id is not None:
            sku_attr_groups.setdefault(a.sku_id, []).append(a)

    # SKU 序列化带属性
    skus_data = []
    for s in p.skus:
        d = _sku_to_operator(s)
        d["attributes"] = _enrich_attrs(sku_attr_groups.get(s.id, []), tpl_map)
        skus_data.append(d)

    data = ProductOperatorDetail(
        id=p.id,
        spu_code=p.spu_code,
        name=get_localized(p, "name"),
        name_zh=p.name_zh,
        name_en=p.name_en,
        description=get_localized(p, "description"),
        description_zh=p.description_zh,
        description_en=p.description_en,
        category_code=p.category_code,
        origin=get_localized(p, "origin"),
        origin_zh=p.origin_zh,
        origin_en=p.origin_en,
        brand=get_localized(p, "brand") or None,
        brand_zh=p.brand_zh,
        brand_en=p.brand_en,
        hs_code=p.hs_code,
        certifications=p.certifications,
        selling_points=get_localized(p, "selling_points"),
        selling_points_zh=p.selling_points_zh,
        selling_points_en=p.selling_points_en,
        source_lang=p.source_lang,
        is_featured=p.is_featured,
        supply_mode=p.supply_mode,
        unit=p.unit,
        currency=p.currency,
        moq=p.moq,
        moq_unit=p.moq_unit,
        # 物流参数（SPU 级）
        lead_time_min=p.lead_time_min,
        lead_time_max=p.lead_time_max,
        packing_quantity=p.packing_quantity,
        gross_weight_kg=p.gross_weight_kg,
        volume_cbm=p.volume_cbm,
        can_consolidate=p.can_consolidate,
        cargo_type=p.cargo_type,
        status=p.status,
        created_by_name=created_by_name,
        skus=skus_data,
        images=[_img_to_dict(img) for img in p.images],
        attributes=_enrich_attrs(spu_attrs, tpl_map),
        created_at=p.created_at,
        updated_at=p.updated_at,
    ).model_dump()
    return success(data)


# ── 聚合保存（单事务）─────────────────────────────────────

@router.post("/aggregate", summary="聚合创建商品（SPU+SKU 单事务）")
async def create_product_aggregate(
    request: Request,
    background_tasks: BackgroundTasks,
    data: ProductAggregateCreate,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    result = await product_svc.create_product_aggregate(
        db, data,
        actor_id=current.id, actor_email=current.email, request=request,
    )
    product = result["product"]
    # 写后触发 i18n 补译(SPU + 所有新建 SKU)
    from app.db.models.product import Product
    from app.db.models.product_sku import ProductSku
    from app.services.i18n_sweeper import enqueue_translation
    enqueue_translation(background_tasks, Product, product.id)
    for m in result["sku_mappings"]:
        enqueue_translation(background_tasks, ProductSku, m["id"])
    return success({
        "id": product.id,
        "spu_code": product.spu_code,
        "skus": result["sku_mappings"],
    })


@router.put("/{product_id}/aggregate", summary="聚合保存商品（SPU+SKU diff 单事务）")
async def save_product_aggregate(
    product_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    data: ProductAggregateSave,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    product = await product_svc.save_product_aggregate(
        db, product_id, data,
        actor_id=current.id, actor_email=current.email, request=request,
    )
    # 聚合保存后触发 SPU 补译(SKU 由 sweep 兜底)
    from app.db.models.product import Product
    from app.services.i18n_sweeper import enqueue_translation
    enqueue_translation(background_tasks, Product, product.id)
    return success({"id": product.id})


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
    background_tasks: BackgroundTasks,
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
    from app.db.models.product_sku import ProductSku as SkuModel
    from app.services.i18n_sweeper import enqueue_translation
    enqueue_translation(background_tasks, SkuModel, sku.id)
    return success({"id": sku.id, "sku_code": sku.sku_code})


@router.put("/{product_id}/skus/{sku_id}", summary="编辑 SKU")
async def update_sku(
    product_id: int,
    sku_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    data: SkuUpdate,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    sku = await product_svc.update_sku(db, product_id, sku_id, data)
    await write_audit(
        db, resource_type=AuditResourceType.PRODUCT_SKU, action=AuditAction.UPDATE,
        user_id=current.id, user_email=current.email,
        resource_id=sku.id, request=request,
    )
    from app.db.models.product_sku import ProductSku as SkuModel
    from app.services.i18n_sweeper import enqueue_translation
    enqueue_translation(background_tasks, SkuModel, sku.id)
    return success({"id": sku.id})


@router.delete("/{product_id}/skus/{sku_id}", summary="删除 SKU")
async def delete_sku(
    product_id: int,
    sku_id: int,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    await product_svc.delete_sku(db, product_id, sku_id, operator_id=current.id)
    await write_audit(
        db, resource_type=AuditResourceType.PRODUCT_SKU, action=AuditAction.DELETE,
        user_id=current.id, user_email=current.email,
        resource_id=sku_id, request=request,
    )
    return success()


@router.patch("/{product_id}/skus/{sku_id}/status", summary="SKU 启用/停用")
async def update_sku_status(
    product_id: int,
    sku_id: int,
    request: Request,
    data: SkuStatusUpdate,
    current: CurrentUser = Depends(require_permission(Permissions.PRODUCT_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    result = await product_svc.update_sku_status(db, product_id, sku_id, data.status)
    sku = result["sku"]
    await write_audit(
        db, resource_type=AuditResourceType.PRODUCT_SKU, action=AuditAction.STATUS_CHANGE,
        user_id=current.id, user_email=current.email,
        resource_id=sku.id, request=request,
        extra={"new_status": sku.status},
    )
    return success({
        "id": sku.id,
        "status": sku.status,
    })


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
    await product_svc.delete_product_image(db, product_id, image_id, operator_id=current.id)
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
    items = await product_svc.list_sku_suppliers(db, product_id, sku_id)
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
    ps = await product_svc.add_sku_supplier(db, product_id, sku_id, data)
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
    ps = await product_svc.update_sku_supplier(db, product_id, sku_id, ps_id, data)
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
    await product_svc.remove_sku_supplier(db, product_id, sku_id, ps_id, operator_id=current.id)
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
