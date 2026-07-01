"""附件 Service — 上传/下载/关联/解关联,policy-free 通用层。

安全核心:
- 扩展名白名单 + 声明 MIME + 内容嗅探(libmagic)允许族匹配
- 私有存储,不经公开静态挂载
- 下载逐文件 scope,委托 owner 域;上传者放行仅孤儿期
- 孤儿 TTL(72h) + 单用户孤儿配额(20 个 / 100MB)
- Content-Disposition 安全编码 + nosniff + 强制下载
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
import warnings
import zipfile
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from urllib.parse import quote as url_quote

import magic
from PIL import Image

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AttachmentAlreadyLinkedError,
    AttachmentNotFoundError,
    AttachmentOrphanQuotaError,
    AttachmentTooLargeError,
    AttachmentTooManyError,
    AttachmentTypeNotAllowedError,
)
from app.db.base import _utcnow
from app.db.models.attachment import Attachment, OwnerType
from app.schemas.attachment import AttachmentPublic
from app.services.storage import get_attachment_storage
from app.services.upload_pipeline import run_image_processing, stream_binary_to_temp

logger = logging.getLogger(__name__)

# ── 配置常量 ──────────────────────────────────────────────

MAX_FILE_SIZE = 50 * 1024 * 1024       # 50MB
MAX_ATTACHMENTS_PER_OWNER = 6
ORPHAN_TTL_HOURS = 72
ORPHAN_QUOTA_COUNT = 20
ORPHAN_QUOTA_BYTES = 100 * 1024 * 1024  # 100MB

# ── 允许族定义 ────────────────────────────────────────────

ALLOWED_FAMILIES: dict[str, dict] = {
    "image/jpeg": {
        "mimes": {"image/jpeg"},
        "ext": {".jpg", ".jpeg"},
        "canonical": "image/jpeg",
        "max_size": MAX_FILE_SIZE,
    },
    "image/png": {
        "mimes": {"image/png"},
        "ext": {".png"},
        "canonical": "image/png",
        "max_size": MAX_FILE_SIZE,
    },
    "image/webp": {
        "mimes": {"image/webp"},
        "ext": {".webp"},
        "canonical": "image/webp",
        "max_size": MAX_FILE_SIZE,
    },
    "application/pdf": {
        "mimes": {"application/pdf"},
        "ext": {".pdf"},
        "canonical": "application/pdf",
        "max_size": MAX_FILE_SIZE,
    },
    "spreadsheet_xlsx": {
        "mimes": {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/zip",
            "application/octet-stream",
        },
        "ext": {".xlsx"},
        "canonical": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "max_size": MAX_FILE_SIZE,
    },
    "spreadsheet_xls": {
        "mimes": {"application/vnd.ms-excel", "application/octet-stream"},
        "ext": {".xls"},
        "canonical": "application/vnd.ms-excel",
        "max_size": MAX_FILE_SIZE,
    },
    "archive_zip": {
        "mimes": {"application/zip", "application/x-zip-compressed", "application/octet-stream"},
        "ext": {".zip"},
        "canonical": "application/zip",
        "max_size": MAX_FILE_SIZE,
    },
    "archive_rar": {
        "mimes": {"application/x-rar-compressed", "application/vnd.rar", "application/octet-stream"},
        "ext": {".rar"},
        "canonical": "application/x-rar-compressed",
        "max_size": MAX_FILE_SIZE,
    },
    "document_docx": {
        "mimes": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/octet-stream"},
        "ext": {".docx"},
        "canonical": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "max_size": MAX_FILE_SIZE,
    },
    "document_doc": {
        "mimes": {"application/msword", "application/octet-stream"},
        "ext": {".doc"},
        "canonical": "application/msword",
        "max_size": MAX_FILE_SIZE,
    },
}

# 扩展名 → 族映射(快速查找)
_EXT_TO_FAMILY: dict[str, dict] = {}
for _fam in ALLOWED_FAMILIES.values():
    for _ext in _fam["ext"]:
        _EXT_TO_FAMILY[_ext] = _fam

# 所有合法扩展名
ALLOWED_EXTENSIONS = set(_EXT_TO_FAMILY.keys())


# ── 安全工具 ──────────────────────────────────────────────

_UNSAFE_CHARS = re.compile(r'[\r\n\x00-\x1f/\\]')


def _sanitize_filename(name: str) -> str:
    """清理文件名:去除 CRLF、路径分隔符、控制字符。"""
    return _UNSAFE_CHARS.sub("_", name).strip()


def _make_ascii_fallback(name: str) -> str:
    """非 ASCII 字符降级为下划线。"""
    return "".join(c if ord(c) < 128 else "_" for c in name)


def _content_disposition(original_filename: str) -> str:
    """RFC 5987 Content-Disposition: attachment + ASCII fallback + UTF-8 原名。"""
    safe = _sanitize_filename(original_filename)
    ascii_name = _make_ascii_fallback(safe)
    utf8_name = url_quote(safe, safe="")
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{utf8_name}'


# ── 类型校验 ──────────────────────────────────────────────

def validate_file_type(
    ext: str,
    declared_mime: str,
    file_bytes: bytes,
) -> tuple[str, int]:
    """校验文件类型:扩展名 + 声明 MIME + 内容嗅探允许族匹配。

    返回 (canonical_mime, max_size)。校验失败抛 AttachmentTypeNotAllowedError。
    """
    ext_lower = ext.lower()
    family = _EXT_TO_FAMILY.get(ext_lower)
    if not family:
        raise AttachmentTypeNotAllowedError()

    # 声明 MIME 必须在族的 mimes 内
    if declared_mime not in family["mimes"]:
        raise AttachmentTypeNotAllowedError()

    # 内容嗅探
    sniffed = magic.from_buffer(file_bytes, mime=True)
    if sniffed not in family["mimes"]:
        raise AttachmentTypeNotAllowedError()

    # .xlsx 加固:嗅探得 zip/octet-stream 时校验 ZIP 内部结构
    if ext_lower == ".xlsx" and sniffed in ("application/zip", "application/octet-stream"):
        if not _verify_xlsx_structure(file_bytes):
            raise AttachmentTypeNotAllowedError()

    return family["canonical"], family["max_size"]


def validate_file_type_from_path(
    ext: str,
    declared_mime: str,
    path: Path,
    head: bytes,
) -> tuple[str, int]:
    """校验文件类型:扩展名 + 声明 MIME + 文件内容嗅探允许族匹配。"""
    ext_lower = ext.lower()
    family = _EXT_TO_FAMILY.get(ext_lower)
    if not family:
        raise AttachmentTypeNotAllowedError()

    if declared_mime not in family["mimes"]:
        raise AttachmentTypeNotAllowedError()

    sniffed = magic.from_file(str(path), mime=True)
    if sniffed not in family["mimes"]:
        # 某些 libmagic 版本对短文件 from_file 更保守,用 header 兜底一次。
        sniffed = magic.from_buffer(head, mime=True)
    if sniffed not in family["mimes"]:
        raise AttachmentTypeNotAllowedError()

    if ext_lower == ".xlsx" and sniffed in ("application/zip", "application/octet-stream"):
        if not _verify_xlsx_structure_from_path(path):
            raise AttachmentTypeNotAllowedError()

    return family["canonical"], family["max_size"]


def _verify_xlsx_structure(file_bytes: bytes) -> bool:
    """校验 ZIP 内部至少含 [Content_Types].xml 与 xl/workbook.xml。"""
    try:
        with zipfile.ZipFile(BytesIO(file_bytes)) as zf:
            names = zf.namelist()
            return "[Content_Types].xml" in names and "xl/workbook.xml" in names
    except (zipfile.BadZipFile, Exception):
        return False


def _verify_xlsx_structure_from_path(path: Path) -> bool:
    """校验 ZIP 文件至少含 [Content_Types].xml 与 xl/workbook.xml。"""
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            return "[Content_Types].xml" in names and "xl/workbook.xml" in names
    except (zipfile.BadZipFile, Exception):
        return False


# ── 缩略图生成 ──────────────────────────────────────────

THUMBNAIL_MAX_EDGE = 300
THUMBNAIL_QUALITY = 80
_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
IMAGE_MAX_EDGE = 8000
Image.MAX_IMAGE_PIXELS = settings.IMAGE_MAX_PIXELS


def generate_thumbnail(file_bytes: bytes) -> tuple[bytes, str, int] | None:
    """为图片生成缩略图。返回 (thumb_bytes, content_type, size) 或 None。"""
    try:
        img = Image.open(BytesIO(file_bytes))
        img.thumbnail((THUMBNAIL_MAX_EDGE, THUMBNAIL_MAX_EDGE), Image.LANCZOS)
        # RGBA → RGB（JPEG 不支持 alpha 通道）
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=THUMBNAIL_QUALITY, optimize=True)
        thumb_bytes = buf.getvalue()
        return thumb_bytes, "image/jpeg", len(thumb_bytes)
    except Exception:
        logger.warning("缩略图生成失败", exc_info=True)
        return None


def generate_thumbnail_from_path(path: Path) -> tuple[bytes, str, int] | None:
    """为图片文件生成缩略图。返回 (thumb_bytes, content_type, size) 或 None。"""
    try:
        with Image.open(path) as img:
            img.thumbnail((THUMBNAIL_MAX_EDGE, THUMBNAIL_MAX_EDGE), Image.LANCZOS)
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=THUMBNAIL_QUALITY, optimize=True)
        thumb_bytes = buf.getvalue()
        return thumb_bytes, "image/jpeg", len(thumb_bytes)
    except Exception:
        logger.warning("缩略图生成失败", exc_info=True)
        return None


def validate_image_pixels(path: Path) -> None:
    """Reject image files that would decode to excessive pixel counts."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as img:
                if (
                    img.width * img.height > settings.IMAGE_MAX_PIXELS
                    or max(img.width, img.height) > IMAGE_MAX_EDGE
                ):
                    raise AttachmentTooLargeError()
    except AttachmentTooLargeError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise AttachmentTooLargeError()
    except Exception:
        raise AttachmentTypeNotAllowedError()


