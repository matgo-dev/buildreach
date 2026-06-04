"""详情接口 evaluation_status 状态判定(Δ7 → Δ8 五态:pending/ready/empty/failed)。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.v1.credit import _evaluation_status
from app.db.models import CreditCompany, CreditDataHarvestRun, ScoreSnapshot, TriggerType


def _run(company_id: int, status: str, started_at: datetime) -> CreditDataHarvestRun:
    return CreditDataHarvestRun(
        company_id=company_id, status=status, triggered_by="manual", started_at=started_at,
    )


def _current_snapshot(company_id: int) -> ScoreSnapshot:
    """构造一条 current 真实快照(满足 NOT NULL 字段即可)。"""
    return ScoreSnapshot(
        company_id=company_id, total_score=80, grade="B",
        dimension_1_score=20, dimension_2_score=20, dimension_3_score=20, dimension_4_score=20,
        rule_version=1, trigger_type=TriggerType.REAL_TIME_ONBOARD,
        is_current=True, calculated_at=datetime(2026, 5, 26),
    )


async def test_eval_status_states(test_engine):
    """Δ8 五态:非 KH→ready;KH 无 run→pending;running→pending;
    succeeded 无快照→empty;succeeded 有快照→ready;failed→failed。"""
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        # 非 KH → 恒 ready
        cn = CreditCompany(name="CN", country_code="CN")
        db.add(cn)
        await db.flush()
        st, latest = await _evaluation_status(db, cn)
        assert st == "ready" and latest is None

        # KH 无 run → pending(注册刚完成,Task 还没启动)
        kh_pending = CreditCompany(name="KH Pending", country_code="KH")
        db.add(kh_pending)
        await db.flush()
        st, latest = await _evaluation_status(db, kh_pending)
        assert st == "pending" and latest is None

        # running → pending
        kh_running = CreditCompany(name="KH Running", country_code="KH")
        db.add(kh_running)
        await db.flush()
        db.add(_run(kh_running.id, "running", datetime(2026, 5, 25)))
        await db.flush()
        st, _ = await _evaluation_status(db, kh_running)
        assert st == "pending"

        # Δ8:succeeded 但无 current snapshot → empty(公开源 0 命中)
        kh_empty = CreditCompany(name="KH Empty", country_code="KH")
        db.add(kh_empty)
        await db.flush()
        db.add(_run(kh_empty.id, "succeeded", datetime(2026, 5, 26)))
        await db.flush()
        st, latest = await _evaluation_status(db, kh_empty)
        assert st == "empty"
        assert latest["status"] == "succeeded"

        # succeeded + current snapshot → ready
        kh_ready = CreditCompany(name="KH Ready", country_code="KH")
        db.add(kh_ready)
        await db.flush()
        db.add(_run(kh_ready.id, "succeeded", datetime(2026, 5, 26)))
        db.add(_current_snapshot(kh_ready.id))
        await db.flush()
        st, _ = await _evaluation_status(db, kh_ready)
        assert st == "ready"

        # cached_hit 无快照 → empty
        kh_cached = CreditCompany(name="KH Cached", country_code="KH")
        db.add(kh_cached)
        await db.flush()
        db.add(_run(kh_cached.id, "cached_hit", datetime(2026, 5, 26)))
        await db.flush()
        st, _ = await _evaluation_status(db, kh_cached)
        assert st == "empty"

        # failed → failed
        kh_failed = CreditCompany(name="KH Failed", country_code="KH")
        db.add(kh_failed)
        await db.flush()
        db.add(_run(kh_failed.id, "failed", datetime(2026, 5, 27)))
        await db.flush()
        st, _ = await _evaluation_status(db, kh_failed)
        assert st == "failed"


async def _operator_token(client) -> str:
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "operator@platform.local", "password": "Aa123456789"},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def test_detail_endpoint_returns_evaluation_status(client, test_engine):
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        kh = CreditCompany(name="KH Detail", country_code="KH", registration_no="KH-D-1")
        db.add(kh)
        await db.flush()
        db.add(CreditDataHarvestRun(
            company_id=kh.id, status="running", triggered_by="supplier_register",
            started_at=datetime(2026, 5, 25),
        ))
        cid = kh.id
        await db.commit()

    t = await _operator_token(client)
    r = await client.get(f"/api/v1/credit/companies/{cid}", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["evaluation_status"] == "pending"
    assert data["latest_harvest_run"]["status"] == "running"
