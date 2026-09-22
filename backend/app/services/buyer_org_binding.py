"""买家 → 组织的确定性解析(「我的订单」授权链的根)。

契约 §5.2(BLOCKER B3 收口):`dependencies.py` 里 `current.organization` 取自
`buyer_members … limit(1)` 无 ORDER BY,一人多组织时随机 → 跨租户可达。
BFF 不用它,显式查该用户全部成员关系再判定。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.buyer_member import BuyerMember
from app.db.models.buyer_organization import BuyerOrganization, BuyerOrgStatus

logger = logging.getLogger(__name__)

BindingState = Literal["NO_ORG", "AMBIGUOUS_ORG", "ORG_DISABLED"]


@dataclass(frozen=True)
class OrgResolution:
    """恰一个 ACTIVE 组织 → org_id 有值且 state 为 None;否则 state 说明拒绝原因。"""
    org_id: int | None
    state: BindingState | None


def classify_memberships(orgs: list[tuple[int, str]]) -> OrgResolution:
    """纯判定:输入该用户全部 (org_id, org_status),输出解析结果。

    0 条 → NO_ORG;>1 条 → AMBIGUOUS_ORG(不看状态:两个组织哪怕一个停用也不能替用户选);
    恰 1 条但非 ACTIVE → ORG_DISABLED;恰 1 条 ACTIVE → 用之。
    """
    if not orgs:
        return OrgResolution(None, "NO_ORG")
    if len(orgs) > 1:
        return OrgResolution(None, "AMBIGUOUS_ORG")
    org_id, status = orgs[0]
    if status != BuyerOrgStatus.ACTIVE:
        return OrgResolution(None, "ORG_DISABLED")
    return OrgResolution(org_id, None)


async def resolve_buyer_org(db: AsyncSession, user_id: int) -> OrgResolution:
    """查该用户全部 buyer_members(uq(user_id, buyer_org_id) 保证每组织一行,量级个位数)。"""
    rows = await db.execute(
        select(BuyerOrganization.id, BuyerOrganization.status)
        .join(BuyerMember, BuyerMember.buyer_org_id == BuyerOrganization.id)
        .where(BuyerMember.user_id == user_id)
        .order_by(BuyerOrganization.id)
    )
    orgs = [(int(r.id), str(r.status)) for r in rows]
    result = classify_memberships(orgs)
    if result.state == "AMBIGUOUS_ORG":
        logger.warning(
            "buyer user %s belongs to %d organizations %s; refusing order access",
            user_id, len(orgs), [o[0] for o in orgs],
        )
    return result
