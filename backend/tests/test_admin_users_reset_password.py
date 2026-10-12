"""ADMIN 重置用户密码接口测试。

覆盖:重置后 must_change_password=True 且旧 token 失效、新密码可登录 /
不能重置自己 400 / OPERATOR 无权 403 / 弱密码 422。
"""
from __future__ import annotations

import pytest

_OLD = "Aa123456789"
_NEW = "Zz999888777"


async def _login(client, identifier, password):
    r = await client.post(
        "/api/v1/auth/login", json={"identifier": identifier, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def _create_operator(client, headers: dict, email: str) -> int:
    r = await client.post(
        "/api/v1/admin/users",
        json={"email": email, "name": "op", "password": _OLD,
              "role": "OPERATOR", "must_change_password": False},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


@pytest.mark.asyncio
async def test_reset_password_revokes_old_token_and_forces_change(client, superadmin_headers):
    op_id = await _create_operator(client, superadmin_headers, "rp1@x.com")
    old_token = await _login(client, "rp1@x.com", _OLD)
    old_h = {"Authorization": f"Bearer {old_token}"}
    assert (await client.get("/api/v1/auth/me", headers=old_h)).status_code == 200

    r = await client.post(
        f"/api/v1/admin/users/{op_id}/reset-password",
        json={"new_password": _NEW}, headers=superadmin_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["must_change_password"] is True

    # 旧 token 失效
    assert (await client.get("/api/v1/auth/me", headers=old_h)).status_code == 401
    # 旧密码不能登录,新密码可以,且被要求改密
    bad = await client.post(
        "/api/v1/auth/login", json={"identifier": "rp1@x.com", "password": _OLD}
    )
    assert bad.status_code == 401
    new_token = await _login(client, "rp1@x.com", _NEW)
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me.json()["data"]["must_change_password"] is True


@pytest.mark.asyncio
async def test_reset_own_password_400(client, superadmin_headers):
    me = await client.get("/api/v1/auth/me", headers=superadmin_headers)
    my_id = me.json()["data"]["id"]
    r = await client.post(
        f"/api/v1/admin/users/{my_id}/reset-password",
        json={"new_password": _NEW}, headers=superadmin_headers,
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_operator_cannot_reset_403(client, superadmin_headers):
    await _create_operator(client, superadmin_headers, "rp2@x.com")
    victim_id = await _create_operator(client, superadmin_headers, "rp3@x.com")
    op_token = await _login(client, "rp2@x.com", _OLD)
    r = await client.post(
        f"/api/v1/admin/users/{victim_id}/reset-password",
        json={"new_password": _NEW}, headers={"Authorization": f"Bearer {op_token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_reset_weak_password_422(client, superadmin_headers):
    op_id = await _create_operator(client, superadmin_headers, "rp4@x.com")
    r = await client.post(
        f"/api/v1/admin/users/{op_id}/reset-password",
        json={"new_password": "123456"}, headers=superadmin_headers,
    )
    assert r.status_code == 422
