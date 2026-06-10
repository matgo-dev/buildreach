"""T6 · demo seed 开关化测试。

直接调 seed 函数,不通过 client fixture（client fixture 强制开启 demo seed）。
使用 db_session: TRUNCATE 清空 → 自行 seed → 验证 → SAVEPOINT 回滚恢复 seed 初始态。
"""
from __future__ import annotations

import pytest
from sqlalchemy import select, text

from app.core.config import settings
from app.db.base import Base
from app.db.models.buyer_organization import BuyerOrganization
from app.db.models.user import User
from app.rbac.sync import sync_rbac
from app.seed import run_all_seeds


async def _truncate_all(db_session) -> None:
    """TRUNCATE 所有表，为 seed 行为测试准备干净环境。"""
    tables = ", ".join(Base.metadata.tables.keys())
    await db_session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.mark.asyncio
async def test_seed_demo_off_only_super_admin(db_session, monkeypatch):
    """SEED_DEMO_ACCOUNTS=false → 仅 super_admin,无中建三局,无 demo 账号。"""
    await _truncate_all(db_session)
    monkeypatch.setattr(settings, "SEED_DEMO_ACCOUNTS", False)

    await sync_rbac(db_session)
    await run_all_seeds(db_session)

    users = (await db_session.execute(select(User))).scalars().all()
    emails = {u.email for u in users}
    assert settings.SUPER_ADMIN_EMAIL in emails
    assert "admin@platform.local" not in emails
    assert "operator@platform.local" not in emails
    assert "buyer@cscec3b.local" not in emails

    orgs = (await db_session.execute(select(BuyerOrganization))).scalars().all()
    assert orgs == [], "demo 关闭时不应种入任何 BuyerOrganization"


@pytest.mark.asyncio
async def test_seed_demo_on_creates_full_demo_set(db_session, monkeypatch):
    """SEED_DEMO_ACCOUNTS=true → 中建三局 + admin/operator/buyer 全齐。"""
    await _truncate_all(db_session)
    monkeypatch.setattr(settings, "SEED_DEMO_ACCOUNTS", True)

    await sync_rbac(db_session)
    await run_all_seeds(db_session)

    emails = {u.email for u in (await db_session.execute(select(User))).scalars().all()}
    for expected in (
        settings.SUPER_ADMIN_EMAIL,
        "admin@platform.local",
        "operator@platform.local",
        "buyer@cscec3b.local",
    ):
        assert expected in emails, f"demo 开启时应种入 {expected}"

    orgs = (await db_session.execute(select(BuyerOrganization))).scalars().all()
    assert len(orgs) == 1
    assert orgs[0].code == "CSCEC3B"
    assert orgs[0].unified_social_credit_code == "91420100MA4KXXXX01"


@pytest.mark.asyncio
async def test_seed_is_idempotent(db_session, monkeypatch):
    """重复执行 run_all_seeds 不产生重复账号或组织。"""
    await _truncate_all(db_session)
    monkeypatch.setattr(settings, "SEED_DEMO_ACCOUNTS", True)

    await sync_rbac(db_session)
    await run_all_seeds(db_session)
    await run_all_seeds(db_session)  # 第二次

    users = (await db_session.execute(select(User))).scalars().all()
    emails = [u.email for u in users]
    assert len(emails) == len(set(emails)), "重复 seed 不应产生重复用户"

    orgs = (await db_session.execute(select(BuyerOrganization))).scalars().all()
    assert len(orgs) == 1
