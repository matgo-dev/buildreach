"""客服联系 — WhatsApp 号解析与链接生成。"""
from __future__ import annotations

import re

from app.core.config import settings


def resolve_whatsapp_link(context: dict | None = None) -> str | None:
    """将配置中的 WhatsApp 号码规范化为 wa.me 链接。

    context 参数 v1 忽略 — 保留签名作为「按语言/品类路由」的接入点。
    """
    raw = settings.WHATSAPP_DEFAULT_NUMBER
    if not raw or not raw.strip():
        return None

    # 去除所有非数字字符(+、空格、横线等)
    digits = re.sub(r"\D", "", raw)

    # 去掉国际冠码 00
    if digits.startswith("00"):
        digits = digits[2:]

    if not digits:
        return None

    return f"https://wa.me/{digits}"


def parse_localized_name(raw: str | None) -> dict[str, str] | None:
    """解析按语言配置的联系人称呼。

    支持两种写法:
      - 单值:``廖先生``                      → {"default": "廖先生"}
      - 按语言:``zh=廖先生;en=Mr. Liao``     → {"zh": "廖先生", "en": "Mr. Liao"}
    混写时不带 ``=`` 的段落视为 default。语言键小写;空段落/空值忽略;全空返回 None。
    前端按 当前语言 → en → 任意一个 的顺序回落。
    """
    if not raw or not raw.strip():
        return None
    names: dict[str, str] = {}
    for seg in raw.split(";"):
        seg = seg.strip()
        if not seg:
            continue
        key, eq, val = seg.partition("=")
        if eq:
            key, val = key.strip().lower(), val.strip()
        else:
            key, val = "default", key.strip()
        if key and val:
            names[key] = val
    return names or None


def build_contact_payload() -> dict:
    """平台联系方式 payload — 供 /contact/info 与统一 /config 端点共用。"""
    link = resolve_whatsapp_link()
    raw = settings.WHATSAPP_DEFAULT_NUMBER.strip() or None
    return {
        "whatsapp_link": link,
        "whatsapp_number": raw if link else None,
        "whatsapp_qr_image": (settings.WHATSAPP_QR_IMAGE.strip() or None) if link else None,
        "wechat_id": settings.WECHAT_ID.strip() or None,
        "wechat_qr_image": settings.WECHAT_QR_IMAGE.strip() or None,
        "email": settings.CONTACT_EMAIL.strip() or None,
        "whatsapp_contact_name": parse_localized_name(settings.WHATSAPP_CONTACT_NAME),
        "wechat_contact_name": parse_localized_name(settings.WECHAT_CONTACT_NAME),
    }
