"""运营端 — 专区授权管理 API。

只管「买家组织 ↔ 专区」授权(列出/新增/撤销);专区选品仍走导入脚本。
权限: zone:manage (已授予 OPERATOR 角色)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.constants import AuditAction, AuditResourceType
from app.audit.logger import write_audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import NotFoundError, success
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_permission
from app.services import zone_grant as zone_grant_service

router = APIRouter(prefix="/operator/zones", tags=["operator-zones"])


class GrantCreate(BaseModel):
    buyer_org_id: int


@router.get("", summary="专区列表")
async def list_zones(
    db: AsyncSession = Depends(get_db),
    _current: CurrentUser = Depends(require_permission(Permissions.ZONE_MANAGE)),
):
    return success(await zone_grant_service.list_zones(db))


@router.get("/{zone_code}/grants", summary="某专区已授权的买家组织")
async def list_grants(
    zone_code: str,
    db: AsyncSession = Depends(get_db),
    _current: CurrentUser = Depends(require_permission(Permissions.ZONE_MANAGE)),
):
    zone = await zone_grant_service._get_zone(db, zone_code)
    if zone is None:
        raise NotFoundError("专区不存在")
    return success(await zone_grant_service.list_grants(db, zone))


@router.post("/{zone_code}/grants", summary="授权买家组织访问专区(幂等)")
async def create_grant(
    zone_code: str,
    payload: GrantCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_permission(Permissions.ZONE_MANAGE)),
):
    zone = await zone_grant_service._get_zone(db, zone_code)
    if zone is None:
        raise NotFoundError("专区不存在")
    row, status = await zone_grant_service.grant(
        db, zone, payload.buyer_org_id, granted_by=current.id
    )
    if status == "org_not_found":
        raise NotFoundError("买家组织不存在")
    if status == "created":  # 幂等重复授权不产生状态变更,不审计
        await write_audit(
            db,
            resource_type=AuditResourceType.ZONE_GRANT,
            action=AuditAction.CREATE,
            user_id=current.id,
            user_email=current.email,
            resource_id=payload.buyer_org_id,
            request=request,
            extra={"zone_code": zone_code, "buyer_org_id": payload.buyer_org_id},
            commit=False,
        )
    await db.commit()
    return success(row)


@router.delete("/{zone_code}/grants/{buyer_org_id}", summary="撤销授权")
async def delete_grant(
    zone_code: str,
    buyer_org_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(require_permission(Permissions.ZONE_MANAGE)),
):
    zone = await zone_grant_service._get_zone(db, zone_code)
    if zone is None:
        raise NotFoundError("专区不存在")
    ok = await zone_grant_service.revoke(db, zone, buyer_org_id)
    if not ok:
        raise NotFoundError("该组织未被授权此专区")
    await write_audit(
        db,
        resource_type=AuditResourceType.ZONE_GRANT,
        action=AuditAction.DELETE,
        user_id=current.id,
        user_email=current.email,
        resource_id=buyer_org_id,
        request=request,
        extra={"zone_code": zone_code, "buyer_org_id": buyer_org_id},
        commit=False,
    )
    await db.commit()
    return success(None)
