"""报价单 PDF 导出服务。"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import time
from datetime import datetime
from decimal import Decimal
from functools import partial
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.core.exceptions import RfqNoQuoteToExportError, RfqNotFoundError
from app.db.base import _utcnow
from app.db.models.product_image import ImageType, ProductImage
from app.db.models.quote_document import QuoteDocument
from app.schemas.quote import RfqQuoteBuyerPublic
from app.services._rfq_loader import (
    _resolve_buyer_org_id,
    load_rfq,
    resolve_rfq_scope,
)
from app.services.quote import load_quote_for_rfq_detail
from app.templates.quote_pdf.labels import get_labels

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "quote_pdf"
_UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads"
logger = logging.getLogger("app.quote_export")
_PDF_CACHE_DIRNAME = ".quote_pdf_cache"

MAX_RETRIES = 3

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
)

# 平台静态抬头(发出方)
_PLATFORM_INFO = {
    "name": "BuildLink East Africa",
    "address": "",
    "email": "info@buildlink.co",
}


def _format_amount(value: Decimal | float | None) -> str:
    """金额格式化:千分位 + 两位小数。"""
    if value is None:
        return "—"
    return f"{Decimal(str(value)):,.2f}"


def _format_date(dt: datetime | str | None, locale: str) -> str:
    """日期格式化。"""
    if dt is None:
        return "—"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except (ValueError, TypeError):
            return str(dt)
    return dt.strftime("%Y-%m-%d")


def _image_key_to_file_uri(image_key: str | None) -> str | None:
    """Return a local file URI for product images used by PDF rendering.

    WeasyPrint would otherwise fetch IMAGE_BASE_URL over HTTP while the request
    is already inside the backend container. On ECS that self-roundtrip can add
    seconds and can fail independently of PDF generation.
    """
    if not image_key:
        return None

    normalized = Path(image_key)
    if normalized.is_absolute() or ".." in normalized.parts:
        return None

    image_path = (_UPLOADS_DIR / normalized).resolve()
    try:
        image_path.relative_to(_UPLOADS_DIR.resolve())
    except ValueError:
        return None

    if not image_path.is_file():
        return None
    return image_path.as_uri()


def _image_key_to_pdf_src(image_key: str | None) -> str | None:
    """Return a small cached data URI for product images embedded in quote PDFs."""
    if not image_key:
        return None

    normalized = Path(image_key)
    if normalized.is_absolute() or ".." in normalized.parts:
        return None

    uploads_root = _UPLOADS_DIR.resolve()
    image_path = (_UPLOADS_DIR / normalized).resolve()
    try:
        relative_key = image_path.relative_to(uploads_root).as_posix()
    except ValueError:
        return None

    if not image_path.is_file():
        return None

    try:
        stat = image_path.stat()
        cache_key = hashlib.sha256(
            f"{relative_key}:{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8")
        ).hexdigest()
        thumb_dir = _UPLOADS_DIR / ".quote_pdf_thumbs"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = thumb_dir / f"{cache_key}.jpg"

        if not thumb_path.is_file():
            from PIL import Image, ImageOps

            with Image.open(image_path) as img:
                img = ImageOps.exif_transpose(img).convert("RGB")
                img.thumbnail((96, 96), Image.LANCZOS)
                img.save(thumb_path, format="JPEG", quality=72, optimize=True)

        encoded = base64.b64encode(thumb_path.read_bytes()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        logger.warning(
            "quote PDF image thumbnail failed image_key=%s",
            image_key,
            exc_info=True,
        )
        return None


def _safe_upload_path(upload_key: str | None) -> Path | None:
    if not upload_key:
        return None

    normalized = Path(upload_key)
    if normalized.is_absolute() or ".." in normalized.parts:
        return None

    uploads_root = _UPLOADS_DIR.resolve()
    path = (_UPLOADS_DIR / normalized).resolve()
    try:
        path.relative_to(uploads_root)
    except ValueError:
        return None
    return path


def _file_signature(path: Path) -> dict[str, int | str | bool]:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return {"path": path.name, "exists": False}
    return {
        "path": path.name,
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _image_signature(image_key: str | None) -> dict[str, int | str | bool | None]:
    path = _safe_upload_path(image_key)
    if path is None:
        return {"key": image_key, "exists": False}
    signature = _file_signature(path)
    signature["key"] = image_key
    return signature


def _jsonable(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return value


def _quote_cache_payload(
    *,
    rfq: object,
    quote: RfqQuoteBuyerPublic,
    locale: str,
    cache_date: str,
    image_keys: dict[int, str],
) -> dict[str, object]:
    return {
        "version": 1,
        "locale": locale,
        # The footer includes generated_at and the download filename uses the
        # current date, so cache for the day instead of forever.
        "cache_date": cache_date,
        "template": _file_signature(_TEMPLATE_DIR / "quote.html"),
        "labels": _file_signature(_TEMPLATE_DIR / "labels.py"),
        "platform": _PLATFORM_INFO,
        "rfq": {
            "id": getattr(rfq, "id", None),
            "rfq_no": getattr(rfq, "rfq_no", None),
            "contact_name": getattr(rfq, "contact_name", None),
            "contact_phone": getattr(rfq, "contact_phone", None),
            "contact_email": getattr(rfq, "contact_email", None),
            "requested_delivery_place": getattr(rfq, "requested_delivery_place", None),
            "destination_port": getattr(rfq, "destination_port", None),
            "expected_delivery_date": _jsonable(
                getattr(rfq, "expected_delivery_date", None)
            ),
            "created_at": _jsonable(getattr(rfq, "created_at", None)),
        },
        "quote": quote.model_dump(mode="json"),
        "images": {
            str(product_id): _image_signature(image_key)
            for product_id, image_key in sorted(image_keys.items())
        },
    }


def _quote_pdf_cache_key(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _quote_pdf_cache_path(cache_key: str) -> Path:
    return _UPLOADS_DIR / _PDF_CACHE_DIRNAME / f"{cache_key}.pdf"


def _read_cached_pdf(cache_key: str) -> bytes | None:
    cache_path = _quote_pdf_cache_path(cache_key)
    try:
        return cache_path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError:
        logger.warning(
            "quote PDF cache read failed cache_key=%s",
            cache_key,
            exc_info=True,
        )
        return None


def _write_cached_pdf(cache_key: str, pdf_bytes: bytes) -> None:
    cache_path = _quote_pdf_cache_path(cache_key)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = cache_path.with_name(
            f".{cache_path.name}.{os.getpid()}.{time.time_ns()}.tmp"
        )
        tmp_path.write_bytes(pdf_bytes)
        tmp_path.replace(cache_path)
    except OSError:
        logger.warning(
            "quote PDF cache write failed cache_key=%s",
            cache_key,
            exc_info=True,
        )


def _download_filename(rfq_no: str, now: datetime) -> str:
    return f"{rfq_no}_{now.strftime('%Y-%m-%d')}.pdf"


def build_content_disposition(filename: str) -> str:
    """Build a safe RFC 5987 Content-Disposition value."""
    fallback = "".join(
        ch if ch.isascii() and ch not in {'"', "\\", "\r", "\n"} else "_"
        for ch in filename
    ) or "quotation.pdf"
    encoded = quote(filename, safe="")
    return f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{encoded}'


async def generate_quote_pdf(
    db: AsyncSession,
    rfq_id: int,
    user: object,
    locale: str = "en",
) -> tuple[bytes, str]:
    """生成买方报价单 PDF。

    Returns:
        (pdf_bytes, filename)

    Raises:
        RfqNotFoundError: RFQ 不存在或越权
        RfqNoQuoteToExportError: 无 ACTIVE 报价
    """
    started_at = time.perf_counter()
    scope = resolve_rfq_scope(user)  # type: ignore[arg-type]

    # 鉴权:买方只能看自己的 RFQ
    buyer_org_id = None
    if scope.is_buyer:
        buyer_org_id = await _resolve_buyer_org_id(db, user)  # type: ignore[arg-type]

    rfq = await load_rfq(db, rfq_id, buyer_org_id=buyer_org_id)
    if rfq is None:
        raise RfqNotFoundError()

    # 仅 QUOTED / ACCEPTED 状态允许导出
    _EXPORTABLE = {"QUOTED", "ACCEPTED"}
    if rfq.status not in _EXPORTABLE:
        raise RfqNoQuoteToExportError()

    # 取 ACTIVE 买方报价
    quote_data = await load_quote_for_rfq_detail(db, rfq_id, is_operator=False)
    if quote_data is None:
        raise RfqNoQuoteToExportError()

    # load_quote_for_rfq_detail 非运营模式返回 RfqQuoteBuyerPublic 或 None
    quote: RfqQuoteBuyerPublic = quote_data  # type: ignore[assignment]

    # 分离商品行和费用行
    product_items = [i for i in quote.items if i.line_type == "PRODUCT"]
    fee_items = [i for i in quote.items if i.line_type == "FEE"]

    # 批量查商品主图 key。缩略图生成放到缓存未命中之后,避免命中缓存时仍做图片 I/O。
    product_ids = [i.product_id for i in product_items if i.product_id]
    image_keys: dict[int, str] = {}
    if product_ids:
        rows = await db.execute(
            select(ProductImage.product_id, ProductImage.image_key)
            .where(
                ProductImage.product_id.in_(product_ids),
                ProductImage.image_type == ImageType.MAIN,
                ProductImage.deleted_at.is_(None),
            )
        )
        for pid, key in rows.all():
            if key:
                image_keys[pid] = key

    subtotal_products = sum(
        (i.line_amount or Decimal("0")) for i in product_items
    )
    subtotal_fees = sum(
        (i.line_amount or Decimal("0")) for i in fee_items
    )

    # 买方显示名:用 RFQ 联系人姓名,不额外查组织表
    buyer_org = rfq.contact_name or ""

    labels = get_labels(locale)
    now = datetime.utcnow()
    cache_date = now.strftime("%Y-%m-%d")
    cache_payload = _quote_cache_payload(
        rfq=rfq,
        quote=quote,
        locale=locale,
        cache_date=cache_date,
        image_keys=image_keys,
    )
    cache_key = _quote_pdf_cache_key(cache_payload)
    filename = _download_filename(rfq.rfq_no, now)

    cached_pdf = _read_cached_pdf(cache_key)
    if cached_pdf is not None:
        logger.info(
            "quote PDF cache hit rfq_id=%s locale=%s items=%d images=%d total_ms=%.1f",
            rfq_id,
            locale,
            len(product_items),
            len(image_keys),
            (time.perf_counter() - started_at) * 1000,
        )
        return cached_pdf, filename

    image_map: dict[int, str] = {}
    for pid, key in image_keys.items():
        src = _image_key_to_pdf_src(key)
        if src:
            image_map[pid] = src

    # CJK 字体 ~18MB，weasyprint 每次加载子集化需 3s+；en/sw 纯拉丁字母无需 CJK
    if locale == "zh":
        font_family = '"Noto Sans CJK SC", "Noto Sans", "Helvetica Neue", Arial, sans-serif'
    else:
        font_family = '"Helvetica Neue", Helvetica, Arial, sans-serif'

    template = _jinja_env.get_template("quote.html")
    html_str = template.render(
        font_family=font_family,
        L=labels,
        locale=locale,
        rfq=rfq,
        quote=quote,
        platform=_PLATFORM_INFO,
        buyer_org=buyer_org,
        product_items=product_items,
        image_map=image_map,
        fee_items=fee_items,
        subtotal_products=subtotal_products,
        subtotal_fees=subtotal_fees,
        # RfqQuoteBuyerPublic 无 created_at,用 rfq.created_at 作签发日期
        issue_date=_format_date(rfq.created_at, locale),
        valid_until=_format_date(quote.valid_until, locale),
        expected_delivery_date=_format_date(rfq.expected_delivery_date, locale),
        generated_at=now.strftime("%Y-%m-%d %H:%M UTC"),
        format_amount=_format_amount,
    )

    # weasyprint 是 CPU 密集同步操作，放线程池避免阻塞事件循环
    render_started_at = time.perf_counter()
    pdf_bytes = await asyncio.get_event_loop().run_in_executor(
        None, partial(_render_pdf, html_str),
    )
    _write_cached_pdf(cache_key, pdf_bytes)

    logger.info(
        "quote PDF generated rfq_id=%s locale=%s items=%d images=%d cache_key=%s render_ms=%.1f total_ms=%.1f",
        rfq_id,
        locale,
        len(product_items),
        len(image_map),
        cache_key,
        (time.perf_counter() - render_started_at) * 1000,
        (time.perf_counter() - started_at) * 1000,
    )

    return pdf_bytes, filename


async def prewarm_quote_pdf_cache(
    rfq_id: int,
    user: object,
    locales: tuple[str, ...] = ("zh", "en"),
) -> None:
    """Best-effort background cache warmup after an operator submits a quote."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        for locale in locales:
            try:
                await generate_quote_pdf(db, rfq_id, user, locale)
            except Exception:
                await db.rollback()
                logger.warning(
                    "quote PDF cache prewarm failed rfq_id=%s locale=%s",
                    rfq_id,
                    locale,
                    exc_info=True,
                )


