"""分类 Service + API 测试。

公开接口,不需要登录态。直接在 test_engine 提供的空库中插入几个节点验证。
"""
from __future__ import annotations

import pytest

from app.db.base import _utcnow
from app.db.models import Category
from app.services import category as cs


async def _seed(db_session, rows: list[tuple]):
    """插入 (code, name_zh, level, parent_code, sort_order, is_active) 元组。"""
    now = _utcnow()
    for code, name_zh, level, parent_code, sort_order, is_active in rows:
        db_session.add(
            Category(
                code=code,
                name_zh=name_zh,
                level=level,
                parent_code=parent_code,
                sort_order=sort_order,
                is_active=is_active,
                created_at=now,
                updated_at=now,
            )
        )
    await db_session.commit()


SAMPLE = [
    ("01", "土建", 1, None, 0, True),
    ("01.001", "钢筋类", 2, "01", 0, True),
    ("01.001.001", "螺纹钢", 3, "01.001", 0, True),
    ("01.001.002", "圆钢", 3, "01.001", 1, True),
    ("01.002", "商砼", 2, "01", 1, True),
    ("01.002.001", "混凝土", 3, "01.002", 0, True),
    ("02", "安装", 1, None, 1, True),
    ("02.001", "弱电", 2, "02", 0, True),
    ("99", "已停用一级", 1, None, 99, False),
]


# ---------- Service: list_flat ----------


@pytest.mark.asyncio
async def test_list_flat_default_active_only(db_session):
    await _seed(db_session, SAMPLE)
    rows = await cs.list_flat(db_session)
    codes = [r.code for r in rows]
    assert "99" not in codes  # is_active=false 默认过滤
    assert codes == ["01", "02", "01.001", "01.002", "02.001",
                     "01.001.001", "01.001.002", "01.002.001"]


@pytest.mark.asyncio
async def test_list_flat_filter_level(db_session):
    await _seed(db_session, SAMPLE)
    rows = await cs.list_flat(db_session, level=1)
    assert [r.code for r in rows] == ["01", "02"]


@pytest.mark.asyncio
async def test_list_flat_filter_parent_code(db_session):
    await _seed(db_session, SAMPLE)
    rows = await cs.list_flat(db_session, parent_code="01")
    assert [r.code for r in rows] == ["01.001", "01.002"]


@pytest.mark.asyncio
async def test_list_flat_include_inactive(db_session):
    await _seed(db_session, SAMPLE)
    rows = await cs.list_flat(db_session, is_active=None)
    assert any(r.code == "99" for r in rows)


# ---------- Service: get_tree ----------


@pytest.mark.asyncio
async def test_get_tree_shape(db_session):
    await _seed(db_session, SAMPLE)
    tree = await cs.get_tree(db_session)
    assert [r.code for r in tree] == ["01", "02"]

    l1 = tree[0]
    assert l1.name_zh == "土建"
    assert [c.code for c in l1.children] == ["01.001", "01.002"]
    assert [c.code for c in l1.children[0].children] == ["01.001.001", "01.001.002"]


@pytest.mark.asyncio
async def test_get_tree_excludes_inactive_branches(db_session):
    rows = list(SAMPLE) + [
        ("01.001.999", "停用三级", 3, "01.001", 99, False),
    ]
    await _seed(db_session, rows)
    tree = await cs.get_tree(db_session)
    l1 = tree[0]
    l2 = l1.children[0]  # 01.001 钢筋类
    assert "停用三级" not in [c.name_zh for c in l2.children]


# ---------- API ----------


@pytest.mark.asyncio
async def test_api_list_categories_default(client, db_session):
    await _seed(db_session, SAMPLE)
    r = await client.get("/api/v1/categories")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["message"] == "ok"
    codes = [n["code"] for n in body["data"]]
    assert "99" not in codes


@pytest.mark.asyncio
async def test_api_list_categories_filter_level(client, db_session):
    await _seed(db_session, SAMPLE)
    r = await client.get("/api/v1/categories?level=1")
    assert r.status_code == 200
    codes = [n["code"] for n in r.json()["data"]]
    assert codes == ["01", "02"]


@pytest.mark.asyncio
async def test_api_list_categories_filter_parent(client, db_session):
    await _seed(db_session, SAMPLE)
    r = await client.get("/api/v1/categories?parent_code=01.001")
    assert r.status_code == 200
    codes = [n["code"] for n in r.json()["data"]]
    assert codes == ["01.001.001", "01.001.002"]


@pytest.mark.asyncio
async def test_api_list_categories_level_validation(client):
    """level 必须在 1..3 之间。"""
    r = await client.get("/api/v1/categories?level=4")
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_api_tree(client, db_session):
    await _seed(db_session, SAMPLE)
    r = await client.get("/api/v1/categories/tree")
    assert r.status_code == 200
    data = r.json()["data"]
    assert [n["code"] for n in data] == ["01", "02"]
    l1 = data[0]
    assert [c["code"] for c in l1["children"]] == ["01.001", "01.002"]
    assert [c["code"] for c in l1["children"][0]["children"]] == [
        "01.001.001",
        "01.001.002",
    ]


@pytest.mark.asyncio
async def test_api_no_permission_required(client, db_session):
    """公开 API:不携带任何 Authorization 都能访问。"""
    await _seed(db_session, SAMPLE)
    r = await client.get("/api/v1/categories/tree")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_api_trace_id_header_present(client):
    r = await client.get("/api/v1/categories")
    assert r.status_code == 200
    assert r.headers.get("x-trace-id"), "X-Trace-Id 响应头缺失"
