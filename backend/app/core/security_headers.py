"""安全响应头中间件。

后端只加 ``X-Content-Type-Options: nosniff``:上传的商品图与站点同源经 ``/static`` 直出,
nosniff 阻止浏览器把它们当脚本/样式嗅探执行(MDN:所有站点必须设)。
``X-Frame-Options`` / ``Referrer-Policy`` 等页面级头对 JSON、图片无意义,由前端 Next 设置。
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
