"""信用评估评分引擎(信用评估 §3.2 + v0.2 维度级 override 重构)。

主入口:`ScoringEngine.compute(session, company_id, trigger_type, trigger_detail)`

工作流程(v0.2 两步):
1. 加载 active 规则集(score_rule + score_dimension_override + score_dimension + score_subitem)
2. 通过 DataSource 获取四类数据 + 证书清单
3. **子项级自然评分**:每个 subitem 跑 SUBITEM_EVALUATORS,首条命中即停,得 natural sub score
4. 维度自然分 = 该维度所有子项自然分之和 → natural_dim_score[N]
5. **维度级 override post-process**:每个维度跑 DIMENSION_OVERRIDE_EVALUATORS(按 priority 升序),
   首条命中:
     - 该维度最终分 = override.override_score(覆盖自然分)
     - dimension_overrides 数组 append 一条 {dim_code, rule_code, description, natural, final}
   未命中:final_score = natural_score
6. 总分 = sum(各维度 final_score)
7. grade 阈值映射(A≥80 / B≥60 / C≥40 / D<40)
8. 写 score_snapshot(同时写 natural_score 和 final_score 两份 + dimension_overrides)
9. 写 12 条 score_detail(hit_rule_code/description 保留**自然命中规则**,不受 override 影响;
   score 字段也是**自然得分** — 因此 sum(detail.score per dim) 可能 ≠ snapshot.dimension_N_score)
10. 对比前快照,如分数有变化,写 score_audit_log + 平台 audit_logs

事务:8-10 在单事务内提交。AI 评价生成由调用方在 commit 后另起调用。
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import _utcnow
from app.db.models import (
    AuditLog,
    CreditCompany,
    Grade,
    ScoreAuditLog,
    ScoreDetail,
    ScoreDimension,
    ScoreDimensionOverride,
    ScoreRule,
    ScoreSnapshot,
    ScoreSubitem,
    TriggerType,
)
from app.services.credit.data_source.base import DataSource
from app.services.credit.errors import CompanyNotFoundError
from app.services.credit.evaluators import (
    DIMENSION_OVERRIDE_EVALUATORS,
    SUBITEM_EVALUATORS,
)
from app.services.credit.types import (
    DimensionOverrideHit,
    DimensionResult,
    EvaluationInput,
    ScoringResult,
    SubitemResult,
)

logger = logging.getLogger(__name__)


GRADE_THRESHOLDS = [
    (80, Grade.A),
    (60, Grade.B),
    (40, Grade.C),
    (0, Grade.D),
]


def _grade_of(total: int) -> str:
    for threshold, g in GRADE_THRESHOLDS:
        if total >= threshold:
            return g
    return Grade.D


class ScoringEngine:
    """评分引擎(v0.2)。

    DI:DataSource 通过构造注入,便于单测换 mock 数据源。
    """

    def __init__(self, data_source: DataSource) -> None:
        self._data_source = data_source

    # =========================================================================
    # 主入口
    # =========================================================================
    async def compute(
        self,
        session: AsyncSession,
        company_id: int,
        trigger_type: str,
        trigger_detail: dict[str, Any] | None = None,
        operator_user_id: int | None = None,
    ) -> ScoreSnapshot:
        """完整评分流程。**调用方负责事务提交。**"""
        # ---- 1. 加载公司 ----
        company = await session.get(CreditCompany, company_id)
        if company is None:
            raise CompanyNotFoundError(f"company_id={company_id} 不存在")

        # ---- 2. 加载 active 规则集(含维度级 override)----
        dims, subitems, rules_by_subitem, overrides_by_dim = await self._load_rules(
            session
        )
        if not dims:
            raise RuntimeError("score_dimension 未配置;先执行 seed_credit_module()")

        rule_version = max(d.version for d in dims)  # 各维度 version 应该一致

        # ---- 3. 拉数据 ----
        basic = await self._data_source.fetch_basic_data(session, company_id)
        finance = await self._data_source.fetch_finance_data(session, company_id)
        legal = await self._data_source.fetch_legal_data(session, company_id)
        certs = await self._data_source.fetch_certifications(session, company_id)

        ctx = EvaluationInput(
            company_id=company_id,
            country_code=company.country_code,
            basic=basic,
            finance=finance,
            legal=legal,
            certifications=certs,
            today=date.today(),
        )
        # 给 evaluator 用的 plain dict(扁平,JSON 序列化友好)
        ctx_dict = self._to_eval_dict(ctx)

        # ---- 4. 子项级自然评分(每维度的 subitem 求值 + 求和)----
        dim_natural_results: list[DimensionResult] = []
        for dim in sorted(dims, key=lambda d: d.display_order):
            dim_subs = [s for s in subitems if s.dimension_id == dim.id]
            dim_subs.sort(key=lambda s: s.display_order)
            sub_results: list[SubitemResult] = []
            for sub in dim_subs:
                rules = sorted(
                    rules_by_subitem.get(sub.id, []), key=lambda r: r.priority
                )
                sub_result = self._evaluate_subitem(sub, rules, ctx_dict)
                sub_results.append(sub_result)
            dim_score = sum(r.score for r in sub_results)
            dim_natural_results.append(
                DimensionResult(
                    dimension_code=dim.code,
                    score=dim_score,  # 自然分(post-process 前)
                    max_score=dim.max_score,
                    subitems=sub_results,
                )
            )

        natural_dim_scores = {d.dimension_code: d.score for d in dim_natural_results}

        # ---- 5. 维度级 override post-process ----
        override_hits: list[DimensionOverrideHit] = []
        final_dim_results: list[DimensionResult] = []
        for natural in dim_natural_results:
            dim_obj = next(d for d in dims if d.code == natural.dimension_code)
            override_rules = sorted(
                overrides_by_dim.get(dim_obj.id, []), key=lambda o: o.priority
            )
            hit = self._evaluate_dimension_overrides(override_rules, ctx_dict)
            if hit is None:
                # 没 override 命中 → 自然分 = 最终分
                final_dim_results.append(natural)
            else:
                ov_rule, _ = hit
                final = DimensionResult(
                    dimension_code=natural.dimension_code,
                    score=ov_rule.override_score,  # 最终分被覆盖
                    max_score=natural.max_score,
                    subitems=natural.subitems,  # subitem 仍是自然命中,不动
                )
                final_dim_results.append(final)
                override_hits.append(
                    DimensionOverrideHit(
                        dimension_code=natural.dimension_code,
                        override_rule_code=ov_rule.code,
                        override_description=ov_rule.description,
                        natural_score=natural.score,
                        final_score=ov_rule.override_score,
                    )
                )

        # ---- 6-7. 总分 + grade ----
        total = sum(d.score for d in final_dim_results)
        grade = _grade_of(total)

        result = ScoringResult(
            company_id=company_id,
            total_score=total,
            grade=grade,
            dimensions=final_dim_results,
            natural_dim_scores=natural_dim_scores,
            dimension_overrides=override_hits,
            rule_version=rule_version,
            basic_data_id=getattr(basic, "id", None) if not basic.is_missing else None,
            finance_data_id=(
                getattr(finance, "id", None) if not finance.is_missing else None
            ),
            legal_data_id=(
                getattr(legal, "id", None) if not legal.is_missing else None
            ),
        )

        # ---- 8-10. 写库(同事务)----
        snapshot = await self._persist(
            session=session,
            company=company,
            result=result,
            dims=dims,
            subitems=subitems,
            ctx_dict=ctx_dict,
            trigger_type=trigger_type,
            trigger_detail=trigger_detail,
            operator_user_id=operator_user_id,
        )

        return snapshot

    # =========================================================================
    # 内部:规则加载
    # =========================================================================
    async def _load_rules(
        self, session: AsyncSession
    ) -> tuple[
        list[ScoreDimension],
        list[ScoreSubitem],
        dict[int, list[ScoreRule]],
        dict[int, list[ScoreDimensionOverride]],
    ]:
        dims_q = select(ScoreDimension).where(ScoreDimension.is_active.is_(True))
        subs_q = select(ScoreSubitem).where(ScoreSubitem.is_active.is_(True))
        rules_q = select(ScoreRule).where(ScoreRule.is_active.is_(True))
        overrides_q = select(ScoreDimensionOverride).where(
            ScoreDimensionOverride.is_active.is_(True)
        )
        dims = list((await session.execute(dims_q)).scalars().all())
        subs = list((await session.execute(subs_q)).scalars().all())
        rules = list((await session.execute(rules_q)).scalars().all())
        overrides = list((await session.execute(overrides_q)).scalars().all())
        rules_by_sub: dict[int, list[ScoreRule]] = {}
        for r in rules:
            rules_by_sub.setdefault(r.subitem_id, []).append(r)
        overrides_by_dim: dict[int, list[ScoreDimensionOverride]] = {}
        for o in overrides:
            overrides_by_dim.setdefault(o.dimension_id, []).append(o)
        return dims, subs, rules_by_sub, overrides_by_dim

    @staticmethod
    def _to_eval_dict(ctx: EvaluationInput) -> dict[str, Any]:
        # `mode="json"` 把 date/datetime/Decimal 都转成 JSON 友好类型;
        # `today` 也走 isoformat,evaluators 内 _today() 会 parse 回 date。
        return {
            "company_id": ctx.company_id,
            "country_code": ctx.country_code,
            "basic": ctx.basic.model_dump(mode="json"),
            "finance": ctx.finance.model_dump(mode="json"),
            "legal": ctx.legal.model_dump(mode="json"),
            "certifications": [c.model_dump(mode="json") for c in ctx.certifications],
            "today": ctx.today.isoformat(),
        }

    @staticmethod
    def _evaluate_subitem(
        sub: ScoreSubitem,
        rules: list[ScoreRule],
        ctx_dict: dict[str, Any],
    ) -> SubitemResult:
        """对单 subitem 求值:按 priority 升序遍历,首条命中即停。"""
        for r in rules:
            fn = SUBITEM_EVALUATORS.get(r.evaluator_key)
            if fn is None:
                logger.warning(
                    "subitem evaluator '%s' 不存在,跳过 rule %s",
                    r.evaluator_key,
                    r.code,
                )
                continue
            try:
                hit = fn(ctx_dict)
            except Exception:  # noqa: BLE001
                logger.exception("subitem evaluator '%s' 抛错,视为未命中", r.evaluator_key)
                hit = False
            if hit:
                return SubitemResult(
                    subitem_code=sub.code,
                    score=r.score,
                    hit_rule_code=r.code,
                    hit_rule_description=r.description,
                    is_default_score=False,
                )
        # 全部未命中 → 默认分
        return SubitemResult(
            subitem_code=sub.code,
            score=sub.default_score,
            hit_rule_code=None,
            hit_rule_description=None,
            is_default_score=True,
        )

    @staticmethod
    def _evaluate_dimension_overrides(
        overrides: list[ScoreDimensionOverride],
        ctx_dict: dict[str, Any],
    ) -> tuple[ScoreDimensionOverride, bool] | None:
        """对单维度的 override 列表求值,首条命中即停;全部未命中返 None。"""
        for ov in overrides:
            fn = DIMENSION_OVERRIDE_EVALUATORS.get(ov.evaluator_key)
            if fn is None:
                logger.warning(
                    "dimension override evaluator '%s' 不存在,跳过 override %s",
                    ov.evaluator_key,
                    ov.code,
                )
                continue
            try:
                hit = fn(ctx_dict)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "dimension override evaluator '%s' 抛错,视为未命中", ov.evaluator_key
                )
                hit = False
            if hit:
                return ov, True
        return None

    # =========================================================================
    # 内部:持久化
    # =========================================================================
    async def _persist(
        self,
        session: AsyncSession,
        company: CreditCompany,
        result: ScoringResult,
        dims: list[ScoreDimension],
        subitems: list[ScoreSubitem],
        ctx_dict: dict[str, Any],
        trigger_type: str,
        trigger_detail: dict[str, Any] | None,
        operator_user_id: int | None,
    ) -> ScoreSnapshot:
        """写 snapshot(同时 natural + final + overrides)+ detail(自然命中)+ audit。"""
        # 旧快照 is_current 切 false
        prev_q = select(ScoreSnapshot).where(
            ScoreSnapshot.company_id == company.id,
            ScoreSnapshot.is_current.is_(True),
        )
        prev = (await session.execute(prev_q)).scalar_one_or_none()
        if prev is not None:
            await session.execute(
                update(ScoreSnapshot)
                .where(ScoreSnapshot.id == prev.id)
                .values(is_current=False)
            )

        # 维度 1-4 按 display_order 映射(PRD 顺序固定)
        dim_by_order = {
            d.display_order: d.code
            for d in sorted(dims, key=lambda d: d.display_order)
        }
        final_by_code = {d.dimension_code: d.score for d in result.dimensions}
        natural_by_code = result.natural_dim_scores

        def _pick(code_map: dict[str, int], order: int) -> int:
            return code_map.get(dim_by_order.get(order, ""), 0)

        now = _utcnow()
        snapshot = ScoreSnapshot(
            company_id=company.id,
            total_score=result.total_score,
            grade=result.grade,
            # 最终分(可能被 override 覆盖)
            dimension_1_score=_pick(final_by_code, 1),
            dimension_2_score=_pick(final_by_code, 2),
            dimension_3_score=_pick(final_by_code, 3),
            dimension_4_score=_pick(final_by_code, 4),
            # 自然分(子项加总,未 override)
            dimension_1_natural_score=_pick(natural_by_code, 1),
            dimension_2_natural_score=_pick(natural_by_code, 2),
            dimension_3_natural_score=_pick(natural_by_code, 3),
            dimension_4_natural_score=_pick(natural_by_code, 4),
            # 命中的维度级 override 明细数组(可为空 [])
            dimension_overrides=[h.model_dump() for h in result.dimension_overrides],
            rule_version=result.rule_version,
            trigger_type=trigger_type,
            trigger_detail=trigger_detail,
            basic_data_id=result.basic_data_id,
            finance_data_id=result.finance_data_id,
            legal_data_id=result.legal_data_id,
            is_current=True,
            calculated_at=now,
        )
        session.add(snapshot)
        await session.flush()  # 拿到 snapshot.id

        # 写 12 条 score_detail(score + hit_rule 都是**自然**值,不受 override 影响)
        for dim_result in result.dimensions:
            dim = next(d for d in dims if d.code == dim_result.dimension_code)
            for sub_r in dim_result.subitems:
                sub = next(s for s in subitems if s.code == sub_r.subitem_code)
                session.add(
                    ScoreDetail(
                        snapshot_id=snapshot.id,
                        company_id=company.id,
                        dimension_code=dim.code,
                        dimension_name=dim.name,
                        subitem_code=sub.code,
                        subitem_name=sub.name,
                        hit_rule_code=sub_r.hit_rule_code,
                        hit_rule_description=sub_r.hit_rule_description,
                        score=sub_r.score,  # 自然得分(可能 ≠ snapshot.dim_score 当 override 触发)
                        max_score=sub.max_score,
                        is_default_score=sub_r.is_default_score,
                        evaluation_context=ctx_dict,
                    )
                )

        # 评分变动审计
        if (
            prev is None
            or prev.total_score != snapshot.total_score
            or prev.grade != snapshot.grade
        ):
            changed_items: list[dict[str, Any]] = []
            if prev is not None:
                # TODO(T-5): 对比上一快照的 score_detail 计算子项级差异
                changed_items.append(
                    {
                        "type": "summary",
                        "previous_total_score": prev.total_score,
                        "current_total_score": snapshot.total_score,
                        "previous_grade": prev.grade,
                        "current_grade": snapshot.grade,
                    }
                )
            session.add(
                ScoreAuditLog(
                    company_id=company.id,
                    previous_snapshot_id=prev.id if prev else None,
                    current_snapshot_id=snapshot.id,
                    previous_total_score=prev.total_score if prev else None,
                    current_total_score=snapshot.total_score,
                    score_delta=snapshot.total_score - (prev.total_score if prev else 0),
                    previous_grade=prev.grade if prev else None,
                    current_grade=snapshot.grade,
                    grade_changed=(prev is None) or (prev.grade != snapshot.grade),
                    changed_subitems=changed_items,
                    trigger_type=trigger_type,
                )
            )
            if operator_user_id is not None:
                from app.audit.context import get_trace_id

                session.add(
                    AuditLog(
                        trace_id=get_trace_id() or "no-trace",
                        user_id=operator_user_id,
                        resource_type="credit_company",
                        resource_id=str(company.id),
                        action="CREDIT_RECOMPUTE",
                        status="SUCCESS",
                        extra={
                            "trigger_type": trigger_type,
                            "previous_total_score": prev.total_score if prev else None,
                            "current_total_score": snapshot.total_score,
                            "current_grade": snapshot.grade,
                        },
                    )
                )

        await session.flush()
        return snapshot
