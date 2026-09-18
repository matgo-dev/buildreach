"""安全响应头接线的集成测试:中间件是否真的包住了 API、静态文件与错误响应。"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.main import _uploads_dir

NOSNIFF = ("x-content-type-options", "nosniff")


@pytest.mark.asyncio
async def test_api_json_response_has_nosniff(client):
    r = await client.get("/api/v1/config")
    assert r.status_code == 200, r.text
    assert r.headers.get(NOSNIFF[0]) == NOSNIFF[1]


@pytest.mark.asyncio
async def test_static_file_has_nosniff(client):
    """上传图经 /static 直出,同源脚本嗅探是 nosniff 要挡的核心场景。"""
    f: Path = _uploads_dir / "_test_security_headers.txt"
    f.write_text("not-a-script")
    try:
        r = await client.get(f"/static/{f.name}")
        assert r.status_code == 200
        assert r.headers.get(NOSNIFF[0]) == NOSNIFF[1]
    finally:
        f.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_error_responses_have_nosniff(client):
    """404(路由未命中)与 401(业务错误信封)都要带,不能只有成功路径有。"""
    r404 = await client.get("/api/v1/definitely-not-a-route")
    assert r404.status_code == 404
    assert r404.headers.get(NOSNIFF[0]) == NOSNIFF[1]

    r401 = await client.get("/api/v1/auth/me")
    assert r401.status_code == 401, r401.text
    assert r401.headers.get(NOSNIFF[0]) == NOSNIFF[1]
