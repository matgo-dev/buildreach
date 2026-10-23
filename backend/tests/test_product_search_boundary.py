"""商城公开列表 keyword 词首匹配集成测试(真实 PG,ILIKE 走 trigram 索引 + 正则过滤)。"""
from __future__ import annotations

from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.category import Category
from app.db.models.product import Product, ProductStatus, ProductVisibility


async def _seed(db: AsyncSession, rows: list[dict]) -> None:
    cat = (await db.execute(
        select(Category.code).where(Category.is_leaf.is_(True), Category.is_active.is_(True)).limit(1)
    )).scalar_one()
    for row in rows:
        db.add(Product(
            category_code=cat, status=ProductStatus.ACTIVE, visibility=ProductVisibility.PUBLIC,
            published_at=datetime(2026, 10, 1), **row,
        ))
    await db.flush()


async def _codes(client: AsyncClient, keyword: str) -> set[str]:
    r = await client.get("/api/v1/products", params={"keyword": keyword, "size": 50})
    assert r.status_code == 200, r.text
    return {i["spu_code"] for i in r.json()["data"]["items"] if i["spu_code"].startswith("SWB-")}


@pytest.mark.asyncio
async def test_latin_fields_require_word_start(client: AsyncClient, db_session: AsyncSession):
    await _seed(db_session, [
        {"spu_code": "SWB-C1", "name_zh": "硅酸盐水泥", "name_en": "Portland Cement 42.5R"},
        {"spu_code": "SWB-PUMP", "name_zh": "容积泵", "name_en": "Positive Displacement Pump"},
        {"spu_code": "SWB-H1", "name_zh": "双壁波纹管", "name_en": "HDPE double-wall pipe"},
        {"spu_code": "SWB-P1", "name_zh": "给水管", "name_en": "PE water pipe"},
        {"spu_code": "SWB-T1", "name_zh": "钢尺", "name_en": "Deli Steel Ruler 150mm"},
        {"spu_code": "SWB-T2", "name_zh": "三通", "name_en": "Brass Tee fitting"},
        {"spu_code": "SWB-SW", "name_zh": "水泥", "name_sw": "Saruji ya Portland"},
        {"spu_code": "SWB-SWMID", "name_zh": "工具", "name_sw": "Kisaruji kifaa"},
    ])
    assert await _codes(client, "cement") == {"SWB-C1"}
    assert await _codes(client, " cement") == {"SWB-C1"}   # 前导空格:不能把 Portland Cement 杀掉
    assert await _codes(client, "tee") == {"SWB-T2"}
    assert await _codes(client, "PE") == {"SWB-P1", "SWB-H1"}   # <3 字符不约束,与现状一致
    assert await _codes(client, "saruji") == {"SWB-SW"}


@pytest.mark.asyncio
async def test_digits_and_specs_in_chinese_names(client: AsyncClient, db_session: AsyncSession):
    await _seed(db_session, [
        {"spu_code": "SWB-S1", "name_zh": "不锈钢板", "name_en": "SUS304 stainless sheet"},
        {"spu_code": "SWB-X1", "name_zh": "零件", "name_en": "Part 1304 steel"},
        {"spu_code": "SWB-D1", "name_zh": "搜界球阀DN20", "name_en": None},
        {"spu_code": "SWB-B1", "name_zh": "板材", "name_en": "Panel 600*120mm"},
        {"spu_code": "SWB-B2", "name_zh": "管材", "name_en": "PE pipe 20mm"},
        {"spu_code": "SWB-B3", "name_zh": "管材", "name_en": "Size 16mm,20mm,25mm"},
        {"spu_code": "SWB-X2", "name_zh": "阀", "name_en": "Art.No.304 valve"},
        {"spu_code": "SWB-X3", "name_zh": "件", "name_en": "Qty 1,304 pcs"},
    ])
    assert await _codes(client, "304") == {"SWB-S1", "SWB-X2"}   # 点前非数字 → 分隔;1,304 仍不命中
    assert await _codes(client, "DN20") == {"SWB-D1"}   # 中文名字段不加约束,照常子串命中
    assert await _codes(client, "20mm") == {"SWB-B2", "SWB-B3"}  # 逗号分隔的规格列表照常命中


@pytest.mark.asyncio
async def test_chinese_model_and_code_unchanged(client: AsyncClient, db_session: AsyncSession):
    await _seed(db_session, [
        {"spu_code": "SWB-ZH", "name_zh": "搜界硅酸盐水泥", "manufacturer_model": "XGEM-42"},
    ])
    assert await _codes(client, "搜界水泥") == set()          # 中文仍是子串:不连续不命中
    assert await _codes(client, "酸盐水泥") == {"SWB-ZH"}     # 中文词中间命中照旧
    assert await _codes(client, "GEM-4") == {"SWB-ZH"}       # 型号仍是子串
    assert await _codes(client, "WB-ZH") == {"SWB-ZH"}       # 编码仍是子串


@pytest.mark.asyncio
async def test_special_characters_go_through_real_postgres(client: AsyncClient, db_session: AsyncSession):
    """正则/LIKE 元字符走真实 PG(ARE + ILIKE ESCAPE):按字面匹配,不报错,两者口径一致。"""
    await _seed(db_session, [
        {"spu_code": "SWB-M1", "name_zh": "螺栓", "name_en": "Hex Bolt M8*20 zinc"},
        {"spu_code": "SWB-M2", "name_zh": "螺栓", "name_en": "Hex Bolt M820 zinc"},
        {"spu_code": "SWB-D1", "name_zh": "板", "name_en": "Crystal board 1.5mm"},
        {"spu_code": "SWB-D2", "name_zh": "板", "name_en": "Crystal board 105mm"},
        {"spu_code": "SWB-P1", "name_zh": "件", "name_en": "part A(B) x"},
        {"spu_code": "SWB-B1", "name_zh": "件", "name_en": "item a{b} y"},
        {"spu_code": "SWB-S1", "name_zh": "件", "name_en": "path C\\D here"},
        {"spu_code": "SWB-U1", "name_zh": "管", "name_en": "PE_pipe black"},
        {"spu_code": "SWB-U2", "name_zh": "管", "name_en": "PE pipe black"},
    ])
    assert await _codes(client, "M8*20") == {"SWB-M1"}
    assert await _codes(client, "1.5mm") == {"SWB-D1"}
    assert await _codes(client, "A(B)") == {"SWB-P1"}
    assert await _codes(client, "a{b") == {"SWB-B1"}
    assert await _codes(client, "C\\D") == {"SWB-S1"}
    assert await _codes(client, "PE_pipe") == {"SWB-U1"}   # _ 按字面,不再是单字符通配
    assert await _codes(client, "100%") == set()           # % 按字面


@pytest.mark.asyncio
async def test_every_regex_special_is_valid_in_postgres(client: AsyncClient):
    """_REGEX_SPECIALS 是 PG ARE 的权威转义集:每个字符单独作为关键词都不能让查询报错。"""
    from app.services.product import _REGEX_SPECIALS
    for ch in sorted(_REGEX_SPECIALS) + ["\\", "%", "_", "\'", '"']:
        r = await client.get("/api/v1/products", params={"keyword": f"ab{ch}cd"})
        assert r.status_code == 200, (ch, r.text)
