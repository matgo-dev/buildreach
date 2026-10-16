"""商城关键词检索集成测试:整词匹配 / 中文 n-gram / 相关度排序 / 总数封顶(走真实 PG 生成列与 GIN 索引)。"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import products as products_api
from app.db.models.category import Category
from app.db.models.product import Product, ProductStatus, ProductVisibility
from app.services import product as product_svc

_NOW = datetime(2026, 10, 1)


async def _seed(db: AsyncSession, rows: list[dict]) -> None:
    cat = (await db.execute(
        select(Category.code).where(Category.is_leaf.is_(True), Category.is_active.is_(True)).limit(1)
    )).scalar_one()
    for i, row in enumerate(rows):
        db.add(Product(
            category_code=cat,
            status=ProductStatus.ACTIVE,
            visibility=ProductVisibility.PUBLIC,
            published_at=row.pop("published_at", _NOW - timedelta(days=i)),
            **row,
        ))
    await db.flush()


async def _search(client: AsyncClient, keyword: str, **params) -> dict:
    r = await client.get("/api/v1/products", params={"keyword": keyword, "size": 50, **params})
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _codes(data: dict) -> list[str]:
    return [i["spu_code"] for i in data["items"] if i["spu_code"].startswith("SRCH-")]


@pytest.mark.asyncio
async def test_whole_word_match_any_order_stemming_and_stopwords(client: AsyncClient, db_session: AsyncSession):
    await _seed(db_session, [
        {"spu_code": "SRCH-CEM", "name_zh": "硅酸盐水泥", "name_en": "Portland Cement 42.5R"},
        {"spu_code": "SRCH-PUMP", "name_zh": "容积泵", "name_en": "Positive Displacement Pump"},
        {"spu_code": "SRCH-PIPE", "name_zh": "水管", "name_en": "Water Supply Pipe"},
    ])
    assert _codes(await _search(client, "cement")) == ["SRCH-CEM"]          # 不再命中 displacement
    assert _codes(await _search(client, "42.5 cement")) == ["SRCH-CEM"]     # 顺序不限
    assert _codes(await _search(client, "pipes")) == ["SRCH-PIPE"]          # 词形归一
    assert _codes(await _search(client, "pipe for water")) == ["SRCH-PIPE"]  # 停用词不拖垮全部命中
    assert _codes(await _search(client, "cement pump")) == []               # 每个词都要命中
    assert _codes(await _search(client, "the")) == []                       # 全是停用词不退化成全表


@pytest.mark.asyncio
async def test_digit_words_prefix_and_code_substring(client: AsyncClient, db_session: AsyncSession):
    await _seed(db_session, [
        {"spu_code": "SRCH-BOLT-7Q", "name_zh": "六角螺栓", "name_en": "Hex Bolt M8x20"},
        {"spu_code": "SRCH-NUT", "name_zh": "螺母", "name_en": "Hex Nut M10", "manufacturer_model": "HN-M10-ZP"},
    ])
    assert _codes(await _search(client, "m8")) == ["SRCH-BOLT-7Q"]
    assert _codes(await _search(client, "BOLT-7")) == ["SRCH-BOLT-7Q"]   # SPU 编码子串
    assert _codes(await _search(client, "M10-Z")) == ["SRCH-NUT"]        # 型号子串


@pytest.mark.asyncio
async def test_latin_tokens_inside_chinese_name_and_code_in_multi_word(client: AsyncClient, db_session: AsyncSession):
    await _seed(db_session, [
        # 只有中文名(name_en 为空),规格型号写在中文名里
        {"spu_code": "SRCH-ZHONLY-9K", "name_zh": "搜测给水管 DN20 Zqppr", "name_en": None},
        {"spu_code": "SRCH-MIX", "name_zh": "搜测不锈钢304管"},
    ])
    assert _codes(await _search(client, "dn20 zqppr")) == ["SRCH-ZHONLY-9K"]
    assert _codes(await _search(client, "ZHONLY-9K 给水管")) == ["SRCH-ZHONLY-9K"]  # 多词里的编码
    assert _codes(await _search(client, "搜测不锈钢304管")) == ["SRCH-MIX"]           # 混写词按片段取 n-gram


@pytest.mark.asyncio
async def test_chinese_short_words_and_multi_word(client: AsyncClient, db_session: AsyncSession):
    await _seed(db_session, [
        {"spu_code": "SRCH-ZH1", "name_zh": "搜测热熔器 800W", "brand_zh": "搜测得力"},
        {"spu_code": "SRCH-ZH2", "name_zh": "搜测扳手"},
    ])
    assert _codes(await _search(client, "搜测热熔器")) == ["SRCH-ZH1"]
    assert set(_codes(await _search(client, "搜测"))) == {"SRCH-ZH1", "SRCH-ZH2"}  # 两字词走 n-gram
    assert _codes(await _search(client, "搜测得力 热熔器")) == ["SRCH-ZH1"]           # 品牌 + 品名分开写
    assert _codes(await _search(client, "搜测热扳")) == []                          # n-gram 粗筛后 ILIKE 精确核对


@pytest.mark.asyncio
async def test_name_match_ranks_above_model_only_match(client: AsyncClient, db_session: AsyncSession):
    await _seed(db_session, [
        {"spu_code": "SRCH-MODEL", "name_zh": "瓷砖胶", "name_en": "Tile Adhesive",
         "manufacturer_model": "zqmortar-42", "published_at": _NOW},
        {"spu_code": "SRCH-NAME", "name_zh": "砂浆", "name_en": "Zqmortar Dry Mix",
         "published_at": _NOW - timedelta(days=30)},
    ])
    assert _codes(await _search(client, "zqmortar")) == ["SRCH-NAME", "SRCH-MODEL"]


@pytest.mark.asyncio
async def test_ranking_survives_stopwords(client: AsyncClient, db_session: AsyncSession):
    """带停用词的多词搜索仍按相关度排(名称命中的旧商品排在只有型号命中的新商品前)。"""
    await _seed(db_session, [
        {"spu_code": "SRCH-SW-MODEL", "name_zh": "瓷砖", "name_en": "Ceramic Tile",
         "manufacturer_model": "zqpipe zqwater", "published_at": _NOW},
        {"spu_code": "SRCH-SW-NAME", "name_zh": "水管", "name_en": "Zqpipe Zqwater Hose",
         "published_at": _NOW - timedelta(days=30)},
    ])
    assert _codes(await _search(client, "zqpipe for zqwater")) == ["SRCH-SW-NAME", "SRCH-SW-MODEL"]


@pytest.mark.asyncio
async def test_total_capped_falls_back_to_newest_and_limits_pages(
    client: AsyncClient, db_session: AsyncSession, monkeypatch,
):
    # 与线上配置同向:总数上限 > 最多可翻条数
    monkeypatch.setattr(product_svc, "SEARCH_COUNT_CAP", 2)
    monkeypatch.setattr(product_svc, "SEARCH_MAX_RESULTS", 1)
    monkeypatch.setattr(products_api, "SEARCH_MAX_RESULTS", 1)
    await _seed(db_session, [
        {"spu_code": "SRCH-CAP-OLD", "name_zh": "旧", "name_en": "Zqcap Zqcap Zqcap", "published_at": _NOW - timedelta(days=9)},
        {"spu_code": "SRCH-CAP-NEW", "name_zh": "新", "name_en": "Zqcap Board", "published_at": _NOW},
        {"spu_code": "SRCH-CAP-MID", "name_zh": "中", "name_en": "Zqcap Panel", "published_at": _NOW - timedelta(days=5)},
    ])
    data = await _search(client, "zqcap", size=1)
    assert data["total"] == 2 and data["total_capped"] is True
    assert data["pages"] == 1
    assert _codes(data) == ["SRCH-CAP-NEW"]  # 封顶后不按相关度(OLD 词频最高),按上架时间
    assert _codes(await _search(client, "zqcap", size=1, page=2)) == []  # 超出最多可翻条数
