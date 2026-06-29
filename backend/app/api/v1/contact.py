"""客服联系公开 API /api/v1/contact/*。

无需登录,不挂权限点(对齐 categories.py 写法)。
"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.core.exceptions import success
from app.services.contact import resolve_whatsapp_link

router = APIRouter(prefix="/contact", tags=["contact"])


@router.get("/whatsapp", summary="获取客服 WhatsApp 链接")
async def get_whatsapp_link():
    link = resolve_whatsapp_link()
    raw = settings.WHATSAPP_DEFAULT_NUMBER.strip() or None
    return success({
        "whatsapp_link": link,
        "number": raw if link else None,
    })


@router.get("/info", summary="获取平台联系方式")
async def get_contact_info():
    link = resolve_whatsapp_link()
    raw = settings.WHATSAPP_DEFAULT_NUMBER.strip() or None
    email = settings.CONTACT_EMAIL.strip() or None
    return success({
        "whatsapp_link": link,
        "whatsapp_number": raw if link else None,
        "email": email,
    })
