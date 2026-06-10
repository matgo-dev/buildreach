"""认证流程测试。"""
from __future__ import annotations

import pytest

from app.core.config import settings


BUYER_PAYLOAD = {
    "email": "zhang@cscec3b.com",
    "name": "张三",
    "phone": "13800138000",
    "password": "Aa123456789",
    # 与 seed 的中建三局 USC 一致 → 注册时加入该组织,不新建
    "company_name": "中建三局",
    "unified_social_credit_code": "91420100MA4KXXXX01",
}

SUPPLIER_PAYLOAD = {
    "email": "li@huajian.com",
    "name": "李四",
    "phone": "13800138001",
    "password": "Aa123456789",
    "company_name": "华建供应链有限公司",
    "country_code": "CN",
    "registration_no": "91110000XXXXXXXXXX",
    "language_preference": "zh-CN",
}


async def _login(client, email: str, password: str):
    return await client.post("/api/v1/auth/login", json={"identifier": email, "password": password})


@pytest.mark.asyncio
async def test_buyer_register_success(client):
    r = await client.post("/api/v1/auth/register/buyer", json=BUYER_PAYLOAD)
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["email"] == BUYER_PAYLOAD["email"]
    # 不应自动登录
    assert "access_token" not in (body.get("data") or {})


@pytest.mark.asyncio
async def test_buyer_register_duplicate_email(client):
    await client.post("/api/v1/auth/register/buyer", json=BUYER_PAYLOAD)
    r = await client.post("/api/v1/auth/register/buyer", json=BUYER_PAYLOAD)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_buyer_register_weak_password(client):
    bad = {**BUYER_PAYLOAD, "password": "abc"}
    r = await client.post("/api/v1/auth/register/buyer", json=bad)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_password_length_below_11_rejected(client):
    """密码 < 11 位被拒(PRD v1.4 Δ1:11-50 位)。"""
    bad = {**BUYER_PAYLOAD, "password": "Aa12345"}  # 7 位
    r = await client.post("/api/v1/auth/register/buyer", json=bad)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_password_3_categories_required(client):
    """密码长度合规但只 1 类字符 → 拒绝(PRD v1.4 Δ1:11-50 + 3 类)。"""
    # 11 位但只有小写一类
    bad1 = {**BUYER_PAYLOAD, "password": "aaaaaaaaaaa"}
    r1 = await client.post("/api/v1/auth/register/buyer", json=bad1)
    assert r1.status_code == 422, r1.text

    # 11 位但只有 2 类(小写 + 数字)
    bad2 = {**BUYER_PAYLOAD, "email": "x2@y.com", "password": "abcdefg1234"}
    r2 = await client.post("/api/v1/auth/register/buyer", json=bad2)
    assert r2.status_code == 422, r2.text


@pytest.mark.asyncio
async def test_password_3_categories_passes(client):
    """密码 11 位 + 3 类(数字 + 大写 + 小写)→ 通过。"""
    ok = {**BUYER_PAYLOAD, "email": "ok@y.com", "password": "Aa123456789"}
    r = await client.post("/api/v1/auth/register/buyer", json=ok)
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_supplier_register_success(client, db_session):
    r = await client.post("/api/v1/auth/register/supplier", json=SUPPLIER_PAYLOAD)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["email"] == SUPPLIER_PAYLOAD["email"]

    # 断言 language_preference 落库正确
    from sqlalchemy import select
    from app.db.models.user import User
    row = await db_session.execute(
        select(User).where(User.email == SUPPLIER_PAYLOAD["email"])
    )
    user = row.scalar_one()
    assert user.language_preference == SUPPLIER_PAYLOAD["language_preference"]


