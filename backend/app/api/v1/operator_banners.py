"""运营 Banner 管理 API — CRUD + 图片上传。

权限: banner:read / banner:write
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.core.exceptions import (
    ImageFormatInvalidError,
    ImageTooLargeError,
    NotFoundError,
    success,
)
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_permission
from app.schemas.banner import BannerCreate, BannerUpdate
from app.services import banner as banner_service
from app.services._buyer_utils import (
    ALLOWED_EXTENSIONS,
    MAX_IMAGE_SIZE,
    save_uploaded_image_from_path,
)
from app.services.upload_pipeline import run_image_processing, stream_upload_file_to_temp

router = APIRouter(prefix="/operator/banners", tags=["operator-banners"])


@router.post("/upload", summary="上传 Banner 图片")
async def upload_banner_image(
    file: UploadFile = File(...),
    _current: CurrentUser = Depends(require_permission(Permissions.BANNER_WRITE)),
):
    """存到 uploads/banners/,返回相对 key 与可预览的完整 URL。

    横幅不做正方形裁剪(square=False)。前端把返回的 image_url 提交到创建/更新接口,
    banner_service._full_image_url() 会拼上 /static 前缀。
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ImageFormatInvalidError(", ".join(ALLOWED_EXTENSIONS))

    try:
        temp_upload = await stream_upload_file_to_temp(
            file, max_size=MAX_IMAGE_SIZE, suffix=ext,
        )
    except ValueError:
        raise ImageTooLargeError()

    try:
        image_key, _w, _h, _size = await run_image_processing(
            save_uploaded_image_from_path,
            temp_upload.path,
            file.filename or "banner.jpg",
            "banners",
            square=False,
        )
    finally:
        temp_upload.cleanup()

    full_url = f"{settings.IMAGE_PATH_PREFIX.rstrip('/')}/{image_key.lstrip('/')}"
    return success({"image_url": image_key, "full_url": full_url})


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
    db: AsyncSession = Depends(get_db),
    _current: CurrentUser = Depends(require_permission(Permissions.BANNER_WRITE)),
):
    row = await banner_service.create(db, payload)
    await db.commit()
    return success(row.model_dump())


@router.put("/{banner_id}", summary="更新 Banner")
async def update_banner(
    banner_id: int,
    payload: BannerUpdate,
    db: AsyncSession = Depends(get_db),
    _current: CurrentUser = Depends(require_permission(Permissions.BANNER_WRITE)),
):
    row = await banner_service.update(db, banner_id, payload)
    if row is None:
        raise NotFoundError("Banner not found")
    await db.commit()
    return success(row.model_dump())


@router.delete("/{banner_id}", summary="删除 Banner")
async def delete_banner(
    banner_id: int,
    db: AsyncSession = Depends(get_db),
    _current: CurrentUser = Depends(require_permission(Permissions.BANNER_WRITE)),
):
    ok = await banner_service.delete(db, banner_id)
    if not ok:
        raise NotFoundError("Banner not found")
    await db.commit()
    return success(None)
