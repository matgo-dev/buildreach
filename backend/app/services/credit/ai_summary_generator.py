"""AI 综合评价生成器(信用评估 §3.5)。

基于 snapshot + detail + 公司元信息拼装 prompt 调 LLM 生成 200-400 字总评。
失败时返回 None,**不抛异常**(交由调用方决定 ai_summary 字段是否留空)。

调用时机:
- API /credit/companies/{id}:首访发现 ai_summary 为 null 时同步调用,生成后回写 snapshot
- Seed:不调(工单 Step 10 + 启动加速)
- 重算接口:在事务 commit 后同步调用
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import _utcnow
from app.db.models import (
    CreditCompany,
    CreditCompanyBasicData,
    ScoreDetail,
    ScoreDimension,
    ScoreSnapshot,
)
from app.services.llm.base import LLMService, LLMUnavailableError

logger = logging.getLogger(__name__)


PROMPT_TEMPLATE = """你是海外工程供应链领域的企业风控分析师。
基于以下企业的结构化评分数据,生成约 200-400 字的综合评价。

要点:
① 综合得分与等级解读
② 优势(高分维度)
③ 风险提示(低分 / 数据缺失维度)
④ 合作建议

要求:
- 语气专业客观,不使用绝对化措辞
- 若某子项数据状态为 missing,如实说明而不编造
- 用中文输出,Markdown 段落格式
- 不要用表情符号

【企业数据】
{snapshot_json}
"""


class AISummaryGenerator:
    """LLM 综合评价生成器。"""

    def __init__(self, llm: LLMService) -> None:
        self._llm = llm

    async def generate_for_snapshot(
        self, session: AsyncSession, snapshot_id: int
    ) -> str | None:
        """根据 snapshot_id 拼 prompt 并调 LLM。

        成功时:回写 snapshot 的 ai_summary + ai_summary_generated_at,返回文本
        失败时:不回写,返回 None
        """
        snapshot = await session.get(ScoreSnapshot, snapshot_id)
        if snapshot is None:
            logger.warning("snapshot_id=%s 不存在,跳过 AI 评价生成", snapshot_id)
            return None

        try:
            prompt_data = await self._build_prompt_data(session, snapshot)
            prompt = PROMPT_TEMPLATE.format(
                snapshot_json=json.dumps(prompt_data, ensure_ascii=False, indent=2)
            )
            text = (await self._llm.generate(prompt)).strip()
            if not text:
                return None
            # 回写
            snapshot.ai_summary = text
            snapshot.ai_summary_generated_at = _utcnow()
            await session.flush()
            return text
        except LLMUnavailableError as exc:
            logger.warning("AI 评价生成失败(snapshot=%s): %s", snapshot_id, exc)
            return None
        except Exception:  # noqa: BLE001 — AI 评价是纯降级功能,任何异常都返回 None 不外抛
            logger.exception("AI 评价生成异常(snapshot=%s)", snapshot_id)
            return None

    @staticmethod
    async def _build_prompt_data(
        session: AsyncSession, snapshot: ScoreSnapshot
    ) -> dict[str, Any]:
        company = await session.get(CreditCompany, snapshot.company_id)
        # 维度元信息(从 dimension 表拿名字)
        dims_q = select(ScoreDimension).order_by(ScoreDimension.display_order)
        dims = list((await session.execute(dims_q)).scalars().all())

        # 12 条 detail
        details_q = select(ScoreDetail).where(ScoreDetail.snapshot_id == snapshot.id)
        details = list((await session.execute(details_q)).scalars().all())

        # 工商基础信息(轻量,只取展示字段)
        basic_q = (
            select(CreditCompanyBasicData)
            .where(CreditCompanyBasicData.company_id == snapshot.company_id)
            .order_by(CreditCompanyBasicData.fetched_at.desc())
            .limit(1)
        )
        basic = (await session.execute(basic_q)).scalar_one_or_none()

        return {
            "company": {
                "name": company.name if company else None,
                "country_code": company.country_code if company else None,
                "registered_capital": basic.registered_capital if basic else None,
                "established_date": (
                    basic.established_date.isoformat() if basic and basic.established_date else None
                ),
                "status_text": basic.status_text if basic else None,
            },
            "total_score": snapshot.total_score,
            "grade": snapshot.grade,
            "dimensions": [
                {
                    "code": d.code,
                    "name": d.name,
                    "max_score": d.max_score,
                    "score": getattr(snapshot, f"dimension_{d.display_order}_score"),
                }
                for d in dims
            ],
            "subitems": [
                {
                    "dimension_code": dt.dimension_code,
                    "subitem_code": dt.subitem_code,
                    "subitem_name": dt.subitem_name,
                    "score": dt.score,
                    "max_score": dt.max_score,
                    "hit_rule_description": dt.hit_rule_description,
                    "is_default_score": dt.is_default_score,
                }
                for dt in details
            ],
        }
