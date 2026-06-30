"""token_version 会话吊销测试。

覆盖工单 19 §四全部 6 个验收场景。
"""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.security import decode_token


async def _login(client, identifier: str, password: str):
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


# ── 场景 1: 登录 token 含 tv,值 == user.token_version ──


@pytest.mark.asyncio
async def test_login_token_contains_tv(client, db_session):
    """登录拿 token,解码确认含 tv == user.token_version。"""
    from app.db.models.user import User

    token = await _login(client, "operator@platform.local", "Aa123456789")
    payload = decode_token(token, expected_type="access")
    assert "tv" in payload

    # 从 DB 查 user.token_version 对比
    from sqlalchemy import select
    row = await db_session.execute(
        select(User).where(User.email == "operator@platform.local")
    )
    user = row.scalar_one()
    assert payload["tv"] == user.token_version


# ── 场景 2: 直接 bump token_version,旧 token → 401 Token revoked ──


@pytest.mark.asyncio
async def test_old_token_revoked_after_version_bump(client, db_session):
    """直接 bump 某 user 的 token_version,用其旧 token 调鉴权接口 → 401。"""
    from app.db.models.user import User
    from sqlalchemy import select

    token = await _login(client, "operator@platform.local", "Aa123456789")

    # 直接 bump
    row = await db_session.execute(
        select(User).where(User.email == "operator@platform.local")
    )
    user = row.scalar_one()
    user.token_version += 1
    await db_session.commit()

    # 旧 token 应失效
    r = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401
    assert "Token revoked" in r.json().get("message", "")


# ── 场景 3: 改密后旧 token 失效,新密码登录正常 ──


@pytest.mark.asyncio
async def test_change_password_revokes_old_token(client):
    """用户改密成功后,用改密前 access token 调鉴权接口 → 401;新密码登录正常。"""
    token = await _login(client, "operator@platform.local", "Aa123456789")
    headers = {"Authorization": f"Bearer {token}"}

    # 改密
    r = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"old_password": "Aa123456789", "new_password": "NewOpPass999"},
    )
    assert r.status_code == 200

    # 旧 token 应失效
    r2 = await client.get("/api/v1/auth/me", headers=headers)
    assert r2.status_code == 401

    # 新密码登录正常
    new_token = await _login(client, "operator@platform.local", "NewOpPass999")
    r3 = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert r3.status_code == 200


# ── 场景 4: 管理员 force-logout ──


@pytest.mark.asyncio
async def test_force_logout(client, superadmin_headers, db_session):
    """管理员对目标用户调 force-logout → 200 + 审计落库;目标旧 token → 401;目标重登正常。"""
    from sqlalchemy import select
    from app.db.models.audit_log import AuditLog
    from app.db.models.user import User

    # operator 登录拿 token
    op_token = await _login(client, "operator@platform.local", "Aa123456789")
    op_headers = {"Authorization": f"Bearer {op_token}"}

    # 确认 operator 当前正常
    r0 = await client.get("/api/v1/auth/me", headers=op_headers)
    assert r0.status_code == 200

    # 查 operator 的 user_id
    row = await db_session.execute(
        select(User).where(User.email == "operator@platform.local")
    )
    op_user = row.scalar_one()

    # 管理员强制下线
    r = await client.post(
        f"/api/v1/admin/users/{op_user.id}/force-logout",
        headers=superadmin_headers,
    )
    assert r.status_code == 200

    # 审计落库
    audit_rows = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "FORCE_LOGOUT")
    )
    logs = audit_rows.scalars().all()
    assert any(
        log.extra and log.extra.get("target_email") == "operator@platform.local"
        for log in logs
    )

    # 目标旧 token → 401
    r2 = await client.get("/api/v1/auth/me", headers=op_headers)
    assert r2.status_code == 401

    # 目标重登正常
    new_op_token = await _login(client, "operator@platform.local", "Aa123456789")
    r3 = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_op_token}"},
    )
    assert r3.status_code == 200


# ── 场景 5: 缺 tv 的存量 token → 401 ──


@pytest.mark.asyncio
async def test_token_without_tv_is_rejected(client):
    """手动构造缺 tv 的 token(模拟迁移前签发)→ 401。"""
    from jose import jwt
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    payload = {
        "sub": "1",
        "email": "superadmin@platform.local",
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        # 故意不带 tv
    }
    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    r = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401


# ── 场景 6: /refresh 用 tv 已过期的 refresh → 401 ──


@pytest.mark.asyncio
async def test_refresh_with_stale_tv_rejected(client, db_session):
    """refresh token 的 tv 与库不匹配 → 401。"""
    from app.db.models.user import User
    from sqlalchemy import select

    # 登录拿 refresh cookie
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "operator@platform.local", "password": "Aa123456789"},
    )
    assert r.status_code == 200

    # bump token_version
    row = await db_session.execute(
        select(User).where(User.email == "operator@platform.local")
    )
    user = row.scalar_one()
    user.token_version += 1
    await db_session.commit()

    # 用旧的 refresh cookie 调 /refresh → 401
    r2 = await client.post(
        "/api/v1/auth/refresh",
        headers={"origin": "http://localhost:3000"},
    )
    assert r2.status_code == 401
