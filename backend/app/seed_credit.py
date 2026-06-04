"""信用评估模块种子(信用评估技术方案 §七 + 工单 Step 9-10)。

种入内容:
1. 评分模型骨架 — 4 维度 + 12 子项 + 51 规则(对齐 PRD v0.3 §4.3)
2. 4 家 demo 企业 mock 数据(覆盖 A/B/C/D 各档)
3. 调用 ScoringEngine 给每家算一次分(写 snapshot + 12 detail + audit_log)

幂等:每步用 code / 复合键判断是否已存在再插入。
不调 LLM 生成 ai_summary(节约启动时间;首访详情页时再生成)。
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DimensionCode,
    ScoreDimension,
    ScoreDimensionOverride,
    ScoreRule,
    ScoreSnapshot,
    ScoreSubitem,
)
from app.db.models.supplier_organization import SupplierOrganization, SupplierOrgStatus
from app.services.credit.evaluators import (
    DIMENSION_OVERRIDE_EVALUATORS,
    SUBITEM_EVALUATORS,
)
from app.services.credit.registration_hook import create_credit_for_supplier

logger = logging.getLogger(__name__)


# =============================================================================
# 评分模型骨架配置
# =============================================================================

# (dim_code, name, max_score, display_order)
_DIMENSIONS: list[tuple[str, str, int, int]] = [
    (DimensionCode.BASIC_INFO, "基础工商信息", 15, 1),
    (DimensionCode.CERTIFICATION, "资质认证储备", 25, 2),
    (DimensionCode.FINANCE, "财务健康状况", 30, 3),
    (DimensionCode.LEGAL, "司法与舆情风险", 30, 4),
]

# (subitem_code, dim_code, name, max_score, default_score, display_order, hint)
_SUBITEMS: list[tuple[str, str, str, int, int, int, str]] = [
    # 维度1
    ("BASIC_REG_INFO", DimensionCode.BASIC_INFO, "注册信息完整性", 5, 0, 1,
     "国家企业信用信息公示系统 / 海外工商数据库"),
    ("BASIC_STATUS", DimensionCode.BASIC_INFO, "存续状态", 5, 0, 2,
     "同上"),
    ("BASIC_SHAREHOLDERS", DimensionCode.BASIC_INFO, "股东与股权", 5, 0, 3,
     "同上"),
    # 维度2
    ("CERT_MANDATORY", DimensionCode.CERTIFICATION, "目标国强制认证", 10, 0, 1,
     "认证机构公开数据库(目标国 SASO/SNI/CE 等)"),
    ("CERT_SYSTEM_GENERAL", DimensionCode.CERTIFICATION, "通用体系认证", 8, 0, 2,
     "ISO9001 / ISO14001 等"),
    ("CERT_INDUSTRY_SPECIFIC", DimensionCode.CERTIFICATION, "行业专项认证", 7, 0, 3,
     "CE / UL / OHSAS 等"),
    # 维度3(整维度 missing 时 default=4,但 default_score 字段是 fallback,
    # 我们用 priority=0 的 override rule 处理 missing 情况)
    ("FINANCE_REVENUE", DimensionCode.FINANCE, "营收与盈利", 10, 0, 1, "企业年报 / 财报公开渠道"),
    ("FINANCE_DEBT", DimensionCode.FINANCE, "资产负债", 10, 0, 2, "同上"),
    ("FINANCE_CASHFLOW", DimensionCode.FINANCE, "现金流", 10, 0, 3, "同上"),
    # 维度4
    ("LEGAL_LITIGATION", DimensionCode.LEGAL, "法律诉讼", 10, 0, 1, "裁判文书网 / 海外法院公开系统"),
    ("LEGAL_DEFAULTER", DimensionCode.LEGAL, "失信被执行", 10, 0, 2, "同上"),
    ("LEGAL_NEWS", DimensionCode.LEGAL, "负面舆情", 10, 0, 3, "媒体舆情监测"),
]

# (subitem_code, rule_code, description, score, evaluator_key, priority)
# priority 0 = 维度级 override(优先级最高);10/20/30... = 档位由高到低
_RULES: list[tuple[str, str, str, int, str, int]] = [
    # =========================================================================
    # 维度1
    # =========================================================================
    ("BASIC_REG_INFO", "R_BASIC_REG_FULL", "注册时间/资本金/经营范围齐全", 5, "basic_reg_info_full", 10),
    ("BASIC_REG_INFO", "R_BASIC_REG_MISS_ONE", "缺 1 项", 3, "basic_reg_info_miss_one", 20),
    ("BASIC_REG_INFO", "R_BASIC_REG_MISS_TWO", "缺 ≥2 项", 0, "basic_reg_info_miss_two_or_more", 30),

    ("BASIC_STATUS", "R_BASIC_STATUS_NORMAL", "正常经营", 5, "basic_status_normal", 10),
    ("BASIC_STATUS", "R_BASIC_STATUS_ABNORMAL", "存续但有异常", 2, "basic_status_abnormal", 20),
    ("BASIC_STATUS", "R_BASIC_STATUS_CANCELLED", "已注销/吊销/未知", 0, "basic_status_cancelled", 30),

    ("BASIC_SHAREHOLDERS", "R_BASIC_SH_CLEAR", "股权结构清晰可查", 5, "basic_shareholders_clear", 10),
    ("BASIC_SHAREHOLDERS", "R_BASIC_SH_PARTIAL", "部分可查", 3, "basic_shareholders_partial", 20),
    ("BASIC_SHAREHOLDERS", "R_BASIC_SH_MISSING", "无法查证", 0, "basic_shareholders_missing", 30),

    # =========================================================================
    # 维度2(v0.2:维度级 override 已移到 score_dimension_override 表,见 _DIMENSION_OVERRIDES)
    # =========================================================================
    ("CERT_MANDATORY", "R_CERT_MANDATORY_VALID", "目标国强制认证且有效期内", 10, "cert_mandatory_valid", 10),
    ("CERT_MANDATORY", "R_CERT_MANDATORY_EXPIRED", "目标国强制认证已过期", 3, "cert_mandatory_expired", 20),
    ("CERT_MANDATORY", "R_CERT_MANDATORY_MISSING", "无目标国强制认证", 0, "cert_mandatory_missing", 30),

    ("CERT_SYSTEM_GENERAL", "R_CERT_SYSTEM_2_OR_MORE", "通用体系认证 ≥2 项", 8, "cert_system_count_2_or_more", 10),
    ("CERT_SYSTEM_GENERAL", "R_CERT_SYSTEM_1", "通用体系认证 1 项", 4, "cert_system_count_1", 20),
    ("CERT_SYSTEM_GENERAL", "R_CERT_SYSTEM_0", "无通用体系认证", 0, "cert_system_count_0", 30),

    ("CERT_INDUSTRY_SPECIFIC", "R_CERT_INDUSTRY_3_OR_MORE", "行业专项认证 ≥3 项(cap 7)", 7, "cert_industry_count_3_or_more", 10),
    ("CERT_INDUSTRY_SPECIFIC", "R_CERT_INDUSTRY_2", "行业专项认证 2 项", 6, "cert_industry_count_2", 20),
    ("CERT_INDUSTRY_SPECIFIC", "R_CERT_INDUSTRY_1", "行业专项认证 1 项", 3, "cert_industry_count_1", 30),
    ("CERT_INDUSTRY_SPECIFIC", "R_CERT_INDUSTRY_0", "无行业专项认证", 0, "cert_industry_count_0", 40),

    # =========================================================================
    # 维度3(v0.2:整维度数据缺失走维度级 override,见 _DIMENSION_OVERRIDES)
    # =========================================================================
    ("FINANCE_REVENUE", "R_FIN_REV_GROWING", "近 2 年营收稳定或增长", 10, "finance_revenue_growing", 10),
    ("FINANCE_REVENUE", "R_FIN_REV_FLUCTUATING", "波动但盈利", 7, "finance_revenue_fluctuating", 20),
    ("FINANCE_REVENUE", "R_FIN_REV_LOSS", "亏损", 3, "finance_revenue_loss", 30),
    ("FINANCE_REVENUE", "R_FIN_REV_UNKNOWN", "数据不可查", 5, "finance_revenue_unknown", 40),

    ("FINANCE_DEBT", "R_FIN_DEBT_LOW", "资产负债率 < 70%", 10, "finance_debt_low", 10),
    ("FINANCE_DEBT", "R_FIN_DEBT_MEDIUM", "资产负债率 70-85%", 6, "finance_debt_medium", 20),
    ("FINANCE_DEBT", "R_FIN_DEBT_HIGH", "资产负债率 > 85%", 2, "finance_debt_high", 30),
    ("FINANCE_DEBT", "R_FIN_DEBT_UNKNOWN", "数据不可查", 5, "finance_debt_unknown", 40),

    ("FINANCE_CASHFLOW", "R_FIN_CASH_POSITIVE", "经营性现金流为正", 10, "finance_cashflow_positive", 10),
    ("FINANCE_CASHFLOW", "R_FIN_CASH_NEG_FUND", "为负但融资正常", 6, "finance_cashflow_negative_with_funding", 20),
    ("FINANCE_CASHFLOW", "R_FIN_CASH_PERSIST_NEG", "持续为负", 2, "finance_cashflow_persistent_negative", 30),
    ("FINANCE_CASHFLOW", "R_FIN_CASH_UNKNOWN", "数据不可查", 5, "finance_cashflow_unknown", 40),

    # =========================================================================
    # 维度4(v0.2:失信未结案一票否决走维度级 override,见 _DIMENSION_OVERRIDES)
    # =========================================================================
    ("LEGAL_LITIGATION", "R_LEG_LITI_ZERO", "无诉讼记录", 10, "legal_litigation_zero", 10),
    ("LEGAL_LITIGATION", "R_LEG_LITI_LOW", "诉讼 < 5 起", 7, "legal_litigation_low", 20),
    ("LEGAL_LITIGATION", "R_LEG_LITI_MEDIUM", "诉讼 5-20 起", 4, "legal_litigation_medium", 30),
    ("LEGAL_LITIGATION", "R_LEG_LITI_HIGH", "诉讼 > 20 起", 1, "legal_litigation_high", 40),

    ("LEGAL_DEFAULTER", "R_LEG_DEF_NONE", "无失信记录", 10, "legal_defaulter_none", 10),
    ("LEGAL_DEFAULTER", "R_LEG_DEF_RESOLVED", "有失信记录但已结案", 4, "legal_defaulter_resolved_only", 20),
    ("LEGAL_DEFAULTER", "R_LEG_DEF_UNRESOLVED", "有未结案失信记录", 0, "legal_defaulter_unresolved", 30),

    ("LEGAL_NEWS", "R_LEG_NEWS_NONE", "无负面报道", 10, "legal_news_none", 10),
    ("LEGAL_NEWS", "R_LEG_NEWS_OCCASIONAL", "偶发已澄清", 6, "legal_news_occasional", 20),
    ("LEGAL_NEWS", "R_LEG_NEWS_PERSISTENT", "持续负面", 2, "legal_news_persistent", 30),
    ("LEGAL_NEWS", "R_LEG_NEWS_MAJOR", "重大丑闻", 0, "legal_news_major_scandal", 40),
]


# v0.2 维度级 override 配置(对齐 score_dimension_override 表)。
# 一个 dim 可以挂多条,按 priority 升序求值,首条命中即停。
# (dim_code, override_code, description, override_score, evaluator_key, priority)
_DIMENSION_OVERRIDES: list[tuple[str, str, str, int, str, int]] = [
    (
        DimensionCode.CERTIFICATION,
        "DIM2_CERT_FORGED_OR_EXPIRED",
        "关键证书伪造或过期未更新,维度强制清零",
        0,
        "dim2_cert_forged_or_expired",
        0,
    ),
    (
        DimensionCode.FINANCE,
        "DIM3_UNKNOWN",
        "财务数据完全缺失,维度给满分 40%(12 分)",
        12,
        "dim3_unknown",
        0,
    ),
    (
        DimensionCode.LEGAL,
        "DIM4_UNRESOLVED_DEFAULTER",
        "失信被执行未结案,维度直接判 0(一票否决)",
        0,
        "dim4_unresolved_defaulter",
        0,
    ),
]



# =============================================================================
# Seed 主流程
# =============================================================================

async def seed_credit_score_model(db: AsyncSession) -> None:
    """种入评分模型骨架:4 维度 + 12 子项 + 51 规则。

    幂等:按 code 检查是否已存在。
    启动后校验:每条 rule 的 evaluator_key 必须在 EVALUATORS 字典中存在,否则日志 WARN(不阻断)。
    """
    # ---- dimensions ----
    code_to_dim: dict[str, ScoreDimension] = {}
    for code, name, max_score, order in _DIMENSIONS:
        row = await db.execute(
            select(ScoreDimension).where(ScoreDimension.code == code)
        )
        existing = row.scalar_one_or_none()
        if existing is None:
            d = ScoreDimension(
                code=code, name=name, max_score=max_score, display_order=order,
                description=f"{name}(满分 {max_score})", is_active=True, version=1,
            )
            db.add(d)
            await db.flush()
            code_to_dim[code] = d
        else:
            code_to_dim[code] = existing

    # ---- subitems ----
    code_to_sub: dict[str, ScoreSubitem] = {}
    for sub_code, dim_code, name, max_score, default_score, order, hint in _SUBITEMS:
        row = await db.execute(
            select(ScoreSubitem).where(ScoreSubitem.code == sub_code)
        )
        existing = row.scalar_one_or_none()
        if existing is None:
            s = ScoreSubitem(
                dimension_id=code_to_dim[dim_code].id,
                code=sub_code, name=name, max_score=max_score,
                default_score=default_score, display_order=order,
                data_source_hint=hint, is_active=True, version=1,
            )
            db.add(s)
            await db.flush()
            code_to_sub[sub_code] = s
        else:
            code_to_sub[sub_code] = existing

    # ---- rules(子项级)----
    orphan_evaluator_keys: list[str] = []
    for sub_code, rule_code, desc, score, ev_key, priority in _RULES:
        row = await db.execute(select(ScoreRule).where(ScoreRule.code == rule_code))
        if row.scalar_one_or_none() is not None:
            continue
        if ev_key not in SUBITEM_EVALUATORS:
            orphan_evaluator_keys.append(f"{rule_code} → {ev_key}")
        db.add(
            ScoreRule(
                subitem_id=code_to_sub[sub_code].id,
                code=rule_code, description=desc, score=score,
                evaluator_key=ev_key, condition_expr=None,
                priority=priority, is_active=True, version=1,
            )
        )
    await db.commit()
    if orphan_evaluator_keys:
        logger.warning(
            "Credit seed: 发现 %d 条 rule 的 evaluator_key 在 SUBITEM_EVALUATORS 中找不到: %s",
            len(orphan_evaluator_keys), orphan_evaluator_keys,
        )
    logger.info(
        "Credit seed: 评分模型骨架完成 (4 维度 / 12 子项 / %d 子项级规则)",
        len(_RULES),
    )


async def seed_credit_dimension_overrides(db: AsyncSession) -> None:
    """种入维度级 override(v0.2 重构,从 score_rule 表剥离)。

    幂等:按 code 检查是否已存在。
    启动校验:每条 override 的 evaluator_key 必须在 DIMENSION_OVERRIDE_EVALUATORS,否则 WARN。
    """
    # 拿维度对应表
    dim_rows = await db.execute(select(ScoreDimension))
    dim_by_code = {d.code: d for d in dim_rows.scalars().all()}

    orphan: list[str] = []
    inserted = 0
    for dim_code, ov_code, desc, score, ev_key, priority in _DIMENSION_OVERRIDES:
        existing = await db.execute(
            select(ScoreDimensionOverride).where(
                ScoreDimensionOverride.code == ov_code
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue
        dim = dim_by_code.get(dim_code)
        if dim is None:
            logger.error(
                "Credit seed: override %s 引用的 dimension %s 不存在,跳过",
                ov_code, dim_code,
            )
            continue
        if ev_key not in DIMENSION_OVERRIDE_EVALUATORS:
            orphan.append(f"{ov_code} → {ev_key}")
        db.add(
            ScoreDimensionOverride(
                dimension_id=dim.id,
                code=ov_code,
                description=desc,
                override_score=score,
                evaluator_key=ev_key,
                priority=priority,
                is_active=True,
                version=1,
            )
        )
        inserted += 1
    await db.commit()
    if orphan:
        logger.warning(
            "Credit seed: 发现 %d 条 override 的 evaluator_key 在 DIMENSION_OVERRIDE_EVALUATORS 中找不到: %s",
            len(orphan), orphan,
        )
    if inserted:
        logger.info(
            "Credit seed: 维度级 override 配置完成 (%d 条新增)", inserted
        )


# 4 家 demo「已注册 Supplier」:(name, country, registration_no, tier)
# 信用评估新定位 = 评估平台已注册 Supplier;每家先建 supplier_org,再建 credit 镜像 + 评分。
_DEMO_SUPPLIERS: list[tuple[str, str, str, str]] = [
    ("Al-Rashid Industrial Co.", "SA", "1010-XXXXX-A1", "A"),
    ("PT Cahaya Sentosa", "ID", "AHU-B2", "B"),
    ("Karachi Steel Works Ltd.", "PK", "SECP-C3", "C"),
    ("Atlas Construction SARL", "MA", "RC-D4", "D"),
]


async def seed_credit_demo_companies(db: AsyncSession) -> None:
    """种入 4 家 demo「已注册 Supplier」+ credit 镜像 + mock 数据 + 首次评分。

    信用评估定位变更(工单 Δ5):评估对象 = 平台已注册 Supplier。
    每家:supplier_organizations(APPROVED) → credit_company 镜像 → 评分。
    幂等:supplier_org 按 (country_code, registration_no) 查;credit 镜像由
    create_credit_for_supplier 内部幂等。seed 不调 LLM(run_ai=False,启动快;
    首访详情页时再生成 ai_summary)。
    """
    for name, country, regno, tier in _DEMO_SUPPLIERS:
        row = await db.execute(
            select(SupplierOrganization).where(
                SupplierOrganization.country_code == country,
                SupplierOrganization.registration_no == regno,
            )
        )
        org = row.scalar_one_or_none()
        if org is None:
            org = SupplierOrganization(
                name=name,
                country_code=country,
                registration_no=regno,
                status=SupplierOrgStatus.APPROVED,
            )
            db.add(org)
            await db.flush()

        created = await create_credit_for_supplier(
            db, org, target_tier=tier, source="seed", run_ai=False
        )
        await db.commit()

        if created is None:
            logger.info("Credit seed: Supplier %s 已有信用镜像,跳过", name)
            continue

        snapshot = (await db.execute(
            select(ScoreSnapshot).where(
                ScoreSnapshot.company_id == created.id,
                ScoreSnapshot.is_current.is_(True),
            )
        )).scalar_one_or_none()
        if snapshot is not None:
            logger.info(
                "Credit seed: Supplier %s 首次评分 = %d (%s),预期 %s",
                name, snapshot.total_score, snapshot.grade, tier,
            )
            if snapshot.grade != tier:
                logger.warning(
                    "Credit seed: Supplier %s 实际评级 %s 与预期 %s 不一致(检查 mock / 规则)",
                    name, snapshot.grade, tier,
                )


async def seed_credit_module(db: AsyncSession) -> None:
    """信用评估模块种子入口。"""
    await seed_credit_score_model(db)
    await seed_credit_dimension_overrides(db)
    await seed_credit_demo_companies(db)
    logger.info(
        "Credit seed: 评分模型骨架 + 维度级 override + 4 家 demo 企业 seed 完成"
    )
