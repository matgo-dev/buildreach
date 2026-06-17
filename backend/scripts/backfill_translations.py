"""补译 / 扫描重译 CLI — 读注册表,处理 pending/failed/缺译列。

用法:
    python scripts/backfill_translations.py [--entity product|sku|all]
                                            [--only-failed] [--limit N]
                                            [--batch-size N] [--dry-run]

设计:
- 幂等:已 auto/manual/src 跳过,可重跑
- 限速:--batch-size 控制每批数量
- 单字段失败标 failed 继续,不中断
- 读注册表获取字段列表,不硬编码
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# 让脚本能 import app.*
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import select, or_  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.i18n_registry import all_registered, get_i18n_fields  # noqa: E402
from app.core.i18n_write import process_pending_translations  # noqa: E402
from app.core.locale import SUPPORTED_LOCALES  # noqa: E402
from app.db.models.product import Product  # noqa: E402
from app.db.models.product_sku import ProductSku  # noqa: E402
from app.db.models.category import Category  # noqa: E402
from app.db.models.product_attr import ProductAttr  # noqa: E402

from scripts._log_setup import setup_logging  # noqa: E402
setup_logging("backfill_translations")
log = logging.getLogger("backfill_translations")

# 实体别名映射
_ENTITY_MAP = {
    "product": Product,
    "sku": ProductSku,
    "category": Category,
    "attr": ProductAttr,
}


def _needs_translation(obj: object, fields: tuple[str, ...]) -> bool:
    """检查对象是否有 pending/failed 翻译或缺译列。"""
    source_lang = getattr(obj, "source_lang", None)
    if not source_lang:
        return False

    meta = getattr(obj, "trans_meta", {}) or {}

    for field in fields:
        src_value = getattr(obj, f"{field}_{source_lang}", None)
        if not src_value:
            continue
        for locale in SUPPORTED_LOCALES:
            if locale == source_lang:
                continue
            meta_key = f"{field}_{locale}"
            status = meta.get(meta_key)
            # 需要处理:pending / failed / 无状态但源有值
            if status in ("pending", "failed", None):
                target_value = getattr(obj, f"{field}_{locale}", None)
                if not target_value or status in ("pending", "failed"):
                    return True
    return False


async def backfill(
    entity_name: str | None,
    only_failed: bool,
    limit: int,
    batch_size: int,
    dry_run: bool,
) -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    registry = all_registered()

    # 过滤要处理的实体
    if entity_name and entity_name != "all":
        model_cls = _ENTITY_MAP.get(entity_name)
        if not model_cls:
            log.error("未知实体: %s,可选: %s", entity_name, list(_ENTITY_MAP.keys()))
            return
        targets = {model_cls: registry[model_cls]}
    else:
        targets = {k: v for k, v in registry.items() if k in _ENTITY_MAP.values()}

    total_processed = 0
    total_translated = 0
    total_skipped = 0
    total_failed = 0

    for model_cls, spec in targets.items():
        model_name = model_cls.__tablename__
        fields = spec.fields
        log.info("扫描 %s (字段: %s)...", model_name, ", ".join(fields))

        async with async_session() as session:
            # 扫全部行,靠 _needs_translation 过滤;兜底覆盖缺译列
            query = select(model_cls)

            query = query.limit(limit).order_by(model_cls.id)
            result = await session.execute(query)
            rows = result.scalars().all()

            log.info("  找到 %d 行(limit=%d)", len(rows), limit)

            batch_count = 0
            for row in rows:
                if not _needs_translation(row, fields):
                    continue

                if only_failed:
                    meta = getattr(row, "trans_meta", {}) or {}
                    if not any(v == "failed" for v in meta.values()):
                        continue

                total_processed += 1

                if dry_run:
                    source_lang = getattr(row, "source_lang", "?")
                    meta = getattr(row, "trans_meta", {}) or {}
                    pending_fields = [k for k, v in meta.items() if v in ("pending", "failed")]
                    log.info("  [DRY] id=%s source_lang=%s pending=%s",
                             getattr(row, "id", "?"), source_lang, pending_fields)
                    continue

                try:
                    row_stats = await process_pending_translations(row)
                    total_translated += row_stats.get("translated", 0)
                    total_skipped += row_stats.get("skipped", 0)
                    total_failed += row_stats.get("failed", 0)
                    batch_count += 1

                    if batch_count >= batch_size:
                        await session.commit()
                        batch_count = 0
                        log.info("  已提交 %d 行", total_translated)
                except Exception as e:
                    log.error("  id=%s 翻译失败: %s", getattr(row, "id", "?"), e)

            if batch_count > 0 and not dry_run:
                await session.commit()

        log.info("  %s 完成: scanned=%d translated=%d skipped=%d failed=%d",
                 model_name, total_processed, total_translated, total_skipped, total_failed)

    await engine.dispose()

    if dry_run:
        log.info("[DRY RUN] 共 %d 行需翻译,未执行。", total_processed)
    else:
        log.info("补译完成: scanned=%d translated=%d skipped=%d failed=%d",
                 total_processed, total_translated, total_skipped, total_failed)


def main() -> None:
    parser = argparse.ArgumentParser(description="i18n 补译 / 扫描重译")
    parser.add_argument(
        "--entity", choices=["product", "sku", "category", "attr", "all"], default="all",
        help="处理哪个实体(默认 all)",
    )
    parser.add_argument(
        "--only-failed", action="store_true",
        help="仅处理 failed 项",
    )
    parser.add_argument(
        "--limit", type=int, default=500,
        help="最多处理多少行(默认 500)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=50,
        help="每批提交多少行(默认 50)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只报告,不执行翻译",
    )
    args = parser.parse_args()

    asyncio.run(backfill(
        entity_name=args.entity,
        only_failed=args.only_failed,
        limit=args.limit,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    ))


if __name__ == "__main__":
    main()
