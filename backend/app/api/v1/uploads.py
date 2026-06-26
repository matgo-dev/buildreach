"""文件上传端点 — 与 RFQ 业务域绑定。"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from starlette import status as http_status

from app.core.dependencies import CurrentUser
from app.core.exceptions import success
from app.rbac.constants import Permissions
from app.rbac.guards import require_permission

router = APIRouter(prefix="/uploads", tags=["uploads"])

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.ms-excel",  # .xls
}
IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 50 * 1024 * 1024       # 50MB

MIME_TO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel": ".xls",
}

# uploads/ 目录与 main.py 里 StaticFiles mount 的根目录对齐
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent.parent / "uploads" / "rfq-attachments"


@router.post("/files", summary="上传 RFQ 附件", status_code=http_status.HTTP_200_OK)
async def upload_file(
    file: UploadFile = File(...),
    current: CurrentUser = Depends(require_permission(Permissions.RFQ_CREATE)),
):
    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File type '{content_type}' not allowed",
        )

    # 读取全部内容后再校验大小，避免流式读到一半判断
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE // (1024 * 1024)
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File too large, maximum {max_mb}MB",
        )

    # UUID 文件名防路径注入；扩展名从 MIME 映射表取，不信任用户输入
    ext = MIME_TO_EXT.get(content_type, "")
    filename = f"{uuid.uuid4()}{ext}"

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / filename
    dest.write_bytes(contents)

    url = f"/static/rfq-attachments/{filename}"
    return success({"url": url, "filename": file.filename or ""})
