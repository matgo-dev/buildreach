"""翻译服务 — 四态 provider:aliyun / google / mock / none。

aliyun:调阿里云机器翻译通用版
google:调 Google Cloud Translation v2 Basic (API Key)
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

# 平台 locale → 阿里云语言码
_ALIYUN_LANG_MAP: dict[str, str] = {
    "zh": "zh",
    "en": "en",
    "sw": "sw",
}


# ---- 阿里云客户端(延迟初始化) ----

_aliyun_client = None
_aliyun_available = None


def _get_aliyun_client():
    """延迟初始化阿里云机器翻译客户端,缺凭据降级为 None。"""
    global _aliyun_client, _aliyun_available
    if _aliyun_available is not None:
        return _aliyun_client

    ak_id = settings.ALIYUN_TRANSLATE_ACCESS_KEY_ID
    ak_secret = settings.ALIYUN_TRANSLATE_ACCESS_KEY_SECRET
    if not ak_id or not ak_secret:
        logger.warning("ALIYUN_TRANSLATE_ACCESS_KEY_ID/SECRET 未配置,翻译降级为 none")
        _aliyun_available = False
        return None

    try:
        from aliyunsdkcore.client import AcsClient
        _aliyun_client = AcsClient(
            ak_id,
            ak_secret,
            settings.ALIYUN_TRANSLATE_REGION,
        )
        _aliyun_available = True
        logger.info("阿里云机器翻译客户端初始化成功 (region=%s)", settings.ALIYUN_TRANSLATE_REGION)
    except Exception as e:
        logger.warning("阿里云机器翻译客户端初始化失败,降级为 none: %s", e)
        _aliyun_available = False
        _aliyun_client = None

    return _aliyun_client


# ---- 公共入口 ----

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

    if provider == "aliyun":
        return await _translate_aliyun(text, source_locale, target_locale)

    if provider == "google":
        return await _translate_google(text, source_locale, target_locale)

    # 未知 provider 当 none 处理
    logger.warning("未知 TRANSLATION_PROVIDER=%s,降级为 none", provider)
    return {"translated": text, "status": "skipped"}


# ---- Google 实现 (v2 Basic, API Key) ----

_GOOGLE_V2_URL = "https://translation.googleapis.com/language/translate/v2"


async def _translate_google(
    text: str,
    source_locale: str,
    target_locale: str,
) -> dict:
    """调 Google Cloud Translation v2 Basic REST API。"""
    api_key = settings.GOOGLE_TRANSLATE_API_KEY
    if not api_key:
        logger.warning("GOOGLE_TRANSLATE_API_KEY 未配置,翻译降级为 none")
        return {"translated": text, "status": "skipped"}

    source_lang = _GOOGLE_LANG_MAP.get(source_locale, source_locale)
    target_lang = _GOOGLE_LANG_MAP.get(target_locale, target_locale)

    try:
        import httpx
        async with httpx.AsyncClient(timeout=settings.GOOGLE_TRANSLATE_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                _GOOGLE_V2_URL,
                params={"key": api_key},
                json={
                    "q": text,
                    "source": source_lang,
                    "target": target_lang,
                    "format": "text",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            translated = data["data"]["translations"][0]["translatedText"]
            return {"translated": translated, "status": "nmt"}
    except Exception as e:
        logger.error("Google Translation v2 调用失败: %s→%s, error=%s", source_locale, target_locale, e)
        raise


# ---- 阿里云实现 ----

async def _translate_aliyun(
    text: str,
    source_locale: str,
    target_locale: str,
) -> dict:
    """调阿里云机器翻译通用版。"""
    client = _get_aliyun_client()
    if client is None:
        return {"translated": text, "status": "skipped"}

    source_lang = _ALIYUN_LANG_MAP.get(source_locale, source_locale)
    target_lang = _ALIYUN_LANG_MAP.get(target_locale, target_locale)

    try:
        import asyncio
        import json
        from aliyunsdkalimt.request.v20181012 import TranslateGeneralRequest

        request = TranslateGeneralRequest.TranslateGeneralRequest()
        request.set_SourceLanguage(source_lang)
        request.set_TargetLanguage(target_lang)
        request.set_SourceText(text)
        request.set_FormatType("text")
        request.set_method("POST")

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.do_action_with_exception(request),
        )
        result = json.loads(response)
        translated = result["Data"]["Translated"]
        return {"translated": translated, "status": "nmt"}
    except Exception as e:
        logger.error("阿里云机器翻译调用失败: %s→%s, error=%s", source_locale, target_locale, e)
        raise