def _render_pdf(html_str: str) -> bytes:
    """同步 PDF 渲染，由线程池调用。懒加载 weasyprint 避免启动时缺库崩溃。"""
    from weasyprint import HTML
    return HTML(string=html_str).write_pdf()


# ── 产物预生成 ────────────────────────────────────────────────


async def _render_quote_pdf_bytes(
    db: AsyncSession, rfq_id: int, locale: str,
) -> bytes:
    """渲染指定 locale 的报价单 PDF，返回 bytes。

    复用 generate_quote_pdf 的全部渲染逻辑，但不做鉴权（后台任务无 user 上下文）。
    """
    rfq = await load_rfq(db, rfq_id)
    if rfq is None:
        raise RfqNotFoundError()

    quote_data = await load_quote_for_rfq_detail(db, rfq_id, is_operator=False)
    if quote_data is None:
        raise RfqNoQuoteToExportError()

    quote_view: RfqQuoteBuyerPublic = quote_data  # type: ignore[assignment]

    product_items = [i for i in quote_view.items if i.line_type == "PRODUCT"]
    fee_items = [i for i in quote_view.items if i.line_type == "FEE"]

    product_ids = [i.product_id for i in product_items if i.product_id]
    image_map: dict[int, str] = {}
    if product_ids:
        rows = await db.execute(
            select(ProductImage.product_id, ProductImage.image_key)
            .where(
                ProductImage.product_id.in_(product_ids),
                ProductImage.image_type == ImageType.MAIN,
                ProductImage.deleted_at.is_(None),
            )
        )
        for pid, key in rows.all():
            src = _image_key_to_pdf_src(key)
            if src:
                image_map[pid] = src

    subtotal_products = sum(
        (i.line_amount or Decimal("0")) for i in product_items
    )
    subtotal_fees = sum(
        (i.line_amount or Decimal("0")) for i in fee_items
    )

    buyer_org = rfq.contact_name or ""
    labels = get_labels(locale)
    now = datetime.utcnow()

    if locale == "zh":
        font_family = '"Noto Sans CJK SC", "Noto Sans", "Helvetica Neue", Arial, sans-serif'
    else:
        font_family = '"Helvetica Neue", Helvetica, Arial, sans-serif'

    template = _jinja_env.get_template("quote.html")
    html_str = template.render(
        font_family=font_family,
        L=labels,
        locale=locale,
        rfq=rfq,
        quote=quote_view,
        platform=_PLATFORM_INFO,
        buyer_org=buyer_org,
        product_items=product_items,
        image_map=image_map,
        fee_items=fee_items,
        subtotal_products=subtotal_products,
        subtotal_fees=subtotal_fees,
        issue_date=_format_date(rfq.created_at, locale),
        valid_until=_format_date(quote_view.valid_until, locale),
        expected_delivery_date=_format_date(rfq.expected_delivery_date, locale),
        generated_at=now.strftime("%Y-%m-%d %H:%M UTC"),
        format_amount=_format_amount,
    )

    pdf_bytes = await asyncio.get_event_loop().run_in_executor(
        None, partial(_render_pdf, html_str),
    )
    return pdf_bytes


