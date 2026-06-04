"""信用评估路由 /api/v1/credit/*(对齐技术方案 §四)。

9 个端点:
- 搜索 / 详情
- 触发重算(单家 / 全平台)
- 搜索历史(查 / 删)
- AI 会话 + 流式消息

权限点与 scope(详见 app/rbac/scope_config.py):
- credit:read         BUYER / OPERATOR / SUPPLIER(ADMIN 不持有)
                      SUPPLIER scope=OWN,只能看 linked_supplier_org_id 等于自身 supplier_org_id 的数据
                      其他角色 scope=ALL
- credit:recompute    OPERATOR(ADMIN/SUPPLIER 不持有,require_permission 阶段直接 403)
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.core.exceptions import BusinessError, success
from app.db.base import _utcnow
from app.db.models import (
    CreditAiConversation,
    CreditAiMessage,
    CreditCompany,
    CreditDataHarvestRun,
    CreditSearchHistory,
    MessageRole,
    ScoreDetail,
    ScoreDimension,
    ScoreSnapshot,
    TriggerType,
)
from app.rbac.constants import Permissions
from app.rbac.guards import require_permission
from app.db.models.supplier_organization import SupplierOrganization
from app.db.session import get_db
from app.schemas.credit import (
    AiConversationCreateIn,
    AiConversationOut,
    AiMessageOut,
    AiMessageSendIn,
    BasicDataOut,
    CertificationOut,
    CompanyDetailOut,
    CompanyListItem,
    DimensionOut,
    FinanceDataOut,
    LegalDataOut,
    ScoreDetailOut,
    SearchHistoryItem,
    SnapshotOut,
    TriggerDetail,
)
from app.audit.logger import write_audit
from app.db.models.audit_log import AuditStatus
from app.services.credit.ai_summary_generator import AISummaryGenerator
from app.services.credit.data_source.registry import resolve_data_source
from app.services.credit.harvester.harvest_task import manual_harvest
from app.services.credit.scoring_engine import ScoringEngine
from app.services.llm import LLMUnavailableError, QwenChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/credit", tags=["credit"])

SEARCH_RESULT_LIMIT = 20
SEARCH_HISTORY_LIMIT = 5


def _llm_service() -> QwenChatService:
    """每次请求实例化一个轻量 LLM 客户端;httpx connection pool 内置复用。"""
    return QwenChatService(settings)


async def _verify_company_access(
    db: AsyncSession, current: CurrentUser, company_id: int
) -> CreditCompany:
    """查 company,未命中 404(不暴露存在性)。

    Δ5 后 credit:read 仅 BUYER/OPERATOR 持有(均 scope=ALL),不再有 OWN 数据范围,
    故无需按角色过滤;require_permission 已在路由层拦截无权角色。
    """
    company = await db.get(CreditCompany, company_id)
    if company is None:
        raise BusinessError(http_status=404, biz_code=40404, message="企业不存在")
    return company


_HARVEST_STATUS_TO_EVAL = {
    "pending": "pending", "running": "pending",
    "succeeded": "ready", "partial_succeeded": "ready", "cached_hit": "ready",
    "failed": "failed",
}


async def _evaluation_status(
    db: AsyncSession, company: CreditCompany
) -> tuple[str, dict | None]:
    """Δ8 评分状态判定。非 KH 公司恒 ready;KH 看最近一条 harvest_run。

    Δ8:KH 不再写 mock 占位 snapshot。新增 empty 态——抓取成功完成(succeeded/
    partial_succeeded/cached_hit)但无 current snapshot(公开源 0 命中),区别于 ready。
    """
    if company.country_code != "KH":
        return "ready", None
    run = (await db.execute(
        select(CreditDataHarvestRun)
        .where(CreditDataHarvestRun.company_id == company.id)
        .order_by(CreditDataHarvestRun.started_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if run is None:
        return "pending", None  # 注册刚完成,Task 还没启动
    latest = {
        "id": run.id, "status": run.status, "triggered_by": run.triggered_by,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }
    # 抓取已成功完成:有 current snapshot → ready;无 → empty(0 命中,未生成评分)
    if run.status in ("succeeded", "partial_succeeded", "cached_hit"):
        has_snap = (await db.execute(
            select(ScoreSnapshot.id).where(
                ScoreSnapshot.company_id == company.id,
                ScoreSnapshot.is_current.is_(True),
            )
        )).scalar_one_or_none()
        return ("ready" if has_snap is not None else "empty"), latest
    # pending / running / failed
    return _HARVEST_STATUS_TO_EVAL.get(run.status, "pending"), latest


# =============================================================================
# 1. 搜索候选企业
# =============================================================================

@router.get("/companies/search", summary="搜索候选企业(国别 + 关键词)")
async def search_companies(
    country: str = Query("", description="国别 ISO-2 码;留空表示全部"),
    q: str = Query("", description="企业名/英文名/注册号关键词"),
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    # Δ5 定位变更:评估对象 = 平台已注册 Supplier
    # → INNER JOIN supplier_organizations,只返回有 Supplier 关联的 credit_company
    stmt = select(CreditCompany).join(
        SupplierOrganization,
        CreditCompany.linked_supplier_org_id == SupplierOrganization.id,
    )
    if country:
        stmt = stmt.where(CreditCompany.country_code == country.upper())
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                CreditCompany.name.ilike(like),
                CreditCompany.legal_name_en.ilike(like),
                CreditCompany.registration_no.ilike(like),
            )
        )
    stmt = stmt.order_by(CreditCompany.created_at.desc()).limit(SEARCH_RESULT_LIMIT)
    companies = list((await db.execute(stmt)).scalars().all())

    # 批量取最新 is_current 快照
    snap_map: dict[int, ScoreSnapshot] = {}
    if companies:
        ids = [c.id for c in companies]
        snap_stmt = select(ScoreSnapshot).where(
            ScoreSnapshot.company_id.in_(ids),
            ScoreSnapshot.is_current.is_(True),
        )
        for s in (await db.execute(snap_stmt)).scalars().all():
            snap_map[s.company_id] = s

    items = []
    for c in companies:
        snap = snap_map.get(c.id)
        items.append(
            CompanyListItem(
                id=c.id, name=c.name, legal_name_en=c.legal_name_en,
                country_code=c.country_code, registration_no=c.registration_no,
                total_score=snap.total_score if snap else None,
                grade=snap.grade if snap else None,
            ).model_dump(mode="json")
        )
    _ = current  # 仅鉴权,未使用 user_id
    return success(items)


# =============================================================================
# 2. 企业详情(首访自动生成 ai_summary)
# =============================================================================

@router.get("/companies/{company_id}", summary="企业详情")
async def get_company_detail(
    company_id: int = Path(..., ge=1),
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    company = await _verify_company_access(db, current, company_id)
    eval_status, latest_harvest_run = await _evaluation_status(db, company)

    # 写搜索历史(同 company 去重:删旧+写新)
    await db.execute(
        delete(CreditSearchHistory).where(
            CreditSearchHistory.user_id == current.id,
            CreditSearchHistory.company_id == company_id,
        )
    )
    db.add(
        CreditSearchHistory(
            user_id=current.id,
            company_id=company_id,
            searched_at=_utcnow(),
        )
    )
    await db.commit()

    # 拿当前快照
    snap_stmt = select(ScoreSnapshot).where(
        ScoreSnapshot.company_id == company_id,
        ScoreSnapshot.is_current.is_(True),
    )
    snapshot = (await db.execute(snap_stmt)).scalar_one_or_none()

    # Δ5 优雅降级:异步评分未完成 / 失败 → 无 snapshot,返回企业基础信息 + score=null
    # 前端据此展示"评分生成中,请稍后刷新"(不再现算,避免详情页阻塞)
    if snapshot is None:
        payload = CompanyDetailOut(
            id=company.id,
            name=company.name,
            legal_name_en=company.legal_name_en,
            country_code=company.country_code,
            registration_no=company.registration_no,
            snapshot=None,
            dimensions=[],
            details=[],
            basic=None,
            finance=None,
            legal=None,
            certifications=[],
            evaluation_status=eval_status,
            latest_harvest_run=latest_harvest_run,
        )
        return success(payload.model_dump(mode="json"))

    # AI 评价**不在详情接口里同步生成**:LLM 慢/联网/可能失败,绝不阻塞页面渲染。
    # 改由评分后台任务(registration_hook / harvest_task)异步生成并落库;
    # 详情接口只读库,ai_summary 未就绪则返回 null,前端显示"AI 评价生成中"。
    # 详见 CLAUDE.md「外部慢调用(LLM/网络)不得阻塞请求路径」。

    # 12 条 score_detail
    detail_stmt = (
        select(ScoreDetail)
        .where(ScoreDetail.snapshot_id == snapshot.id)
        .order_by(ScoreDetail.dimension_code, ScoreDetail.subitem_code)
    )
    details_rows = list((await db.execute(detail_stmt)).scalars().all())

    # 维度元信息 + 当前分
    dims_stmt = select(ScoreDimension).order_by(ScoreDimension.display_order)
    dims_rows = list((await db.execute(dims_stmt)).scalars().all())
    dim_outs = [
        DimensionOut(
            code=d.code, name=d.name, max_score=d.max_score,
            score=getattr(snapshot, f"dimension_{d.display_order}_score"),
        )
        for d in dims_rows
    ]

    # 工商 / 财务 / 司法 最新数据(从 snapshot 引用的 ID 取;若 ID 为空则当前查最新)
    basic_out: BasicDataOut | None = None
    finance_out: FinanceDataOut | None = None
    legal_out: LegalDataOut | None = None
    if snapshot.basic_data_id is not None:
        from app.db.models import CreditCompanyBasicData
        basic_row = await db.get(CreditCompanyBasicData, snapshot.basic_data_id)
        basic_out = BasicDataOut.model_validate(basic_row) if basic_row else None
    if snapshot.finance_data_id is not None:
        from app.db.models import CreditCompanyFinanceData
        finance_row = await db.get(CreditCompanyFinanceData, snapshot.finance_data_id)
        finance_out = FinanceDataOut.model_validate(finance_row) if finance_row else None
    if snapshot.legal_data_id is not None:
        from app.db.models import CreditCompanyLegalData
        legal_row = await db.get(CreditCompanyLegalData, snapshot.legal_data_id)
        legal_out = LegalDataOut.model_validate(legal_row) if legal_row else None

    # 证书(不分快照,全部当前)
    from app.db.models import CreditCompanyCertification
    cert_stmt = (
        select(CreditCompanyCertification)
        .where(CreditCompanyCertification.company_id == company_id)
        .order_by(CreditCompanyCertification.cert_type, CreditCompanyCertification.id)
    )
    cert_rows = list((await db.execute(cert_stmt)).scalars().all())

    payload = CompanyDetailOut(
        id=company.id,
        name=company.name,
        legal_name_en=company.legal_name_en,
        country_code=company.country_code,
        registration_no=company.registration_no,
        snapshot=SnapshotOut.model_validate(snapshot),
        dimensions=dim_outs,
        details=[ScoreDetailOut.model_validate(d) for d in details_rows],
        basic=basic_out,
        finance=finance_out,
        legal=legal_out,
        certifications=[CertificationOut.model_validate(c) for c in cert_rows],
        evaluation_status=eval_status,
        latest_harvest_run=latest_harvest_run,
    )
    return success(payload.model_dump(mode="json"))


# =============================================================================
# 3. 单家重算
# =============================================================================

@router.post("/companies/{company_id}/recompute", summary="单家重算")
async def recompute_company(
    company_id: int = Path(..., ge=1),
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_RECOMPUTE)),
    db: AsyncSession = Depends(get_db),
):
    company = await db.get(CreditCompany, company_id)
    if company is None:
        raise BusinessError(http_status=404, biz_code=40404, message="企业不存在")

    engine = ScoringEngine(resolve_data_source(company.country_code))
    snapshot = await engine.compute(
        session=db,
        company_id=company_id,
        trigger_type=TriggerType.MANUAL_RECALC,
        trigger_detail=TriggerDetail(
            actor_user_id=current.id,
            actor_email=current.email,
            source="api",
        ).model_dump(),
        operator_user_id=current.id,
    )
    await db.commit()

    # AI summary 同步生成
    try:
        generator = AISummaryGenerator(_llm_service())
        await generator.generate_for_snapshot(db, snapshot.id)
        await db.commit()
        await db.refresh(snapshot)
    except LLMUnavailableError as exc:
        logger.warning("AI summary 生成失败 company_id=%s: %s", company_id, exc)
    except Exception:  # noqa: BLE001
        logger.exception("AI summary 生成抛错 company_id=%s", company_id)

    return success(SnapshotOut.model_validate(snapshot).model_dump(mode="json"))


# =============================================================================
# 3a. AI 评语按需触发(Δ8,详情页按钮同步生成)
# =============================================================================

@router.post(
    "/companies/{company_id}/ai-summary/generate",
    summary="按需触发 AI 评语生成(同步)",
)
async def generate_ai_summary(
    request: Request,
    company_id: int = Path(..., ge=1),
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Δ8:同步生成 AI 评语并写库。前端展示 loading 态,完成后刷新详情。

    - 无 current snapshot → 400(评分未就绪,无法生成)
    - 已生成过(ai_summary 非空)→ 直接返回缓存文本,不重复调 LLM
    - LLM 失败(generate_for_snapshot 返回 None)→ 503

    审计:所有调用(成功/缓存命中/失败)都记一条 audit_log,记 user_id + snapshot_id,
    便于 LLM 成本归因与异常排查(CLAUDE.md「任何业务写操作必记 audit」)。
    """
    company = await _verify_company_access(db, current, company_id)

    snapshot = (await db.execute(
        select(ScoreSnapshot).where(
            ScoreSnapshot.company_id == company.id,
            ScoreSnapshot.is_current.is_(True),
        )
    )).scalar_one_or_none()

    if snapshot is None:
        await write_audit(
            db,
            resource_type="credit_ai_summary",
            action="GENERATE",
            status=AuditStatus.FAILED,
            user_id=current.id,
            user_email=current.email,
            resource_id=None,
            request=request,
            error_message="snapshot_not_ready",
            extra={"company_id": company_id},
        )
        raise BusinessError(
            http_status=400, biz_code=40001, message="评分未就绪,无法生成 AI 评语"
        )

    if snapshot.ai_summary:
        await write_audit(
            db,
            resource_type="credit_ai_summary",
            action="GENERATE",
            status=AuditStatus.SUCCESS,
            user_id=current.id,
            user_email=current.email,
            resource_id=snapshot.id,
            request=request,
            extra={"company_id": company_id, "cached": True},
        )
        return success({
            "ai_summary": snapshot.ai_summary,
            "generated_at": (
                snapshot.ai_summary_generated_at.isoformat()
                if snapshot.ai_summary_generated_at else None
            ),
            "cached": True,
        })

    text = await AISummaryGenerator(_llm_service()).generate_for_snapshot(db, snapshot.id)
    await db.commit()

    if text is None:
        await write_audit(
            db,
            resource_type="credit_ai_summary",
            action="GENERATE",
            status=AuditStatus.FAILED,
            user_id=current.id,
            user_email=current.email,
            resource_id=snapshot.id,
            request=request,
            error_message="llm_unavailable",
            extra={"company_id": company_id},
        )
        raise BusinessError(
            http_status=503, biz_code=50301, message="AI 评语暂时不可用,请稍后重试"
        )

    await db.refresh(snapshot)
    await write_audit(
        db,
        resource_type="credit_ai_summary",
        action="GENERATE",
        status=AuditStatus.SUCCESS,
        user_id=current.id,
        user_email=current.email,
        resource_id=snapshot.id,
        request=request,
        extra={"company_id": company_id, "cached": False},
    )
    return success({
        "ai_summary": text,
        "generated_at": (
            snapshot.ai_summary_generated_at.isoformat()
            if snapshot.ai_summary_generated_at else None
        ),
        "cached": False,
    })


