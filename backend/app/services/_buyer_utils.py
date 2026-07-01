"""买方注册工具函数 — 手机号归一化、品类校验、图片处理。"""
from __future__ import annotations

import logging
import os
import re
import uuid
import warnings
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status

from app.core.config import settings
from app.core.exceptions import BusinessError, ImageTooSmallError
from app.core.message_keys import MessageKey
from app.db.models.category import Category

logger = logging.getLogger(__name__)

# ── 图片处理常量 ─────────────────────────────────────────────
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
TARGET_SIZE = (800, 800)
JPEG_QUALITY = 85
UPLOAD_BASE_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
PRIVATE_UPLOAD_BASE_DIR = Path(__file__).resolve().parent.parent.parent / "private_uploads"
IMAGE_MAX_EDGE = 8000
_IMAGE_FORMATS = ["JPEG", "PNG", "WEBP"]
Image.MAX_IMAGE_PIXELS = settings.IMAGE_MAX_PIXELS

# ── 缩略图常量 ───────────────────────────────────────────────
THUMB_SIZE = (300, 300)
THUMB_WEBP_QUALITY = 80


# ── 缩略图工具函数 ───────────────────────────────────────────

def thumb_key_from_image_key(image_key: str) -> str:
    """image_key → 缩略图 key（约定推导，不查 DB）。"""
    stem, _ = os.path.splitext(image_key)
    return f"{stem}_thumb.webp"


def thumb_url_from_image_key(image_key: str) -> str:
    """image_key → 缩略图完整 URL。"""
    return f"{settings.IMAGE_PATH_PREFIX}/{thumb_key_from_image_key(image_key)}"


def generate_thumbnail(original_path: Path) -> Path | None:
    """为原图生成 WebP 缩略图。幂等：已存在则跳过。"""
    thumb_path = original_path.with_name(
        original_path.stem + "_thumb.webp"
    )
    if thumb_path.exists():
        return thumb_path
    try:
        img = _open_verified_image(lambda: original_path)
        img.thumbnail(THUMB_SIZE, Image.LANCZOS)
        img.save(thumb_path, format="WEBP", quality=THUMB_WEBP_QUALITY)
        return thumb_path
    except Exception:
        logger.warning("缩略图生成失败: %s", original_path, exc_info=True)
        return None

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
    """校验品类 code 列表均为有效的一级品类（允许空列表）。"""
    if not codes:
        return

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


def _safe_upload_dir(base_dir: Path, subdir: str) -> Path:
    subdir_path = Path(subdir)
    if subdir_path.is_absolute() or ".." in subdir_path.parts:
        raise ValueError("Invalid upload subdir")
    return base_dir / subdir_path


def _raise_image_format() -> None:
    raise BusinessError(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        42206,
        f"Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        message_key=MessageKey.BUYER_IMAGE_FORMAT,
    )


def _raise_image_size() -> None:
    raise BusinessError(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        42207,
        "Image size must be under 5MB and within pixel limits",
        message_key=MessageKey.BUYER_IMAGE_SIZE,
    )


def _open_verified_image(source_factory) -> Image.Image:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(source_factory(), formats=_IMAGE_FORMATS) as probe:
                probe.verify()
            with Image.open(source_factory(), formats=_IMAGE_FORMATS) as img:
                img = ImageOps.exif_transpose(img)
                if (
                    img.width * img.height > settings.IMAGE_MAX_PIXELS
                    or max(img.width, img.height) > IMAGE_MAX_EDGE
                ):
                    _raise_image_size()
                img.load()
                return img.convert("RGB")
    except BusinessError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        _raise_image_size()
    except (UnidentifiedImageError, OSError, ValueError):
        _raise_image_format()


def _prepare_image(
    file_content: bytes,
    filename: str,
    square: bool = False,
) -> tuple[bytes, int, int]:
    """校验并处理上传图片,返回 (jpeg_bytes, width, height)。"""
    # a. 校验扩展名
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        _raise_image_format()

    # b. 校验文件大小
    if len(file_content) > MAX_IMAGE_SIZE:
        _raise_image_size()

    # c. 打开图片并转 RGB
    img = _open_verified_image(lambda: BytesIO(file_content))

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

    # g. 编码为 JPEG
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue(), img.width, img.height


