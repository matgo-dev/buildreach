"""系统告警接口接线:权限门(匿名 401 / 买家 403 / 内部账号 200)+ 故障态落到响应。"""
from __future__ import annotations

import pytest

from app.services import system_alerts
from app.services.system_alerts import TranslationHealth

URL = "/api/v1/operator/system-alerts"


@pytest.fixture(autouse=True)
def _reset_state():
    system_alerts.reset_for_tests()
    yield
    system_alerts.reset_for_tests()


@pytest.mark.asyncio
async def test_anonymous_401(client):
    r = await client.get(URL)
    assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_buyer_403(client):
    from tests.conftest import register_buyer_tz
    reg = await register_buyer_tz(client, phone="+255712340001")
    assert reg["response"].status_code == 200, reg["response"].text
    login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": reg["email"], "password": reg["password"]},
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    r = await client.get(URL, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_admin_sees_empty_then_outage(client, superadmin_headers):
    r = await client.get(URL, headers=superadmin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["items"] == []

    from datetime import datetime, timezone
    state = system_alerts.translation_state()
    state.down_since = datetime(2026, 10, 17, 3, 45, tzinfo=timezone.utc)
    state.last_error = "403 userRateLimitExceeded"

    r = await client.get(URL, headers=superadmin_headers)
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["kind"] == "translation_down"
    assert items[0]["detail"] == "403 userRateLimitExceeded"
    assert items[0]["since"].startswith("2026-10-17T03:45")
    assert isinstance(items[0]["pending_rows"], int)
