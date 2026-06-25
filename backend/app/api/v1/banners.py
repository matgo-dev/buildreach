"""轮播 Banner 公开 API — GET /api/v1/banners。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import success
from app.db.session import get_db
from app.services import banner as banner_service

router = APIRouter(prefix="/banners", tags=["banners"])

# banner 图片目录：容器内 /srv/banners，本地开发 frontend/public/banners
_BANNER_DIR = Path("/srv/banners")
_LOCAL_BANNER_DIR = Path(__file__).resolve().parents[4] / "frontend" / "public" / "banners"
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


@router.get("", summary="获取指定位置的启用 Banner 列表(公开)")
async def list_banners(
    position: str = Query("home_carousel", description="广告位标识"),
    db: AsyncSession = Depends(get_db),
):
    rows = await banner_service.list_active(db, position=position)
    return success([r.model_dump() for r in rows])


@router.get("/slides", summary="扫描 banner 目录返回图片列表(公开，热更新)")
async def list_banner_slides():
    """扫描 data/banners/ 目录，返回除 hero-main 外的所有图片文件名。
    前端轮播组件调用此接口实现 banner 热更新，无需重新构建部署。
    """
    scan_dir = _BANNER_DIR if _BANNER_DIR.is_dir() else _LOCAL_BANNER_DIR
    files = []
    if scan_dir.is_dir():
        files = sorted(
            f.name for f in scan_dir.iterdir()
            if f.is_file() and f.suffix.lower() in _IMAGE_EXTS and f.name != "hero-main.jpg"
        )
    return success(files)
