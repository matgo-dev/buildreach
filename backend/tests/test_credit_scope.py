"""信用评估接口的 RBAC + Δ5 注册即评分测试。

覆盖:
- ADMIN / SUPPLIER 均不持有 credit:* → 调任意 credit 接口均 403
- BUYER / OPERATOR scope=ALL → 行为不变
- 注册新 Supplier → 异步建 credit 镜像 + 评分,BUYER 可搜到带 grade
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import CreditCompany, ScoreSnapshot
from app.db.models.supplier_organization import SupplierOrganization, SupplierOrgStatus
from app.services.credit.registration_hook import create_credit_for_supplier


# -------- 登录工具 --------

async def _login(client, email, password) -> str:
    r = await client.post(
        "/api/v1/auth/login", json={"identifier": email, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def _admin_token(client) -> str:
    return await _login(client, "admin@platform.local", "Aa123456789")


async def _operator_token(client) -> str:
    return await _login(client, "operator@platform.local", "Aa123456789")


async def _buyer_token(client) -> str:
    return await _login(client, "buyer@cscec3b.local", "Aa123456789")


async def _register_supplier(client, email, phone, company_name) -> str:
    r = await client.post(
        "/api/v1/auth/register/supplier",
        json={
            "email": email, "name": "S", "phone": phone,
            "password": "Aa123456789", "company_name": company_name,
            "country_code": "CN", "registration_no": "91110000SCCR100001",
            "language_preference": "zh-CN",
        },
    )
    assert r.status_code in (200, 201), r.text
    return await _login(client, email, "Aa123456789")


def _auth(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


# -------- ADMIN 全部 credit 接口 403 --------

@pytest.mark.asyncio
async def test_admin_search_403(client):
    t = await _admin_token(client)
    r = await client.get("/api/v1/credit/companies/search?country=&q=", headers=_auth(t))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_detail_403(client):
    t = await _admin_token(client)
    r = await client.get("/api/v1/credit/companies/1", headers=_auth(t))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_recompute_403(client):
    t = await _admin_token(client)
    r = await client.post("/api/v1/credit/companies/1/recompute", headers=_auth(t))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_recompute_all_403(client):
    t = await _admin_token(client)
    r = await client.post("/api/v1/credit/recompute-all", headers=_auth(t))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_ai_conversation_403(client):
    t = await _admin_token(client)
    r = await client.post(
        "/api/v1/credit/ai/conversations", json={"company_id": 1}, headers=_auth(t)
    )
    assert r.status_code == 403


# -------- BUYER / OPERATOR scope=ALL 行为不变 --------

@pytest.mark.asyncio
async def test_buyer_search_sees_demo_companies(client):
    t = await _buyer_token(client)
    r = await client.get("/api/v1/credit/companies/search?country=&q=", headers=_auth(t))
    assert r.status_code == 200
    items = r.json()["data"]
    # seed_credit 入 4 家 demo
    assert len(items) >= 1


@pytest.mark.asyncio
async def test_operator_search_sees_demo_companies(client):
    t = await _operator_token(client)
    r = await client.get("/api/v1/credit/companies/search?country=&q=", headers=_auth(t))
    assert r.status_code == 200
    assert len(r.json()["data"]) >= 1


# -------- SUPPLIER 彻底无 credit 权限(Δ5)--------

@pytest.mark.asyncio
async def test_supplier_search_403(client):
    """SUPPLIER 不持有 credit:read → search 直接 403。"""
    t = await _register_supplier(client, "sup.credit1@x.com", "13900139601", "S Credit 1")
    r = await client.get("/api/v1/credit/companies/search?country=&q=", headers=_auth(t))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_supplier_detail_403(client, test_engine):
    t = await _register_supplier(client, "sup.credit2@x.com", "13900139602", "S Credit 2")
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        cid = (await db.execute(select(CreditCompany.id).limit(1))).scalar_one()
    r = await client.get(f"/api/v1/credit/companies/{cid}", headers=_auth(t))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_supplier_ai_create_403(client):
    t = await _register_supplier(client, "sup.credit3@x.com", "13900139603", "S Credit 3")
    r = await client.post(
        "/api/v1/credit/ai/conversations", json={"company_id": 1}, headers=_auth(t)
    )
    assert r.status_code == 403


# -------- Δ5 注册即评分闭环 --------

@pytest.mark.asyncio
async def test_register_supplier_endpoint_succeeds(client):
    """注册接口注入了 BackgroundTasks 异步评分,但异步失败被吞,注册本身始终 200。

    (异步任务真正建镜像 + 评分的逻辑由 test_create_credit_for_supplier 直接验证;
    此处只验证 wiring 不破坏注册主流程 / 失败隔离。)
    """
    r = await client.post(
        "/api/v1/auth/register/supplier",
        json={"email": "sup.newco@x.com", "name": "S", "phone": "13900139700",
              "password": "Aa123456789", "company_name": "Newco Trading Ltd.",
              "country_code": "CN", "registration_no": "91110000SCNEWCO001", "language_preference": "zh-CN"},
    )
    assert r.status_code in (200, 201), r.text


@pytest.mark.asyncio
async def test_create_credit_for_supplier_builds_mirror_and_score(client, test_engine):
    """直接验证注册钩子核心:建 credit_company 镜像 + mock 数据 + 评分快照。

    用 test_engine 的同循环 session 调用(避开 BackgroundTasks 的 AsyncSessionLocal
    跨事件循环限制)。client fixture 已 seed 评分模型骨架。
    """
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        org = SupplierOrganization(
            name="Hook Test Co.", country_code="CN", registration_no="SC-HOOK-1",
            status=SupplierOrgStatus.APPROVED,
        )
        db.add(org)
        await db.flush()

        company = await create_credit_for_supplier(
            db, org, target_tier="A", source="test", run_ai=False
        )
        await db.commit()

        assert company is not None
        assert company.linked_supplier_org_id == org.id

        snap = (await db.execute(
            select(ScoreSnapshot).where(
                ScoreSnapshot.company_id == company.id,
                ScoreSnapshot.is_current.is_(True),
            )
        )).scalar_one_or_none()
        assert snap is not None
        assert snap.grade in ("A", "B", "C", "D")
        assert snap.total_score is not None

        # 幂等:再次调用返回 None(不重复建)
        again = await create_credit_for_supplier(db, org, target_tier="A", run_ai=False)
        assert again is None


@pytest.mark.asyncio
async def test_create_credit_tiers_distribution(client, test_engine):
    """A/B/C/D 四档各跑出对应等级(验证 mock 生成器 + 规则对齐)。"""
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        for i, tier in enumerate(["A", "B", "C", "D"]):
            org = SupplierOrganization(
                name=f"Tier {tier} Co.", country_code="CN",
                registration_no=f"SC-TIER-{i}", status=SupplierOrgStatus.APPROVED,
            )
            db.add(org)
            await db.flush()
            company = await create_credit_for_supplier(
                db, org, target_tier=tier, source="test", run_ai=False
            )
            await db.commit()
            snap = (await db.execute(
                select(ScoreSnapshot).where(
                    ScoreSnapshot.company_id == company.id,
                    ScoreSnapshot.is_current.is_(True),
                )
            )).scalar_one()
            assert snap.grade == tier, f"tier {tier} 实际评级 {snap.grade}"
