"""内部账号管理路由 /api/v1/admin/users"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.constants import AuditAction, AuditResourceType
from app.audit.logger import write_audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import NotFoundError, success
from app.db.models.user import User
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_permission
from app.schemas.user import AdminUserCreateIn, AdminUserListOut, AdminUserOut, AdminUserUpdateIn
from app.services import user_service

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.post("", summary="创建 ADMIN / OPERATOR 内部账号")
async def create_user(
    body: AdminUserCreateIn,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.USER_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.create_internal_user(
        db,
        email=body.email,
        username=body.username,
        name=body.name,
        password=body.password,
        role=body.role,
        must_change_password=body.must_change_password,
        actor_user_id=current.id,
        actor_user_email=current.email,
        request=request,
    )
    out = AdminUserOut(
        id=user.id,
        email=user.email,
        username=user.username,
        name=user.name,
        status=user.status,
        must_change_password=user.must_change_password,
        roles=[body.role],
    )
    return success(out.model_dump())


@router.get("", summary="用户列表(内部)")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current: CurrentUser = Depends(require_permission(Permissions.USER_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    items, total = await user_service.list_users(db, page=page, page_size=page_size)
    out = AdminUserListOut(
        items=[
            AdminUserOut(
                id=u.id,
                email=u.email,
                phone=getattr(u, "phone", None),
                username=u.username,
                name=u.name,
                status=u.status,
                must_change_password=u.must_change_password,
                roles=roles,
            )
            for u, roles in items
        ],
        total=total,
    )
    return success(out.model_dump())


def _user_to_out(user, roles: list[str]) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        email=user.email,
        phone=getattr(user, "phone", None),
        username=user.username,
        name=user.name,
        status=user.status,
        must_change_password=user.must_change_password,
        roles=roles,
    )


async def _load_roles_of(db: AsyncSession, user_id: int) -> list[str]:
    from sqlalchemy import select
    from app.db.models.role import Role
    from app.db.models.user_role import UserRole
    rows = await db.execute(
        select(Role.code).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return sorted(rows.scalars().all())


@router.put("/{user_id}", summary="编辑用户信息(email/phone/name)")
async def update_user_route(
    body: AdminUserUpdateIn,
    user_id: int = Path(..., ge=1),
    request: Request = None,  # type: ignore[assignment]
    current: CurrentUser = Depends(require_permission(Permissions.USER_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.update_user(
        db,
        target_user_id=user_id,
        actor_user_id=current.id,
        actor_user_email=current.email,
        email=body.email,
        phone=body.phone,
        name=body.name,
        request=request,
    )
    roles = await _load_roles_of(db, user.id)
    return success(_user_to_out(user, roles).model_dump())


@router.post("/{user_id}/disable", summary="停用账号(ADMIN/OPERATOR/BUYER/SUPPLIER 均可)")
async def disable_user_route(
    user_id: int = Path(..., ge=1),
    request: Request = None,  # type: ignore[assignment]
    current: CurrentUser = Depends(require_permission(Permissions.USER_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.disable_user(
        db,
        target_user_id=user_id,
        actor_user_id=current.id,
        actor_user_email=current.email,
        request=request,
    )
    roles = await _load_roles_of(db, user.id)
    return success(_user_to_out(user, roles).model_dump())


@router.post("/{user_id}/enable", summary="启用已停用的账号")
async def enable_user_route(
    user_id: int = Path(..., ge=1),
    request: Request = None,  # type: ignore[assignment]
    current: CurrentUser = Depends(require_permission(Permissions.USER_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.enable_user(
        db,
        target_user_id=user_id,
        actor_user_id=current.id,
        actor_user_email=current.email,
        request=request,
    )
    roles = await _load_roles_of(db, user.id)
    return success(_user_to_out(user, roles).model_dump())


@router.post("/{user_id}/force-logout", summary="强制下线(bump token_version,使该用户所有旧 token 失效)")
async def force_logout(
    user_id: int = Path(..., ge=1),
    request: Request = None,  # type: ignore[assignment]
    current: CurrentUser = Depends(require_permission(Permissions.USER_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    user.token_version += 1
    await write_audit(
        db,
        resource_type=AuditResourceType.USER,
        action=AuditAction.FORCE_LOGOUT,
        user_id=current.id,
        user_email=current.email,
        resource_id=user_id,
        request=request,
        extra={"target_email": user.email, "new_token_version": user.token_version},
        commit=False,
    )
    await db.commit()
    return success(None)
