"""审计日志测试。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.models.audit_log import AuditLog


SUPER_EMAIL = settings.SUPER_ADMIN_EMAIL
SUPER_PASS = settings.SUPER_ADMIN_INITIAL_PASSWORD


async def _audit_count(db, **filters):
    stmt = select(AuditLog)
    for k, v in filters.items():
        stmt = stmt.where(getattr(AuditLog, k) == v)
    rows = (await db.execute(stmt)).scalars().all()
    return len(rows), rows


@pytest.mark.asyncio
async def test_login_success_audit(client, db_session):
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": SUPER_EMAIL, "password": SUPER_PASS},
    )
    assert r.status_code == 200
    n, rows = await _audit_count(db_session, action="LOGIN_SUCCESS")
    assert n >= 1
    assert all(row.trace_id for row in rows)


@pytest.mark.asyncio
async def test_login_failed_audit(client, db_session):
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "ghost@x.com", "password": "Wrong1234"},
    )
    assert r.status_code == 401
    n, _ = await _audit_count(db_session, action="LOGIN_FAILED")
    assert n >= 1


@pytest.mark.asyncio
async def test_login_locked_audit(client, db_session):
    for _ in range(5):
        await client.post(
            "/api/v1/auth/login",
            json={"identifier": "ghost@x.com", "password": "Wrong1234"},
        )
    n, _ = await _audit_count(db_session, action="LOGIN_LOCKED")
    assert n >= 1


def _make_test_image(w: int = 300, h: int = 300) -> bytes:
    """生成最小合法测试图片。"""
    from io import BytesIO
    from PIL import Image
    img = Image.new("RGB", (w, h), (128, 128, 128))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_register_audit(client, db_session):
    # 需要先获取一个有效的 L1 品类 code
    from sqlalchemy import text
    row = await db_session.execute(text("SELECT code FROM categories WHERE level=1 AND is_active=true LIMIT 1"))
    cat_code = row.scalar()
    assert cat_code is not None, "需要至少一个 L1 品类"

    img_bytes = _make_test_image()
    resp = await client.post(
        "/api/v1/auth/register/buyer",
        data={
            "phone": "+255712345678",
            "password": "Aa123456789!",
            "name": "Z",
            "company_name": "Test Shop",
            "address": "Dar es Salaam",
            "business_category_codes": cat_code,
        },
        files=[("storefront_images", ("shop.jpg", img_bytes, "image/jpeg"))],
    )
    n, rows = await _audit_count(db_session, action="REGISTER")
    assert n >= 1
    assert any(row.user_email == "+255712345678" for row in rows)


@pytest.mark.asyncio
async def test_create_internal_user_audit(client, superadmin_headers, db_session):
    await client.post(
        "/api/v1/admin/users",
        json={
            "email": "op@x.com",
            "name": "OP",
            "password": "Aa123456789",
            "role": "OPERATOR",
        },
        headers=superadmin_headers,
    )
    n_create, _ = await _audit_count(db_session, action="CREATE", resource_type="user")
    n_role, _ = await _audit_count(db_session, action="ROLE_ASSIGN")
    assert n_create >= 1
    assert n_role >= 1


@pytest.mark.asyncio
async def test_password_change_audit(client, db_session):
    from tests.conftest import register_buyer_tz
    result = await register_buyer_tz(client)
    token = result["response"].json()["data"]["access_token"]
    await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": result["password"], "new_password": "NewPass1234!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    n, _ = await _audit_count(db_session, action="PASSWORD_CHANGE")
    assert n >= 1


@pytest.mark.asyncio
async def test_get_request_not_audited(client, db_session):
    """GET 请求不应写审计日志。"""
    await client.get("/healthz")
    await client.get("/api/v1/test/all-roles")  # 未登录 → 401,也不写审计
    n, _ = await _audit_count(db_session, method="GET")
    assert n == 0


@pytest.mark.asyncio
async def test_x_trace_id_in_response_header(client):
    r = await client.get("/healthz")
    assert "X-Trace-Id" in r.headers
    assert len(r.headers["X-Trace-Id"]) > 0


@pytest.mark.asyncio
async def test_trace_id_propagates_to_audit(client, db_session, monkeypatch):
    """同一请求的 trace_id 应能在响应头和审计表里关联。"""
    monkeypatch.setattr(settings, "TRUST_INBOUND_TRACE_ID", True)
    trace = "fixed-trace-test-001"
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": SUPER_EMAIL, "password": SUPER_PASS},
        headers={"X-Trace-Id": trace},
    )
    assert r.status_code == 200
    assert r.headers["X-Trace-Id"] == trace
    n, rows = await _audit_count(db_session, action="LOGIN_SUCCESS", trace_id=trace)
    assert n >= 1
