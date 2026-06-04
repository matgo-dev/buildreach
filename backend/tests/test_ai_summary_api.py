"""Δ8:AI 评语按需触发接口 POST /credit/companies/{id}/ai-summary/generate。

验收点 #7-10:
- 无 current snapshot → 400
- 已生成过 → cached=true,不调 LLM
- 未生成 → 调 LLM 并回写,cached=false
- LLM 失败(generate_for_snapshot 返回 None)→ 503
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.api.v1.credit as credit_api
from app.db.base import _utcnow
from app.db.models import CreditCompany, ScoreSnapshot, TriggerType
from app.db.models.audit_log import AuditLog


async def _operator_token(client) -> str:
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "operator@platform.local", "password": "Aa123456789"},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _auth(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


async def _make_company(test_engine, *, with_snapshot: bool, ai_summary: str | None = None) -> int:
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        c = CreditCompany(name=f"KH AISum {datetime.now().timestamp()}", country_code="KH")
        db.add(c)
        await db.flush()
        if with_snapshot:
            db.add(ScoreSnapshot(
                company_id=c.id, total_score=80, grade="B",
                dimension_1_score=20, dimension_2_score=20,
                dimension_3_score=20, dimension_4_score=20,
                rule_version=1, trigger_type=TriggerType.REAL_TIME_ONBOARD,
                is_current=True, calculated_at=_utcnow(),
                ai_summary=ai_summary,
                ai_summary_generated_at=_utcnow() if ai_summary else None,
            ))
        cid = c.id
        await db.commit()
    return cid


@pytest.mark.asyncio
async def test_no_snapshot_returns_400(client, test_engine):
    cid = await _make_company(test_engine, with_snapshot=False)
    t = await _operator_token(client)
    r = await client.post(
        f"/api/v1/credit/companies/{cid}/ai-summary/generate", headers=_auth(t)
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_already_generated_returns_cached(client, test_engine, monkeypatch):
    cid = await _make_company(test_engine, with_snapshot=True, ai_summary="已有评语")

    # 已生成应直接返回缓存,不得调 LLM:patch 成抛错,若被调到则测试失败
    async def _must_not_call(self, session, snapshot_id):  # noqa: ANN001
        raise AssertionError("已生成场景不应调用 LLM")

    monkeypatch.setattr(credit_api.AISummaryGenerator, "generate_for_snapshot", _must_not_call)

    t = await _operator_token(client)
    r = await client.post(
        f"/api/v1/credit/companies/{cid}/ai-summary/generate", headers=_auth(t)
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["cached"] is True
    assert data["ai_summary"] == "已有评语"


@pytest.mark.asyncio
async def test_first_generation_calls_llm(client, test_engine, monkeypatch):
    cid = await _make_company(test_engine, with_snapshot=True, ai_summary=None)

    async def _fake_generate(self, session, snapshot_id):  # noqa: ANN001
        snap = await session.get(ScoreSnapshot, snapshot_id)
        snap.ai_summary = "新生成评语"
        snap.ai_summary_generated_at = _utcnow()
        return "新生成评语"

    monkeypatch.setattr(credit_api.AISummaryGenerator, "generate_for_snapshot", _fake_generate)

    t = await _operator_token(client)
    r = await client.post(
        f"/api/v1/credit/companies/{cid}/ai-summary/generate", headers=_auth(t)
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["cached"] is False
    assert data["ai_summary"] == "新生成评语"


@pytest.mark.asyncio
async def test_llm_failure_returns_503(client, test_engine, monkeypatch):
    cid = await _make_company(test_engine, with_snapshot=True, ai_summary=None)

    async def _fake_fail(self, session, snapshot_id):  # noqa: ANN001
        return None  # generate_for_snapshot 内部吞错后返回 None

    monkeypatch.setattr(credit_api.AISummaryGenerator, "generate_for_snapshot", _fake_fail)

    t = await _operator_token(client)
    r = await client.post(
        f"/api/v1/credit/companies/{cid}/ai-summary/generate", headers=_auth(t)
    )
    assert r.status_code == 503, r.text


async def _ai_summary_audits(test_engine) -> list[AuditLog]:
    """读出全部 credit_ai_summary 资源的 audit_log 行(按时间正序)。"""
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(AuditLog)
            .where(AuditLog.resource_type == "credit_ai_summary")
            .order_by(AuditLog.id.asc())
        )).scalars().all()
    return list(rows)


@pytest.mark.asyncio
async def test_audit_log_written_on_success(client, test_engine, monkeypatch):
    """成功生成场景写一条 SUCCESS 审计,带 user_id/snapshot_id/cached=False。"""
    cid = await _make_company(test_engine, with_snapshot=True, ai_summary=None)

    async def _fake_generate(self, session, snapshot_id):  # noqa: ANN001
        snap = await session.get(ScoreSnapshot, snapshot_id)
        snap.ai_summary = "x"
        snap.ai_summary_generated_at = _utcnow()
        return "x"

    monkeypatch.setattr(credit_api.AISummaryGenerator, "generate_for_snapshot", _fake_generate)

    before = await _ai_summary_audits(test_engine)
    t = await _operator_token(client)
    r = await client.post(
        f"/api/v1/credit/companies/{cid}/ai-summary/generate", headers=_auth(t)
    )
    assert r.status_code == 200, r.text

    after = await _ai_summary_audits(test_engine)
    assert len(after) == len(before) + 1
    row = after[-1]
    assert row.action == "GENERATE"
    assert row.status == "SUCCESS"
    assert row.user_id is not None
    assert row.resource_id is not None
    assert row.extra and row.extra.get("cached") is False
    assert row.extra.get("company_id") == cid


@pytest.mark.asyncio
async def test_audit_log_written_on_cached(client, test_engine, monkeypatch):
    """缓存命中也记 SUCCESS 审计,extra.cached=True(便于成本归因)。"""
    cid = await _make_company(test_engine, with_snapshot=True, ai_summary="已存")

    async def _must_not_call(self, session, snapshot_id):  # noqa: ANN001
        raise AssertionError("缓存命中不应调 LLM")

    monkeypatch.setattr(credit_api.AISummaryGenerator, "generate_for_snapshot", _must_not_call)

    before = await _ai_summary_audits(test_engine)
    t = await _operator_token(client)
    r = await client.post(
        f"/api/v1/credit/companies/{cid}/ai-summary/generate", headers=_auth(t)
    )
    assert r.status_code == 200, r.text

    after = await _ai_summary_audits(test_engine)
    assert len(after) == len(before) + 1
    row = after[-1]
    assert row.status == "SUCCESS"
    assert row.extra and row.extra.get("cached") is True


@pytest.mark.asyncio
async def test_audit_log_written_on_no_snapshot(client, test_engine):
    """无 snapshot(400)也记一条 FAILED 审计,error_message=snapshot_not_ready。"""
    cid = await _make_company(test_engine, with_snapshot=False)

    before = await _ai_summary_audits(test_engine)
    t = await _operator_token(client)
    r = await client.post(
        f"/api/v1/credit/companies/{cid}/ai-summary/generate", headers=_auth(t)
    )
    assert r.status_code == 400, r.text

    after = await _ai_summary_audits(test_engine)
    assert len(after) == len(before) + 1
    row = after[-1]
    assert row.status == "FAILED"
    assert row.error_message == "snapshot_not_ready"


@pytest.mark.asyncio
async def test_audit_log_written_on_llm_failure(client, test_engine, monkeypatch):
    """LLM 返回 None(503)记一条 FAILED 审计,error_message=llm_unavailable。"""
    cid = await _make_company(test_engine, with_snapshot=True, ai_summary=None)

    async def _fake_fail(self, session, snapshot_id):  # noqa: ANN001
        return None

    monkeypatch.setattr(credit_api.AISummaryGenerator, "generate_for_snapshot", _fake_fail)

    before = await _ai_summary_audits(test_engine)
    t = await _operator_token(client)
    r = await client.post(
        f"/api/v1/credit/companies/{cid}/ai-summary/generate", headers=_auth(t)
    )
    assert r.status_code == 503, r.text

    after = await _ai_summary_audits(test_engine)
    assert len(after) == len(before) + 1
    row = after[-1]
    assert row.status == "FAILED"
    assert row.error_message == "llm_unavailable"
