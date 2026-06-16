"""买方注册工具函数 — 手机号归一化、品类校验、图片处理。"""
from __future__ import annotations

import os
import re
import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status

from app.core.exceptions import BusinessError, ImageTooSmallError
from app.core.message_keys import MessageKey
from app.db.models.category import Category

# ── 图片处理常量 ─────────────────────────────────────────────
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
TARGET_SIZE = (800, 800)
JPEG_QUALITY = 85
UPLOAD_BASE_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"

# ── 手机号正则 ───────────────────────────────────────────────
_TZ_E164_RE = re.compile(r"^\+255\d{9}$")


def validate_tz_phone(raw: str) -> str:
    """归一化坦桑尼亚手机号为 E.164 格式 (+255XXXXXXXXX)。

    接受三种输入:+255712345678 / 0712345678 / 712345678
    """
    # TODO: 号段精确校验待运营确认,当前用宽松规则
    phone = raw.strip().replace("-", "").replace(" ", "")

    if phone.startswith("0"):
        phone = "+255" + phone[1:]
    elif phone.startswith("255") and not phone.startswith("+"):
        phone = "+" + phone
    elif not phone.startswith("+255"):
        phone = "+255" + phone

    if not _TZ_E164_RE.match(phone):
        raise BusinessError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            42201,
            "Invalid Tanzania phone number format",
            message_key=MessageKey.BUYER_PHONE_FORMAT,
        )
    return phone


async def validate_active_level1_categories(
    db: AsyncSession, codes: list[str]
) -> None:
    """校验品类 code 列表均为有效的一级品类。"""
    if not codes:
        raise BusinessError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            42203,
            "At least one category is required",
            message_key=MessageKey.BUYER_CATEGORY_REQUIRED,
        )

    stmt = (
        select(Category.code)
        .where(
            Category.code.in_(codes),
            Category.level == 1,
            Category.is_active == True,  # noqa: E712
        )
    )
    result = await db.execute(stmt)
    valid_codes = {row[0] for row in result.all()}

    invalid = [c for c in codes if c not in valid_codes]
    if invalid:
        raise BusinessError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            42204,
            f"Invalid category codes: {', '.join(invalid)}",
            message_key=MessageKey.BUYER_CATEGORY_INVALID,
            message_params={"codes": invalid},
        )


def save_uploaded_image(
    file_content: bytes,
    filename: str,
    subdir: str,
    square: bool = False,
) -> tuple[str, int, int, int]:
    """处理并保存上传图片,返回 (relative_key, width, height, file_size)。"""
    # a. 校验扩展名
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise BusinessError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            42206,
            f"Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            message_key=MessageKey.BUYER_IMAGE_FORMAT,
        )

    # b. 校验文件大小
    if len(file_content) > MAX_IMAGE_SIZE:
        raise BusinessError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            42207,
            "Image size must be under 5MB",
            message_key=MessageKey.BUYER_IMAGE_SIZE,
        )

    # c. 打开图片并转 RGB
    img = Image.open(BytesIO(file_content)).convert("RGB")

    # d. 最小尺寸校验
    if img.width < 200 or img.height < 200:
        raise ImageTooSmallError()

    # e. 缩放到目标尺寸
    img.thumbnail(TARGET_SIZE, Image.LANCZOS)

    # f. 正方形填充(白色背景)
    if square:
        max_side = max(img.width, img.height)
        bg = Image.new("RGB", (max_side, max_side), (255, 255, 255))
        offset = ((max_side - img.width) // 2, (max_side - img.height) // 2)
        bg.paste(img, offset)
        img = bg

    # g/h. 保存为 JPEG
    dest_dir = UPLOAD_BASE_DIR / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex
    dest_path = dest_dir / f"{file_id}.jpg"

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    file_bytes = buf.getvalue()

    dest_path.write_bytes(file_bytes)

    # i. 返回相对路径 key + 尺寸 + 大小
    relative_key = f"{subdir}/{file_id}.jpg"
    return relative_key, img.width, img.height, len(file_bytes)


def validate_image_file(filename: str, content_length: int) -> None:
    """仅校验扩展名和大小,不做图片处理。"""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise BusinessError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            42206,
            f"Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            message_key=MessageKey.BUYER_IMAGE_FORMAT,
        )

    if content_length > MAX_IMAGE_SIZE:
        raise BusinessError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            42207,
            "Image size must be under 5MB",
            message_key=MessageKey.BUYER_IMAGE_SIZE,
        )
