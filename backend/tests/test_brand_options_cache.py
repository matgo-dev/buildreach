"""GET /products/brands:缓存键含客户端传入的 category_code,只对真实品类缓存,防随机参数刷爆进程内缓存。"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1 import products as products_api
from app.db.models.category import Category


@pytest.mark.asyncio
async def test_unknown_category_returns_empty_and_is_not_cached(client: AsyncClient):
    products_api._BRAND_CACHE.clear()
    for i in range(5):
        r = await client.get(f"/api/v1/products/brands?category_code=NOPE-{i}")
        assert r.status_code == 200, r.text
        assert r.json()["data"] == []
    assert products_api._BRAND_CACHE == {}


@pytest.mark.asyncio
async def test_existing_category_is_cached_once(client: AsyncClient, db_session):
    code = (await db_session.execute(select(Category.code).limit(1))).scalar_one()
    products_api._BRAND_CACHE.clear()
    for _ in range(3):
        r = await client.get(f"/api/v1/products/brands?category_code={code}")
        assert r.status_code == 200, r.text
    assert list(products_api._BRAND_CACHE) == [f"zh:{code}"]
