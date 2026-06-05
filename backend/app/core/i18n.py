"""业务数据本地化读取工具。

存储模式:分列(name_zh / name_en),每个 locale 一列。
回退链:请求 locale 列 → source_lang 列 → DEFAULT_LOCALE 列 → 空字符串。
"""
from __future__ import annotations

from app.core.locale import DEFAULT_LOCALE, get_current_locale


def get_localized(obj: object, field: str) -> str:
    """按当前请求 locale 选取本地化字段值。

    支持两种 i18n 存储模式:
    A. 分列模式: name_zh / name_en（I18nMixin，如 categories）
    B. JSON 模式: name + name_i18n {"zh": "...", "en": "..."}（如 products）

    回退优先级:
    1. 请求 locale 对应值
    2. source_lang 对应值（仅分列模式）
    3. DEFAULT_LOCALE 对应值
    4. 原始字段值（JSON 模式的 field 列）
    5. 空字符串
    """
    locale = get_current_locale()

    # 尝试 JSON i18n 模式: 有 {field}_i18n 属性即判定为 JSON 模式
    i18n_attr = f"{field}_i18n"
    if hasattr(obj, i18n_attr):
        i18n_data = getattr(obj, i18n_attr)
        if not isinstance(i18n_data, dict):
            # i18n JSON 为空，回退到原始字段
            raw = getattr(obj, field, None)
            return raw or ""
        return _resolve_json_i18n(obj, field, i18n_data, locale)
    # 分列模式: {field}_{locale} 列
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


def _resolve_json_i18n(obj: object, field: str, i18n_data: dict, locale: str) -> str:
    """从 {field}_i18n JSON dict 中按 locale 取值，回退到原始字段。"""
    val = i18n_data.get(locale)
    if val:
        return val
    if locale != DEFAULT_LOCALE:
        val = i18n_data.get(DEFAULT_LOCALE)
        if val:
            return val
    raw = getattr(obj, field, None)
    return raw or ""


def _try_col(obj: object, field: str, locale: str) -> str | None:
    """尝试读取 {field}_{locale} 列,返回非空字符串或 None。"""
    attr = f"{field}_{locale}"
    if hasattr(obj, attr):
        v = getattr(obj, attr)
        if v:
            return v
    return None
