"""买方行为事件路由 — 最近浏览 / 最近搜索。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.exceptions import success
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_any_role, require_permission
from app.services import buyer_event as event_svc

router = APIRouter(
    prefix="/buyer/events",
    tags=["buyer-events"],
    dependencies=[Depends(require_any_role("BUYER"))],
)


@router.get("/recent-views", summary="最近浏览商品")
async def recent_views(
    current: CurrentUser = Depends(require_permission(Permissions.BUYER_EVENT_READ)),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(8, ge=1, le=20),
):
    items = await event_svc.get_recent_views(db, current.id, limit=limit)
    return success(items)


@router.get("/recent-searches", summary="最近搜索词")
async def recent_searches(
    current: CurrentUser = Depends(require_permission(Permissions.BUYER_EVENT_READ)),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, ge=1, le=30),
):
    keywords = await event_svc.get_recent_searches(db, current.id, limit=limit)
    return success(keywords)


@router.delete("/recent-searches", summary="清空搜索历史")
async def clear_searches(
    current: CurrentUser = Depends(require_permission(Permissions.BUYER_EVENT_READ)),
    db: AsyncSession = Depends(get_db),
):
    deleted = await event_svc.clear_recent_searches(db, current.id)
    await db.commit()
    return success({"deleted": deleted})
