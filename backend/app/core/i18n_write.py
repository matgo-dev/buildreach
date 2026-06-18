"""i18n 写入中枢 — 所有多语言字段的写入必须经过此模块。

禁止任何 route / service 直接操作 trans_meta,统一走这里的入口:
- apply_i18n_create: 创建时写源列 + 标 pending(不内联翻译)
- apply_i18n_edit: 编辑某个 locale 列
- process_pending_translations: 后台任务/CLI 调用,处理 pending/failed 翻译
- retranslate_pending_or_failed: 单行补偿重试(兼容旧调用)

写路径异步化:请求事务内只做状态记账,翻译在提交后后台任务执行。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.locale import SUPPORTED_LOCALES
from app.services.translation_service import translate_text

logger = logging.getLogger("app.i18n_write")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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


def _set_pending_at(obj: object) -> None:
    """设置 i18n_pending_at,标记有待处理翻译。"""
    if hasattr(obj, "i18n_pending_at"):
        obj.i18n_pending_at = _utcnow()  # type: ignore[attr-defined]


def _clear_pending_at_if_done(obj: object) -> None:
    """如果 trans_meta 中无 pending/failed,清除 i18n_pending_at。"""
    if not hasattr(obj, "i18n_pending_at"):
        return
    meta = _get_meta(obj)
    has_pending = any(
        v in ("pending", "failed") for v in meta.values()
    )
    if not has_pending:
        obj.i18n_pending_at = None  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 创建流程(只做状态记账,不调翻译 API)
# ---------------------------------------------------------------------------

async def apply_i18n_create(
    obj: object,
    field: str,
    value: str,
    source_lang: str,
    *,
    domain: str = "general",
) -> None:
    """创建时写入:设置源列值 + 标记 src,其他 locale 标 pending。

    不内联翻译,翻译由后台任务异步完成。
    """
    meta = _get_meta(obj)

    # 写源列
    src_col = f"{field}_{source_lang}"
    setattr(obj, src_col, value)
    meta[f"{field}_{source_lang}"] = "src"

    # 其他 locale 标 pending
    for locale in SUPPORTED_LOCALES:
        if locale == source_lang:
            continue
        meta_key = f"{field}_{locale}"
        meta[meta_key] = "pending"

    _set_meta(obj, meta)
    _set_pending_at(obj)


# ---------------------------------------------------------------------------
# 编辑流程(只做状态记账)
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

    源语言编辑 → 其他 locale:auto 标 pending,manual 标 stale(不覆盖值)。
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
        has_pending = False
        for other in SUPPORTED_LOCALES:
            if other == locale:
                continue
            other_key = f"{field}_{other}"
            other_status = meta.get(other_key)
            if other_status == "manual":
                # 人工编辑的翻译不覆盖,仅标记过期
                meta[other_key] = "stale"
            else:
                # auto / pending / failed → 标 pending 等后台任务重翻
                meta[other_key] = "pending"
                has_pending = True
        if has_pending:
            _set_pending_at(obj)
    else:
        # 编辑非源语言 → manual
        meta[f"{field}_{locale}"] = "manual"

    _set_meta(obj, meta)


# ---------------------------------------------------------------------------
# 后台翻译处理(提交后调用)
# ---------------------------------------------------------------------------

async def process_pending_translations(obj: object) -> dict[str, int]:
    """处理单个对象的所有 pending/failed 翻译。

    由后台任务或 CLI 在独立 session 中调用,事务外执行翻译 API。
    字段状态 CAS:仅 pending/failed 才翻,避免覆盖并发手工编辑。

    返回 {"translated": N, "skipped": N, "failed": N} 统计。
    """
    stats: dict[str, int] = {"translated": 0, "skipped": 0, "failed": 0}

    source_lang = getattr(obj, "source_lang", None)
    if not source_lang:
        return stats

    meta = _get_meta(obj)
    changed = False

    for meta_key, status in list(meta.items()):
        if status not in ("pending", "failed"):
            continue

        # 解析 meta_key → field + locale
        parts = meta_key.rsplit("_", 1)
        if len(parts) != 2:
            continue
        field, locale = parts
        if locale not in SUPPORTED_LOCALES or locale == source_lang:
            continue

        # 读当前源值
        src_col = f"{field}_{source_lang}"
        source_value = getattr(obj, src_col, None)
        if not source_value:
            # 源值为空,无需翻译,清除 pending 状态避免 sweeper 永久循环
            if meta.get(meta_key) in ("pending", "failed"):
                meta[meta_key] = "src"
                changed = True
            continue

        # CAS:再检一次当前状态,仍为 pending/failed 才处理
        current_status = meta.get(meta_key)
        if current_status not in ("pending", "failed"):
            continue

        try:
            result = await translate_text(source_value, source_lang, locale)
            if result["status"] == "skipped":
                # 无翻译 provider,保持 pending 不改
                stats["skipped"] += 1
                if stats["skipped"] == 1:
                    logger.warning(
                        "翻译跳过: 无翻译 provider 配置,字段 %s %s→%s 保持 pending",
                        field, source_lang, locale,
                    )
                else:
                    logger.debug(
                        "翻译跳过: %s %s→%s (无 provider)", field, source_lang, locale,
                    )
                continue
            setattr(obj, f"{field}_{locale}", result["translated"])
            meta[meta_key] = "auto" if result["status"] != "mock" else "mock"
            changed = True
            stats["translated"] += 1
        except Exception:
            logger.warning("翻译失败: %s, %s→%s", field, source_lang, locale, exc_info=True)
            meta[meta_key] = "failed"
            changed = True
            stats["failed"] += 1

    if changed:
        _set_meta(obj, meta)
    _clear_pending_at_if_done(obj)
    return stats


# ---------------------------------------------------------------------------
# 补偿重试(兼容旧接口)
# ---------------------------------------------------------------------------

async def retranslate_pending_or_failed(
    obj: object,
    field: str,
    *,
    domain: str = "general",
) -> None:
    """扫描 trans_meta 中 pending/failed 的条目,重试翻译。

    兼容旧接口,内部委托给 process_pending_translations。
    """
    await process_pending_translations(obj)
