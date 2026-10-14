"""分类 Service + API 测试。

公开接口,不需要登录态。直接在 test_engine 提供的空库中插入几个节点验证。
"""
from __future__ import annotations

import pytest

from sqlalchemy import delete, text

from app.db.base import _utcnow
from app.db.models import Category
from app.services import category as cs


async def _seed(db_session, rows: list[tuple]):
    """插入 (code, name_zh, level, parent_code, sort_order, is_active) 元组。

    先清理可能由 seed_categories 种入的品类(外键约束:先删 L3→L2→L1)。
    """
    # seed_categories 全量覆盖可能已种入品类 + 属性模板,按 FK 依赖顺序清理
    await db_session.execute(text("DELETE FROM attr_templates"))
    await db_session.execute(text("DELETE FROM product_attrs"))
    await db_session.execute(text("DELETE FROM categories WHERE level = 4"))
    await db_session.execute(text("DELETE FROM categories WHERE level = 3"))
    await db_session.execute(text("DELETE FROM categories WHERE level = 2"))
    await db_session.execute(text("DELETE FROM categories WHERE level = 1"))
    await db_session.commit()

    # 收集有 active 子节点的 parent_code,用于计算 is_leaf
    parent_codes_with_active_children: set[str] = set()
    for code, name_zh, level, parent_code, sort_order, is_active in rows:
        if parent_code and is_active:
            parent_codes_with_active_children.add(parent_code)

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
                is_leaf=code not in parent_codes_with_active_children,
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
    """level 必须在 1..4 之间。"""
    r = await client.get("/api/v1/categories?level=5")
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
async def test_api_tree_is_leaf_values(client, db_session):
    """树响应中 is_leaf 值正确：有 active 子节点的品类为非叶子，L3 为叶子。"""
    await _seed(db_session, SAMPLE)
    r = await client.get("/api/v1/categories/tree")
    assert r.status_code == 200
    data = r.json()["data"]

    # 构建 code→node 映射方便断言
    node_map: dict = {}
    def _walk(nodes: list) -> None:
        for n in nodes:
            node_map[n["code"]] = n
            _walk(n.get("children", []))
    _walk(data)

    # L1/L2 有 active 子节点，is_leaf=False
    assert node_map["01"]["is_leaf"] is False,   "L1 有子节点，应为非叶子"
    assert node_map["01.001"]["is_leaf"] is False, "L2 有子节点，应为非叶子"
    assert node_map["01.002"]["is_leaf"] is False, "L2 有子节点，应为非叶子"
    # L3 无子节点，is_leaf=True
    assert node_map["01.001.001"]["is_leaf"] is True, "L3 应为叶子"
    assert node_map["01.001.002"]["is_leaf"] is True, "L3 应为叶子"


@pytest.mark.asyncio
async def test_api_list_is_leaf_values(client, db_session):
    """扁平列表响应中 is_leaf 字段存在且值正确。"""
    await _seed(db_session, SAMPLE)
    r = await client.get("/api/v1/categories")
    assert r.status_code == 200
    node_map = {n["code"]: n for n in r.json()["data"]}

    assert node_map["01"]["is_leaf"] is False
    assert node_map["01.001"]["is_leaf"] is False
    assert node_map["01.001.001"]["is_leaf"] is True


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

async def _operator_headers(client) -> dict[str, str]:
    """运营账号(持 zone:manage);超管种子账号没有业务权限,别用 superadmin_headers。"""
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "operator@platform.local", "password": "Aa123456789"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


_ACTIVE_PLUS_INACTIVE = [
    ("01", "启用一级", 1, None, 1, True),
    ("01.001", "启用叶子", 2, "01", 1, True),
    ("98", "停用一级", 1, None, 900, False),
    ("98.001", "停用叶子", 2, "98", 1, False),
]


@pytest.mark.asyncio
async def test_tree_include_inactive_flag(client, db_session):
    """默认树不含停用一级;include_inactive=true(运营登录态)时停用一级连同其停用叶子
    一起返回(嵌套,不顶到根),节点带 is_active 供前端标灰/禁选。"""
    await _seed(db_session, _ACTIVE_PLUS_INACTIVE)
    cs.invalidate_category_cache()  # 进程内 TTL 缓存会留着上个测试的树
    r = await client.get("/api/v1/categories/tree")
    assert {n["code"] for n in r.json()["data"]} == {"01"}

    r2 = await client.get("/api/v1/categories/tree?include_inactive=true", headers=await _operator_headers(client))
    assert r2.status_code == 200, r2.text
    roots = {n["code"]: n for n in r2.json()["data"]}
    assert set(roots) == {"01", "98"}
    assert [c["code"] for c in roots["98"]["children"]] == ["98.001"]
    assert roots["01"]["is_active"] is True
    assert roots["98"]["is_active"] is False
    assert roots["98"]["children"][0]["is_active"] is False


@pytest.mark.asyncio
async def test_list_include_inactive_flag(client, db_session):
    await _seed(db_session, _ACTIVE_PLUS_INACTIVE)
    cs.invalidate_category_cache()
    r = await client.get("/api/v1/categories?include_inactive=true&level=1", headers=await _operator_headers(client))
    assert r.status_code == 200, r.text
    assert {n["code"] for n in r.json()["data"]} == {"01", "98"}
    r2 = await client.get("/api/v1/categories?level=1")
    assert {n["code"] for n in r2.json()["data"]} == {"01"}


@pytest.mark.asyncio
async def test_include_inactive_requires_login(client, db_session):
    """停用类目是刻意对公众隐藏的专区类目:匿名带 include_inactive=true 一律 401,
    默认请求照常 200(公开接口不受影响)。"""
    await _seed(db_session, _ACTIVE_PLUS_INACTIVE)
    cs.invalidate_category_cache()
    for path in ("/api/v1/categories/tree?include_inactive=true",
                 "/api/v1/categories?include_inactive=true&level=1"):
        r = await client.get(path)
        assert r.status_code == 401, (path, r.text)
    # 无效 token 也当匿名
    r = await client.get("/api/v1/categories/tree?include_inactive=true",
                         headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401
    assert (await client.get("/api/v1/categories/tree")).status_code == 200


@pytest.mark.asyncio
async def test_include_inactive_requires_zone_manage(client, db_session):
    """登录但没有 zone:manage(买家,虽有 product:read)→ 403。"""
    await _seed(db_session, _ACTIVE_PLUS_INACTIVE)
    cs.invalidate_category_cache()
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "buyer@cscec3b.local", "password": "Aa123456789"},
    )
    assert r.status_code == 200, r.text
    headers = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
    r = await client.get("/api/v1/categories/tree?include_inactive=true", headers=headers)
    assert r.status_code == 403, r.text
