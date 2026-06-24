"""基础安全响应头。"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_basic_security_headers_present(client: AsyncClient):
    resp = await client.get("/healthz")
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