@pytest.mark.asyncio
async def test_supplier_register_duplicate_per_country(client, db_session):
    """(country_code, registration_no) 复合唯一:
    - 同 country + 同 reg_no → 409 + 标准化文案
    - 不同 country + 同 reg_no → 200(撞号被允许)
    """
    # 首次注册成功
    r1 = await client.post("/api/v1/auth/register/supplier", json=SUPPLIER_PAYLOAD)
    assert r1.status_code == 200

    # 同 country + 同 reg_no → 409
    dup_same_country = {
        **SUPPLIER_PAYLOAD,
        "email": "another@huajian.com",
        "phone": "13900139500",
    }
    r2 = await client.post("/api/v1/auth/register/supplier", json=dup_same_country)
    assert r2.status_code == 409
    body = r2.json()
    assert body["code"] == 40901
    # 单错误 message 仍是注册号重复文案
    assert body["message"] == (
        "当前企业已在平台注册。如需加入,请联系您所在企业的平台管理员添加账号。"
    )
    # v1.5 Δ3:单错误也返回 data.errors 数组(长度 1)
    assert body["data"]["errors"] == [{
        "field": "registration_no",
        "code": 40901,
        "message": (
            "当前企业已在平台注册。如需加入,请联系您所在企业的平台管理员添加账号。"
        ),
    }]
    # 不暴露任何已存在数据(message 里不能出现公司名等)
    assert "华建" not in body["message"]
    assert "li@huajian.com" not in body["message"]

    # 早 raise:不残留新 user 行
    from sqlalchemy import select
    from app.db.models.user import User
    row = await db_session.execute(
        select(User).where(User.email == "another@huajian.com")
    )
    assert row.scalar_one_or_none() is None

    # 不同 country + 同 reg_no 字符串值 → 应该 200(复合唯一关键测试)
    # 注:MY 要求 12 位纯数字,CN 要求 18 位字母数字,不能直接复用同一字符串
    # 改用柬埔寨(KH)测试复合唯一:KH 正则 ^[0-9]{6,12}$ 能兼容纯数字子串
    other_country = {
        **SUPPLIER_PAYLOAD,
        "email": "ahmad@cambodia.com",
        "phone": "85512345678",
        "country_code": "KH",
        "registration_no": "911100001234",  # 12 位纯数字,KH 合法
        "language_preference": "km-KH",
        "company_name": "Cambodia Supply Co",
    }
    r3 = await client.post("/api/v1/auth/register/supplier", json=other_country)
    assert r3.status_code == 200, r3.text


# ---- v1.5 Δ3:一次返回所有错误 ----

@pytest.mark.asyncio
async def test_supplier_register_duplicate_email_only(client):
    """已存在邮箱 + 新手机号 + 新 (country, reg_no) → code=40902,errors 长度 1。"""
    r1 = await client.post("/api/v1/auth/register/supplier", json=SUPPLIER_PAYLOAD)
    assert r1.status_code == 200

    payload = {
        **SUPPLIER_PAYLOAD,
        # email 重
        "phone": "60111222333",  # 新
        "country_code": "MY",  # 切国家
        "registration_no": "999888777666",  # 新
        "language_preference": "ms-MY",
        "company_name": "Another Co",
    }
    r2 = await client.post("/api/v1/auth/register/supplier", json=payload)
    assert r2.status_code == 409
    body = r2.json()
    assert body["code"] == 40902
    assert body["message"] == "该邮箱已注册,请直接登录或更换邮箱"
    assert body["data"]["errors"] == [{
        "field": "email",
        "code": 40902,
        "message": "该邮箱已注册,请直接登录或更换邮箱",
    }]


@pytest.mark.asyncio
async def test_supplier_register_duplicate_phone_only(client):
    """已存在手机号 + 新邮箱 + 新 (country, reg_no) → code=40903,errors 长度 1。"""
    r1 = await client.post("/api/v1/auth/register/supplier", json=SUPPLIER_PAYLOAD)
    assert r1.status_code == 200

    payload = {
        **SUPPLIER_PAYLOAD,
        "email": "fresh@huajian.com",
        # phone 重
        "country_code": "MY",
        "registration_no": "888777666555",
        "language_preference": "ms-MY",
        "company_name": "Another Co",
    }
    r2 = await client.post("/api/v1/auth/register/supplier", json=payload)
    assert r2.status_code == 409
    body = r2.json()
    assert body["code"] == 40903
    assert body["message"] == "该手机号已注册,请直接登录或更换手机号"
    assert len(body["data"]["errors"]) == 1
    assert body["data"]["errors"][0]["field"] == "phone"
    assert body["data"]["errors"][0]["code"] == 40903


@pytest.mark.asyncio
async def test_supplier_register_duplicate_email_and_phone(client):
    """邮箱 + 手机号都重,但 (country, reg_no) 新 → code=40902(40901 不在,40902 优先级最高),errors 长度 2。"""
    r1 = await client.post("/api/v1/auth/register/supplier", json=SUPPLIER_PAYLOAD)
    assert r1.status_code == 200

    payload = {
        **SUPPLIER_PAYLOAD,
        # email 重 + phone 重
        "country_code": "MY",
        "registration_no": "777666555444",
        "language_preference": "ms-MY",
        "company_name": "Another Co",
    }
    r2 = await client.post("/api/v1/auth/register/supplier", json=payload)
    assert r2.status_code == 409
    body = r2.json()
    assert body["code"] == 40902  # 40901 不在,40902 优先于 40903
    assert body["message"] == "请修正以下问题"
    errs = body["data"]["errors"]
    assert len(errs) == 2
    fields = {e["field"] for e in errs}
    codes = {e["code"] for e in errs}
    assert fields == {"email", "phone"}
    assert codes == {40902, 40903}


