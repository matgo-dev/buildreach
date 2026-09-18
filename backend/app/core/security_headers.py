"""安全响应头中间件(纯 ASGI)。

后端只加 ``X-Content-Type-Options: nosniff``:上传的商品图与站点同源经 ``/static`` 直出,
nosniff 阻止浏览器把它们当脚本/样式嗅探执行(MDN:所有站点必须设)。
``X-Frame-Options`` / ``Referrer-Policy`` 等页面级头对 JSON、图片无意义,由前端 Next 设置。

用纯 ASGI 而非 BaseHTTPMiddleware:后者每层都把响应体经内存流转发一遍,
/static 商品图是后端量最大的路径,不值得为一个常量头再多一层。

注意:``@app.exception_handler(Exception)`` 的 500 信封由 Starlette 最外层的
ServerErrorMiddleware 发出,任何 add_middleware 都包不到,所以 main.py 的处理函数里要单独设。
"""
from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

NOSNIFF_HEADER = ("X-Content-Type-Options", "nosniff")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers[NOSNIFF_HEADER[0]] = NOSNIFF_HEADER[1]
            await send(message)

        await self.app(scope, receive, send_with_headers)
