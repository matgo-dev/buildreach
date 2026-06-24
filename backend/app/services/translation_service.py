"""翻译服务 — 四态 provider:aliyun / google / mock / none。

aliyun:调阿里云机器翻译通用版(批量用换行拼接,单次≤5000字符)
google:调 Google Cloud Translation v2 Basic (API Key,原生 q 数组批量)
mock:返回源文,status="mock"(开发用)
none:短路返回,status="skipped"(未配置/降级)
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.services.glossary_cache import GlossaryCache

logger = logging.getLogger("app.translation")


def _sanitize(text: str) -> str:
    """清理翻译 API 返回的异常前缀符号（如阿里云偶尔返回的 '* '）。"""
    return text.lstrip("*").strip()

# 平台 locale → Google 语言码
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

# 批量翻译每片大小(Google/阿里云共用)
_BATCH_CHUNK_SIZE = 100
# 阿里云单次请求最大字符数(拼接后)
_ALIYUN_MAX_CHARS = 4500
# 拼接分隔符
_JOIN_SEP = "\n"


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


# ---- 单条入口(BackgroundTask 用) ----

async def translate_text(
    text: str,
    source_locale: str,
    target_locale: str,
    domain: str = "general",
) -> dict:
    """翻译单条文本。

    返回: {"translated": str, "status": "nmt"|"glossary"|"mock"|"skipped"}
    """
    glossary = GlossaryCache.get(source_locale, target_locale)
    if text in glossary:
        return {"translated": glossary[text], "status": "glossary"}

    provider = settings.TRANSLATION_PROVIDER.lower()

    if provider == "none":
        return {"translated": text, "status": "skipped"}
    if provider == "mock":
        return {"translated": text, "status": "mock"}
    if provider == "aliyun":
        return await _translate_aliyun_single(text, source_locale, target_locale)
    if provider == "google":
        return await _translate_google_single(text, source_locale, target_locale)

    logger.warning("未知 TRANSLATION_PROVIDER=%s,降级为 none", provider)
    return {"translated": text, "status": "skipped"}


# ---- 批量入口(sweeper 用) ----

async def translate_texts_batch(
    texts: list[str],
    source_locale: str,
    target_locale: str,
    domain: str = "general",
) -> list[dict]:
    """批量翻译,返回与输入严格等长等序的结果列表。

    Google: 原生 q 数组,按 _BATCH_CHUNK_SIZE 分片。
    阿里云: 换行拼接发单次请求,按字符数自动分片。
    mock/none: 逐条返回。
    """
    if not texts:
        return []

    provider = settings.TRANSLATION_PROVIDER.lower()

    # 术语表精确匹配 + 空文本跳过
    glossary = GlossaryCache.get(source_locale, target_locale)
    results: list[dict | None] = [None] * len(texts)
    pending_indices: list[int] = []
    pending_texts: list[str] = []

    for i, text in enumerate(texts):
        if not text:
            results[i] = {"translated": "", "status": "skipped"}
        elif text in glossary:
            results[i] = {"translated": glossary[text], "status": "glossary"}
        else:
            pending_indices.append(i)
            pending_texts.append(text)

    if not pending_texts:
        return results  # type: ignore[return-value]

    # 按 provider 分发批量
    if provider == "google" and settings.GOOGLE_TRANSLATE_API_KEY:
        batch_results = await _translate_google_batch(pending_texts, source_locale, target_locale)
    elif provider == "aliyun" and _get_aliyun_client() is not None:
        batch_results = await _translate_aliyun_batch(pending_texts, source_locale, target_locale)
    elif provider == "mock":
        batch_results = [{"translated": t, "status": "mock"} for t in pending_texts]
    else:
        batch_results = [{"translated": t, "status": "skipped"} for t in pending_texts]

    # 按原始位置写回
    for idx, res in zip(pending_indices, batch_results):
        results[idx] = res

    return results  # type: ignore[return-value]


# =====================================================================
# Google v2 实现
# =====================================================================

_GOOGLE_V2_URL = "https://translation.googleapis.com/language/translate/v2"


async def _translate_google_single(
    text: str, source_locale: str, target_locale: str,
) -> dict:
    """Google v2 单条。"""
    api_key = settings.GOOGLE_TRANSLATE_API_KEY
    if not api_key:
        return {"translated": text, "status": "skipped"}

    import httpx
    source_lang = _GOOGLE_LANG_MAP.get(source_locale, source_locale)
    target_lang = _GOOGLE_LANG_MAP.get(target_locale, target_locale)

    async with httpx.AsyncClient(timeout=settings.GOOGLE_TRANSLATE_TIMEOUT_SECONDS) as client:
        resp = await client.post(
            _GOOGLE_V2_URL,
            params={"key": api_key},
            json={"q": text, "source": source_lang, "target": target_lang, "format": "text"},
        )
        resp.raise_for_status()
        data = resp.json()
        return {"translated": data["data"]["translations"][0]["translatedText"], "status": "nmt"}


async def _translate_google_batch(
    texts: list[str], source_locale: str, target_locale: str,
) -> list[dict]:
    """Google v2 批量,q 数组原生支持,按 _BATCH_CHUNK_SIZE 分片,严格保序。"""
    import httpx

    api_key = settings.GOOGLE_TRANSLATE_API_KEY
    source_lang = _GOOGLE_LANG_MAP.get(source_locale, source_locale)
    target_lang = _GOOGLE_LANG_MAP.get(target_locale, target_locale)
    all_results: list[dict] = []

    async with httpx.AsyncClient(timeout=settings.GOOGLE_TRANSLATE_TIMEOUT_SECONDS) as client:
        for start in range(0, len(texts), _BATCH_CHUNK_SIZE):
            chunk = texts[start:start + _BATCH_CHUNK_SIZE]
            try:
                resp = await client.post(
                    _GOOGLE_V2_URL,
                    params={"key": api_key},
                    json={"q": chunk, "source": source_lang, "target": target_lang, "format": "text"},
                )
                resp.raise_for_status()
                translations = resp.json()["data"]["translations"]

                if len(translations) != len(chunk):
                    raise ValueError(f"Google 返回 {len(translations)} 条,期望 {len(chunk)} 条")

                for t in translations:
                    all_results.append({"translated": _sanitize(t["translatedText"]), "status": "nmt"})
            except Exception as e:
                logger.error("Google 批量翻译失败 (chunk %d-%d): %s", start, start + len(chunk), e)
                for _ in chunk:
                    all_results.append({"translated": "", "status": "failed"})

    return all_results


# =====================================================================
# 阿里云实现
# =====================================================================

async def _translate_aliyun_single(
    text: str, source_locale: str, target_locale: str,
) -> dict:
    """阿里云单条。"""
    client = _get_aliyun_client()
    if client is None:
        return {"translated": text, "status": "skipped"}

    import asyncio
    import json
    from aliyunsdkalimt.request.v20181012 import TranslateGeneralRequest

    source_lang = _ALIYUN_LANG_MAP.get(source_locale, source_locale)
    target_lang = _ALIYUN_LANG_MAP.get(target_locale, target_locale)

    request = TranslateGeneralRequest.TranslateGeneralRequest()
    request.set_SourceLanguage(source_lang)
    request.set_TargetLanguage(target_lang)
    request.set_SourceText(text)
    request.set_FormatType("text")
    request.set_method("POST")

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None, lambda: client.do_action_with_exception(request),
    )
    result = json.loads(response)
    return {"translated": _sanitize(result["Data"]["Translated"]), "status": "nmt"}


def _chunk_by_char_limit(texts: list[str], max_chars: int) -> list[list[str]]:
    """按字符数上限分片,每片拼接后不超过 max_chars。"""
    chunks: list[list[str]] = []
    current: list[str] = []
    current_len = 0

    for text in texts:
        text_len = len(text)
        # +1 是分隔符 \n 的长度
        added_len = text_len + (1 if current else 0)
        if current and current_len + added_len > max_chars:
            chunks.append(current)
            current = [text]
            current_len = text_len
        else:
            current.append(text)
            current_len += added_len

    if current:
        chunks.append(current)
    return chunks


async def _translate_aliyun_batch(
    texts: list[str], source_locale: str, target_locale: str,
) -> list[dict]:
    """阿里云批量:用换行拼接多条文本发单次请求,翻译完按换行拆回。

    按 _ALIYUN_MAX_CHARS 自动分片,严格保序。
    """
    client = _get_aliyun_client()
    if client is None:
        return [{"translated": t, "status": "skipped"} for t in texts]

    import asyncio
    import json
    from aliyunsdkalimt.request.v20181012 import TranslateGeneralRequest

    source_lang = _ALIYUN_LANG_MAP.get(source_locale, source_locale)
    target_lang = _ALIYUN_LANG_MAP.get(target_locale, target_locale)
    loop = asyncio.get_event_loop()

    # 先按字符数分片,再按条数上限裁剪
    chunks = _chunk_by_char_limit(texts, _ALIYUN_MAX_CHARS)
    final_chunks: list[list[str]] = []
    for chunk in chunks:
        for i in range(0, len(chunk), _BATCH_CHUNK_SIZE):
            final_chunks.append(chunk[i:i + _BATCH_CHUNK_SIZE])

    all_results: list[dict] = []

    for chunk in final_chunks:
        joined = _JOIN_SEP.join(chunk)
        try:
            request = TranslateGeneralRequest.TranslateGeneralRequest()
            request.set_SourceLanguage(source_lang)
            request.set_TargetLanguage(target_lang)
            request.set_SourceText(joined)
            request.set_FormatType("text")
            request.set_method("POST")

            response = await loop.run_in_executor(
                None, lambda: client.do_action_with_exception(request),
            )
            result = json.loads(response)
            translated_joined = result["Data"]["Translated"]
            parts = translated_joined.split(_JOIN_SEP)

            # 校验拆回条数
            if len(parts) == len(chunk):
                for p in parts:
                    all_results.append({"translated": _sanitize(p), "status": "nmt"})
            else:
                # 条数不匹配,降级逐条重试
                logger.warning(
                    "阿里云批量拆分不匹配: 发 %d 条,回 %d 条,降级逐条",
                    len(chunk), len(parts),
                )
                for text in chunk:
                    try:
                        r = await _translate_aliyun_single(text, source_locale, target_locale)
                        all_results.append(r)
                    except Exception:
                        all_results.append({"translated": "", "status": "failed"})

        except Exception as e:
            logger.error("阿里云批量翻译失败 (%d 条): %s", len(chunk), e)
            # 整片降级逐条重试
            for text in chunk:
                try:
                    r = await _translate_aliyun_single(text, source_locale, target_locale)
                    all_results.append(r)
                except Exception:
                    all_results.append({"translated": "", "status": "failed"})

    return all_results
