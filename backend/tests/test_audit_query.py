"""T5 · 审计日志查询接口测试。"""
from __future__ import annotations

import pytest

from app.core.config import settings


async def _login(client, identifier, password):
    r = await client.post(
        "/api/v1/auth/login", json={"identifier": identifier, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


# ---------- 权限边界 ----------

@pytest.mark.asyncio
async def test_audit_logs_requires_system_audit(client):
    # OPERATOR 无 system:audit
    op_token = await _login(client, "operator@platform.local", "Aa123456789")
    r = await client.get(
        "/api/v1/admin/audit-logs",
        headers={"Authorization": f"Bearer {op_token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_audit_logs_unauthenticated(client):
    r = await client.get("/api/v1/admin/audit-logs")
    assert r.status_code == 401


# ---------- 列表 + 筛选 ----------

@pytest.mark.asyncio
async def test_list_audit_logs_basic(client, superadmin_headers):
    h = superadmin_headers
    # 触发一条注册审计
    from tests.conftest import register_buyer_tz
    await register_buyer_tz(client)

    r = await client.get("/api/v1/admin/audit-logs?page=1&page_size=50", headers=h)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["page"] == 1
    assert data["page_size"] == 50
    assert data["total"] >= 1
    # 排序 created_at desc
    items = data["items"]
    assert len(items) >= 1
    if len(items) > 1:
        for a, b in zip(items, items[1:]):
            assert (a["created_at"] or "") >= (b["created_at"] or "")


@pytest.mark.asyncio
async def test_filter_by_resource_and_action(client, superadmin_headers):
    h = superadmin_headers
    r = await client.get(
        "/api/v1/admin/audit-logs?resource_type=auth&action=LOGIN_SUCCESS",
        headers=h,
    )
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert len(items) >= 1
    assert all(it["resource_type"] == "auth" and it["action"] == "LOGIN_SUCCESS" for it in items)


@pytest.mark.asyncio
async def test_filter_by_user_email_ilike(client, superadmin_headers):
    h = superadmin_headers
    # 注册买方（审计日志中 user_email 记录的是 phone）
    from tests.conftest import register_buyer_tz
    result = await register_buyer_tz(client)
    phone = result["phone"]
    # phone 作为 user_email 存储在审计日志中
    r = await client.get(
        f"/api/v1/admin/audit-logs?user_email={phone[1:]}", headers=h  # 去掉 + 号搜 ilike
    )
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert len(items) >= 1


@pytest.mark.asyncio
async def test_filter_by_trace_id(client, superadmin_headers):
    h = superadmin_headers
    from tests.conftest import register_buyer_tz
    result = await register_buyer_tz(client)
    trace = result["response"].headers.get("X-Trace-Id")
    assert trace, "register 必须返回 X-Trace-Id"

    r = await client.get(f"/api/v1/admin/audit-logs?trace_id={trace}", headers=h)
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert len(items) >= 1
    assert all(it["trace_id"] == trace for it in items)


@pytest.mark.asyncio
async def test_filter_by_status_failed_login(client, superadmin_headers):
    h = superadmin_headers
    await client.post(
        "/api/v1/auth/login", json={"identifier": "ghost@x.com", "password": "WrongPass1"}
    )
    r = await client.get("/api/v1/admin/audit-logs?status=FAILED", headers=h)
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert all(it["status"] == "FAILED" for it in items)
    assert any(it["action"] in ("LOGIN_FAILED", "LOGIN_LOCKED") for it in items)


# ---------- 单条详情 ----------

@pytest.mark.asyncio
async def test_get_audit_log_detail(client, superadmin_headers):
    h = superadmin_headers
    r = await client.get("/api/v1/admin/audit-logs?page_size=1", headers=h)
    assert r.status_code == 200
    log_id = r.json()["data"]["items"][0]["id"]

    detail = await client.get(f"/api/v1/admin/audit-logs/{log_id}", headers=h)
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert body["id"] == log_id


@pytest.mark.asyncio
async def test_get_audit_log_not_found(client, superadmin_headers):
    h = superadmin_headers
    r = await client.get("/api/v1/admin/audit-logs/99999999", headers=h)
    assert r.status_code == 404


# ---------- _options ----------

@pytest.mark.asyncio
async def test_options_returns_enums(client, superadmin_headers):
    h = superadmin_headers
    r = await client.get("/api/v1/admin/audit-logs/_options", headers=h)
    assert r.status_code == 200
    data = r.json()["data"]
    assert "auth" in data["resource_types"]
    assert "user" in data["resource_types"]
    assert "LOGIN_SUCCESS" in data["actions"]
    assert "PHONE_CHANGE" in data["actions"]
    assert data["statuses"] == ["SUCCESS", "FAILED"]


# ---------- GET 不写审计 ----------

@pytest.mark.asyncio
async def test_get_audit_does_not_write_audit(client, superadmin_headers, db_session):
    """对 audit-logs 接口的 GET 调用本身不应再产生新审计记录。"""
    from sqlalchemy import select, func
    from app.db.models.audit_log import AuditLog

    h = superadmin_headers
    before = (await db_session.execute(select(func.count(AuditLog.id)))).scalar_one()
    await client.get("/api/v1/admin/audit-logs?page_size=5", headers=h)
    await client.get("/api/v1/admin/audit-logs/_options", headers=h)
    after = (await db_session.execute(select(func.count(AuditLog.id)))).scalar_one()
    assert after == before, "GET /admin/audit-logs 不应写新审计"
