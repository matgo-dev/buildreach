"""RBAC 测试接口 /api/v1/test/*(本轮临时,后续业务模块上线后移除)。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import CurrentUser, get_current_user
from app.core.exceptions import success
from app.db.models.role import RoleCode
from app.rbac.guards import require_any_role

router = APIRouter(prefix="/test", tags=["rbac-test"])


def _payload(role_label: str, current: CurrentUser) -> dict:
    return {
        "scope": role_label,
        "user": {"id": current.id, "email": current.email, "name": current.name},
        "roles": current.roles,
        "permissions": current.permissions,
    }


@router.get("/buyer-only")
async def buyer_only(current: CurrentUser = Depends(require_any_role(RoleCode.BUYER))):
    return success(_payload("BUYER_ONLY", current))


@router.get("/supplier-only")
async def supplier_only(current: CurrentUser = Depends(require_any_role(RoleCode.SUPPLIER))):
    return success(_payload("SUPPLIER_ONLY", current))


@router.get("/operator-only")
async def operator_only(current: CurrentUser = Depends(require_any_role(RoleCode.OPERATOR))):
    return success(_payload("OPERATOR_ONLY", current))


@router.get("/admin-only")
async def admin_only(current: CurrentUser = Depends(require_any_role(RoleCode.ADMIN))):
    return success(_payload("ADMIN_ONLY", current))


@router.get("/all-roles")
async def all_roles(current: CurrentUser = Depends(get_current_user)):
    return success(_payload("ANY_LOGGED_IN", current))
