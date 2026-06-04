"""Supplier 注册即评分闭环(工单 Δ5 Step 3)。

- create_credit_for_supplier:在给定 session 内,为一家 Supplier 建 credit_company
  镜像 + 写 mock 四类数据 + 跑 ScoringEngine + (可选) AI 评价。seed 与注册钩子共用。
- initialize_credit_for_new_supplier:FastAPI BackgroundTasks 入口,用独立 session,
  失败只记日志不抛(注册主流程不受影响)。
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import _utcnow
from app.db.models import (
    CreditCompany,
    CreditCompanyBasicData,
    CreditCompanyCertification,
    CreditCompanyFinanceData,
    CreditCompanyLegalData,
    DataSourceTag,
    ScoreSnapshot,
    TriggerType,
)
from app.db.models.supplier_organization import SupplierOrganization
from app.db.session import AsyncSessionLocal
from app.services.credit.data_source.mock_data_source import MockDataSource
from app.services.credit.mock_data_generator import (
    MockCreditDataBundle,
    generate_mock_credit_data_for_supplier,
)
from app.services.credit.scoring_engine import ScoringEngine

logger = logging.getLogger(__name__)


def _persist_bundle(db: AsyncSession, company_id: int, bundle: MockCreditDataBundle) -> None:
    """把 mock 数据落到 4 张表(company_id / data_source / fetched_at 在此补)。"""
    now = _utcnow()
    b = bundle.basic_data
    db.add(CreditCompanyBasicData(
        company_id=company_id, data_source=DataSourceTag.MOCK, fetched_at=now, **b
    ))
    if bundle.finance_data is not None:
        db.add(CreditCompanyFinanceData(
            company_id=company_id, data_source=DataSourceTag.MOCK, fetched_at=now,
            raw_data=None, **bundle.finance_data,
        ))
    db.add(CreditCompanyLegalData(
        company_id=company_id, data_source=DataSourceTag.MOCK, fetched_at=now,
        raw_data=None, **bundle.legal_data,
    ))
    for c in bundle.certifications:
        db.add(CreditCompanyCertification(
            company_id=company_id, data_source=DataSourceTag.MOCK, **c
        ))


async def create_credit_for_supplier(
    db: AsyncSession,
    supplier_org: SupplierOrganization,
    *,
    target_tier: str | None = None,
    source: str = "supplier_registration",
    run_ai: bool = True,
) -> CreditCompany | None:
    """在 db session 内为 supplier_org 建信用镜像并完成首次评分。

    幂等 + 收编:credit_company 唯一键是 (country_code, name)。
    - 已有同名镜像且已有 current snapshot → 收编 link 后幂等跳过(返回 None)
    - 已有同名镜像但无 snapshot(残留)→ 复用该行补数据 + 评分
    - 不存在 → 新建
    （收编是为兼容 dev/prod 历史遗留的"平台外 demo"行 linked=NULL 同名情况,
      避免撞 UNIQUE(country_code, name)。)
    **调用方负责 commit。** ScoringEngine 在同 session 内读 flush 后的数据。

    Δ8:柬埔寨改为不写 mock 占位评分——仅建/收编 credit_company 行(空数据、
    无 snapshot),真实数据留待注册链尾的 harvest 抓取。run_ai 参数保留兼容
    seed/测试调用方,但函数体内不再自动生成 AI 评语(改为详情页按需触发)。
    """
    is_kh = supplier_org.country_code == "KH"
    # KH 不生成 mock 数据;其他 8 国保留原 mock 占位流程
    bundle = None if is_kh else generate_mock_credit_data_for_supplier(supplier_org, target_tier)

    company = (await db.execute(
        select(CreditCompany).where(
            CreditCompany.country_code == supplier_org.country_code,
            CreditCompany.name == supplier_org.name,
        )
    )).scalar_one_or_none()

    if company is not None:
        # 收编历史同名行:补 link
        if company.linked_supplier_org_id is None:
            company.linked_supplier_org_id = supplier_org.id
            logger.info(
                "收编历史同名 credit_company=%s → supplier_org=%s",
                company.id, supplier_org.id,
            )
        has_snapshot = (await db.execute(
            select(ScoreSnapshot.id).where(
                ScoreSnapshot.company_id == company.id,
                ScoreSnapshot.is_current.is_(True),
            )
        )).scalar_one_or_none() is not None
        if has_snapshot:
            return None  # 已评分,幂等跳过(收编的 link 改动由调用方 commit)
        # 有镜像但无 snapshot(异常残留 / KH 待抓取)→ 复用 company
        await db.flush()
    else:
        company = CreditCompany(
            name=supplier_org.name,
            legal_name_en=None,
            country_code=supplier_org.country_code,
            registration_no=supplier_org.registration_no,
            linked_supplier_org_id=supplier_org.id,
            # KH 无 mock 故无 expected_grade;非 KH 写入便于后续比对
            data_status=None if is_kh else {"expected_grade": bundle.expected_grade},
        )
        db.add(company)
        await db.flush()  # 拿 company.id;同 session 内后续 SELECT 可见

    # === Δ8:KH 在此 return,不写 mock 数据、不算 mock 分,等待 harvest ===
    if is_kh:
        logger.info(
            "credit init: KH supplier_org=%s company=%s 跳过 mock 占位,等待 harvest",
            supplier_org.id, company.id,
        )
        return company

    _persist_bundle(db, company.id, bundle)
    await db.flush()  # 让 ScoringEngine 的 MockDataSource SELECT 读到

    engine = ScoringEngine(MockDataSource())
    snapshot = await engine.compute(
        session=db,
        company_id=company.id,
        trigger_type=TriggerType.INITIAL,
        trigger_detail={"source": source},
        operator_user_id=None,
    )

    # Δ8:删除 AI 评语自动生成,改为详情页按需触发

    logger.info(
        "credit init done supplier_org=%s company=%s score=%s grade=%s (expected %s)",
        supplier_org.id, company.id, snapshot.total_score, snapshot.grade,
        bundle.expected_grade,
    )
    return company


async def initialize_credit_for_new_supplier(supplier_org_id: int) -> None:
    """BackgroundTasks 入口:新 Supplier 注册成功后异步生成信用评分。

    用独立 DB session;失败只记日志不抛,保证注册请求不受影响。
    """
    try:
        async with AsyncSessionLocal() as db:
            supplier_org = await db.get(SupplierOrganization, supplier_org_id)
            if supplier_org is None:
                logger.warning("supplier_org=%s 不存在,跳过 credit 初始化", supplier_org_id)
                return
            created = await create_credit_for_supplier(
                db, supplier_org, source="supplier_registration", run_ai=True
            )
            if created is not None:
                await db.commit()
    except Exception:  # noqa: BLE001 — 异步任务失败不影响注册主流程
        logger.exception("credit 初始化失败 supplier_org=%s", supplier_org_id)
