"""翻译服务 — 三态 provider:google / mock / none。

google:调 Google Cloud Translation v3 NMT
mock:返回源文,status="mock"(开发用)
none:短路返回,status="skipped"(未配置/降级)
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.services.glossary_cache import GlossaryCache

logger = logging.getLogger("app.translation")

# 平台 locale → Google 语言码(集中一处)
_GOOGLE_LANG_MAP: dict[str, str] = {
    "zh": "zh-CN",
    "en": "en",
    "sw": "sw",
}

# 延迟初始化的 Google 客户端
_google_client = None
_google_available = None  # None=未检测, True/False=已检测


def _get_google_client():
    """延迟初始化 Google Translate 客户端,缺凭据降级为 None。"""
    global _google_client, _google_available
    if _google_available is not None:
        return _google_client

    if not settings.GOOGLE_TRANSLATE_PROJECT_ID:
        logger.warning("GOOGLE_TRANSLATE_PROJECT_ID 未配置,翻译降级为 none")
        _google_available = False
        return None

    try:
        from google.cloud import translate_v3  # noqa: F811
        _google_client = translate_v3.TranslationServiceClient()
        _google_available = True
        logger.info("Google Translation v3 客户端初始化成功")
    except Exception as e:
        logger.warning("Google Translation 客户端初始化失败,降级为 none: %s", e)
        _google_available = False
        _google_client = None

    return _google_client


async def translate_text(
    text: str,
    source_locale: str,
    target_locale: str,
    domain: str = "general",
) -> dict:
    """翻译文本。

    返回:
        {"translated": str, "status": "nmt" | "glossary" | "mock" | "skipped"}
    """
    # 先查术语表精确匹配
    glossary = GlossaryCache.get(source_locale, target_locale)
    if text in glossary:
        return {"translated": glossary[text], "status": "glossary"}

    provider = settings.TRANSLATION_PROVIDER.lower()

    if provider == "none":
        return {"translated": text, "status": "skipped"}

    if provider == "mock":
        return {"translated": text, "status": "mock"}

    if provider == "google":
        return await _translate_google(text, source_locale, target_locale)

    # 未知 provider 当 none 处理
    logger.warning("未知 TRANSLATION_PROVIDER=%s,降级为 none", provider)
    return {"translated": text, "status": "skipped"}


async def _translate_google(
    text: str,
    source_locale: str,
    target_locale: str,
) -> dict:
    """调 Google Cloud Translation v3 NMT。"""
    client = _get_google_client()
    if client is None:
        return {"translated": text, "status": "skipped"}

    source_lang = _GOOGLE_LANG_MAP.get(source_locale, source_locale)
    target_lang = _GOOGLE_LANG_MAP.get(target_locale, target_locale)

    parent = f"projects/{settings.GOOGLE_TRANSLATE_PROJECT_ID}/locations/{settings.GOOGLE_TRANSLATE_LOCATION}"

    try:
        # Google v3 同步 API,用 run_in_executor 避免阻塞事件循环
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.translate_text(
                request={
                    "parent": parent,
                    "contents": [text],
                    "source_language_code": source_lang,
                    "target_language_code": target_lang,
                    "mime_type": "text/plain",
                },
                timeout=settings.GOOGLE_TRANSLATE_TIMEOUT_SECONDS,
            ),
        )
        translated = response.translations[0].translated_text
        return {"translated": translated, "status": "nmt"}
    except Exception as e:
        logger.error("Google Translation 调用失败: %s→%s, error=%s", source_locale, target_locale, e)
        raise
