"""报价单 PDF 导出服务。"""
from __future__ import annotations

import asyncio
import logging
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
from app.db.models.product_image import ImageType, ProductImage
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

    # 批量查商品主图
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
            uri = _image_key_to_file_uri(key)
            if uri:
                image_map[pid] = uri

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

    logger.info(
        "quote PDF generated rfq_id=%s locale=%s items=%d images=%d render_ms=%.1f total_ms=%.1f",
        rfq_id,
        locale,
        len(product_items),
        len(image_map),
        (time.perf_counter() - render_started_at) * 1000,
        (time.perf_counter() - started_at) * 1000,
    )

    filename = _download_filename(rfq.rfq_no, now)
    return pdf_bytes, filename


def _render_pdf(html_str: str) -> bytes:
    """同步 PDF 渲染，由线程池调用。懒加载 weasyprint 避免启动时缺库崩溃。"""
    from weasyprint import HTML
    return HTML(string=html_str).write_pdf()