def _prepare_image_from_path(
    source_path: Path,
    filename: str,
    square: bool = False,
) -> tuple[bytes, int, int]:
    """校验并处理上传图片文件,返回 (jpeg_bytes, width, height)。"""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        _raise_image_format()
    if source_path.stat().st_size > MAX_IMAGE_SIZE:
        _raise_image_size()

    img = _open_verified_image(lambda: source_path)
    if img.width < 200 or img.height < 200:
        raise ImageTooSmallError()
    img.thumbnail(TARGET_SIZE, Image.LANCZOS)
    if square:
        max_side = max(img.width, img.height)
        bg = Image.new("RGB", (max_side, max_side), (255, 255, 255))
        offset = ((max_side - img.width) // 2, (max_side - img.height) // 2)
        bg.paste(img, offset)
        img = bg

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue(), img.width, img.height


def _save_uploaded_image_to_base(
    file_content: bytes,
    filename: str,
    base_dir: Path,
    subdir: str,
    square: bool = False,
) -> tuple[str, int, int, int]:
    file_bytes, width, height = _prepare_image(file_content, filename, square)

    dest_dir = _safe_upload_dir(base_dir, subdir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex
    dest_path = dest_dir / f"{file_id}.jpg"

    dest_path.write_bytes(file_bytes)
    generate_thumbnail(dest_path)

    relative_key = f"{subdir}/{file_id}.jpg"
    return relative_key, width, height, len(file_bytes)


def _save_uploaded_image_path_to_base(
    source_path: Path,
    filename: str,
    base_dir: Path,
    subdir: str,
    square: bool = False,
) -> tuple[str, int, int, int]:
    file_bytes, width, height = _prepare_image_from_path(source_path, filename, square)

    dest_dir = _safe_upload_dir(base_dir, subdir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex
    dest_path = dest_dir / f"{file_id}.jpg"

    dest_path.write_bytes(file_bytes)
    generate_thumbnail(dest_path)

    relative_key = f"{subdir}/{file_id}.jpg"
    return relative_key, width, height, len(file_bytes)


def save_uploaded_image(
    file_content: bytes,
    filename: str,
    subdir: str,
    square: bool = False,
) -> tuple[str, int, int, int]:
    """处理并保存公开上传图片,返回 (relative_key, width, height, file_size)。"""
    return _save_uploaded_image_to_base(
        file_content,
        filename,
        UPLOAD_BASE_DIR,
        subdir,
        square=square,
    )


def save_uploaded_image_from_path(
    source_path: Path,
    filename: str,
    subdir: str,
    square: bool = False,
) -> tuple[str, int, int, int]:
    """处理并保存公开上传图片文件,返回 (relative_key, width, height, file_size)。"""
    return _save_uploaded_image_path_to_base(
        source_path,
        filename,
        UPLOAD_BASE_DIR,
        subdir,
        square=square,
    )


def save_private_buyer_image(
    file_content: bytes,
    filename: str,
    subdir: str,
    square: bool = False,
) -> tuple[str, int, int, int]:
    """处理并保存买方注册私有图片,返回相对 private_uploads 的 key。"""
    return _save_uploaded_image_to_base(
        file_content,
        filename,
        PRIVATE_UPLOAD_BASE_DIR,
        subdir,
        square=square,
    )


def save_private_buyer_image_from_path(
    source_path: Path,
    filename: str,
    subdir: str,
    square: bool = False,
) -> tuple[str, int, int, int]:
    """处理并保存买方注册私有图片文件,返回相对 private_uploads 的 key。"""
    return _save_uploaded_image_path_to_base(
        source_path,
        filename,
        PRIVATE_UPLOAD_BASE_DIR,
        subdir,
        square=square,
    )


def delete_private_buyer_image(image_key: str) -> None:
    """删除买方注册私有图片(best-effort 调用方自行吞异常)。"""
    path = _safe_upload_dir(PRIVATE_UPLOAD_BASE_DIR, image_key)
    path.unlink(missing_ok=True)


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
