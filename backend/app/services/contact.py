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
