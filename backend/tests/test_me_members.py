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


@pytest.mark.asyncio
async def test_disable_self_400(client):
    owner_h, _ = await _register_owner(client)
    me = await client.get("/api/v1/auth/me", headers=owner_h)
    my_id = me.json()["data"]["id"]
    r = await client.post(f"{MEMBERS}/{my_id}/disable", headers=owner_h)
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_disable_other_org_user_404(client):
    owner_h, _ = await _register_owner(client)
    other = await register_buyer_tz(client, company_name="Other Co")
    other_token = other["response"].json()["data"]["access_token"]
    other_me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {other_token}"}
    )
    other_id = other_me.json()["data"]["id"]
    r = await client.post(f"{MEMBERS}/{other_id}/disable", headers=owner_h)
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_disable_then_enable_member(client):
    owner_h, _ = await _register_owner(client)
    email = f"emp{_next_phone().replace('+', '')}@test.com"
    created = (await _create_member(client, owner_h, email)).json()["data"]

    r = await client.post(f"{MEMBERS}/{created['id']}/disable", headers=owner_h)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "DISABLED"

    bad = await _login(client, email, _MEMBER_PASSWORD)
    assert bad.status_code in (401, 403)

    r2 = await client.post(f"{MEMBERS}/{created['id']}/enable", headers=owner_h)
    assert r2.status_code == 200
    assert r2.json()["data"]["status"] == "ACTIVE"

    ok = await _login(client, email, _MEMBER_PASSWORD)
    assert ok.status_code == 200


# ---------- 终审修复:停用/启用的作用域 ----------

async def _member_id(client, owner_h: dict) -> int:
    email = f"emp{_next_phone().replace('+', '')}@test.com"
    return (await _create_member(client, owner_h, email)).json()["data"]["id"]


@pytest.mark.asyncio
async def test_owner_cannot_disable_another_owner_404(client, db_session):
    """同组织另一个 owner 不在可操作范围内 → 404(与"非成员"同口径)。"""
    from sqlalchemy import select
    from app.db.models.buyer_member import BuyerMember

    owner_h, org_id = await _register_owner(client)
    mid = await _member_id(client, owner_h)
    row = await db_session.execute(
        select(BuyerMember).where(BuyerMember.user_id == mid, BuyerMember.buyer_org_id == org_id)
    )
    row.scalar_one().is_owner = True
    await db_session.commit()

    r = await client.post(f"{MEMBERS}/{mid}/disable", headers=owner_h)
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_owner_cannot_disable_member_with_internal_role_404(client, db_session):
    """成员兼有 OPERATOR 角色 → users.status 是平台级,owner 不能动 → 404。"""
    from sqlalchemy import select
    from app.db.models.role import Role
    from app.db.models.user_role import UserRole

    owner_h, _ = await _register_owner(client)
    mid = await _member_id(client, owner_h)
    role_id = (await db_session.execute(select(Role.id).where(Role.code == "OPERATOR"))).scalar_one()
    db_session.add(UserRole(user_id=mid, role_id=role_id))
    await db_session.commit()

    r = await client.post(f"{MEMBERS}/{mid}/disable", headers=owner_h)
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_owner_cannot_disable_multi_org_member_404(client, db_session):
    """成员同时属于另一组织(运营合并产生)→ 停用会波及他组织 → 404。"""
    from app.db.models.buyer_member import BuyerMember

    owner_h, _ = await _register_owner(client)
    mid = await _member_id(client, owner_h)
    other = await register_buyer_tz(client, company_name="Other Co")
    other_token = other["response"].json()["data"]["access_token"]
    other_org = (await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {other_token}"}
    )).json()["data"]["organization"]["id"]
    db_session.add(BuyerMember(user_id=mid, buyer_org_id=other_org, is_owner=False))
    await db_session.commit()

    r = await client.post(f"{MEMBERS}/{mid}/disable", headers=owner_h)
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_deactivated_member_cannot_be_toggled_400(client, db_session):
    """成员自己注销(DEACTIVATED)后,owner 既不能停用也不能启用 → 400。"""
    from app.db.models.user import User, UserStatus

    owner_h, _ = await _register_owner(client)
    mid = await _member_id(client, owner_h)
    (await db_session.get(User, mid)).status = UserStatus.DEACTIVATED
    await db_session.commit()

    assert (await client.post(f"{MEMBERS}/{mid}/disable", headers=owner_h)).status_code == 400
    assert (await client.post(f"{MEMBERS}/{mid}/enable", headers=owner_h)).status_code == 400
    lst = await client.get(MEMBERS, headers=owner_h)
    assert [m["status"] for m in lst.json()["data"] if m["id"] == mid] == ["DEACTIVATED"]
