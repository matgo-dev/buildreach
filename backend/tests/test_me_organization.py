"""买方组织自助编辑(PATCH /auth/me/organization)+ 运营按 uscc 检索 集成测试。

覆盖关键路径:owner 落库 / PATCH 语义 / uscc 唯一冲突 / 非 owner 门 / 授权检索按 uscc 命中。
"""
from __future__ import annotations

import pytest

from app.core.security import hash_password
from app.db.models.buyer_member import BuyerMember
from app.db.models.user import User, UserStatus
from tests.conftest import _next_phone, register_buyer_tz

_PASSWORD = "Aa123456789"
_USCC = "91110000ABCDEF1234"  # 18 位


async def _register_owner(client, company_name: str = "Owner Co") -> tuple[dict, int]:
    """注册买方 owner,返回 (headers, org_id)。"""
    result = await register_buyer_tz(client, password=_PASSWORD, company_name=company_name)
    assert result["response"].status_code == 200, result["response"].text
    token = result["response"].json()["data"]["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    me = await client.get("/api/v1/auth/me", headers=h)
    return h, me.json()["data"]["organization"]["id"]


@pytest.mark.asyncio
async def test_owner_update_name_and_uscc(client):
    h, _ = await _register_owner(client)
    r = await client.patch(
        "/api/v1/auth/me/organization",
        json={"name": "央企采购中心", "unified_social_credit_code": _USCC},
        headers=h,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["name"] == "央企采购中心"
    assert data["unified_social_credit_code"] == _USCC
    # /me 同步反映(证明落库,不是只回显)
    me = await client.get("/api/v1/auth/me", headers=h)
    org = me.json()["data"]["organization"]
    assert org["name"] == "央企采购中心"
    assert org["unified_social_credit_code"] == _USCC


@pytest.mark.asyncio
async def test_update_partial_keeps_uscc(client):
    """只传 name,uscc 不应被清空(PATCH 语义)。"""
    h, _ = await _register_owner(client)
    await client.patch(
        "/api/v1/auth/me/organization",
        json={"unified_social_credit_code": _USCC}, headers=h,
    )
    r = await client.patch(
        "/api/v1/auth/me/organization", json={"name": "只改名字"}, headers=h,
    )
    assert r.status_code == 200
    assert r.json()["data"]["unified_social_credit_code"] == _USCC


@pytest.mark.asyncio
async def test_clear_uscc_with_empty_string(client):
    """uscc 传空串 → 清空。"""
    h, _ = await _register_owner(client)
    await client.patch(
        "/api/v1/auth/me/organization",
        json={"unified_social_credit_code": _USCC}, headers=h,
    )
    r = await client.patch(
        "/api/v1/auth/me/organization",
        json={"unified_social_credit_code": ""}, headers=h,
    )
    assert r.status_code == 200
    assert r.json()["data"]["unified_social_credit_code"] is None


@pytest.mark.asyncio
async def test_uscc_conflict_returns_409(client):
    ha, _ = await _register_owner(client)
    await client.patch(
        "/api/v1/auth/me/organization",
        json={"unified_social_credit_code": _USCC}, headers=ha,
    )
    hb, _ = await _register_owner(client)
    r = await client.patch(
        "/api/v1/auth/me/organization",
        json={"unified_social_credit_code": _USCC}, headers=hb,
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_empty_name_rejected(client):
    h, _ = await _register_owner(client)
    r = await client.patch(
        "/api/v1/auth/me/organization", json={"name": ""}, headers=h,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_requires_auth(client):
    r = await client.patch("/api/v1/auth/me/organization", json={"name": "X"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_non_owner_forbidden(client, db_session):
    """非 owner 成员即使属于该组织也不能改 → 403。"""
    _, org_id = await _register_owner(client)
    phone = _next_phone()
    email = f"emp{phone.replace('+', '')}@test.com"
    u = User(
        email=email, name="Employee", phone=phone,
        password_hash=hash_password(_PASSWORD),
        status=UserStatus.ACTIVE, must_change_password=False,
    )
    db_session.add(u)
    await db_session.flush()
    db_session.add(BuyerMember(user_id=u.id, buyer_org_id=org_id, is_owner=False))
    await db_session.commit()

    login = await client.post(
        "/api/v1/auth/login", json={"identifier": email, "password": _PASSWORD},
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    r = await client.patch(
        "/api/v1/auth/me/organization",
        json={"name": "想改但没权限"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_no_buyer_org_returns_404(client):
    """无买方组织的账号(种子运营)调该接口 → 404。"""
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "operator@platform.local", "password": _PASSWORD},
    )
    assert login.status_code == 200, login.text
    h = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    r = await client.patch(
        "/api/v1/auth/me/organization", json={"name": "X"}, headers=h,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_noop_update_returns_200(client):
    """name 传当前值、uscc 不传 → 无变更,幂等 200。"""
    h, _ = await _register_owner(client, company_name="Same Co")
    r = await client.patch(
        "/api/v1/auth/me/organization", json={"name": "Same Co"}, headers=h,
    )
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "Same Co"


# ----- 任务 B:运营授权检索支持 uscc -----

@pytest.mark.asyncio
async def test_operator_search_buyer_org_by_uscc(client):
    """运营授权时可按统一社会信用代码检索到买方组织(种子运营账号)。"""
    h, _ = await _register_owner(client, company_name="不含关键词的公司名")
    await client.patch(
        "/api/v1/auth/me/organization",
        json={"unified_social_credit_code": _USCC}, headers=h,
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "operator@platform.local", "password": _PASSWORD},
    )
    assert login.status_code == 200, login.text
    op_headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    r = await client.get(
        f"/api/v1/operator/buyer-orgs?q={_USCC}", headers=op_headers,
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert any(it["unified_social_credit_code"] == _USCC for it in items)
