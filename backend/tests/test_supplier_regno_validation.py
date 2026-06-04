"""供应商注册号格式后端兜底校验(9 国全覆盖)。

前端正则可被绕过(直接调 API),后端 SupplierRegisterIn 必须兜底校验,
保证前后端一致。每个国家都有精确正则。
"""
from __future__ import annotations

import pytest


async def _register(client, country_code, regno, email, phone):
    return await client.post("/api/v1/auth/register/supplier", json={
        "email": email, "name": "S", "phone": phone, "password": "Aa123456789",
        "company_name": f"Co {email}", "country_code": country_code,
        "registration_no": regno, "language_preference": "en",
    })


# ---- KH: ^[0-9]{6,12}$ ----

async def test_kh_valid_digits_ok(client):
    r = await _register(client, "KH", "12345678", "kh.ok@x.com", "+85512345678")
    assert r.status_code == 200, r.text


async def test_kh_with_letters_rejected(client):
    r = await _register(client, "KH", "ABC12345", "kh.b1@x.com", "+85512345601")
    assert r.status_code == 422


async def test_kh_too_short_rejected(client):
    r = await _register(client, "KH", "12345", "kh.b2@x.com", "+85512345602")
    assert r.status_code == 422


async def test_kh_too_long_rejected(client):
    r = await _register(client, "KH", "1234567890123", "kh.b3@x.com", "+85512345603")
    assert r.status_code == 422


# ---- CN: ^[0-9A-Z]{18}$ ----

async def test_cn_valid_18_chars_ok(client):
    r = await _register(client, "CN", "91110000MA01ABCD01", "cn.ok@x.com", "13800138000")
    assert r.status_code == 200, r.text


async def test_cn_with_dashes_rejected(client):
    r = await _register(client, "CN", "SC-CN-XYZ-001", "cn.b1@x.com", "13800138088")
    assert r.status_code == 422


async def test_cn_too_short_rejected(client):
    r = await _register(client, "CN", "91110000", "cn.b2@x.com", "13800138089")
    assert r.status_code == 422


# ---- 参数化:各国合法/非法值 ----

@pytest.mark.parametrize("country,valid_regno", [
    ("PK", "ABCD1234"),      # 7-10 位字母数字
    ("MA", "123456789012345"),  # 15 位纯数字
    ("IQ", "12345678"),      # 6-10 位纯数字
    ("ID", "1234567890123"),  # 13 位纯数字
    ("MY", "123456789012"),  # 12 位纯数字
    ("SA", "1234567890"),    # 10 位纯数字
    ("AE", "ABC1234567"),    # 6-12 位字母数字
])
async def test_other_countries_valid_ok(client, country, valid_regno):
    email = f"{country.lower()}.ok@x.com"
    phone = f"+1555000{COUNTRIES.index(country):04d}"
    r = await _register(client, country, valid_regno, email, phone)
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("country,bad_regno", [
    ("PK", "AB"),            # 太短
    ("MA", "12345"),         # 不足 15 位
    ("IQ", "12345"),         # 不足 6 位
    ("ID", "123456"),        # 不足 13 位
    ("MY", "12345"),         # 不足 12 位
    ("SA", "12345"),         # 不足 10 位
    ("AE", "AB"),            # 太短
])
async def test_other_countries_bad_rejected(client, country, bad_regno):
    email = f"{country.lower()}.bad@x.com"
    phone = f"+1555001{COUNTRIES.index(country):04d}"
    r = await _register(client, country, bad_regno, email, phone)
    assert r.status_code == 422


COUNTRIES = ["PK", "MA", "IQ", "ID", "MY", "SA", "AE"]
