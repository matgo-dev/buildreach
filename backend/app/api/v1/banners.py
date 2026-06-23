"""轮播 Banner 公开 API — GET /api/v1/banners。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import success
from app.db.session import get_db
from app.services import banner as banner_service

router = APIRouter(prefix="/banners", tags=["banners"])


@router.get("", summary="获取指定位置的启用 Banner 列表(公开)")
async def list_banners(
    position: str = Query("home_carousel", description="广告位标识"),
    db: AsyncSession = Depends(get_db),
):
    rows = await banner_service.list_active(db, position=position)
    return success([r.model_dump() for r in rows])
