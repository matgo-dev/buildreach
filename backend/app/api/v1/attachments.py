"""附件端点 — 上传 + 鉴权下载。

上传:multipart/form-data, 流式读取,类型校验(允许族匹配),孤儿配额。
下载:逐文件 scope,委托 owner 域;强制下载 Content-Disposition + nosniff。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.constants import AuditAction, AuditResourceType
from app.audit.logger import write_audit
from app.core.dependencies import CurrentUser, get_current_user
from app.core.exceptions import AttachmentNotFoundError, success
from app.db.models.attachment import Attachment
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_any_permission
from app.services.attachment import (
    resolve_attachment_scope,
    serialize_attachment,
    upload_attachment,
    _content_disposition,
)
from app.services.storage import get_attachment_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attachments", tags=["attachments"])


# ── 上传 ──────────────────────────────────────────────────

@router.post("")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    current: CurrentUser = Depends(
        require_any_permission(Permissions.RFQ_CREATE, Permissions.QUOTE_WRITE),
    ),
    db: AsyncSession = Depends(get_db),
):
    """上传附件,返回孤儿记录(未关联 owner)。"""
    att = await upload_attachment(
        db,
        user_id=current.id,
        filename=file.filename or "unnamed",
        declared_content_type=file.content_type or "application/octet-stream",
        file_stream=file.file,
    )

    await write_audit(
        db,
        resource_type=AuditResourceType.ATTACHMENT,
        action=AuditAction.UPLOAD,
        user_id=current.id,
        user_email=current.email,
        resource_id=att.id,
        request=request,
        extra={
            "file_key": att.file_key,
            "original_filename": att.original_filename,
            "size_bytes": att.size_bytes,
        },
        commit=False,
    )
    await db.commit()

    return success(serialize_attachment(att).model_dump())


# ── 鉴权下载 ──────────────────────────────────────────────

@router.get("/{attachment_id}/download")
async def download(
    attachment_id: int,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """鉴权流式下载。单端点恒 attachment,不提供 inline/preview。"""
    row = await db.execute(
        select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.deleted_at.is_(None),
        )
    )
    att = row.scalar_one_or_none()

    if att is None:
        raise AttachmentNotFoundError()

    # scope 校验
    user_roles = set(current.roles)
    allowed = await resolve_attachment_scope(db, current.id, user_roles, att)
    if not allowed:
        raise AttachmentNotFoundError()

    # 流式下发
    storage = get_attachment_storage()
    try:
        stream = storage.open(att.file_key)
    except FileNotFoundError:
        logger.error(
            "附件存储缺失: attachment_id=%d, file_key=%s, owner_type=%s, owner_id=%s",
            att.id, att.file_key, att.owner_type, att.owner_id,
        )
        raise AttachmentNotFoundError()

    disposition = _content_disposition(att.original_filename)

    return StreamingResponse(
        stream,
        media_type=att.content_type,
        headers={
            "Content-Disposition": disposition,
            "X-Content-Type-Options": "nosniff",
            "Content-Length": str(att.size_bytes),
        },
    )


# ── 鉴权缩略图 ──────────────────────────────────────────

@router.get("/{attachment_id}/thumbnail")
async def thumbnail(
    attachment_id: int,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """鉴权缩略图。有缩略图返回小文件,无则降级返回原图。"""
    row = await db.execute(
        select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.deleted_at.is_(None),
        )
    )
    att = row.scalar_one_or_none()

    if att is None:
        raise AttachmentNotFoundError()

    # scope 校验
    user_roles = set(current.roles)
    allowed = await resolve_attachment_scope(db, current.id, user_roles, att)
    if not allowed:
        raise AttachmentNotFoundError()

    storage = get_attachment_storage()

    # 优先返回缩略图,无则降级返回原图
    if att.thumbnail_key:
        try:
            stream = storage.open(att.thumbnail_key)
            return StreamingResponse(
                stream,
                media_type=att.thumbnail_content_type or "image/jpeg",
                headers={
                    "X-Content-Type-Options": "nosniff",
                    "Content-Length": str(att.thumbnail_size_bytes or 0),
                    "Cache-Control": "private, max-age=3600",
                },
            )
        except FileNotFoundError:
            logger.warning("缩略图文件缺失,降级返回原图: attachment_id=%d", att.id)

    # 降级:返回原图
    try:
        stream = storage.open(att.file_key)
    except FileNotFoundError:
        raise AttachmentNotFoundError()

    return StreamingResponse(
        stream,
        media_type=att.content_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Length": str(att.size_bytes),
            "Cache-Control": "private, max-age=3600",
        },
    )
