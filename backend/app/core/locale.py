"""请求级 locale 检测:从 Accept-Language 头提取,写入 contextvar。"""
from __future__ import annotations

from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

SUPPORTED_LOCALES = {"zh", "en"}
DEFAULT_LOCALE = "zh"

_current_locale: ContextVar[str] = ContextVar("current_locale", default=DEFAULT_LOCALE)


def get_current_locale() -> str:
    return _current_locale.get()


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
        lang = part.split(";")[0].strip().split("-")[0].lower()
        if lang in SUPPORTED_LOCALES:
            return lang
    return DEFAULT_LOCALE
