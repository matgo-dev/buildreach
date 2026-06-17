"""运营分析路由 — 热门商品 / 转化漏斗。"""
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
    prefix="/operator/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_any_role("OPERATOR"))],
)


@router.get("/popular-products", summary="热门商品 Top N")
async def popular_products(
    current: CurrentUser = Depends(require_permission(Permissions.ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    metric: str = Query("view", pattern="^(view|cart|rfq)$"),
):
    data = await event_svc.get_popular_products(db, days=days, limit=limit, metric=metric)
    return success(data)


@router.get("/funnel", summary="转化漏斗")
async def funnel(
    current: CurrentUser = Depends(require_permission(Permissions.ANALYTICS_READ)),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    data = await event_svc.get_funnel_stats(db, days=days)
    return success(data)
