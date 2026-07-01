"""统一公开运行时配置 /api/v1/config。

前端启动所需的公开配置(联系方式、功能开关等)一次性返回,单一真源。
无需登录,不挂权限点(对齐 contact.py / categories.py 写法)。
"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.core.exceptions import success
from app.services.contact import build_contact_payload

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", summary="获取前端公开运行时配置")
async def get_public_config():
    return success({
        "contact": build_contact_payload(),
        "auth": {
            "require_email_verification": settings.REQUIRE_EMAIL_VERIFICATION,
        },
    })
