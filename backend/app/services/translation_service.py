"""翻译服务占位 — 接口定义好,内部 mock,不真调外部 API。"""
from __future__ import annotations

from app.services.glossary_cache import GlossaryCache


async def translate_text(
    text: str,
    source_locale: str,
    target_locale: str,
    domain: str = "general",
) -> dict:
    """翻译文本。

    当前 mock 实现,未来替换为 Google Cloud Translation V3。

    返回:
        {"translated": str, "status": "glossary" | "mock"}
    """
    # 先查术语表精确匹配
    glossary = GlossaryCache.get(source_locale, target_locale)
    if text in glossary:
        return {"translated": glossary[text], "status": "glossary"}

    # TODO(i18n): 接入 Google Cloud Translation V3
    return {"translated": text, "status": "mock"}
