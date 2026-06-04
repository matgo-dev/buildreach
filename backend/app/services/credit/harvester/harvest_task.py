"""抓取任务编排(Δ7 Step 10/11/12)。

run_harvest_for_company:完整抓取流程(缓存检查 → 写 run → 四维度抓取 → 落快照
→ 更新 run → 触发评分),调用方负责事务提交。
harvest_after_register / manual_harvest:BackgroundTask 入口,各用独立 session,
失败只记日志不抛(不影响主流程)。
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.context import get_trace_id
from app.core.config import settings
from app.db.base import _utcnow
from app.db.models import (
    AuditLog,
    CertStatus,
    CertType,
    CreditCompany,
    CreditCompanyBasicData,
    CreditCompanyCertification,
    CreditCompanyFinanceData,
    CreditCompanyLegalData,
    CreditDataHarvestRun,
    HarvestRunStatus,
    HarvestTriggeredBy,
    TriggerType,
)
from app.db.session import AsyncSessionLocal
from app.services.credit.data_source.registry import resolve_data_source
from app.services.credit.errors import CompanyNotFoundError
from app.services.credit.harvester.public_web_harvester import (
    HarvestResult,
    PublicWebHarvester,
)
from app.services.credit.harvester.tavily_client import TavilyClient, TavilySearchResult
from app.services.credit.scoring_engine import ScoringEngine
from app.services.llm import QwenChatService

logger = logging.getLogger(__name__)

_PROMPTS_ROOT = Path(__file__).parent / "prompts"


# =============================================================================
# helpers
# =============================================================================

# =============================================================================
# [2026-05-27 临时关停] Tavily + qwen-plus 外部 API mock(节约费用)
# -----------------------------------------------------------------------------
# 原因:评分链路每次抓取消耗 ~10 次 Tavily 调用 + 4 次 qwen LLM 抽取,持续产生费用。
# 选址:仅替换 _build_harvester 里两个 client 的构造,真实 TavilyClient /
#       QwenChatService 类与单测均不动。单测全部走 harvester=... 注入,绕开此函数,
#       故零测试影响;生产路径 (harvest_after_register 仅 KH 触发) 必走此处 →
#       柬埔寨评分链路零真实外部调用。
# 后续恢复:删除下方 _MOCK_* 常量与 _Mock* 两个类,取消 _build_harvester 内原构造
#         注释,删除 mock 构造 + 头部注释块即可。
#
# Mock 一致性:_MOCK_TAVILY_CONTENT 内嵌 4 维度所有占位字段的 quote 原文,
# _MOCK_LLM_JSON 各字段 evidence.quote 均为 content 子串、source_index=0,
# 通过 PublicWebHarvester 反幻觉后处理(quote ≥10 字符 + fuzzy 匹配 ≥0.3)。
# =============================================================================

_MOCK_TAVILY_CONTENT = (
    "[占位 mock 数据] 该柬埔寨公司于 2015-03-12 在柬埔寨商业部(MOC)登记注册,"
    "注册资本为 500000 美元。经营范围涵盖建筑材料供应、工程设备租赁与基础设施施工服务。"
    "法定代表人为 Sok Chanthy。主要股东为 Mekong Infrastructure Holdings Co., Ltd.,持股比例 70%。"
    "公司当前登记状态为正常经营。注册地址位于 No. 128, Street 271, Sangkat Boeung Salang, "
    "Khan Tuol Kork, Phnom Penh, Cambodia。公司官方网站为 https://example-supplier-kh.com。"
    "根据公开年报,公司近三年营业收入呈稳定增长态势,资产负债率约为 0.45,经营性现金流持续为正。"
    "在公开司法与媒体渠道中未检索到该公司涉及诉讼、法院判决或失信被执行的记录,"
    "也未发现重大负面新闻报道。"
    "公司已通过 ISO 9001 质量管理体系认证、ISO 14001 环境管理体系认证以及 ISO 45001 职业健康安全管理体系认证。"
)

_MOCK_TAVILY_URL = "https://mock-placeholder.invalid/profile"

# superset JSON:4 维度 schema 通过 extra=ignore 各取所需字段;evidence dict 保留所有 key
_MOCK_LLM_JSON: str = json.dumps(
    {
        # --- basic ---
        "established_date": "2015-03-12",
        "registered_capital": "500000 USD",
        "business_scope": "建筑材料供应、工程设备租赁与基础设施施工服务",
        "legal_representative": "Sok Chanthy",
        "shareholders": "Mekong Infrastructure Holdings Co., Ltd.(70%)",
        "status_text": "正常",
        "address": "No. 128, Street 271, Sangkat Boeung Salang, Khan Tuol Kork, Phnom Penh, Cambodia",
        "website": "https://example-supplier-kh.com",
        # --- finance ---
        "revenue_trend": "growing",
        "debt_ratio": 0.45,
        "cash_flow_status": "positive",
        # --- legal ---
        "litigation_count": 0,
        "defaulter_unresolved_count": 0,
        "defaulter_resolved_count": 0,
        "negative_news_level": "none",
        # --- qualification ---
        "has_iso_9001": True,
        "has_iso_14001": True,
        "has_iso_45001": True,
        "has_isc_certification": None,  # 留 null 不冒认 ISC(柬埔寨建筑业强制证)
        "other_certifications": [],
        # --- evidence(每个有值字段都给一条,quote 为 content 子串) ---
        "_evidence": {
            "established_date": {"quote": "2015-03-12 在柬埔寨商业部(MOC)登记注册", "source_index": 0},
            "registered_capital": {"quote": "注册资本为 500000 美元", "source_index": 0},
            "business_scope": {"quote": "经营范围涵盖建筑材料供应、工程设备租赁与基础设施施工服务", "source_index": 0},
            "legal_representative": {"quote": "法定代表人为 Sok Chanthy", "source_index": 0},
            "shareholders": {"quote": "主要股东为 Mekong Infrastructure Holdings Co., Ltd.,持股比例 70%", "source_index": 0},
            "status_text": {"quote": "公司当前登记状态为正常经营", "source_index": 0},
            "address": {"quote": "注册地址位于 No. 128, Street 271, Sangkat Boeung Salang, Khan Tuol Kork, Phnom Penh, Cambodia", "source_index": 0},
            "website": {"quote": "公司官方网站为 https://example-supplier-kh.com", "source_index": 0},
            "revenue_trend": {"quote": "近三年营业收入呈稳定增长态势", "source_index": 0},
            "debt_ratio": {"quote": "资产负债率约为 0.45", "source_index": 0},
            "cash_flow_status": {"quote": "经营性现金流持续为正", "source_index": 0},
            "litigation_count": {"quote": "未检索到该公司涉及诉讼、法院判决或失信被执行的记录", "source_index": 0},
            "defaulter_unresolved_count": {"quote": "未检索到该公司涉及诉讼、法院判决或失信被执行的记录", "source_index": 0},
            "defaulter_resolved_count": {"quote": "未检索到该公司涉及诉讼、法院判决或失信被执行的记录", "source_index": 0},
            "negative_news_level": {"quote": "也未发现重大负面新闻报道", "source_index": 0},
            "has_iso_9001": {"quote": "已通过 ISO 9001 质量管理体系认证", "source_index": 0},
            "has_iso_14001": {"quote": "ISO 14001 环境管理体系认证", "source_index": 0},
            "has_iso_45001": {"quote": "ISO 45001 职业健康安全管理体系认证", "source_index": 0},
        },
        "_confidence": "medium",
        "_notes": "占位 mock 数据(2026-05-27 临时关停 Tavily/qwen 外部 API)",
    },
    ensure_ascii=False,
)


class _MockTavilyClient(TavilyClient):
    """[2026-05-27 临时关停] 不调外部 Tavily API,返回固定占位结果。

    返回结构与 TavilyClient.search 完全一致:list[TavilySearchResult]。
    """

    async def search(  # type: ignore[override]
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_domains: list[str] | None = None,
        country: str | None = None,
    ) -> list[TavilySearchResult]:
        # 忽略 api_key / query / whitelist / country,固定返回 1 条占位结果
        return [
            TavilySearchResult(
                title="[Mock 占位] Cambodia company profile",
                url=_MOCK_TAVILY_URL,
                content=_MOCK_TAVILY_CONTENT,
                score=0.95,
            ),
        ]


class _MockQwenChatService(QwenChatService):
    """[2026-05-27 临时关停] 不调外部 qwen-plus API,返回固定占位 JSON 字符串。

    返回结构与 QwenChatService.generate_json 完全一致:json.dumps 后的字符串。
    """

    async def generate_json(  # type: ignore[override]
        self,
        prompt: str,
        *,
        timeout_seconds: int | None = None,
    ) -> str:
        # 忽略 _check_configured / prompt / timeout,固定返回 superset JSON
        return _MOCK_LLM_JSON


def _build_harvester() -> PublicWebHarvester:
    # [2026-05-27 临时关停] 用 mock 客户端,真实外部 API 调用已停。原构造保留于下方注释,
    # 后续恢复时删除本块 mock 构造 + 上方 _MOCK_* / _Mock* 定义,取消下方注释即可。
    tavily: TavilyClient = _MockTavilyClient(
        api_key="mock-disabled",
        base_url="https://mock-placeholder.invalid",
    )
    llm: QwenChatService = _MockQwenChatService(settings)
    # 原构造代码(临时关停结束后取消注释):
    # tavily = TavilyClient(
    #     settings.TAVILY_API_KEY,
    #     settings.TAVILY_API_URL,
    #     settings.TAVILY_TIMEOUT_SECONDS,
    # )
    # llm = QwenChatService(settings)
    return PublicWebHarvester(
        tavily,
        llm,
        _PROMPTS_ROOT,
        max_results=settings.TAVILY_MAX_RESULTS_PER_QUERY,
        llm_timeout_seconds=settings.CREDIT_HARVEST_LLM_TIMEOUT_SECONDS,
        llm_retry=settings.CREDIT_HARVEST_LLM_RETRY,
        fuzzy_threshold=settings.CREDIT_HARVEST_EVIDENCE_FUZZY_THRESHOLD,
        whitelist_fallback_threshold=settings.CREDIT_HARVEST_WHITELIST_FALLBACK_THRESHOLD,
    )


def _parse_date(s: Any) -> date | None:
    if not s or not isinstance(s, str):
        return None
    try:
        return date.fromisoformat(s.strip())
    except ValueError:
        return None


def _to_decimal(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def _raw(r: HarvestResult, run_id: int) -> dict[str, Any]:
    """落库 raw_data 结构(v0.3:evidence 为对象 {quote,source_index,source_url}+queries)。"""
    return {
        "llm_response": r.raw_llm_response,
        "evidence": {k: v.model_dump() for k, v in r.evidence.items()},
        "confidence": r.confidence,
        "queries": r.queries,
        "tavily_results": [{"index": i, **t} for i, t in enumerate(r.tavily_results)],
        "harvest_run_id": run_id,
    }


def _aggregate_status(dim_status: dict[str, dict[str, Any]]) -> str:
    """4 维度结果汇总成 run.status(§4.6)。dim_status 值为 v0.3 详情对象。"""
    vals = [d["status"] for d in dim_status.values()]
    if vals and all(v == "failed" for v in vals):
        return HarvestRunStatus.FAILED
    if vals and all(v == "ok" for v in vals):
        return HarvestRunStatus.SUCCEEDED
    return HarvestRunStatus.PARTIAL_SUCCEEDED


async def _find_cache_hit(
    session: AsyncSession, company_id: int
) -> CreditDataHarvestRun | None:
    """24h 内是否有 succeeded / partial_succeeded 的 run(§4.4)。"""
    cutoff = _utcnow() - timedelta(hours=settings.CREDIT_HARVEST_CACHE_TTL_HOURS)
    stmt = (
        select(CreditDataHarvestRun)
        .where(
            CreditDataHarvestRun.company_id == company_id,
            CreditDataHarvestRun.status.in_(
                [HarvestRunStatus.SUCCEEDED, HarvestRunStatus.PARTIAL_SUCCEEDED]
            ),
            CreditDataHarvestRun.started_at >= cutoff,
        )
        .order_by(CreditDataHarvestRun.started_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _audit_trigger(
    session: AsyncSession,
    run: CreditDataHarvestRun,
    triggered_by: str,
    force_refresh: bool,
    operator_user_id: int | None,
) -> None:
    """触发 harvest 时写一条 audit_logs(§4.7:谁触发了 harvest)。"""
    session.add(
        AuditLog(
            trace_id=get_trace_id() or "no-trace",
            user_id=operator_user_id,
            resource_type="credit_harvest_run",
            resource_id=str(run.id),
            action="trigger",
            status="SUCCESS",
            extra={"triggered_by": triggered_by, "force_refresh": force_refresh},
        )
    )


# =============================================================================
# 落快照(维度级)
# =============================================================================

def _persist_basic(
    session: AsyncSession, company_id: int, r: HarvestResult, run_id: int, now: datetime
) -> None:
    if r.status == "failed":
        return  # 失败不落快照
    ex = r.extracted
    session.add(
        CreditCompanyBasicData(
            company_id=company_id,
            established_date=_parse_date(ex.get("established_date")),
            registered_capital=ex.get("registered_capital"),
            business_scope=ex.get("business_scope"),
            legal_representative=ex.get("legal_representative"),
            shareholders=ex.get("shareholders"),
            status_text=ex.get("status_text"),
            address=ex.get("address"),
            website=ex.get("website"),
            data_source=r.data_source,
            fetched_at=now,
            raw_data=_raw(r, run_id),
            harvest_run_id=run_id,
        )
    )


def _persist_finance(
    session: AsyncSession, company_id: int, r: HarvestResult, run_id: int, now: datetime
) -> None:
    if r.status == "failed":
        return
    ex = r.extracted
    session.add(
        CreditCompanyFinanceData(
            company_id=company_id,
            revenue_trend=ex.get("revenue_trend"),
            debt_ratio=_to_decimal(ex.get("debt_ratio")),
            cash_flow_status=ex.get("cash_flow_status"),
            raw_data=_raw(r, run_id),
            data_source=r.data_source,
            fetched_at=now,
            harvest_run_id=run_id,
        )
    )


def _persist_legal(
    session: AsyncSession, company_id: int, r: HarvestResult, run_id: int, now: datetime
) -> None:
    if r.status == "failed":
        return
    ex = r.extracted
    session.add(
        CreditCompanyLegalData(
            company_id=company_id,
            # 这三列 NOT NULL default 0;柬埔寨场景多为 null → 落 0
            litigation_count=ex.get("litigation_count") or 0,
            defaulter_unresolved_count=ex.get("defaulter_unresolved_count") or 0,
            defaulter_resolved_count=ex.get("defaulter_resolved_count") or 0,
            negative_news_level=ex.get("negative_news_level"),
            raw_data=_raw(r, run_id),
            data_source=r.data_source,
            fetched_at=now,
            harvest_run_id=run_id,
        )
    )


_ISO_CERT_MAP = [
    ("has_iso_9001", "ISO 9001", CertType.SYSTEM_GENERAL),
    ("has_iso_14001", "ISO 14001", CertType.SYSTEM_GENERAL),
    ("has_iso_45001", "ISO 45001", CertType.SYSTEM_GENERAL),
    ("has_isc_certification", "ISC Certification", CertType.MANDATORY_COUNTRY),
]


async def _persist_certifications(
    session: AsyncSession,
    company_id: int,
    country_code: str,
    r: HarvestResult,
    run_id: int,
) -> None:
    """证书维度落库。

    证书表是"多行全读"(不像其他三表读最新一条),按抓取结论分三档处理:
    - failed:抓取技术性出错(Tavily/LLM 报错),数据未知 → 保留旧证书不动
      (不能凭一次失败就断言"无资质")。
    - missing:真实查无资质 → 清空该 company 现存证书(含 Δ5 mock 占位),不落新行,
      维度2 评分按"无证书"走。**否则 Δ5 mock 证书会残留充数,污染真实评分。**
    - ok/partial:清空旧证书后落本次 public 证书。
    """
    if r.status == "failed":
        return
    # missing / ok / partial:真实抓取已有结论,先清掉旧证书(Δ5 mock + 历史 harvest)
    await session.execute(
        delete(CreditCompanyCertification).where(
            CreditCompanyCertification.company_id == company_id
        )
    )
    if r.status == "missing":
        return  # 真实查无资质,清空即可,不落新行
    ex = r.extracted
    raw = _raw(r, run_id)
    for field, cert_name, cert_type in _ISO_CERT_MAP:
        if ex.get(field) is True:
            session.add(
                CreditCompanyCertification(
                    company_id=company_id,
                    cert_type=cert_type,
                    cert_name=cert_name,
                    target_country_code=(
                        country_code if cert_type == CertType.MANDATORY_COUNTRY else None
                    ),
                    status=CertStatus.VALID,
                    data_source=r.data_source,
                    raw_data=raw,
                    harvest_run_id=run_id,
                )
            )
    for name in ex.get("other_certifications", []) or []:
        session.add(
            CreditCompanyCertification(
                company_id=company_id,
                cert_type=CertType.INDUSTRY_SPECIFIC,
                cert_name=str(name)[:200],
                status=CertStatus.VALID,
                data_source=r.data_source,
                raw_data=raw,
                harvest_run_id=run_id,
            )
        )


# =============================================================================
# 主流程
# =============================================================================

async def run_harvest_for_company(
    session: AsyncSession,
    company_id: int,
    triggered_by: str,
    operator_user_id: int | None = None,
    force_refresh: bool = False,
    harvester: PublicWebHarvester | None = None,
) -> CreditDataHarvestRun:
    """完整抓取流程。**调用方负责事务提交。**

    harvester 参数仅用于单测注入;生产留 None,内部按 settings 构造。
    """
    company = await session.get(CreditCompany, company_id)
    if company is None:
        raise CompanyNotFoundError(f"company_id={company_id} 不存在")
    now = _utcnow()

    # 1. 缓存检查
    if not force_refresh:
        cached = await _find_cache_hit(session, company_id)
        if cached is not None:
            run = CreditDataHarvestRun(
                company_id=company_id,
                status=HarvestRunStatus.CACHED_HIT,
                triggered_by=triggered_by,
                operator_user_id=operator_user_id,
                started_at=now,
                finished_at=now,
                dimensions_status=dict(cached.dimensions_status or {}),
                cache_source_run_id=cached.id,
                tavily_calls=0,
                llm_calls=0,
            )
            session.add(run)
            await session.flush()
            _audit_trigger(session, run, triggered_by, force_refresh, operator_user_id)
            # 缓存命中:不写新快照、不触发评分(快照不变,评分必然不变)
            return run

    # 2. 写 running run(先拿 id,快照要引用 harvest_run_id)
    run = CreditDataHarvestRun(
        company_id=company_id,
        status=HarvestRunStatus.RUNNING,
        triggered_by=triggered_by,
        operator_user_id=operator_user_id,
        started_at=now,
        dimensions_status={},
        tavily_calls=0,
        llm_calls=0,
    )
    session.add(run)
    await session.flush()
    _audit_trigger(session, run, triggered_by, force_refresh, operator_user_id)

    # 3. 四维度抓取
    h = harvester or _build_harvester()
    name, regno, cc = company.name, company.registration_no, company.country_code
    basic_r = await h.harvest_basic(name, cc, regno)
    finance_r = await h.harvest_finance(name, cc, regno)
    legal_r = await h.harvest_legal(name, cc, regno)
    qual_r = (await h.harvest_qualifications(name, cc, regno))[0]

    dim_status: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    total_tavily = total_llm = 0
    for dim, res in [
        ("basic", basic_r), ("finance", finance_r),
        ("legal", legal_r), ("qualification", qual_r),
    ]:
        # v0.3:dimensions_status 从字符串扩展为详情对象,便于排查召回质量
        dim_status[dim] = {
            "status": res.status,
            "queries": res.queries,
            "tavily_results_count": len(res.tavily_results),
            "extracted_fields_count": sum(1 for v in res.extracted.values() if v is not None),
            "missing_fields": [k for k, v in res.extracted.items() if v is None],
        }
        total_tavily += res.tavily_calls
        total_llm += res.llm_calls
        if res.error:
            errors.append(f"{dim}: {res.error}")

    # 4. 落快照
    _persist_basic(session, company_id, basic_r, run.id, now)
    _persist_finance(session, company_id, finance_r, run.id, now)
    _persist_legal(session, company_id, legal_r, run.id, now)
    await _persist_certifications(session, company_id, cc, qual_r, run.id)
    await session.flush()

    # 5. 更新 run 终态
    run.status = _aggregate_status(dim_status)
    run.finished_at = _utcnow()
    run.dimensions_status = dim_status
    run.tavily_calls = total_tavily
    run.llm_calls = total_llm
    run.error_detail = "; ".join(errors) if errors else None
    await session.flush()

    # 6. 触发评分(即使全 failed 也跑,走 missing 降级路径)
    trigger_type = (
        TriggerType.REAL_TIME_ONBOARD
        if triggered_by == HarvestTriggeredBy.SUPPLIER_REGISTER
        else TriggerType.MANUAL_RECALC
    )
    engine = ScoringEngine(resolve_data_source(cc))
    snapshot = await engine.compute(
        session=session,
        company_id=company_id,
        trigger_type=trigger_type,
        trigger_detail={"harvest_run_id": run.id, "triggered_by": triggered_by},
        operator_user_id=operator_user_id,
    )
    await session.flush()

    # Δ8:删除 AI 评语自动生成,改为详情页按需触发(POST .../ai-summary/generate)

    logger.info(
        "harvest done company=%s run=%s status=%s dims=%s",
        company_id, run.id, run.status, dim_status,
    )
    return run


# =============================================================================
# BackgroundTask 入口(各用独立 session,失败只记日志)
# =============================================================================

async def harvest_after_register(supplier_org_id: int) -> None:
    """注册链尾触发抓取(Δ5 占位评分之后)。仅柬埔寨。"""
    try:
        async with AsyncSessionLocal() as db:
            company = (
                await db.execute(
                    select(CreditCompany)
                    .where(CreditCompany.linked_supplier_org_id == supplier_org_id)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if company is None:
                logger.warning("harvest skip: supplier_org=%s 无 credit_company", supplier_org_id)
                return
            # 本期仅柬埔寨抓真实数据源;其他国别仍 mock,无需 harvest
            if company.country_code != "KH":
                return
            # Δ8:KH 不再写 mock 占位 snapshot,故删除"必须有 snapshot 才继续"的前置守卫,
            #     注册链尾直接抓取真实数据
            await run_harvest_for_company(
                db, company.id, triggered_by=HarvestTriggeredBy.SUPPLIER_REGISTER
            )
            await db.commit()
    except Exception:  # noqa: BLE001 — 异步任务失败不影响注册主流程
        logger.exception("注册触发抓取失败 supplier_org=%s", supplier_org_id)


async def manual_harvest(
    company_id: int, operator_user_id: int, force_refresh: bool = False
) -> None:
    """手动 API 触发抓取。"""
    try:
        async with AsyncSessionLocal() as db:
            await run_harvest_for_company(
                db,
                company_id,
                triggered_by=HarvestTriggeredBy.MANUAL,
                operator_user_id=operator_user_id,
                force_refresh=force_refresh,
            )
            await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("手动触发抓取失败 company_id=%s", company_id)
