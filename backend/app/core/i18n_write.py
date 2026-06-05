"""i18n 写入中枢 — 所有多语言字段的写入必须经过此模块。

禁止任何 route / service 直接操作 trans_meta,统一走这里的三个入口:
- apply_i18n_create: 创建时写源列 + 触发其他 locale 翻译
- apply_i18n_edit: 编辑某个 locale 列
- retranslate_pending_or_failed: 补偿重试失败/挂起的翻译
"""
from __future__ import annotations

import logging

from app.core.locale import SUPPORTED_LOCALES
from app.services.translation_service import translate_text

logger = logging.getLogger("app.i18n_write")


# ---------------------------------------------------------------------------
# trans_meta 读写工具
# ---------------------------------------------------------------------------

def _get_meta(obj: object) -> dict:
    meta = getattr(obj, "trans_meta", None)
    if not isinstance(meta, dict):
        return {}
    return dict(meta)  # 浅拷贝,避免直接修改 ORM tracked dict


def _set_meta(obj: object, meta: dict) -> None:
    # 赋值新 dict 触发 SQLAlchemy 变更检测
    obj.trans_meta = meta  # type: ignore[attr-defined]


def _get_field_status(obj: object, field: str, locale: str) -> str | None:
    meta = _get_meta(obj)
    return meta.get(f"{field}_{locale}")


# ---------------------------------------------------------------------------
# 创建流程
# ---------------------------------------------------------------------------

async def apply_i18n_create(
    obj: object,
    field: str,
    value: str,
    source_lang: str,
    *,
    domain: str = "general",
) -> None:
    """创建时写入:设置源列值 + 标记 src,然后为其他 locale 触发翻译。

    翻译失败不阻塞主流程,仅标记 failed。
    """
    meta = _get_meta(obj)

    # 写源列
    src_col = f"{field}_{source_lang}"
    setattr(obj, src_col, value)
    meta[f"{field}_{source_lang}"] = "src"

    # 为其他 locale 触发翻译
    for locale in SUPPORTED_LOCALES:
        if locale == source_lang:
            continue
        target_col = f"{field}_{locale}"
        meta_key = f"{field}_{locale}"
        meta[meta_key] = "pending"
        try:
            result = await translate_text(value, source_lang, locale, domain=domain)
            setattr(obj, target_col, result["translated"])
            meta[meta_key] = "auto"
        except Exception:
            logger.warning("翻译失败: field=%s, %s→%s", field, source_lang, locale, exc_info=True)
            meta[meta_key] = "failed"

    _set_meta(obj, meta)


# ---------------------------------------------------------------------------
# 编辑流程
# ---------------------------------------------------------------------------

async def apply_i18n_edit(
    obj: object,
    field: str,
    locale: str,
    new_value: str,
    old_value: str | None,
    *,
    domain: str = "general",
) -> None:
    """编辑某个 locale 的字段值。遵循 diff 原则:值未变则不动。

    源语言编辑 → 重新翻译 auto 列,manual 列标 stale(不覆盖值)。
    非源语言编辑 → 标 manual,其他列不动。
    """
    if new_value == old_value:
        return

    meta = _get_meta(obj)
    source_lang = getattr(obj, "source_lang", None)
    target_col = f"{field}_{locale}"

    setattr(obj, target_col, new_value)

    if locale == source_lang:
        # 编辑源语言
        meta[f"{field}_{locale}"] = "src"
        for other in SUPPORTED_LOCALES:
            if other == locale:
                continue
            other_key = f"{field}_{other}"
            other_status = meta.get(other_key)
            if other_status == "manual":
                # 人工编辑的翻译不覆盖,仅标记过期
                meta[other_key] = "stale"
            else:
                # auto / pending / failed / src(不应出现) → 重新翻译
                meta[other_key] = "pending"
                try:
                    result = await translate_text(new_value, locale, other, domain=domain)
                    setattr(obj, f"{field}_{other}", result["translated"])
                    meta[other_key] = "auto"
                except Exception:
                    logger.warning("重翻译失败: field=%s, %s→%s", field, locale, other, exc_info=True)
                    meta[other_key] = "failed"
    else:
        # 编辑非源语言 → manual
        meta[f"{field}_{locale}"] = "manual"

    _set_meta(obj, meta)


# ---------------------------------------------------------------------------
# 补偿重试
# ---------------------------------------------------------------------------

async def retranslate_pending_or_failed(
    obj: object,
    field: str,
    *,
    domain: str = "general",
) -> None:
    """扫描 trans_meta 中 pending/failed 的条目,重试翻译。

    调度(cron)不在本版本实现,此函数供上层按需调用。
    """
    meta = _get_meta(obj)
    source_lang = getattr(obj, "source_lang", None)
    if not source_lang:
        return

    # 读取源列值
    src_col = f"{field}_{source_lang}"
    source_value = getattr(obj, src_col, None)
    if not source_value:
        return

    changed = False
    for locale in SUPPORTED_LOCALES:
        if locale == source_lang:
            continue
        meta_key = f"{field}_{locale}"
        status = meta.get(meta_key)
        if status not in ("pending", "failed"):
            continue
        meta[meta_key] = "pending"
        try:
            result = await translate_text(source_value, source_lang, locale, domain=domain)
            setattr(obj, f"{field}_{locale}", result["translated"])
            meta[meta_key] = "auto"
            changed = True
        except Exception:
            logger.warning("补偿翻译失败: field=%s, %s→%s", field, source_lang, locale, exc_info=True)
            meta[meta_key] = "failed"
            changed = True

    if changed:
        _set_meta(obj, meta)
