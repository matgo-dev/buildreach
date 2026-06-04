"""抓取失败兜底(Δ7 §4.6)。维度级隔离 + run.status 准确 + 失败仍评分(missing 路径)。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    CreditCompany,
    CreditCompanyBasicData,
    CreditCompanyCertification,
    ScoreSnapshot,
)
from app.services.credit.harvester.harvest_task import run_harvest_for_company
from tests._harvest_fakes import FakeHarvester, make_result

FULL_BASIC = {
    "established_date": "2008-04-15", "registered_capital": "USD 1",
    "business_scope": "x", "legal_representative": "y", "shareholders": "z",
    "status_text": "normal", "address": "PP", "website": "https://x",
}


async def _new_kh(db, regno) -> int:
    c = CreditCompany(name="Fail Co", country_code="KH", registration_no=regno)
    db.add(c)
    await db.flush()
    return c.id


async def test_all_dimensions_failed_run_failed_but_scores(client, test_engine):
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        cid = await _new_kh(db, "KHF1")
        fake = FakeHarvester(
            basic=make_result("failed", "missing", {}, error="llm: timeout"),
            finance=make_result("failed", "missing", {}, error="tavily: 429"),
            legal=make_result("failed", "missing", {}, error="schema"),
            qual=make_result("failed", "missing", {}, error="llm: down"),
        )
        run = await run_harvest_for_company(db, cid, "manual", harvester=fake)
        await db.commit()

        assert run.status == "failed"
        assert run.error_detail  # 汇总各维度错误
        # 失败维度不落快照
        basic = (await db.execute(
            select(CreditCompanyBasicData).where(CreditCompanyBasicData.company_id == cid)
        )).scalars().all()
        assert len(basic) == 0
        # 但评分仍跑(走 missing 降级路径)→ 快照存在
        snap = (await db.execute(
            select(ScoreSnapshot).where(
                ScoreSnapshot.company_id == cid, ScoreSnapshot.is_current.is_(True)
            )
        )).scalar_one_or_none()
        assert snap is not None


async def test_partial_failure_run_partial_succeeded(client, test_engine):
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        cid = await _new_kh(db, "KHF2")
        fake = FakeHarvester(
            basic=make_result("ok", "public", FULL_BASIC),
            finance=make_result("failed", "missing", {}, error="tavily: timeout"),
            legal=make_result("missing", "missing", {}),
            qual=make_result("failed", "missing", {}, error="llm: down"),
        )
        run = await run_harvest_for_company(db, cid, "manual", harvester=fake)
        await db.commit()

        assert run.status == "partial_succeeded"
        assert run.dimensions_status["basic"]["status"] == "ok"
        assert run.dimensions_status["finance"]["status"] == "failed"
        assert run.dimensions_status["legal"]["status"] == "missing"
        # basic 落库,finance 失败不落
        basic = (await db.execute(
            select(CreditCompanyBasicData).where(CreditCompanyBasicData.company_id == cid)
        )).scalars().all()
        assert len(basic) == 1


def _add_mock_cert(db, cid: int) -> None:
    """模拟 Δ5 注册时落的 mock 占位证书。"""
    db.add(CreditCompanyCertification(
        company_id=cid, cert_type="system_general", cert_name="ISO 9001",
        status="valid", data_source="mock",
    ))


async def test_qualification_missing_clears_stale_mock_certs(client, test_engine):
    """回归:真实抓取 qualification=missing 时清掉 Δ5 mock 证书,不让残留充数评分。"""
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        cid = await _new_kh(db, "KHF3")
        _add_mock_cert(db, cid)
        await db.flush()
        fake = FakeHarvester(
            basic=make_result("ok", "public", FULL_BASIC),
            finance=make_result("missing", "missing", {}),
            legal=make_result("missing", "missing", {}),
            qual=make_result("missing", "missing", {}),  # 真实查无资质
        )
        await run_harvest_for_company(db, cid, "manual", harvester=fake)
        await db.commit()
        certs = (await db.execute(
            select(CreditCompanyCertification).where(CreditCompanyCertification.company_id == cid)
        )).scalars().all()
        assert len(certs) == 0  # mock 证书被清,真实查无 = 无证书


async def test_qualification_failed_keeps_certs(client, test_engine):
    """qualification=failed(抓取出错)时保留旧证书,不能凭一次失败断言无资质。"""
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        cid = await _new_kh(db, "KHF4")
        _add_mock_cert(db, cid)
        await db.flush()
        fake = FakeHarvester(
            basic=make_result("ok", "public", FULL_BASIC),
            finance=make_result("missing", "missing", {}),
            legal=make_result("missing", "missing", {}),
            qual=make_result("failed", "missing", {}, error="llm: down"),
        )
        await run_harvest_for_company(db, cid, "manual", harvester=fake)
        await db.commit()
        certs = (await db.execute(
            select(CreditCompanyCertification).where(CreditCompanyCertification.company_id == cid)
        )).scalars().all()
        assert len(certs) == 1  # 抓取失败,保留旧证书不动
