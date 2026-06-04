"""scope 查表函数 + /api/v1/_debug/scope 调试接口测试。"""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.rbac.scope_config import Scope, get_scope


# ----- 查表函数单测 -----

def test_get_scope_buyer_project_is_org():
    assert get_scope(["BUYER"], "project") == Scope.ORG


def test_get_scope_supplier_order_is_own():
    assert get_scope(["SUPPLIER"], "order") == Scope.OWN


def test_get_scope_operator_supplier_is_all():
    assert get_scope(["OPERATOR"], "supplier") == Scope.ALL


def test_get_scope_admin_business_is_none():
    """ADMIN 对业务资源全部 NONE(Q25 + RBAC 规范 §4.3 / §8.6)。"""
    for r in ["supplier", "product", "project", "rfq", "order", "risk", "credit"]:
        assert get_scope(["ADMIN"], r) == Scope.NONE


def test_get_scope_supplier_credit_is_none():
    """SUPPLIER 信用评估:Δ5 定位变更后不持有 credit 权限点,scope=NONE。"""
    assert get_scope(["SUPPLIER"], "credit") == Scope.NONE


def test_get_scope_buyer_operator_credit_is_all():
    assert get_scope(["BUYER"], "credit") == Scope.ALL
    assert get_scope(["OPERATOR"], "credit") == Scope.ALL


def test_get_scope_admin_system_is_all():
    for r in ["user", "role", "permission", "system"]:
        assert get_scope(["ADMIN"], r) == Scope.ALL


def test_get_scope_unknown_resource_returns_none():
    assert get_scope(["BUYER"], "ghost_resource") == Scope.NONE


def test_get_scope_multi_role_picks_most_permissive():
    """多角色取最宽松(ALL > ORG > OWN > NONE)。"""
    assert get_scope(["BUYER", "OPERATOR"], "project") == Scope.ALL
    assert get_scope(["BUYER", "SUPPLIER"], "rfq") == Scope.ORG


# ----- 调试接口 -----

SUPER_EMAIL = settings.SUPER_ADMIN_EMAIL
SUPER_PASS = settings.SUPER_ADMIN_INITIAL_PASSWORD


async def _login(client, email, password):
    r = await client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def _buyer_token(client):
    await client.post(
        "/api/v1/auth/register/buyer",
        json={
            "email": "buyer.scope@x.com",
            "name": "B",
            "password": "Aa123456789",
            "company_name": "中建三局",
            "unified_social_credit_code": "91420100MA4KXXXX01",
        },
    )
    return await _login(client, "buyer.scope@x.com", "Aa123456789")


async def _supplier_token(client):
    await client.post(
        "/api/v1/auth/register/supplier",
        json={"email": "sup.scope@x.com", "name": "S", "phone": "13900139501",
              "password": "Aa123456789", "company_name": "S Co",
              "country_code": "CN", "registration_no": "91110000SC00000001",
              "language_preference": "zh-CN"},
    )
    return await _login(client, "sup.scope@x.com", "Aa123456789")


@pytest.mark.asyncio
async def test_debug_scope_requires_auth(client):
    r = await client.get("/api/v1/_debug/scope?resource=project")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_debug_scope_buyer_project_org(client):
    token = await _buyer_token(client)
    r = await client.get(
        "/api/v1/_debug/scope?resource=project",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["roles"] == ["BUYER"]
    assert d["resource"] == "project"
    assert d["permission_check"]["passed"] is True
    assert d["permission_check"]["required"] == "project:read"
    assert d["scope_resolved"] == "ORG"
    assert "buyer_organization_id" in d["would_apply_filter"]


@pytest.mark.asyncio
async def test_debug_scope_supplier_order_own(client):
    token = await _supplier_token(client)
    r = await client.get(
        "/api/v1/_debug/scope?resource=order",
        headers={"Authorization": f"Bearer {token}"},
    )
    d = r.json()["data"]
    assert d["scope_resolved"] == "OWN"
    assert d["permission_check"]["passed"] is True


@pytest.mark.asyncio
async def test_debug_scope_admin_project_none(client):
    """ADMIN 对业务资源 scope=NONE,permission_check.passed=False。"""
    token = await _login(client, SUPER_EMAIL, SUPER_PASS)
    r = await client.get(
        "/api/v1/_debug/scope?resource=project",
        headers={"Authorization": f"Bearer {token}"},
    )
    d = r.json()["data"]
    assert d["scope_resolved"] == "NONE"
    assert d["permission_check"]["passed"] is False


@pytest.mark.asyncio
async def test_debug_scope_unknown_resource(client):
    token = await _login(client, SUPER_EMAIL, SUPER_PASS)
    r = await client.get(
        "/api/v1/_debug/scope?resource=ghost",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_debug_matrix_returns_full_mapping(client):
    token = await _login(client, SUPER_EMAIL, SUPER_PASS)
    r = await client.get(
        "/api/v1/_debug/matrix",
        headers={"Authorization": f"Bearer {token}"},
    )
    d = r.json()["data"]
    # 16 资源 × 4 角色
    assert set(d["resources"].keys()) == {
        "supplier", "product", "country", "credit",
        "project", "purchase_list", "cart",
        "rfq", "quote", "order", "membership", "risk",
        "user", "role", "permission", "system",
    }
    assert set(d["role_resource_scope"].keys()) == {"BUYER", "SUPPLIER", "OPERATOR", "ADMIN"}
    # 抽查
    assert d["role_resource_scope"]["BUYER"]["project"] == "ORG"
    assert d["role_resource_scope"]["ADMIN"]["user"] == "ALL"
    assert d["role_resource_scope"]["ADMIN"]["project"] == "NONE"
    # 信用评估 scope:SUPPLIER=OWN、ADMIN=NONE、BUYER/OPERATOR=ALL(本工单)
    assert d["role_resource_scope"]["SUPPLIER"]["credit"] == "NONE"
    assert d["role_resource_scope"]["ADMIN"]["credit"] == "NONE"
    assert d["role_resource_scope"]["BUYER"]["credit"] == "ALL"
    assert d["role_resource_scope"]["OPERATOR"]["credit"] == "ALL"
