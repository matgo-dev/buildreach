"""业务数据本地化读取工具。

存储模式:分列(name_zh / name_en),每个 locale 一列。
回退链:请求 locale 列 → source_lang 列 → DEFAULT_LOCALE 列 → 空字符串。
"""
from __future__ import annotations

from app.core.locale import DEFAULT_LOCALE, get_current_locale


def get_localized(obj: object, field: str) -> str:
    """按当前请求 locale 选取本地化字段值。

    回退优先级:
    1. 请求 locale 对应列(如 name_en)
    2. obj.source_lang 对应列(如 name_zh)— 适用于有 I18nMixin 的表
    3. DEFAULT_LOCALE 对应列 — 兜底,兼容无 source_lang 的旧表(如 categories)
    4. 空字符串
    """
    locale = get_current_locale()

    # 1. 请求 locale
    val = _try_col(obj, field, locale)
    if val:
        return val

    # 2. source_lang(仅在 locale != source_lang 时尝试,避免重复)
    source_lang = getattr(obj, "source_lang", None)
    if source_lang and source_lang != locale:
        val = _try_col(obj, field, source_lang)
        if val:
            return val

    # 3. DEFAULT_LOCALE 兜底(仅在前两步都未命中时)
    if DEFAULT_LOCALE not in (locale, source_lang):
        val = _try_col(obj, field, DEFAULT_LOCALE)
        if val:
            return val

    return ""


def _try_col(obj: object, field: str, locale: str) -> str | None:
    """尝试读取 {field}_{locale} 列,返回非空字符串或 None。"""
    attr = f"{field}_{locale}"
    if hasattr(obj, attr):
        v = getattr(obj, attr)
        if v:
            return v
    return None