@pytest.mark.asyncio
async def test_supplier_register_duplicate_all_three(client):
    """三者全重 → code=40901(优先级最高),errors 长度 3。"""
    r1 = await client.post("/api/v1/auth/register/supplier", json=SUPPLIER_PAYLOAD)
    assert r1.status_code == 200

    # 同 email + 同 phone + 同 (country, reg_no)
    r2 = await client.post("/api/v1/auth/register/supplier", json=SUPPLIER_PAYLOAD)
    assert r2.status_code == 409
    body = r2.json()
    assert body["code"] == 40901
    assert body["message"] == "请修正以下问题"
    errs = body["data"]["errors"]
    assert len(errs) == 3
    fields = {e["field"] for e in errs}
    codes = {e["code"] for e in errs}
    assert fields == {"registration_no", "email", "phone"}
    assert codes == {40901, 40902, 40903}


@pytest.mark.asyncio
async def test_supplier_register_response_structure(client):
    """单错误也必须以数组形式返回 data.errors,前端可统一按数组解析。"""
    r1 = await client.post("/api/v1/auth/register/supplier", json=SUPPLIER_PAYLOAD)
    assert r1.status_code == 200

    # 仅邮箱重 → 单错误
    payload = {
        **SUPPLIER_PAYLOAD,
        "phone": "13900139999",
        "country_code": "MY",
        "registration_no": "666555444333",
        "language_preference": "ms-MY",
        "company_name": "Another Co",
    }
    r2 = await client.post("/api/v1/auth/register/supplier", json=payload)
    body = r2.json()
    assert isinstance(body["data"]["errors"], list)
    assert len(body["data"]["errors"]) == 1


@pytest.mark.asyncio
async def test_supplier_register_invalid_country_code(client):
    bad = {**SUPPLIER_PAYLOAD, "country_code": "XX"}
    r = await client.post("/api/v1/auth/register/supplier", json=bad)
    assert r.status_code == 409  # MultipleValidationError → 409


@pytest.mark.asyncio
async def test_supplier_register_missing_language_preference(client):
    bad = {**SUPPLIER_PAYLOAD}
    bad.pop("language_preference")
    r = await client.post("/api/v1/auth/register/supplier", json=bad)
    assert r.status_code == 409  # MultipleValidationError → 409


@pytest.mark.asyncio
async def test_supplier_register_no_username_field(client):
    """payload 多带 username 字段应被 Pydantic extra_forbidden 拦截 → 409。"""
    bad = {**SUPPLIER_PAYLOAD, "username": "ghost"}
    r = await client.post("/api/v1/auth/register/supplier", json=bad)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_login_buyer_success(client):
    await client.post("/api/v1/auth/register/buyer", json=BUYER_PAYLOAD)
    r = await _login(client, BUYER_PAYLOAD["email"], BUYER_PAYLOAD["password"])
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["access_token"]
    assert data["token_type"] == "Bearer"
    # 不返回 permissions
    assert "permissions" not in data


