"""i18n 补译自动化 — 调度扫描 + 写后 BackgroundTask。

两条触发并存、幂等共存:
- sweep_pending: 调度扫描(Cron),兜底/重试/覆盖导入后补译
- translate_one: 写后 BackgroundTask,近实时补译单行
- enqueue_translation: 在 API 路由层注入 BackgroundTask 的 helper

批量优化:
sweep 按模型分批取行,按目标语言收集待译文本,一次调用批量翻译接口。
Google v2 单次最多 100 条,阿里云退化为逐条。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.core.i18n_registry import all_registered
from app.core.i18n_write import process_pending_translations, _get_meta, _set_meta, _clear_pending_at_if_done
from app.core.locale import SUPPORTED_LOCALES
from app.db.session import AsyncSessionLocal
from app.services.translation_service import translate_texts_batch

logger = logging.getLogger("app.i18n_sweeper")


# ---------------------------------------------------------------------------
# 调度扫描(Cron) — 批量模式
# ---------------------------------------------------------------------------

async def sweep_pending(limit: int | None = None) -> dict[str, int]:
    """扫描所有注册模型的 pending/failed 行,批量翻译。

    返回 {scanned, translated, failed}。
    独立 session,按模型分批查询走 i18n_pending_at 索引。
    每批 limit 行(默认 100),翻完立即 commit 入库,循环取下一批直到清空。
    """
    if limit is None:
        limit = settings.I18N_SWEEP_BATCH_LIMIT

    registry = all_registered()
    stats: dict[str, int] = {"scanned": 0, "translated": 0, "failed": 0}

    for model_cls, spec in registry.items():
        table_name = getattr(model_cls, "__tablename__", model_cls.__name__)
        # 循环分批,一次触发处理完该模型所有待译行
        while True:
            try:
                async with AsyncSessionLocal() as session:
                    stmt = (
                        select(model_cls)
                        .where(model_cls.i18n_pending_at.isnot(None))
                        .order_by(model_cls.i18n_pending_at)
                        .limit(limit)
                    )
                    result = await session.execute(stmt)
                    rows = result.scalars().all()

                    if not rows:
                        break

                    logger.info("sweep: %s 发现 %d 行待译", table_name, len(rows))

                    batch_failed = await _batch_translate_rows(rows, spec.fields, stats)

                    # product_attrs 翻译后可能产生重复 (product_id, attr_key_en, attr_value_en)
                    # flush 前回滚冲突行,避免唯一约束报错
                    if table_name == "product_attrs":
                        await _dedup_attr_translations(session, rows)

                    await session.commit()
                    logger.info("sweep: %s 本批 %d 行已提交", table_name, len(rows))

                    # 本批全部失败则停止,避免死循环重试同一批
                    if batch_failed == len(rows):
                        logger.warning("sweep: %s 本批 %d 行全部失败,停止循环", table_name, len(rows))
                        break

            except Exception:
                logger.error("sweep: %s 本批异常,跳过继续下一批", table_name, exc_info=True)
                # commit 失败(如字段超长),这批数据回滚,继续下一批
                # 但如果是同一批数据反复报错会死循环,所以直接 break
                break

    logger.info(
        "sweep 完成: scanned=%d translated=%d failed=%d",
        stats["scanned"], stats["translated"], stats["failed"],
    )
    return stats


async def _dedup_attr_translations(session: Any, rows: list) -> None:
    """翻译后 attr_key_en + attr_value_en 可能撞唯一约束,回滚冲突行的翻译结果。

    同一 product_id 下如果多行翻译后产生相同 (attr_key_en, attr_value_en),
    只保留第一行的翻译,后续重复行还原为中文值。
    同时检查 DB 中已有的非本批数据,避免跨批次冲突。
    """
    from collections import defaultdict
    from app.db.models.product_attr import ProductAttr

    groups: dict[int, list] = defaultdict(list)
    batch_ids: set[int] = set()
    for row in rows:
        pid = getattr(row, "product_id", None)
        if pid is not None:
            groups[pid].append(row)
            batch_ids.add(getattr(row, "id", 0))

    reverted = 0
    for pid, attrs in groups.items():
        # 先加载该 product 已有的(非本批) attr_key_en + attr_value_en
        existing = await session.execute(
            select(ProductAttr.attr_key_en, ProductAttr.attr_value_en)
            .where(
                ProductAttr.product_id == pid,
                ProductAttr.sku_id.is_(None),
                ProductAttr.id.notin_(batch_ids),
            )
        )
        seen: set[tuple[str, str]] = {(r[0], r[1]) for r in existing}

        for attr in attrs:
            key_en = getattr(attr, "attr_key_en", None) or ""
            val_en = getattr(attr, "attr_value_en", None) or ""
            combo = (key_en, val_en)
            if combo in seen:
                key_zh = getattr(attr, "attr_key_zh", None) or key_en
                val_zh = getattr(attr, "attr_value_zh", None) or val_en
                attr.attr_key_en = key_zh
                attr.attr_value_en = val_zh
                meta = _get_meta(attr)
                meta["attr_key_en"] = "conflict_skipped"
                meta["attr_value_en"] = "conflict_skipped"
                _set_meta(attr, meta)
                reverted += 1
                logger.warning(
                    "sweep: product_attrs#%d 翻译冲突,还原为中文 (%s, %s)",
                    getattr(attr, "id", "?"), key_zh[:30], val_zh[:30],
                )
            else:
                seen.add(combo)

    if reverted:
        logger.info("sweep: product_attrs 去重回滚 %d 行", reverted)


async def _batch_translate_rows(
    rows: list,
    fields: tuple[str, ...],
    stats: dict[str, int],
) -> int:
    """按目标语言收集待译文本,批量调翻译接口,写回对应行。

    返回本批失败行数(用于死循环检测)。
    """
    batch_failed_rows = 0

    for target_locale in SUPPORTED_LOCALES:
        # 收集该目标语言下所有待译 (row, field, source_text) 三元组
        tasks: list[tuple[Any, str, str, str]] = []  # (row, field, meta_key, source_text)

        for row in rows:
            source_lang = getattr(row, "source_lang", None)
            if not source_lang or target_locale == source_lang:
                continue

            meta = _get_meta(row)
            for field in fields:
                meta_key = f"{field}_{target_locale}"
                status = meta.get(meta_key)
                if status not in ("pending", "failed"):
                    continue

                src_col = f"{field}_{source_lang}"
                source_value = getattr(row, src_col, None)
                if not source_value:
                    # 源值为空,标记 src 避免永久循环
                    meta[meta_key] = "src"
                    _set_meta(row, meta)
                    continue

                tasks.append((row, field, meta_key, source_value))

        if not tasks:
            continue

        # 批量翻译
        texts = [t[3] for t in tasks]
        try:
            results = await translate_texts_batch(
                texts,
                # 所有 task 的 source_lang 可能不同,但绝大多数场景一致
                # 取第一个即可(混合 source_lang 的极端情况在 translate_texts_batch 内逐条降级)
                getattr(tasks[0][0], "source_lang", "zh"),
                target_locale,
            )
        except Exception:
            logger.error(
                "sweep: 批量翻译异常 target=%s, %d 条",
                target_locale, len(texts), exc_info=True,
            )
            # 全部标 failed
            for row, field, meta_key, _ in tasks:
                meta = _get_meta(row)
                meta[meta_key] = "failed"
                _set_meta(row, meta)
            continue

        # 写回结果,严格按位置对应
        for i, (row, field, meta_key, _) in enumerate(tasks):
            res = results[i]
            meta = _get_meta(row)
            if res["status"] == "skipped":
                continue
            if res["status"] == "failed" or not res.get("translated"):
                meta[meta_key] = "failed"
                _set_meta(row, meta)
                continue
            translated = res["translated"]
            # 防御:截断到列长度,避免 commit 时 VARCHAR 报错
            col = getattr(row.__class__, f"{field}_{target_locale}", None)
            if col is not None:
                col_len = getattr(col.type, "length", None) if hasattr(col, "type") else None
                if col_len is None:
                    # 从 mapped_column 的 property 取
                    try:
                        col_len = col.property.columns[0].type.length
                    except Exception:
                        pass
                if col_len and len(translated) > col_len:
                    logger.warning(
                        "sweep: %s#%s %s_%s 翻译结果 %d 字符超过列长 %d,截断",
                        row.__class__.__tablename__,
                        getattr(row, "id", "?"),
                        field, target_locale,
                        len(translated), col_len,
                    )
                    translated = translated[:col_len]
            setattr(row, f"{field}_{target_locale}", translated)
            meta[meta_key] = "auto" if res["status"] != "mock" else "mock"
            _set_meta(row, meta)

    # 统计 + 清 pending_at
    for row in rows:
        stats["scanned"] += 1
        _clear_pending_at_if_done(row)
        if getattr(row, "i18n_pending_at", None) is None:
            stats["translated"] += 1
        else:
            stats["failed"] += 1
            batch_failed_rows += 1

    return batch_failed_rows


# ---------------------------------------------------------------------------
# 写后 BackgroundTask(单行,保持逐条模式)
# ---------------------------------------------------------------------------

async def translate_one(model_cls: type, obj_id: int) -> None:
    """独立 session 按 id 重载单行,执行翻译后提交。"""
    async with AsyncSessionLocal() as session:
        row = await session.get(model_cls, obj_id)
        if row is None:
            logger.warning("translate_one: %s#%d 不存在", model_cls.__name__, obj_id)
            return

        # i18n_pending_at 为空说明已无待译
        if getattr(row, "i18n_pending_at", None) is None:
            return

        try:
            await process_pending_translations(row)
        except Exception:
            logger.warning(
                "translate_one: %s#%d 翻译异常",
                model_cls.__name__, obj_id,
                exc_info=True,
            )

        await session.commit()


def enqueue_translation(
    background_tasks: Any,
    model_cls: type,
    obj_id: int,
) -> None:
    """总开关判断后,将单行翻译任务加入 BackgroundTasks 队列。"""
    if not settings.I18N_AUTO_TRANSLATE_ENABLED:
        return
    background_tasks.add_task(translate_one, model_cls, obj_id)
