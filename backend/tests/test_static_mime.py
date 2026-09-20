"""/static 接线:.webp 缩略图返回 image/webp(app 导入时已注册)。"""
from __future__ import annotations

import pytest

from app.main import app


@pytest.mark.asyncio
async def test_static_webp_content_type(client, tmp_path, monkeypatch):
    static_app = next(r for r in app.routes if getattr(r, "name", None) == "static").app
    (tmp_path / "probe_thumb.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8 ")
    monkeypatch.setattr(static_app, "all_directories", [tmp_path])

    r = await client.get("/static/probe_thumb.webp")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/webp")
