"""启动种子。

- 中建三局 BuyerOrganization(演示用,带占位 USC)
- 引导管理员(env 注入,must_change_password=true,绝不覆盖已有)

注:register_buyer 不再依赖此种子组织,信用代码识别企业。中建三局组织保留
仅为本地演示便利;生产应通过 SEED_DEMO_ACCOUNTS 开关关闭(T6 引入)。
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.constants import AuditAction, AuditResourceType
from app.audit.logger import write_audit
from app.core.config import settings
from app.core.security import hash_password
from app.db.models.buyer_organization import BuyerOrganization, BuyerOrgStatus
from app.db.models.role import Role, RoleCode
from app.db.models.user import User, UserStatus
from app.db.models.user_role import UserRole

logger = logging.getLogger(__name__)

# 中建三局 demo 组织标识(seed 内部使用)
CSCEC3B_CODE = "CSCEC3B"
# 占位信用代码:18 位假数据,仅 demo seed 使用
CSCEC3B_USC_PLACEHOLDER = "91420100MA4KXXXX01"
_UNSAFE_BOOTSTRAP_PASSWORDS = {
    "",
    "Aa123456789",
    "ChangeMe123",
    "CHANGEME_set_strong_initial_password",
}


def _assert_safe_bootstrap_password() -> None:
    """阻断生产首启时使用代码内置/模板默认的超级管理员密码。"""
    password = settings.SUPER_ADMIN_INITIAL_PASSWORD.strip()
    if password in _UNSAFE_BOOTSTRAP_PASSWORDS or password.upper().startswith("CHANGEME"):
        raise RuntimeError(
            "SUPER_ADMIN_INITIAL_PASSWORD must be set to a unique strong password "
            "before bootstrap admin can be created."
        )


async def seed_buyer_org(db: AsyncSession) -> None:
    """种入中建三局 demo BuyerOrg(含占位信用代码)。

    幂等:已存在则跳过。
    """
    row = await db.execute(
        select(BuyerOrganization).where(BuyerOrganization.code == CSCEC3B_CODE)
    )
    if row.scalar_one_or_none() is not None:
        return
    db.add(BuyerOrganization(
        name="中建三局",
        code=CSCEC3B_CODE,
        unified_social_credit_code=CSCEC3B_USC_PLACEHOLDER,
        description="中国建筑第三工程局有限公司(MVP 演示用,信用代码为占位假数据)",
        status=BuyerOrgStatus.ACTIVE,
    ))
    await db.commit()
    logger.warning(
        "Seed: BuyerOrganization '中建三局' created (USC=%s). "
        "**仅用于开发演示,生产环境务必删除**",
        CSCEC3B_USC_PLACEHOLDER,
    )


async def _seed_internal_account(
    db: AsyncSession,
    *,
    email: str,
    username: str,
    name: str,
    password: str,
    role_code: str,
) -> None:
    """通用:创建一个内部账号(若已存在 email 或 username 则跳过)。"""
    row = await db.execute(
        select(User).where((User.email == email) | (User.username == username))
    )
    if row.scalar_one_or_none() is not None:
        logger.info("Seed: demo internal account %s already exists — kept as-is.", email)
        return

    role_row = await db.execute(select(Role).where(Role.code == role_code))
    role = role_row.scalar_one_or_none()
    if role is None:
        logger.error("Seed: %s role missing, did rbac sync run first?", role_code)
        return

    user = User(
        email=email,
        username=username,
        name=name,
        password_hash=hash_password(password),
        status=UserStatus.ACTIVE,
        must_change_password=False,  # demo 账号,跳过强制改密以方便体验
    )
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))

    await write_audit(
        db,
        resource_type=AuditResourceType.USER,
        action=AuditAction.REGISTER,
        user_id=user.id,
        user_email=user.email,
        resource_id=user.id,
        extra={"reason": "seed_demo_internal", "role": role_code},
        commit=False,
    )
    await db.commit()
    logger.warning(
        "Seed: demo %s account created — email=%s username=%s. "
        "**仅用于开发演示,生产环境务必删除或改密**",
        role_code, email, username,
    )


async def seed_demo_internal_accounts(db: AsyncSession) -> None:
    """创建 demo ADMIN / OPERATOR 各一个,方便快速进各工作台体验。"""
    await _seed_internal_account(
        db,
        email="admin@platform.local",
        username="admin",
        name="演示管理员",
        password="Aa123456789",
        role_code=RoleCode.ADMIN,
    )
    await _seed_internal_account(
        db,
        email="operator@platform.local",
        username="operator",
        name="演示运营",
        password="Aa123456789",
        role_code=RoleCode.OPERATOR,
    )


async def seed_demo_buyer_account(db: AsyncSession) -> None:
    """在中建三局 BuyerOrg 下创建 demo BUYER 账号 buyer@cscec3b.local。

    依赖 seed_buyer_org 先行(取该组织的 id);幂等。
    """
    from app.db.models.buyer_member import BuyerMember

    email = "buyer@cscec3b.local"
    username = "buyer"

    row = await db.execute(
        select(User).where((User.email == email) | (User.username == username))
    )
    if row.scalar_one_or_none() is not None:
        logger.info("Seed: demo buyer account %s already exists — kept as-is.", email)
        return

    org_row = await db.execute(
        select(BuyerOrganization).where(BuyerOrganization.code == CSCEC3B_CODE)
    )
    org = org_row.scalar_one_or_none()
    if org is None:
        logger.error("Seed: 中建三局 BuyerOrg missing, did seed_buyer_org run first?")
        return

    role_row = await db.execute(select(Role).where(Role.code == RoleCode.BUYER))
    role = role_row.scalar_one_or_none()
    if role is None:
        logger.error("Seed: BUYER role missing, did rbac sync run first?")
        return

    user = User(
        email=email,
        username=username,
        name="演示采购员",
        password_hash=hash_password("Aa123456789"),
        status=UserStatus.ACTIVE,
        must_change_password=False,
    )
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.add(BuyerMember(user_id=user.id, buyer_org_id=org.id, is_owner=False))

    await write_audit(
        db,
        resource_type=AuditResourceType.USER,
        action=AuditAction.REGISTER,
        user_id=user.id,
        user_email=user.email,
        resource_id=user.id,
        extra={"reason": "seed_demo_buyer", "role": RoleCode.BUYER, "buyer_org_id": org.id},
        commit=False,
    )
    await db.commit()
    logger.warning(
        "Seed: demo BUYER account created — email=%s. **仅用于开发演示,生产环境务必删除**",
        email,
    )


async def seed_bootstrap_admin(db: AsyncSession) -> None:
    """种入引导管理员(env 注入密码,must_change_password=True)。

    幂等:已存在则跳过。环境变量键名不变(SUPER_ADMIN_*)。
    """
    email = settings.SUPER_ADMIN_EMAIL
    row = await db.execute(select(User).where(User.email == email))
    if row.scalar_one_or_none() is not None:
        logger.info("Seed: bootstrap admin %s already exists — kept as-is.", email)
        return
    _assert_safe_bootstrap_password()

    role_row = await db.execute(select(Role).where(Role.code == RoleCode.ADMIN))
    admin_role = role_row.scalar_one_or_none()
    if admin_role is None:
        logger.error("Seed: ADMIN role missing, did rbac sync run first?")
        return

    user = User(
        email=email,
        name="Bootstrap Admin",
        password_hash=hash_password(settings.SUPER_ADMIN_INITIAL_PASSWORD),
        status=UserStatus.ACTIVE,
        must_change_password=True,
    )
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=admin_role.id))

    await write_audit(
        db,
        resource_type=AuditResourceType.USER,
        action=AuditAction.REGISTER,
        user_id=user.id,
        user_email=user.email,
        resource_id=user.id,
        extra={"reason": "seed_bootstrap_admin", "role": RoleCode.ADMIN},
        commit=False,
    )
    await db.commit()
    logger.warning(
        "Seed: bootstrap admin %s created with initial password from env. "
        "**MUST change password on first login**.",
        email,
    )


async def seed_glossary(db: AsyncSession) -> None:
    """术语表种子:建材行业常用术语(先查后写,幂等)。"""
    from app.db.models.translation_glossary import TranslationGlossary
    from sqlalchemy import select

    seeds = [
        ("zh", "en", "铝卷", "Aluminum Coil", "building_materials"),
        ("zh", "en", "螺纹钢", "Rebar", "building_materials"),
        ("zh", "en", "工字钢", "I-Beam", "building_materials"),
        ("zh", "en", "热轧", "Hot-Rolled", "building_materials"),
        ("zh", "en", "镀锌板", "Galvanized Sheet", "building_materials"),
        ("zh", "en", "角钢", "Angle Steel", "building_materials"),
        ("zh", "en", "水泥", "Cement", "building_materials"),
        ("zh", "en", "钢筋", "Steel Bar", "building_materials"),
    ]
    for src_l, tgt_l, src_t, tgt_t, domain in seeds:
        exists = await db.execute(
            select(TranslationGlossary).where(
                TranslationGlossary.source_locale == src_l,
                TranslationGlossary.target_locale == tgt_l,
                TranslationGlossary.source_term == src_t,
            )
        )
        if exists.scalar_one_or_none():
            continue
        db.add(TranslationGlossary(
            source_locale=src_l, target_locale=tgt_l,
            source_term=src_t, target_term=tgt_t, domain=domain,
        ))
    await db.commit()
    logger.info("Seed: glossary terms synced.")


async def run_all_seeds(db: AsyncSession) -> None:
    """启动种子总入口。

    - 引导管理员:始终种入(生产唯一保留项)
    - 术语表:始终种入
    - demo 内容(中建三局 / admin / operator / buyer demo 账号):
      仅当 settings.SEED_DEMO_ACCOUNTS=true 时种入
    """
    await seed_bootstrap_admin(db)
    await seed_glossary(db)
    if settings.SEED_DEMO_ACCOUNTS:
        await seed_buyer_org(db)
        await seed_demo_internal_accounts(db)
        await seed_demo_buyer_account(db)
        # 信用评估:评分模型骨架 + 4 家 demo 企业(工单 §C3)
        from app.seed_credit import seed_credit_module

        await seed_credit_module(db)
    else:
        logger.info(
            "Seed: SEED_DEMO_ACCOUNTS=false → 跳过 demo 内容(中建三局组织 / "
            "admin / operator / buyer demo 账号 / 信用评估 demo 企业)"
        )
