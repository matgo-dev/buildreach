"""抓取任务完整闭环集成测试(Δ7 Step 10)。

client fixture 已 seed 评分骨架;用 test_engine 同循环 session 直接调 run_harvest_for_company。
验证:写 run + 落快照(带 raw_data/harvest_run_id)+ 触发评分 + 写 audit_logs。
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    AuditLog,
    CreditCompany,
    CreditCompanyBasicData,
    CreditCompanyCertification,
    CreditCompanyFinanceData,
    ScoreSnapshot,
)
from app.services.credit.harvester.harvest_task import run_harvest_for_company
from tests._harvest_fakes import FakeHarvester, make_result

FULL_BASIC = {
    "established_date": "2008-04-15", "registered_capital": "USD 50,000,000",
    "business_scope": "cement manufacturing", "legal_representative": "John Doe",
    "shareholders": "Group 100%", "status_text": "normal",
    "address": "Phnom Penh", "website": "https://kampot.example",
}


async def test_harvest_writes_run_snapshots_and_scores(client, test_engine):
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        company = CreditCompany(name="Kampot Cement", country_code="KH", registration_no="KH123")
        db.add(company)
        await db.flush()
        cid = company.id

        fake = FakeHarvester(
            basic=make_result("ok", "public", FULL_BASIC),
            finance=make_result("missing", "missing", {}),
            legal=make_result("partial", "media", {"negative_news_level": "none"}),
            qual=make_result("ok", "public", {
                "has_iso_9001": True, "has_iso_14001": None, "has_iso_45001": None,
                "has_isc_certification": None, "other_certifications": [],
            }),
        )
        run = await run_harvest_for_company(
            db, cid, triggered_by="manual", operator_user_id=None, harvester=fake
        )
        await db.commit()

        assert run.status == "partial_succeeded"
        # v0.3:dimensions_status 是详情对象 {status, queries, counts, missing_fields}
        assert run.dimensions_status["basic"]["status"] == "ok"
        assert run.dimensions_status["finance"]["status"] == "missing"
        assert run.dimensions_status["legal"]["status"] == "partial"
        assert run.dimensions_status["qualification"]["status"] == "ok"
        assert "queries" in run.dimensions_status["basic"]
        assert run.tavily_calls > 0 and run.llm_calls > 0

        # basic 快照落库(带 raw_data + harvest_run_id)
        basic = (await db.execute(
            select(CreditCompanyBasicData).where(CreditCompanyBasicData.company_id == cid)
        )).scalars().all()
        assert len(basic) == 1
        assert basic[0].data_source == "public"
        assert basic[0].established_date == date(2008, 4, 15)
        assert basic[0].harvest_run_id == run.id
        assert basic[0].raw_data["harvest_run_id"] == run.id
        assert "tavily_results" in basic[0].raw_data

        # finance missing 占位快照
        fin = (await db.execute(
            select(CreditCompanyFinanceData).where(CreditCompanyFinanceData.company_id == cid)
        )).scalars().all()
        assert len(fin) == 1 and fin[0].data_source == "missing"

        # 证书:ISO 9001 落库
        certs = (await db.execute(
            select(CreditCompanyCertification).where(CreditCompanyCertification.company_id == cid)
        )).scalars().all()
        assert any(c.cert_name == "ISO 9001" for c in certs)

        # 评分触发:trigger_type=MANUAL_RECALC,trigger_detail 含 harvest_run_id
        snap = (await db.execute(
            select(ScoreSnapshot).where(
                ScoreSnapshot.company_id == cid, ScoreSnapshot.is_current.is_(True)
            )
        )).scalar_one()
        assert snap.trigger_type == "MANUAL_RECALC"
        assert snap.trigger_detail["harvest_run_id"] == run.id

        # audit_logs 入口记录
        audits = (await db.execute(
            select(AuditLog).where(AuditLog.resource_type == "credit_harvest_run")
        )).scalars().all()
        assert len(audits) >= 1
        assert audits[0].action == "trigger"


async def test_register_trigger_uses_real_time_onboard(client, test_engine):
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        company = CreditCompany(name="Reg Co", country_code="KH", registration_no="KH999")
        db.add(company)
        await db.flush()
        fake = FakeHarvester(
            basic=make_result("ok", "public", FULL_BASIC),
            finance=make_result("missing", "missing", {}),
            legal=make_result("missing", "missing", {}),
            qual=make_result("missing", "missing", {}),
        )
        await run_harvest_for_company(
            db, company.id, triggered_by="supplier_register", harvester=fake
        )
        await db.commit()
        snap = (await db.execute(
            select(ScoreSnapshot).where(
                ScoreSnapshot.company_id == company.id, ScoreSnapshot.is_current.is_(True)
            )
        )).scalar_one()
        assert snap.trigger_type == "REAL_TIME_ONBOARD"
