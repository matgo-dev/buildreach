"""FastAPI 依赖:从 JWT 解析当前用户,带 roles + permissions。"""
from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountDisabledError, NotAuthenticatedError
from app.core.security import decode_token
from app.db.models.buyer_member import BuyerMember
from app.db.models.buyer_organization import BuyerOrganization
from app.db.models.permission import Permission
from app.db.models.role import Role
from app.db.models.role_permission import RolePermission
from app.db.models.supplier_member import SupplierMember
from app.db.models.supplier_organization import SupplierOrganization
from app.db.models.user import User, UserStatus
from app.db.models.user_role import UserRole
from app.db.session import get_db

# tokenUrl 仅用于 OpenAPI 文档展示,真实登录走 /api/v1/auth/login
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)


@dataclass
class OrganizationInfo:
    type: str  # "BUYER_ORG" / "SUPPLIER_ORG"
    id: int
    name: str
    is_owner: bool
    status: str | None = None
    unified_social_credit_code: str | None = None


@dataclass
class CurrentUser:
    id: int
    email: str
    username: str | None
    name: str
    phone: str | None
    status: str
    must_change_password: bool
    language_preference: str | None = None
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    organization: OrganizationInfo | None = None
    # 该用户的买方组织成员关系条数。organization 取 owner 优先的第一条;>1 时各入口自决:
    # 授权敏感路径(如订单)拒绝多组织(buyer_org_binding),浏览类入口暂沿用第一条(契约 §9 留白)。
    buyer_org_count: int = 0


async def _load_roles_and_permissions(
    db: AsyncSession, user_id: int
) -> tuple[list[str], list[str]]:
    role_rows = await db.execute(
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    role_codes = sorted({r for r in role_rows.scalars().all()})

    if not role_codes:
        return [], []

    perm_rows = await db.execute(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .where(Role.code.in_(role_codes))
        .distinct()
    )
    perm_codes = sorted({p for p in perm_rows.scalars().all()})
    return role_codes, perm_codes


async def _load_organization(
    db: AsyncSession, user_id: int, role_codes: list[str]
) -> tuple[OrganizationInfo | None, int]:
    """根据角色加载关联组织,返回 (组织, 买方成员关系条数)。

    BUYER → 一次取全部 buyer_members(每用户个位数),owner 优先、其次最早加入,取第一条;
    条数交给各入口决定多组织怎么办。SUPPLIER → SupplierMember 同序取一条。其他 (None, 0)。
    """
    if "BUYER" in role_codes:
        rows = (await db.execute(
            select(BuyerMember, BuyerOrganization)
            .join(BuyerOrganization, BuyerOrganization.id == BuyerMember.buyer_org_id)
            .where(BuyerMember.user_id == user_id)
            .order_by(BuyerMember.is_owner.desc(), BuyerMember.id)
        )).all()
        if rows:
            member, org = rows[0]
            return OrganizationInfo(
                type="BUYER_ORG", id=org.id, name=org.name,
                is_owner=member.is_owner, status=org.status,
                unified_social_credit_code=org.unified_social_credit_code,
            ), len(rows)
    if "SUPPLIER" in role_codes:
        row = await db.execute(
            select(SupplierMember, SupplierOrganization)
            .join(SupplierOrganization, SupplierOrganization.id == SupplierMember.supplier_org_id)
            .where(SupplierMember.user_id == user_id)
            .order_by(SupplierMember.is_owner.desc(), SupplierMember.id)
            .limit(1)
        )
        record = row.first()
        if record:
            member, org = record
            return OrganizationInfo(
                type="SUPPLIER_ORG", id=org.id, name=org.name,
                is_owner=member.is_owner, status=org.status,
            ), 0
    return None, 0


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    if not token:
        raise NotAuthenticatedError()
    try:
        payload = decode_token(token, expected_type="access")
    except JWTError:
        raise NotAuthenticatedError("Invalid token")

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        raise NotAuthenticatedError("Invalid token payload")
    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        raise NotAuthenticatedError("Invalid token payload")

    user = await db.get(User, user_id)
    if user is None:
        raise NotAuthenticatedError("User not found")
    if user.status == UserStatus.DISABLED:
        raise AccountDisabledError()
    # DEACTIVATED:token_version +1 后旧 token 已失效,下面 tv 校验会拦截;
    # 此处兜底确保新 token_version 签出前也无法访问
    if user.status == UserStatus.DEACTIVATED:
        from app.core.exceptions import AccountDeactivatedError
        raise AccountDeactivatedError()

    # token_version 校验:tv 不匹配 → 旧 token 已被吊销(改密/强制下线)
    if int(payload.get("tv", -1)) != user.token_version:
        raise NotAuthenticatedError("Token revoked")

    role_codes, perm_codes = await _load_roles_and_permissions(db, user.id)
    org, buyer_org_count = await _load_organization(db, user.id, role_codes)

    return CurrentUser(
        id=user.id,
        email=user.email,
        username=user.username,
        name=user.name,
        phone=user.phone,
        status=user.status,
        must_change_password=user.must_change_password,
        language_preference=user.language_preference,
        roles=role_codes,
        permissions=perm_codes,
        organization=org,
        buyer_org_count=buyer_org_count,
    )