# =============================================================================
# 3b. 手动触发数据抓取(Δ7,运营用)
# =============================================================================

@router.post("/companies/{company_id}/harvest", summary="手动触发数据抓取(运营用)")
async def trigger_harvest(
    background_tasks: BackgroundTasks,
    company_id: int = Path(..., ge=1),
    force_refresh: bool = Query(False, description="强制刷新(绕过 24h 缓存)"),
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_RECOMPUTE)),
    db: AsyncSession = Depends(get_db),
):
    company = await db.get(CreditCompany, company_id)
    if company is None:
        raise BusinessError(http_status=404, biz_code=40404, message="企业不存在")
    # 本期仅柬埔寨支持真实数据源抓取
    if company.country_code != "KH":
        raise BusinessError(
            http_status=400, biz_code=40001,
            message="当前仅支持柬埔寨企业抓取真实数据源",
        )
    background_tasks.add_task(
        manual_harvest,
        company_id=company_id,
        operator_user_id=current.id,
        force_refresh=force_refresh,
    )
    return success({"company_id": company_id, "status": "queued"})


# =============================================================================
# 4. 全平台重算(占位接口,T-1 / T+1 跑批前供 ADMIN 手动触发)
# =============================================================================

@router.post("/recompute-all", summary="全平台重算(占位)")
async def recompute_all(
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_RECOMPUTE)),
    db: AsyncSession = Depends(get_db),
):
    """遍历所有 CreditCompany,逐家重算。本期无并发限流。

    TODO(T-1): 接入 T+1 调度后改异步队列。
    """
    rows = list((await db.execute(select(CreditCompany))).scalars().all())
    recomputed = []
    for c in rows:
        engine = ScoringEngine(resolve_data_source(c.country_code))
        snapshot = await engine.compute(
            session=db,
            company_id=c.id,
            trigger_type=TriggerType.MANUAL_RECALC,
            trigger_detail=TriggerDetail(
                actor_user_id=current.id,
                actor_email=current.email,
                source="api_recompute_all",
            ).model_dump(),
            operator_user_id=current.id,
        )
        await db.commit()
        recomputed.append({"company_id": c.id, "total_score": snapshot.total_score, "grade": snapshot.grade})

    return success({"count": len(recomputed), "items": recomputed})


