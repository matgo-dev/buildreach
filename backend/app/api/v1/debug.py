"""调试接口 /api/_debug/*(v3 §12)。

约束:
- 默认不返回任何业务数据,仅返回 scope 决策信息
- 已登录用户均可调用(无权限点要求,本身是调试用)
- 生产环境通过 settings.ENABLE_DEBUG_API=false 关闭(整个 router 不挂载)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import CurrentUser, get_current_user
from app.core.exceptions import success
from app.rbac.scope_config import (
    RESOURCE_PRIMARY_READ,
    RESOURCES,
    ROLE_RESOURCE_SCOPE,
    Scope,
    explain_scope,
    get_scope,
    would_apply_filter,
)

router = APIRouter(prefix="/_debug", tags=["debug"])


@router.get("/scope", summary="查询当前用户对某资源域的 scope + 模拟过滤条件")
async def scope_check(
    resource: str = Query(..., description="资源域 code,如 project / order"),
    current: CurrentUser = Depends(get_current_user),
):
    if resource not in RESOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown resource: {resource}. Valid: {sorted(RESOURCES.keys())}",
        )

    # 权限点检查(以该资源的"主要 read 权限点"为代表)
    primary = RESOURCE_PRIMARY_READ.get(resource)
    passed = primary in current.permissions if primary else False
    perm_explain = (
        f"{current.roles} 角色拥有 {primary} 权限点"
        if passed
        else f"{current.roles} 角色不持有 {primary},该资源的访问会被 require_permission 拦截"
    )

    scope = get_scope(current.roles, resource)
    org_id = current.organization.id if current.organization else None

    return success({
        "user": current.email,
        "roles": current.roles,
        "resource": resource,
        "resource_name": RESOURCES[resource]["name"],
        "permission_check": {
            "required": primary,
            "passed": passed,
            "explanation": perm_explain,
        },
        "scope_resolved": scope.value,
        "would_apply_filter": would_apply_filter(scope, org_id),
        "explanation": explain_scope(scope, resource),
    })


@router.get("/matrix", summary="返回角色 × 资源 × scope 的完整矩阵(供前端权限矩阵全景页使用)")
async def matrix(
    current: CurrentUser = Depends(get_current_user),  # noqa: ARG001 — 仅作认证拦截
):
    return success({
        "resources": RESOURCES,
        "role_resource_scope": {
            role: {res: s.value for res, s in mapping.items()}
            for role, mapping in ROLE_RESOURCE_SCOPE.items()
        },
    })
