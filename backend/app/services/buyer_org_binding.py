"""买家 → 组织的确定性解析(「我的订单」授权链的根)。

契约 §5.2(BLOCKER B3 收口):成员关系由 `get_current_user` 一次取全,`CurrentUser.buyer_org_count`
记条数、`organization` 为 owner 优先的第一条。本模块只做判定,不再二次查库:
恰 1 条 ACTIVE → 用之;0 → NO_ORG;>1 → AMBIGUOUS_ORG(拒绝,不替用户选);非 ACTIVE → ORG_DISABLED。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from app.core.dependencies import CurrentUser
from app.db.models.buyer_organization import BuyerOrgStatus

logger = logging.getLogger(__name__)

BindingState = Literal["NO_ORG", "AMBIGUOUS_ORG", "ORG_DISABLED"]


@dataclass(frozen=True)
class OrgResolution:
    """恰一个 ACTIVE 组织 → org_id 有值且 state 为 None;否则 state 说明拒绝原因。"""
    org_id: int | None
    state: BindingState | None


def classify_memberships(count: int, org_id: int | None, org_status: str | None) -> OrgResolution:
    """纯判定:输入成员关系条数与首选组织 (id, status),输出解析结果。

    >1 条一律 AMBIGUOUS(不看状态:两个组织哪怕一个停用也不能替用户选)。
    """
    if count <= 0 or org_id is None:
        return OrgResolution(None, "NO_ORG")
    if count > 1:
        return OrgResolution(None, "AMBIGUOUS_ORG")
    if org_status != BuyerOrgStatus.ACTIVE:
        return OrgResolution(None, "ORG_DISABLED")
    return OrgResolution(org_id, None)


def resolve_buyer_org(current: CurrentUser) -> OrgResolution:
    org = current.organization if current.organization and current.organization.type == "BUYER_ORG" else None
    result = classify_memberships(
        current.buyer_org_count, org.id if org else None, org.status if org else None
    )
    if result.state == "AMBIGUOUS_ORG":
        logger.warning(
            "buyer user %s belongs to %d organizations; refusing order access",
            current.id, current.buyer_org_count,
        )
    return result
