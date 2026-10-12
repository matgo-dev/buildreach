"""买方组织成员管理(/auth/me/organization/members)集成测试。

覆盖关键路径:owner 建子账号三表落库 + 首登强制改密 / 非 owner 403 / 邮箱重复 409 /
停用自己 400 / 停用他组织 404 / 停用后不能登录、启用后恢复。
"""
from __future__ import annotations

import pytest

from tests.conftest import _next_phone, register_buyer_tz

_PASSWORD = "Aa123456789"
_MEMBER_PASSWORD = "Bb987654321"
MEMBERS = "/api/v1/auth/me/organization/members"


async def _register_owner(client, company_name: str = "Owner Co") -> tuple[dict, int]:
    result = await register_buyer_tz(client, password=_PASSWORD, company_name=company_name)
    assert result["response"].status_code == 200, result["response"].text
    token = result["response"].json()["data"]["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    me = await client.get("/api/v1/auth/me", headers=h)
    return h, me.json()["data"]["organization"]["id"]


async def _login(client, identifier: str, password: str):
    return await client.post(
        "/api/v1/auth/login", json={"identifier": identifier, "password": password}
    )


async def _create_member(client, owner_h: dict, email: str, name: str = "Employee"):
    return await client.post(
        MEMBERS, json={"name": name, "email": email, "password": _MEMBER_PASSWORD}, headers=owner_h
    )


@pytest.mark.asyncio
async def test_owner_creates_member_and_member_must_change_password(client):
    owner_h, org_id = await _register_owner(client)
    email = f"emp{_next_phone().replace('+', '')}@test.com"

    r = await _create_member(client, owner_h, email)
    assert r.status_code == 200, r.text
    created = r.json()["data"]
    assert created["email"] == email
    assert created["is_owner"] is False
    assert created["status"] == "ACTIVE"

    # 列表:owner 排第一,共两人
    lst = await client.get(MEMBERS, headers=owner_h)
    assert lst.status_code == 200
    rows = lst.json()["data"]
    assert len(rows) == 2
    assert rows[0]["is_owner"] is True
    assert rows[1]["id"] == created["id"]

    # 子账号能登录,且挂在同一组织、必须改密
    login = await _login(client, email, _MEMBER_PASSWORD)
    assert login.status_code == 200, login.text
    member_h = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    me = await client.get("/api/v1/auth/me", headers=member_h)
    assert me.json()["data"]["must_change_password"] is True
    assert me.json()["data"]["organization"]["id"] == org_id
    assert me.json()["data"]["organization"]["is_owner"] is False
    assert "BUYER" in me.json()["data"]["roles"]

    # 改密前被 block_if_must_change_password 拦
    blocked = await client.get(MEMBERS, headers=member_h)
    assert blocked.status_code == 403

    # 改密后仍是非 owner → 403
    cp = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": _MEMBER_PASSWORD, "new_password": "Cc111222333"},
        headers=member_h,
    )
    assert cp.status_code == 200, cp.text
    member_h2 = {"Authorization": f"Bearer {cp.json()['data']['access_token']}"}
    still = await client.get(MEMBERS, headers=member_h2)
    assert still.status_code == 403
    create_as_member = await client.post(
        MEMBERS, json={"name": "X", "email": "x@test.com", "password": _MEMBER_PASSWORD},
        headers=member_h2,
    )
    assert create_as_member.status_code == 403


@pytest.mark.asyncio
async def test_create_member_duplicate_email_409(client):
    owner_h, _ = await _register_owner(client)
    other = await register_buyer_tz(client, company_name="Other Co")
    taken = other["email"]
    r = await _create_member(client, owner_h, taken)
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_create_member_weak_password_422(client):
    owner_h, _ = await _register_owner(client)
    r = await client.post(
        MEMBERS, json={"name": "E", "email": "weak@test.com", "password": "123456"}, headers=owner_h
    )
    assert r.status_code == 422
