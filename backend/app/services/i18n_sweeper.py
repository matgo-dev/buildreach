"""i18n 补译自动化 — 调度扫描 + 写后 BackgroundTask。

两条触发并存、幂等共存:
- sweep_pending: 调度扫描(Cron),兜底/重试/覆盖导入后补译
- translate_one: 写后 BackgroundTask,近实时补译单行
- enqueue_translation: 在 API 路由层注入 BackgroundTask 的 helper
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.core.i18n_registry import all_registered
from app.core.i18n_write import process_pending_translations
from app.db.session import AsyncSessionLocal

logger = logging.getLogger("app.i18n_sweeper")


# ---------------------------------------------------------------------------
# 调度扫描(Cron)
# ---------------------------------------------------------------------------

async def sweep_pending(limit: int | None = None) -> dict[str, int]:
    """扫描所有注册模型的 pending/failed 行,逐行翻译。

    返回 {scanned, translated, failed}。
    独立 session,按模型分批查询走 i18n_pending_at 索引。
    """
    if limit is None:
        limit = settings.I18N_SWEEP_BATCH_LIMIT

    registry = all_registered()
    stats: dict[str, int] = {"scanned": 0, "translated": 0, "failed": 0}

    for model_cls, spec in registry.items():
        table_name = getattr(model_cls, "__tablename__", model_cls.__name__)
        try:
            # 循环分批,一次触发处理完该模型所有待译行
            while True:
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

                    batch_failed = 0
                    for row in rows:
                        stats["scanned"] += 1
                        try:
                            await process_pending_translations(row)
                            if getattr(row, "i18n_pending_at", None) is None:
                                stats["translated"] += 1
                            else:
                                stats["failed"] += 1
                                batch_failed += 1
                        except Exception:
                            logger.warning(
                                "sweep: %s#%s 翻译异常",
                                table_name, getattr(row, "id", "?"),
                                exc_info=True,
                            )
                            stats["failed"] += 1
                            batch_failed += 1

                    await session.commit()

                    # 本批全部失败则停止,避免死循环重试同一批
                    if batch_failed == len(rows):
                        logger.warning("sweep: %s 本批 %d 行全部失败,停止循环", table_name, len(rows))
                        break

        except Exception:
            logger.error("sweep: %s 批次异常", table_name, exc_info=True)

    logger.info(
        "sweep 完成: scanned=%d translated=%d failed=%d",
        stats["scanned"], stats["translated"], stats["failed"],
    )
    return stats


# ---------------------------------------------------------------------------
# 写后 BackgroundTask
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