async def _ensure_document_record(
    db: AsyncSession, quote_id: int, version: int, locale: str,
) -> QuoteDocument:
    """幂等创建产物记录。已存在则返回现有记录。"""
    stmt = select(QuoteDocument).where(
        QuoteDocument.quote_id == quote_id,
        QuoteDocument.version == version,
        QuoteDocument.locale == locale,
    )
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if doc is not None:
        return doc

    doc = QuoteDocument(
        quote_id=quote_id,
        version=version,
        locale=locale,
        status="PENDING",
    )
    db.add(doc)
    return doc


async def _get_document(
    db: AsyncSession, quote_id: int, version: int, locale: str,
) -> QuoteDocument | None:
    stmt = select(QuoteDocument).where(
        QuoteDocument.quote_id == quote_id,
        QuoteDocument.version == version,
        QuoteDocument.locale == locale,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _generate_single_document(
    db: AsyncSession, quote_id: int, version: int, locale: str, rfq_id: int,
) -> None:
    """生成单个 locale 的 PDF 产物。"""
    doc = await _get_document(db, quote_id, version, locale)
    if doc is None or doc.status == "READY":
        return

    # 状态 → GENERATING
    doc.transition_to("GENERATING")
    await db.commit()

    try:
        pdf_bytes = await _render_quote_pdf_bytes(db, rfq_id, locale)

        # 原子写入：tmp → rename
        storage_key = f".quote_documents/{quote_id}/v{version}_{locale}.pdf"
        abs_path = _UPLOADS_DIR / storage_key
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        tmp_path = abs_path.with_name(
            f".{abs_path.name}.{os.getpid()}.{time.time_ns()}.tmp"
        )
        tmp_path.write_bytes(pdf_bytes)
        tmp_path.replace(abs_path)

        # 状态 → READY
        doc.transition_to("READY")
        doc.storage_key = storage_key
        doc.file_size = len(pdf_bytes)
        doc.generated_at = _utcnow()
        doc.error_message = None
        await db.commit()

    except Exception as e:
        await db.rollback()
        # 重新加载 doc（rollback 后 ORM 对象可能 detached）
        doc = await _get_document(db, quote_id, version, locale)
        if doc is not None and doc.status == "GENERATING":
            doc.status = "FAILED"
            doc.error_message = str(e)[:500]
            doc.retry_count += 1
            await db.commit()
        logger.error(
            "quote document generation failed quote_id=%s locale=%s: %s",
            quote_id, locale, e, exc_info=True,
        )


async def generate_quote_documents(
    quote_id: int, version: int, rfq_id: int,
) -> None:
    """为指定报价的所有支持语言生成 PDF 产物。BackgroundTask 入口。"""
    from app.core.locale import SUPPORTED_LOCALES
    from app.db.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            # 幂等创建 PENDING 记录
            for locale in SUPPORTED_LOCALES:
                await _ensure_document_record(db, quote_id, version, locale)
            await db.commit()

            # 串行生成，避免 WeasyPrint 并发吃爆内存
            for locale in SUPPORTED_LOCALES:
                await _generate_single_document(db, quote_id, version, locale, rfq_id)
    except Exception:
        # BackgroundTask best-effort：独立 session 可能因事务隔离
        # 看不到调用方的数据，此处静默失败不影响主流程
        logger.warning(
            "generate_quote_documents failed quote_id=%s version=%s",
            quote_id, version, exc_info=True,
        )


async def get_quote_documents_status(
    db: AsyncSession, quote_id: int, version: int,
) -> list[QuoteDocument]:
    """查询指定报价版本的所有产物状态。"""
    stmt = select(QuoteDocument).where(
        QuoteDocument.quote_id == quote_id,
        QuoteDocument.version == version,
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def retry_failed_documents(
    db: AsyncSession, quote_id: int, version: int, rfq_id: int,
) -> int:
    """将 FAILED 产物重置为 PENDING 并重新触发生成。返回重试数量。"""
    stmt = select(QuoteDocument).where(
        QuoteDocument.quote_id == quote_id,
        QuoteDocument.version == version,
        QuoteDocument.status == "FAILED",
        QuoteDocument.retry_count < MAX_RETRIES,
    )
    result = await db.execute(stmt)
    docs = list(result.scalars().all())
    if not docs:
        return 0

    for doc in docs:
        doc.transition_to("PENDING")
    await db.commit()

    return len(docs)
