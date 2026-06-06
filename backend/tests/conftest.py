"""pytest fixtures(PostgreSQL · brew @16 端口 5433)。

每个测试隔离方案:
- 共用一个 test DB(默认 overseas_supply_test),每测试前 drop_all + create_all
- 启动同步 RBAC + seed 在 client fixture 内执行,httpx AsyncClient 直连 ASGI
- 不依赖 alembic 迁移 — 直接 Base.metadata.create_all,跑测试更快

测试 DB 覆盖:可通过环境变量 TEST_DATABASE_URL 覆盖默认 DSN。
"""
from __future__ import annotations

import os

# 测试环境必要变量(置默认值避免 .env 缺失)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-please-change-1234567890")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://liujingjing@localhost:5433/overseas_supply_test",
    ),
)
os.environ.setdefault("SUPER_ADMIN_EMAIL", "superadmin@platform.local")
os.environ.setdefault("SUPER_ADMIN_INITIAL_PASSWORD", "ChangeMe123")
# 测试默认开启 demo seed:大量已有用例依赖中建三局组织和 demo 账号
os.environ.setdefault("SEED_DEMO_ACCOUNTS", "true")

import asyncio  # noqa: E402
from typing import AsyncGenerator  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db import models as _models  # noqa: E402,F401  注册模型
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.rbac.sync import sync_rbac  # noqa: E402
from app.seed import run_all_seeds  # noqa: E402
from app.services.rate_limit import login_rate_limiter  # noqa: E402

TEST_DSN = os.environ["DATABASE_URL"]

# 引导管理员改密后的固定密码(测试用)
_BOOTSTRAP_NEW_PASSWORD = "TestNewPass_999!"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_engine():
    """每个测试函数:drop 全部表 → create 全部表 → 测后 drop。"""
    engine = create_async_engine(TEST_DSN, poolclass=None, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)

    # 同步 RBAC + 种子(测试库)
    async with SessionLocal() as db:
        await sync_rbac(db)
        # 品类 seed 已从 run_all_seeds 移除(改为手动脚本),测试中仍需种入
        from app.seed_categories import seed_categories
        await seed_categories(db)
        await run_all_seeds(db)

    async def override_get_db():
        async with SessionLocal() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    login_rate_limiter.clear_all()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    login_rate_limiter.clear_all()


@pytest_asyncio.fixture
async def superadmin_headers(client) -> dict[str, str]:
    """引导管理员:登录 → 改密(清 must_change_password)→ 重登,返回可用 headers。

    v0.1 加固后 must_change_password=True 的账号调非豁免端点会 403/40007,
    测试中需要先完成改密才能操作业务/系统 API。
    """
    from app.core.config import settings

    # 1. 初始登录
    r = await client.post(
        "/api/v1/auth/login",
        json={
            "identifier": settings.SUPER_ADMIN_EMAIL,
            "password": settings.SUPER_ADMIN_INITIAL_PASSWORD,
        },
    )
    assert r.status_code == 200
    token = r.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. 改密(豁免端点,must_change 期间可用)
    r2 = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "old_password": settings.SUPER_ADMIN_INITIAL_PASSWORD,
            "new_password": _BOOTSTRAP_NEW_PASSWORD,
        },
    )
    assert r2.status_code == 200

    # 3. 用新密码重新登录
    r3 = await client.post(
        "/api/v1/auth/login",
        json={"identifier": settings.SUPER_ADMIN_EMAIL, "password": _BOOTSTRAP_NEW_PASSWORD},
    )
    assert r3.status_code == 200
    new_token = r3.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {new_token}"}