# =============================================================================
# 5. 搜索历史
# =============================================================================

@router.get("/search-history", summary="当前用户最近 5 条搜索历史")
async def list_search_history(
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    # 同 company 去重:每个 company 只保留 max(searched_at) 那一条
    sub = (
        select(
            CreditSearchHistory.company_id,
            func.max(CreditSearchHistory.searched_at).label("max_at"),
        )
        .where(CreditSearchHistory.user_id == current.id)
        .group_by(CreditSearchHistory.company_id)
        .subquery()
    )
    stmt = (
        select(CreditSearchHistory, CreditCompany)
        .join(
            sub,
            (CreditSearchHistory.company_id == sub.c.company_id)
            & (CreditSearchHistory.searched_at == sub.c.max_at),
        )
        .join(CreditCompany, CreditCompany.id == CreditSearchHistory.company_id)
        .where(CreditSearchHistory.user_id == current.id)
        .order_by(CreditSearchHistory.searched_at.desc())
        .limit(SEARCH_HISTORY_LIMIT)
    )

    # 取每条 company 的当前 grade
    rows = list((await db.execute(stmt)).all())
    if not rows:
        return success([])
    company_ids = [c.id for _, c in rows]
    snap_map: dict[int, ScoreSnapshot] = {}
    snap_stmt = select(ScoreSnapshot).where(
        ScoreSnapshot.company_id.in_(company_ids),
        ScoreSnapshot.is_current.is_(True),
    )
    for s in (await db.execute(snap_stmt)).scalars().all():
        snap_map[s.company_id] = s

    items = [
        SearchHistoryItem(
            id=h.id, company_id=c.id, company_name=c.name, country_code=c.country_code,
            grade=(snap_map.get(c.id).grade if snap_map.get(c.id) else None),
            searched_at=h.searched_at,
        ).model_dump(mode="json")
        for h, c in rows
    ]
    return success(items)


@router.delete("/search-history/{history_id}", summary="删除一条搜索历史")
async def delete_search_history(
    history_id: int = Path(..., ge=1),
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(CreditSearchHistory, history_id)
    if row is None or row.user_id != current.id:
        raise BusinessError(http_status=404, biz_code=40404, message="历史记录不存在")
    await db.delete(row)
    await db.commit()
    return success({"deleted": history_id})


# =============================================================================
# 6-8. AI 会话
# =============================================================================

@router.post("/ai/conversations", summary="创建 AI 会话")
async def create_ai_conversation(
    body: AiConversationCreateIn,
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    await _verify_company_access(db, current, body.company_id)
    conv = CreditAiConversation(
        user_id=current.id,
        company_id=body.company_id,
        started_at=_utcnow(),
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return success(
        AiConversationOut.model_validate(conv).model_dump(mode="json")
    )


@router.get("/ai/conversations/{conv_id}", summary="获取会话历史")
async def get_ai_conversation(
    conv_id: int = Path(..., ge=1),
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    conv = await db.get(CreditAiConversation, conv_id)
    if conv is None or conv.user_id != current.id:
        raise BusinessError(http_status=404, biz_code=40404, message="会话不存在")
    # 会话关联的 company 必须在 scope 范围内,否则 404(不暴露存在性)
    await _verify_company_access(db, current, conv.company_id)
    msg_stmt = (
        select(CreditAiMessage)
        .where(CreditAiMessage.conversation_id == conv_id)
        .order_by(CreditAiMessage.sequence)
    )
    msgs = list((await db.execute(msg_stmt)).scalars().all())
    out = AiConversationOut.model_validate(conv)
    out.messages = [AiMessageOut.model_validate(m) for m in msgs]
    return success(out.model_dump(mode="json"))


@router.post(
    "/ai/conversations/{conv_id}/messages",
    summary="发送对话消息(SSE 流式响应)",
)
async def send_ai_message(
    conv_id: int,
    body: AiMessageSendIn,
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """流式返回 LLM 输出。响应 Content-Type=text/event-stream,逐 chunk 推 data 字段。

    流完整后将 assistant 完整内容落库一条 message。
    """
    conv = await db.get(CreditAiConversation, conv_id)
    if conv is None or conv.user_id != current.id:
        raise BusinessError(http_status=404, biz_code=40404, message="会话不存在")

    company = await _verify_company_access(db, current, conv.company_id)

    # 取当前快照(用于在 system prompt 中提供企业上下文)
    snap = (
        await db.execute(
            select(ScoreSnapshot).where(
                ScoreSnapshot.company_id == conv.company_id,
                ScoreSnapshot.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()

    # 历史消息按 sequence
    msgs_stmt = (
        select(CreditAiMessage)
        .where(CreditAiMessage.conversation_id == conv_id)
        .order_by(CreditAiMessage.sequence)
    )
    history = list((await db.execute(msgs_stmt)).scalars().all())

    # 写本轮 user 消息
    next_seq = (history[-1].sequence + 1) if history else 1
    user_msg = CreditAiMessage(
        conversation_id=conv_id,
        role=MessageRole.USER,
        content=body.content,
        sequence=next_seq,
    )
    db.add(user_msg)
    await db.commit()

    # 构造 LLM messages(system + history + this user message)
    system_prompt = (
        f"你是海外工程供应链领域的企业风控分析师助手。"
        f"用户正在咨询的企业是 '{company.name}'(国别 {company.country_code})。"
    )
    if snap is not None:
        system_prompt += (
            f" 该企业当前综合评分 {snap.total_score} 分 ({snap.grade} 级)。"
            f" 已缓存评价摘要:{snap.ai_summary or '尚未生成'}。"
        )
    llm_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for m in history:
        llm_messages.append({"role": m.role, "content": m.content})
    llm_messages.append({"role": MessageRole.USER, "content": body.content})

    llm = _llm_service()

    async def event_stream() -> AsyncIterator[bytes]:
        """SSE 帧格式:`data: <text>\\n\\n`。流完一行 `data: [DONE]\\n\\n`。

        客户端只看通用文案,不暴露具体 LLM 厂商/凭据/上游错误细节;
        具体原因写服务端日志(LLMUnavailableError 内部 message + logger)。
        """
        collected: list[str] = []
        try:
            async for chunk in llm.stream_chat(llm_messages):
                collected.append(chunk)
                # 转义换行,避免 SSE data 多行混淆
                safe = chunk.replace("\n", "\\n")
                yield f"data: {safe}\n\n".encode("utf-8")
        except LLMUnavailableError as exc:
            logger.warning("SSE LLM 不可用: %s", exc)
            err = json.dumps({"error": "AI 服务暂时不可用,请稍后再试"}, ensure_ascii=False)
            yield f"event: error\ndata: {err}\n\n".encode("utf-8")
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("SSE 流式中断: %s", exc)
            err = json.dumps({"error": "AI 服务暂时不可用,请稍后再试"}, ensure_ascii=False)
            yield f"event: error\ndata: {err}\n\n".encode("utf-8")
            return

        # 流完整 → 落库 assistant 消息(注意:这里启用一个新 session,旧 db 会话已 close)
        full_content = "".join(collected).strip()
        if full_content:
            from app.db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as new_db:
                new_db.add(
                    CreditAiMessage(
                        conversation_id=conv_id,
                        role=MessageRole.ASSISTANT,
                        content=full_content,
                        sequence=next_seq + 1,
                    )
                )
                await new_db.commit()

        yield b"data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 关闭 nginx/反代缓冲
        },
    )