# ── 上传 ──────────────────────────────────────────────────

async def upload_attachment(
    db: AsyncSession,
    user_id: int,
    filename: str,
    declared_content_type: str,
    file_stream: BinaryIO,
) -> Attachment:
    """上传附件:校验 → 写文件 → 落库。返回 Attachment 实例。

    文件写入不参与 DB 事务:临时文件→fsync→rename→DB commit。
    """
    original_filename = _sanitize_filename(filename)
    if not original_filename:
        original_filename = "unnamed"

    # 提取扩展名
    ext = PurePosixPath(original_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise AttachmentTypeNotAllowedError()

    try:
        temp_upload = await stream_binary_to_temp(
            file_stream,
            max_size=MAX_FILE_SIZE,
            suffix=ext,
        )
    except ValueError:
        raise AttachmentTooLargeError()

    storage = get_attachment_storage()
    file_key = f"{uuid.uuid4().hex}{ext}"
    thumbnail_key = None
    thumbnail_content_type = None
    thumbnail_size_bytes = None

    try:
        # 类型校验(扩展名 + 声明 MIME + 嗅探)
        canonical_mime, max_size = await asyncio.to_thread(
            validate_file_type_from_path,
            ext,
            declared_content_type,
            temp_upload.path,
            temp_upload.head,
        )

        # 按实际族的大小限制校验
        if temp_upload.size > max_size:
            raise AttachmentTooLargeError()
        if canonical_mime in _IMAGE_MIMES:
            await asyncio.to_thread(validate_image_pixels, temp_upload.path)

        # 孤儿配额校验
        await _check_orphan_quota(db, user_id)

        # 写文件(不在 DB 事务内)
        with open(temp_upload.path, "rb") as src:
            await asyncio.to_thread(storage.save, file_key, src)

        # 图片类型:生成缩略图
        if canonical_mime in _IMAGE_MIMES:
            result = await run_image_processing(
                generate_thumbnail_from_path,
                temp_upload.path,
            )
            if result:
                thumb_bytes, thumb_ct, thumb_size = result
                thumbnail_key = f"thumbnail_{uuid.uuid4().hex}.jpg"
                await asyncio.to_thread(storage.save, thumbnail_key, BytesIO(thumb_bytes))
                thumbnail_content_type = thumb_ct
                thumbnail_size_bytes = thumb_size

        # 落库
        att = Attachment(
            file_key=file_key,
            original_filename=original_filename,
            content_type=canonical_mime,
            size_bytes=temp_upload.size,
            uploaded_by_user_id=user_id,
            owner_type=None,
            owner_id=None,
            first_linked_at=None,
            thumbnail_key=thumbnail_key,
            thumbnail_content_type=thumbnail_content_type,
            thumbnail_size_bytes=thumbnail_size_bytes,
        )
        db.add(att)
        await db.flush()
        return att
    except BaseException:
        # DB 失败,best-effort 删除已写文件
        try:
            storage.delete(file_key)
        except Exception:
            logger.error("DB commit 失败后删除文件也失败: file_key=%s", file_key)
        if thumbnail_key:
            try:
                storage.delete(thumbnail_key)
            except Exception:
                logger.error("DB commit 失败后删除缩略图也失败: file_key=%s", thumbnail_key)
        raise
    finally:
        temp_upload.cleanup()


async def _check_orphan_quota(db: AsyncSession, user_id: int) -> None:
    """单用户未归属孤儿配额:数量 ≤ 20 且合计 size_bytes ≤ 100MB。"""
    result = await db.execute(
        select(func.count(), func.coalesce(func.sum(Attachment.size_bytes), 0))
        .where(
            Attachment.uploaded_by_user_id == user_id,
            Attachment.owner_type.is_(None),
            Attachment.deleted_at.is_(None),
        )
    )
    count, total_size = result.one()
    if count >= ORPHAN_QUOTA_COUNT or total_size >= ORPHAN_QUOTA_BYTES:
        raise AttachmentOrphanQuotaError()


# ── 下载 scope ────────────────────────────────────────────

async def resolve_attachment_scope(
    db: AsyncSession,
    user_id: int,
    user_roles: set[str],
    att: Attachment,
    *,
    _resolve_rfq_access: object = None,
) -> bool:
    """判断当前用户是否可下载此附件。返回 True 放行,False 拒绝。

    policy-free:通用层不带平台可见性策略,委托 owner 域判定。
    """
    # 1. 孤儿(从未归属)
    if att.owner_type is None:
        if att.first_linked_at is not None:
            # 曾归属、现解绑 → 不退回孤儿下载
            return False
        if att.uploaded_by_user_id != user_id:
            return False
        # 孤儿 TTL 校验
        now = _utcnow()
        if now - att.created_at > timedelta(hours=ORPHAN_TTL_HOURS):
            return False
        return True

    # 2. RFQ 归属 → 委托 RFQ scope
    if att.owner_type == OwnerType.RFQ:
        return await _check_rfq_scope(db, user_id, user_roles, att.owner_id)

    # 3. QUOTE 归属 → 委托 quote→rfq_id→RFQ scope（买方 + 运营可见）
    if att.owner_type == OwnerType.QUOTE:
        from app.db.models.rfq_quote import RfqQuote
        row = await db.execute(
            select(RfqQuote.rfq_id).where(
                RfqQuote.id == att.owner_id,
                RfqQuote.deleted_at.is_(None),
            )
        )
        rfq_id = row.scalar_one_or_none()
        if rfq_id is None:
            return False
        return await _check_rfq_scope(db, user_id, user_roles, rfq_id)

    return False


async def _check_rfq_scope(
    db: AsyncSession,
    user_id: int,
    user_roles: set[str],
    rfq_id: int,
) -> bool:
    """RFQ 附件 scope:买方自有 + 受理运营。"""
    from app.db.models.rfq import Rfq
    from app.db.models.buyer_member import BuyerMember

    row = await db.execute(
        select(Rfq).where(Rfq.id == rfq_id, Rfq.deleted_at.is_(None))
    )
    rfq = row.scalar_one_or_none()
    if not rfq:
        return False

    # 运营:可见(受理人或任一运营)
    if "OPERATOR" in user_roles:
        return True

    # 买方:本组织
    if "BUYER" in user_roles:
        member_row = await db.execute(
            select(BuyerMember.buyer_org_id).where(BuyerMember.user_id == user_id).limit(1)
        )
        buyer_org_id = member_row.scalar_one_or_none()
        return buyer_org_id is not None and buyer_org_id == rfq.buyer_org_id

    return False


# ── 关联/解关联 ───────────────────────────────────────────

async def validate_and_link_attachments(
    db: AsyncSession,
    user_id: int,
    owner_type: str,
    owner_id: int,
    attachment_ids: list[int],
) -> list[Attachment]:
    """在 owner 写事务内关联附件。返回关联后的附件列表。

    §六 完整分支逻辑:
    A. 已属当前 owner → 幂等保留
    B. 未归属草稿孤儿 → 新关联
    C. 已属其他 owner → 40526
    """
    if len(attachment_ids) > MAX_ATTACHMENTS_PER_OWNER:
        raise AttachmentTooManyError()

    now = _utcnow()
    linked: list[Attachment] = []

    for att_id in attachment_ids:
        row = await db.execute(
            select(Attachment).where(
                Attachment.id == att_id,
                Attachment.deleted_at.is_(None),
            )
        )
        att = row.scalar_one_or_none()
        if att is None:
            raise AttachmentNotFoundError()

        # A: 已属当前 owner → 幂等放行
        if att.owner_type == owner_type and att.owner_id == owner_id:
            linked.append(att)
            continue

        # C: 已属其他 owner → 拒绝
        if att.owner_type is not None:
            raise AttachmentAlreadyLinkedError()

        # B: 未归属 → 校验条件
        if att.first_linked_at is not None:
            # 曾归属、现解绑 → 不可作为新关联
            raise AttachmentNotFoundError()

        if att.uploaded_by_user_id != user_id:
            raise AttachmentNotFoundError()

        # TTL 校验
        if now - att.created_at > timedelta(hours=ORPHAN_TTL_HOURS):
            raise AttachmentNotFoundError()

        # 关联
        att.owner_type = owner_type
        att.owner_id = owner_id
        if att.first_linked_at is None:
            att.first_linked_at = now
        linked.append(att)

    # 协调:本 owner 原关联、不在新列表中的 → 解关联
    id_set = set(attachment_ids)
    existing = await db.execute(
        select(Attachment).where(
            Attachment.owner_type == owner_type,
            Attachment.owner_id == owner_id,
            Attachment.deleted_at.is_(None),
        )
    )
    for old_att in existing.scalars().all():
        if old_att.id not in id_set:
            old_att.owner_type = None
            old_att.owner_id = None
            # first_linked_at 保留不清

    return linked


# ── 序列化 ────────────────────────────────────────────────

def serialize_attachment(att: Attachment) -> AttachmentPublic:
    """附件 → DTO。"""
    return AttachmentPublic(
        id=att.id,
        original_filename=att.original_filename,
        content_type=att.content_type,
        size_bytes=att.size_bytes,
        download_url=f"/api/v1/attachments/{att.id}/download",
        thumbnail_url=f"/api/v1/attachments/{att.id}/thumbnail" if att.thumbnail_key else None,
    )


async def list_attachments_for_owner(
    db: AsyncSession,
    owner_type: str,
    owner_id: int,
) -> list[AttachmentPublic]:
    """查询 owner 下所有活跃附件。"""
    result = await db.execute(
        select(Attachment).where(
            Attachment.owner_type == owner_type,
            Attachment.owner_id == owner_id,
            Attachment.deleted_at.is_(None),
        ).order_by(Attachment.id)
    )
    return [serialize_attachment(a) for a in result.scalars().all()]
