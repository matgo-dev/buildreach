"""业务数据本地化工具。

支持两种存储模式:
1. 分列模式:name_zh / name_en(品类表等已有结构)
2. JSONB 模式:name_i18n = {"zh": "...", "en": "..."}(未来新表)
"""
from __future__ import annotations

from app.core.locale import get_current_locale


def get_localized(obj: object, field: str, fallback: str = "en") -> str:
    """按当前请求 locale 选取本地化字段值。"""
    locale = get_current_locale()

    # 模式 1:分列(name_zh / name_en)
    localized_attr = f"{field}_{locale}"
    if hasattr(obj, localized_attr):
        val = getattr(obj, localized_attr)
        if val:
            return val
        # 当前 locale 为空,逐个 fallback:指定 fallback → 所有支持的 locale
        for fb in (fallback, "zh", "en"):
            fb_attr = f"{field}_{fb}"
            if hasattr(obj, fb_attr):
                fb_val = getattr(obj, fb_attr)
                if fb_val:
                    return fb_val

    # 模式 2:JSONB(field_i18n)
    i18n_attr = f"{field}_i18n"
    if hasattr(obj, i18n_attr):
        i18n_val = getattr(obj, i18n_attr)
        if isinstance(i18n_val, dict):
            return i18n_val.get(locale) or i18n_val.get(fallback) or ""

    # 兜底
    return getattr(obj, field, "") or ""
