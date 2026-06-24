"""运营 Banner 管理 API — CRUD。

权限: banner:read / banner:write
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.constants import AuditAction, AuditResourceType
from app.audit.logger import write_audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import NotFoundError, success
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_permission
from app.schemas.banner import BannerCreate, BannerUpdate
from app.services import banner as banner_service

router = APIRouter(prefix="/operator/banners", tags=["operator-banners"])


@router.get("", summary="Banner 列表(含未启用)")
async def list_banners(
    position: str | None = Query(None, description="按广告位筛选"),
    db: AsyncSession = Depends(get_db),
    _current: CurrentUser = Depends(require_permission(Permissions.BANNER_READ)),
):
    rows = await banner_service.list_all(db, position=position)
    return success([r.model_dump() for r in rows])


@router.post("", summary="创建 Banner")
async def create_banner(
    payload: BannerCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_permission(Permissions.BANNER_WRITE)),
):
    row = await banner_service.create(db, payload)
    await write_audit(
        db,
        resource_type=AuditResourceType.BANNER,
        action=AuditAction.CREATE,
        user_id=current.id,
        user_email=current.email,
        resource_id=row.id,
        request=request,
        commit=False,
    )
    await db.commit()
    return success(row.model_dump())


@router.put("/{banner_id}", summary="更新 Banner")
async def update_banner(
    banner_id: int,
    payload: BannerUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_permission(Permissions.BANNER_WRITE)),
):
    row = await banner_service.update(db, banner_id, payload)
    if row is None:
        raise NotFoundError("Banner not found")
    await write_audit(
        db,
        resource_type=AuditResourceType.BANNER,
        action=AuditAction.UPDATE,
        user_id=current.id,
        user_email=current.email,
        resource_id=banner_id,
        request=request,
        commit=False,
    )
    await db.commit()
    return success(row.model_dump())


@router.delete("/{banner_id}", summary="删除 Banner")
async def delete_banner(
    banner_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_permission(Permissions.BANNER_WRITE)),
):
    ok = await banner_service.delete(db, banner_id)
    if not ok:
        raise NotFoundError("Banner not found")
    await write_audit(
        db,
        resource_type=AuditResourceType.BANNER,
        action=AuditAction.DELETE,
        user_id=current.id,
        user_email=current.email,
        resource_id=banner_id,
        request=request,
        commit=False,
    )
    await db.commit()
    return success(None)
