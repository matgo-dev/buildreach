"""安全响应头接线的集成测试:中间件是否真的包住了 API、静态文件与各类错误响应。"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

NOSNIFF = ("x-content-type-options", "nosniff")


@pytest.mark.asyncio
async def test_api_json_response_has_nosniff(client):
    r = await client.get("/api/v1/config")
    assert r.status_code == 200, r.text
    assert r.headers.get(NOSNIFF[0]) == NOSNIFF[1]


@pytest.mark.asyncio
async def test_static_file_has_nosniff(client, tmp_path, monkeypatch):
    """上传图经 /static 直出,同源脚本嗅探是 nosniff 要挡的核心场景。

    StaticFiles 的目录在 mount 时已定死,这里把它指到 tmp_path,不往真实 uploads 写。
    """
    static_app = next(r for r in app.routes if getattr(r, "name", None) == "static").app
    (tmp_path / "probe.txt").write_text("not-a-script")
    monkeypatch.setattr(static_app, "all_directories", [tmp_path])

    r = await client.get("/static/probe.txt")
    assert r.status_code == 200
    assert r.headers.get(NOSNIFF[0]) == NOSNIFF[1]


@pytest.mark.asyncio
async def test_error_responses_have_nosniff(client):
    """404(路由未命中)与 401(业务错误信封)都要带,不能只有成功路径有。"""
    r404 = await client.get("/api/v1/definitely-not-a-route")
    assert r404.status_code == 404
    assert r404.headers.get(NOSNIFF[0]) == NOSNIFF[1]

    r401 = await client.get("/api/v1/auth/me")
    assert r401.status_code == 401, r401.text
    assert r401.headers.get(NOSNIFF[0]) == NOSNIFF[1]


@pytest.mark.asyncio
async def test_unhandled_500_envelope_has_nosniff():
    """500 信封由最外层 ServerErrorMiddleware 发出,中间件包不到,处理函数里单独设了。"""

    async def boom():
        raise RuntimeError("boom")

    app.add_api_route("/_test/boom", boom)
    route = app.router.routes[-1]
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/_test/boom")
        assert r.status_code == 500
        assert r.json()["code"] == 50000
        assert r.headers.get(NOSNIFF[0]) == NOSNIFF[1]
    finally:
        app.router.routes.remove(route)
