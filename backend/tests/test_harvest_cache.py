"""抓取 24h 缓存语义(Δ7 §4.4)。命中跳过 Tavily+LLM+评分;force_refresh 绕过。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import CreditCompany, ScoreSnapshot
from app.services.credit.harvester.harvest_task import run_harvest_for_company
from tests._harvest_fakes import FakeHarvester, RaisingHarvester, make_result

FULL_BASIC = {
    "established_date": "2008-04-15", "registered_capital": "USD 50,000,000",
    "business_scope": "x", "legal_representative": "y", "shareholders": "z",
    "status_text": "normal", "address": "PP", "website": "https://x",
}


def _ok_harvester() -> FakeHarvester:
    return FakeHarvester(
        basic=make_result("ok", "public", FULL_BASIC),
        finance=make_result("missing", "missing", {}),
        legal=make_result("missing", "missing", {}),
        qual=make_result("missing", "missing", {}),
    )


async def _new_kh_company(db, regno="KHC1") -> int:
    company = CreditCompany(name="Cache Co", country_code="KH", registration_no=regno)
    db.add(company)
    await db.flush()
    return company.id


async def _snapshot_count(db, cid: int) -> int:
    return (await db.execute(
        select(func.count()).select_from(ScoreSnapshot).where(ScoreSnapshot.company_id == cid)
    )).scalar_one()


async def test_cache_hit_skips_harvest_and_scoring(client, test_engine):
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        cid = await _new_kh_company(db)
        run1 = await run_harvest_for_company(db, cid, "manual", harvester=_ok_harvester())
        await db.commit()
        assert run1.status == "partial_succeeded"
        snaps_before = await _snapshot_count(db, cid)

        # 第二次:不带 force_refresh + RaisingHarvester(命中则不会被调用)
        run2 = await run_harvest_for_company(db, cid, "manual", harvester=RaisingHarvester())
        await db.commit()

        assert run2.status == "cached_hit"
        assert run2.cache_source_run_id == run1.id
        assert run2.tavily_calls == 0 and run2.llm_calls == 0
        # 缓存命中不评分 → 快照数不变
        assert await _snapshot_count(db, cid) == snaps_before


async def test_force_refresh_bypasses_cache(client, test_engine):
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        cid = await _new_kh_company(db, regno="KHC2")
        await run_harvest_for_company(db, cid, "manual", harvester=_ok_harvester())
        await db.commit()
        snaps_before = await _snapshot_count(db, cid)

        run2 = await run_harvest_for_company(
            db, cid, "manual", force_refresh=True, harvester=_ok_harvester()
        )
        await db.commit()

        assert run2.status != "cached_hit"
        # 绕过缓存 → 重新评分,新增一条快照
        assert await _snapshot_count(db, cid) == snaps_before + 1
