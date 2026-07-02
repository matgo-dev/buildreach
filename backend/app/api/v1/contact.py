"""客服联系公开 API /api/v1/contact/*。

无需登录,不挂权限点(对齐 categories.py 写法)。
"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.core.exceptions import success
from app.services.contact import build_contact_payload, resolve_whatsapp_link

router = APIRouter(prefix="/contact", tags=["contact"])


@router.get("/whatsapp", summary="获取客服 WhatsApp 链接")
async def get_whatsapp_link():
    link = resolve_whatsapp_link()
    raw = settings.WHATSAPP_DEFAULT_NUMBER.strip() or None
    return success({
        "whatsapp_link": link,
        "number": raw if link else None,
    })


@router.get(
    "/info",
    summary="获取平台联系方式",
    deprecated=True,
    description="已被统一端点 /api/v1/config 的 contact 字段取代,保留作向后兼容,下个版本移除。",
)
async def get_contact_info():
    return success(build_contact_payload())
