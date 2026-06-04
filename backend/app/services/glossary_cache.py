"""术语表内存缓存 — 启动加载,变更时刷新。"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.translation_glossary import TranslationGlossary

logger = logging.getLogger("app.glossary")


class GlossaryCache:
    _cache: dict[str, dict[str, str]] = {}

    @classmethod
    async def load(cls, db: AsyncSession) -> None:
        """全量加载术语表到内存。启动时 / 运营改术语后调用。"""
        result = await db.execute(select(TranslationGlossary))
        cache: dict[str, dict[str, str]] = {}
        count = 0
        for row in result.scalars():
            pair_key = f"{row.source_locale}:{row.target_locale}"
            cache.setdefault(pair_key, {})[row.source_term] = row.target_term
            count += 1
        cls._cache = cache
        logger.info("GlossaryCache loaded: %d terms", count)

    @classmethod
    def get(cls, source_locale: str, target_locale: str) -> dict[str, str]:
        """取某语言对的术语表,O(1) 内存读取。"""
        return cls._cache.get(f"{source_locale}:{target_locale}", {})
