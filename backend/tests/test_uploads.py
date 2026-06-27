"""旧版公开文件上传端点测试。"""
import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_legacy_uploads_files_route_disabled(client: AsyncClient):
    """旧 /uploads/files 会写公开 /static/rfq-attachments,生产路由应不可达。"""
    resp = await client.post(
        "/api/v1/uploads/files",
        files={"file": ("test.jpg", io.BytesIO(b"fake"), "image/jpeg")},
    )
    assert resp.status_code == 404
