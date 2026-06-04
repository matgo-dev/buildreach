"""供应商目录路由 /api/v1/suppliers(供应商目录列表页 MVP v0.1)。

BUYER / OPERATOR 浏览平台已注册 Supplier 列表(SUPPLIER 持有 supplier:read 但
前端不给入口;ADMIN 无 supplier:read → 403)。本期不做审批状态过滤(全状态可见)。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.exceptions import success
from app.db.models import CreditCompany, ScoreSnapshot
from app.db.models.supplier_organization import SupplierOrganization
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_permission
from app.schemas.supplier import SupplierListItem

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

SUPPLIER_LIST_LIMIT = 50


@router.get("", summary="供应商目录列表(关键词 / 国别 / 级别筛选)")
async def list_suppliers(
    q: str = Query("", description="供应商名称关键词"),
    country: str = Query("", description="国别 ISO-2 码;留空表示全部"),
    grade: str = Query("", description="信用等级 A/B/C/D;留空表示全部"),
    current: CurrentUser = Depends(require_permission(Permissions.SUPPLIER_READ)),
    db: AsyncSession = Depends(get_db),
):
    # LEFT JOIN 当前评分快照(经 credit_company 镜像);无评分则分数 null
    stmt = (
        select(SupplierOrganization, ScoreSnapshot)
        .outerjoin(
            CreditCompany,
            CreditCompany.linked_supplier_org_id == SupplierOrganization.id,
        )
        .outerjoin(
            ScoreSnapshot,
            (ScoreSnapshot.company_id == CreditCompany.id)
            & (ScoreSnapshot.is_current.is_(True)),
        )
    )
    if q:
        stmt = stmt.where(SupplierOrganization.name.ilike(f"%{q}%"))
    if country:
        stmt = stmt.where(SupplierOrganization.country_code == country.upper())
    if grade:
        stmt = stmt.where(ScoreSnapshot.grade == grade.upper())

    # 分高在前,无分垫底;再按 id 稳定排序
    stmt = stmt.order_by(
        ScoreSnapshot.total_score.desc().nulls_last(),
        SupplierOrganization.id.asc(),
    ).limit(SUPPLIER_LIST_LIMIT)

    rows = (await db.execute(stmt)).all()
    items = [
        SupplierListItem(
            id=org.id,
            name=org.name,
            country_code=org.country_code,
            status=org.status,
            total_score=snap.total_score if snap else None,
            grade=snap.grade if snap else None,
        ).model_dump(mode="json")
        for org, snap in rows
    ]
    _ = current  # 仅鉴权
    return success(items)
