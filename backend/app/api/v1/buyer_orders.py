"""买家「我的订单」BFF /api/v1/buyer/orders:浏览器 → matgo → 履约后台。

契约 §5.2。浏览器任何时候不持有履约令牌、不知道履约地址。
响应二选一:正常数据(履约 `data` 原样透传)或 `{"binding": <状态>}`:
  NO_ORG / AMBIGUOUS_ORG / ORG_DISABLED 由本仓组织解析得出;NOT_BOUND = 履约回 42501。
履约超时 / 5xx / 其他 4xx → 503 + error.orders.unavailable(由 fulfillment_client 直接抛)。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from app.core.dependencies import CurrentUser
from app.core.exceptions import NotFoundError, success
from app.core.locale import get_current_locale
from app.rbac.guards import block_if_must_change_password, require_any_role
from app.services.buyer_org_binding import resolve_buyer_org
from app.services.fulfillment_client import FulfillmentClient, PortalResult, get_fulfillment_client

# 守卫与 cart.py 对齐:BUYER 角色 + 强制改密拦截。只有 buyer_members 行不等于买家身份
# (运营/供应商账号也可能被挂进组织),角色门在前,组织解析在后。
router = APIRouter(
    prefix="/buyer/orders",
    tags=["buyer"],
    dependencies=[Depends(require_any_role("BUYER"))],
)

# 单号只在路径里出现,限制字符集防止把任意串拼进对履约的请求路径
ORDER_NO_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"


def _binding(state: str) -> dict:
    return success({"binding": state})


def _unwrap(result: PortalResult) -> dict:
    if result.kind == "OK":
        return success(result.data)
    if result.kind == "NOT_BOUND":
        return _binding("NOT_BOUND")
    raise NotFoundError("Order not found")


@router.get("", summary="我的订单列表(来自履约后台)")
async def list_my_orders(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current: CurrentUser = Depends(block_if_must_change_password),
    client: FulfillmentClient = Depends(get_fulfillment_client),
):
    resolved = resolve_buyer_org(current)
    if resolved.state is not None:
        return _binding(resolved.state)
    result = await client.list_orders(
        resolved.org_id, page=page, size=size, lang=get_current_locale()
    )
    return _unwrap(result)


@router.get("/{no}", summary="我的订单详情(来自履约后台)")
async def get_my_order(
    no: str = Path(..., pattern=ORDER_NO_PATTERN),
    current: CurrentUser = Depends(block_if_must_change_password),
    client: FulfillmentClient = Depends(get_fulfillment_client),
):
    resolved = resolve_buyer_org(current)
    if resolved.state is not None:
        return _binding(resolved.state)
    result = await client.get_order(resolved.org_id, no, lang=get_current_locale())
    return _unwrap(result)
