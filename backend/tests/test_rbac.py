"""RBAC 测试。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.models.role import Role
from app.db.models.role_permission import RolePermission
from app.rbac.constants import Permissions
from app.rbac.permissions_config import ROLE_PERMISSIONS
from app.rbac.sync import sync_rbac

SUPER_PASS = settings.SUPER_ADMIN_INITIAL_PASSWORD
SUPER_EMAIL = settings.SUPER_ADMIN_EMAIL


async def _login(client, email: str, password: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def _register_buyer(client, email="buyer1@cscec3b.com"):
    from tests.conftest import register_buyer_tz
    result = await register_buyer_tz(client, email=email)
    assert result["response"].status_code == 200, result["response"].text
    # 返回 phone 作为 identifier（用于登录）
    return result["phone"], result["password"]


async def _register_supplier(client, email="supplier1@huajian.com", license_no="91110000LIC0000001"):
    payload = {
        "email": email,
        "name": "Supplier 1",
        # 与 BUYER fixture(13800138000)区分,避免撞 phone UNIQUE
        "phone": "13900139000",
        "password": "Aa123456789",
        "company_name": "Huajian Co",
        "country_code": "CN",
        "registration_no": license_no,
        "language_preference": "zh-CN",
    }
    r = await client.post("/api/v1/auth/register/supplier", json=payload)
    assert r.status_code == 200, r.text
    return email, "Aa123456789"


async def _create_operator_via_super_admin(client, superadmin_headers, email="op1@platform.com"):
    r = await client.post(
        "/api/v1/admin/users",
        json={
            "email": email,
            "name": "OP 1",
            "password": "Aa123456789",
            "role": "OPERATOR",
            "must_change_password": False,
        },
        headers=superadmin_headers,
    )
    assert r.status_code == 200, r.text
    return email, "Aa123456789"


@pytest.mark.asyncio
async def test_buyer_can_access_buyer_only(client):
    email, pwd = await _register_buyer(client)
    token = await _login(client, email, pwd)
    r = await client.get("/api/v1/test/buyer-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_buyer_cannot_access_supplier_only(client):
    email, pwd = await _register_buyer(client)
    token = await _login(client, email, pwd)
    r = await client.get("/api/v1/test/supplier-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_supplier_isolation(client):
    email, pwd = await _register_supplier(client)
    token = await _login(client, email, pwd)
    r = await client.get("/api/v1/test/supplier-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    r = await client.get("/api/v1/test/buyer-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_super_admin_can_access_admin_only(client, superadmin_headers):
    r = await client.get("/api/v1/test/admin-only", headers=superadmin_headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_operator_can_access_operator_only(client, superadmin_headers):
    email, pwd = await _create_operator_via_super_admin(client, superadmin_headers)
    token = await _login(client, email, pwd)
    r = await client.get("/api/v1/test/operator-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    r = await client.get("/api/v1/test/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_create_buyer_role_rejected(client, superadmin_headers):
    """POST /admin/users 不应能创建 BUYER/SUPPLIER。"""
    r = await client.post(
        "/api/v1/admin/users",
        json={
            "email": "fakebuyer@x.com",
            "name": "X",
            "password": "Aa123456789",
            "role": "BUYER",
            "must_change_password": False,
        },
        headers=superadmin_headers,
    )
    assert r.status_code == 422  # pydantic Literal 校验失败


@pytest.mark.asyncio
async def test_non_admin_cannot_create_user(client):
    b_email, b_pwd = await _register_buyer(client)
    token = await _login(client, b_email, b_pwd)
    r = await client.post(
        "/api/v1/admin/users",
        json={
            "email": "x@x.com",
            "name": "X",
            "password": "Aa123456789",
            "role": "OPERATOR",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_rbac_sync_restores_deleted_role_permission(client, db_session):
    """删除一条 role_permission 后重跑同步,应自动恢复。"""
    # 找一条 ADMIN-AUDIT_LOG_READ 关联,删掉
    admin = (await db_session.execute(select(Role).where(Role.code == "ADMIN"))).scalar_one()
    before = (await db_session.execute(
        select(RolePermission).where(RolePermission.role_id == admin.id)
    )).scalars().all()
    assert len(before) == len(ROLE_PERMISSIONS["ADMIN"])

    target = before[0]
    await db_session.delete(target)
    await db_session.commit()

    after_delete = (await db_session.execute(
        select(RolePermission).where(RolePermission.role_id == admin.id)
    )).scalars().all()
    assert len(after_delete) == len(ROLE_PERMISSIONS["ADMIN"]) - 1

    # 重跑同步
    await sync_rbac(db_session)
    restored = (await db_session.execute(
        select(RolePermission).where(RolePermission.role_id == admin.id)
    )).scalars().all()
    assert len(restored) == len(ROLE_PERMISSIONS["ADMIN"])


@pytest.mark.asyncio
async def test_me_permissions_match_config(client, superadmin_headers):
    """OPERATOR 的 permissions 应严格匹配配置。"""
    email, pwd = await _create_operator_via_super_admin(client, superadmin_headers)
    token = await _login(client, email, pwd)
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    perms = set(me.json()["data"]["permissions"])
    assert perms == set(ROLE_PERMISSIONS["OPERATOR"])
    assert Permissions.USER_MANAGE not in perms  # OPERATOR 无系统权限


@pytest.mark.asyncio
async def test_business_permissions_isolated_per_role(client):
    """业务权限点严格隔离(v3 §3)。"""
    # BUYER
    b_email, b_pwd = await _register_buyer(client)
    b_token = await _login(client, b_email, b_pwd)
    b_perms = set((await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {b_token}"}
    )).json()["data"]["permissions"])
    # BUYER 应有(采购流程 + 公开池只读,单边模型:无 project/purchase_list)
    assert Permissions.RFQ_CREATE in b_perms
    assert Permissions.RFQ_CANCEL in b_perms
    assert Permissions.RFQ_DECIDE in b_perms
    assert Permissions.CART_WRITE in b_perms
    assert Permissions.SUPPLIER_READ in b_perms
    assert Permissions.PRODUCT_READ in b_perms
    # BUYER 不应有
    assert Permissions.SUPPLIER_WRITE not in b_perms
    assert Permissions.PRODUCT_WRITE not in b_perms
    assert Permissions.SUPPLIER_APPROVE not in b_perms
    assert Permissions.RFQ_RESPOND not in b_perms
    assert Permissions.QUOTE_WRITE not in b_perms
    assert Permissions.MEMBERSHIP_READ not in b_perms
    assert Permissions.RISK_READ not in b_perms
    assert Permissions.SYSTEM_CONFIG not in b_perms
    assert Permissions.USER_MANAGE not in b_perms

    # SUPPLIER
    s_email, s_pwd = await _register_supplier(client)
    s_token = await _login(client, s_email, s_pwd)
    s_perms = set((await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {s_token}"}
    )).json()["data"]["permissions"])
    # SUPPLIER 应有
    assert Permissions.SUPPLIER_WRITE in s_perms
    assert Permissions.PRODUCT_WRITE in s_perms
    assert Permissions.ORDER_CHECKIN in s_perms
    assert Permissions.MEMBERSHIP_WRITE in s_perms
    # SUPPLIER 不应有(单边模型:无 rfq/quote 权限)
    assert Permissions.RFQ_READ not in s_perms
    assert Permissions.RFQ_CANCEL not in s_perms
    assert Permissions.RFQ_DECIDE not in s_perms
    assert Permissions.RFQ_RESPOND not in s_perms
    assert Permissions.QUOTE_READ not in s_perms
    assert Permissions.QUOTE_WRITE not in s_perms
    assert Permissions.CART_READ not in s_perms
    assert Permissions.RFQ_CREATE not in s_perms
    assert Permissions.SUPPLIER_APPROVE not in s_perms
    assert Permissions.RISK_READ not in s_perms
    assert Permissions.SYSTEM_CONFIG not in s_perms


@pytest.mark.asyncio
async def test_admin_has_system_only_no_business(client):
    """ADMIN 严格不触业务数据(Q25 / v3 §3.1):仅 user/role/permission/system。"""
    token = await _login(client, SUPER_EMAIL, SUPER_PASS)
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    perms = set(me.json()["data"]["permissions"])
    # 系统权限应有
    assert Permissions.USER_MANAGE in perms
    assert Permissions.ROLE_MANAGE in perms
    assert Permissions.PERMISSION_MANAGE in perms
    assert Permissions.SYSTEM_CONFIG in perms
    assert Permissions.SYSTEM_AUDIT in perms
    # 业务权限点全部不应有
    for p in [
        Permissions.SUPPLIER_READ, Permissions.PRODUCT_READ, Permissions.COUNTRY_READ,
        Permissions.CART_READ,
        Permissions.RFQ_READ, Permissions.QUOTE_READ, Permissions.ORDER_READ,
        Permissions.MEMBERSHIP_READ, Permissions.RISK_READ,
        Permissions.SUPPLIER_APPROVE, Permissions.PRODUCT_APPROVE, Permissions.COUNTRY_WRITE,
    ]:
        assert p not in perms, f"ADMIN 不应有业务权限 {p}"


@pytest.mark.asyncio
async def test_operator_has_business_no_system(client, superadmin_headers):
    """OPERATOR 业务全量 + 审核,不触系统。"""
    email, pwd = await _create_operator_via_super_admin(client, superadmin_headers)
    token = await _login(client, email, pwd)
    perms = set((await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )).json()["data"]["permissions"])
    # 业务应有(单边模型:运营代客询价 + 回填报价)
    assert Permissions.SUPPLIER_APPROVE in perms
    assert Permissions.PRODUCT_APPROVE in perms
    assert Permissions.COUNTRY_WRITE in perms
    assert Permissions.RISK_READ in perms
    assert Permissions.RFQ_CREATE in perms
    assert Permissions.RFQ_CANCEL in perms
    assert Permissions.RFQ_DECIDE in perms
    assert Permissions.QUOTE_WRITE in perms
    # 系统权限不应有
    for p in [Permissions.USER_MANAGE, Permissions.ROLE_MANAGE,
              Permissions.PERMISSION_MANAGE, Permissions.SYSTEM_CONFIG, Permissions.SYSTEM_AUDIT]:
        assert p not in perms, f"OPERATOR 不应有系统权限 {p}"
