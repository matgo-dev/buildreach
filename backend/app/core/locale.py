"""请求级 locale 检测:从 Accept-Language 头提取,写入 contextvar。"""
from __future__ import annotations

from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

SUPPORTED_LOCALES = {"zh", "en", "sw"}
DEFAULT_LOCALE = "zh"

_current_locale: ContextVar[str] = ContextVar("current_locale", default=DEFAULT_LOCALE)

# BCP 47 → 平台支持的 locale 显式映射,不做盲目 split
_LOCALE_MAP: dict[str, str] = {
    "zh": "zh",
    "zh-cn": "zh",
    "zh-tw": "zh",      # 繁体暂归 zh,未来可拆 zh-hant
    "zh-hk": "zh",
    "zh-hant": "zh",
    "en": "en",
    "en-us": "en",
    "en-gb": "en",
    "en-au": "en",
    "sw": "sw",
    "sw-tz": "sw",
    "sw-ke": "sw",
}


def get_current_locale() -> str:
    return _current_locale.get()


def normalize_locale(raw: str | None) -> str:
    """BCP 47 标签 → 平台支持的 locale。

    规则:空/None→zh;zh-*→zh;en-*→en;不支持的→en。
    使用显式映射而非盲目 split,新增 locale 只需加 _LOCALE_MAP 条目。
    """
    if not raw:
        return DEFAULT_LOCALE
    key = raw.strip().lower()
    if key in _LOCALE_MAP:
        return _LOCALE_MAP[key]
    # 映射表未命中,尝试基础语言码
    base = key.split("-")[0] if "-" in key else key
    if base in _LOCALE_MAP:
        return _LOCALE_MAP[base]
    # 不认识的语言大概率是外国用户,回退到 en 比 zh 更合理
    return "en"


class LocaleMiddleware(BaseHTTPMiddleware):
    """从 Accept-Language 头提取 locale,写入 contextvar + request.state。"""

    async def dispatch(self, request: Request, call_next):
        locale = _parse_accept_language(request.headers.get("accept-language", ""))
        _current_locale.set(locale)
        request.state.locale = locale
        response = await call_next(request)
        response.headers["Content-Language"] = locale
        return response


def _parse_accept_language(header: str) -> str:
    """解析 Accept-Language 头,取第一个支持的语言。"""
    if not header:
        return DEFAULT_LOCALE
    for part in header.split(","):
        tag = part.split(";")[0].strip()
        result = normalize_locale(tag)
        # normalize_locale 对不支持的返回 "en",需确认原始 tag 确实匹配
        if result in SUPPORTED_LOCALES:
            key = tag.strip().lower()
            # 确保是显式映射命中或 base 命中,而非兜底的 "en"
            base = key.split("-")[0] if "-" in key else key
            if key in _LOCALE_MAP or base in _LOCALE_MAP:
                return result
    return DEFAULT_LOCALE
