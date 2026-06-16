"""手机号 E.164 归一化 — 唯一真相源。

注册校验、查重、登录查询三处共用同一个函数,
不再按长度/前缀猜测国家。MVP 支持 TZ + CN。
"""
from __future__ import annotations

import phonenumbers

from app.core.exceptions import PhoneFormatError, PhoneUnsupportedRegionError

# MVP 支持的国家(ISO 3166-1 alpha-2)
SUPPORTED_REGIONS: set[str] = {"TZ", "CN"}


def normalize_phone_to_e164(raw: str, region: str | None) -> str:
    """将用户原始输入归一化为 E.164。

    raw: 用户输入(可含 +、前导 0、空格、短横)
    region: 国家码下拉对应的 ISO alpha-2(TZ / CN),
            raw 已带 + 时自动忽略 region。
    非法或不支持国家抛业务异常。
    """
    raw = raw.strip()
    if not raw:
        raise PhoneFormatError()
    try:
        num = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        raise PhoneFormatError()

    detected_region = phonenumbers.region_code_for_number(num)
    if detected_region not in SUPPORTED_REGIONS:
        raise PhoneUnsupportedRegionError()

    # 精准校验(含号段),非仅 is_possible_number
    if not phonenumbers.is_valid_number(num):
        raise PhoneFormatError()

    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)


def try_normalize_phone(raw: str, region: str | None) -> str | None:
    """尽力归一化,成功返回 E.164,任何原因失败返回 None。

    适用于供应商等覆盖面广、SUPPORTED_REGIONS 不完全覆盖的场景。
    """
    try:
        return normalize_phone_to_e164(raw, region)
    except (PhoneFormatError, PhoneUnsupportedRegionError):
        return None