@pytest.mark.asyncio
async def test_login_supplier_success(client):
    await client.post("/api/v1/auth/register/supplier", json=SUPPLIER_PAYLOAD)
    r = await _login(client, SUPPLIER_PAYLOAD["email"], SUPPLIER_PAYLOAD["password"])
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_login_super_admin_success(client):
    r = await _login(
        client, settings.SUPER_ADMIN_EMAIL, settings.SUPER_ADMIN_INITIAL_PASSWORD
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/v1/auth/register/buyer", json=BUYER_PAYLOAD)
    r = await _login(client, BUYER_PAYLOAD["email"], "WrongPass123")
    assert r.status_code == 401
    assert r.json()["code"] == 40001


@pytest.mark.asyncio
async def test_login_unknown_email(client):
    r = await _login(client, "ghost@nowhere.com", "Aa123456789")
    assert r.status_code == 401
    assert r.json()["code"] == 40001


@pytest.mark.asyncio
async def test_login_rate_limit_locks_after_5_failures(client):
    await client.post("/api/v1/auth/register/buyer", json=BUYER_PAYLOAD)
    for _ in range(4):
        r = await _login(client, BUYER_PAYLOAD["email"], "WrongPass123")
        assert r.status_code == 401
    # 第 5 次会触发锁定,直接 429
    r5 = await _login(client, BUYER_PAYLOAD["email"], "WrongPass123")
    assert r5.status_code == 429
    # 锁定中即使密码正确也 429
    r6 = await _login(client, BUYER_PAYLOAD["email"], BUYER_PAYLOAD["password"])
    assert r6.status_code == 429


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_full_profile(client):
    await client.post("/api/v1/auth/register/buyer", json=BUYER_PAYLOAD)
    login = await _login(client, BUYER_PAYLOAD["email"], BUYER_PAYLOAD["password"])
    token = login.json()["data"]["access_token"]
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["email"] == BUYER_PAYLOAD["email"]
    assert "BUYER" in data["roles"]
    assert "rfq:read" in data["permissions"]  # BUYER 有询价读权限(单边模型)
    assert data["organization"]["type"] == "BUYER_ORG"
    assert data["organization"]["name"] == "中建三局"
    # PRD v1.3 §5.4:/auth/me 必须返回 organization.status
    assert "status" in data["organization"]


@pytest.mark.asyncio
async def test_me_supplier_organization_status_is_draft(client):
    """SUPPLIER 注册后 /me 返回 organization.status == 'DRAFT',前端 banner 判定基础。"""
    await client.post("/api/v1/auth/register/supplier", json=SUPPLIER_PAYLOAD)
    login = await _login(client, SUPPLIER_PAYLOAD["email"], SUPPLIER_PAYLOAD["password"])
    token = login.json()["data"]["access_token"]
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["organization"]["type"] == "SUPPLIER_ORG"
    assert data["organization"]["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_change_password_flow(client):
    await client.post("/api/v1/auth/register/buyer", json=BUYER_PAYLOAD)
    login = await _login(client, BUYER_PAYLOAD["email"], BUYER_PAYLOAD["password"])
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 旧密码错
    r = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "WrongOld1", "new_password": "NewPass1234"},
        headers=headers,
    )
    assert r.status_code == 401

    # 新密码不合规
    r = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": BUYER_PAYLOAD["password"], "new_password": "abc"},
        headers=headers,
    )
    assert r.status_code == 422

    # 成功
    r = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": BUYER_PAYLOAD["password"], "new_password": "NewPass1234"},
        headers=headers,
    )
    assert r.status_code == 200

    # 新密码可登录
    r = await _login(client, BUYER_PAYLOAD["email"], "NewPass1234")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_register_with_username_and_login_by_username(client):
    """注册时填 username,登录支持邮箱 或 username。"""
    payload = {**BUYER_PAYLOAD, "username": "zhang_san"}
    r = await client.post("/api/v1/auth/register/buyer", json=payload)
    assert r.status_code == 200

    # 用 username 登录
    r2 = await _login(client, "zhang_san", BUYER_PAYLOAD["password"])
    assert r2.status_code == 200, r2.text
    # 用 email 仍可登录
    r3 = await _login(client, BUYER_PAYLOAD["email"], BUYER_PAYLOAD["password"])
    assert r3.status_code == 200

    # me 返回 username
    token = r2.json()["data"]["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["data"]["username"] == "zhang_san"


@pytest.mark.asyncio
async def test_register_duplicate_username(client):
    p1 = {**BUYER_PAYLOAD, "username": "dup_user"}
    p2 = {**BUYER_PAYLOAD, "email": "other@cscec3b.com", "username": "dup_user"}
    r1 = await client.post("/api/v1/auth/register/buyer", json=p1)
    assert r1.status_code == 200
    r2 = await client.post("/api/v1/auth/register/buyer", json=p2)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_register_invalid_username(client):
    bad = {**BUYER_PAYLOAD, "username": "x"}  # 太短
    r = await client.post("/api/v1/auth/register/buyer", json=bad)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_login_unknown_username(client):
    r = await _login(client, "no_such_user", "Aa123456789")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_super_admin_must_change_password(client):
    r = await _login(
        client, settings.SUPER_ADMIN_EMAIL, settings.SUPER_ADMIN_INITIAL_PASSWORD
    )
    token = r.json()["data"]["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["data"]["must_change_password"] is True
