"""pytest fixtures（PostgreSQL · brew @16 端口 5433）。

隔离方案（SAVEPOINT 优化版，从 5min+ 降到 ~1min）:
- session-scope: 一个引擎 + 一次 schema 创建 + 一次 RBAC/seed
- function-scope: 每测试一条连接 + 外层事务 + SAVEPOINT，测后回滚到 seed 初始态
- 不依赖 alembic 迁移 — 直接 Base.metadata.create_all

事件循环: pyproject.toml 设置 asyncio_default_fixture_loop_scope = "session"，
所有 fixture 和测试共享同一个 session-scope 事件循环。
测试 DB 覆盖: 可通过环境变量 TEST_DATABASE_URL 覆盖默认 DSN。
"""
from __future__ import annotations

import os

# 测试环境必要变量（置默认值避免 .env 缺失）
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
# 测试默认开启 demo seed：大量已有用例依赖中建三局组织和 demo 账号
os.environ.setdefault("SEED_DEMO_ACCOUNTS", "true")

from typing import AsyncGenerator  # noqa: E402

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base  # noqa: E402
from app.db import models as _models  # noqa: E402,F401  注册模型
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.rbac.sync import sync_rbac  # noqa: E402
from app.seed import run_all_seeds  # noqa: E402
from app.services.rate_limit import login_rate_limiter  # noqa: E402

# 测试引擎使用 psycopg 驱动（asyncpg 的 task 亲和性限制
# 导致 Starlette BaseHTTPMiddleware 新 task 中无法复用同一连接，
# psycopg3 async 无此限制，可安全跨 task 共享连接实现 SAVEPOINT 隔离）
_raw_dsn = os.environ["DATABASE_URL"]
TEST_DSN = _raw_dsn.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)

# 引导管理员改密后的固定密码（测试用）
_BOOTSTRAP_NEW_PASSWORD = "TestNewPass_999!"


# ─── session-scope: 引擎 + schema + seed（仅一次）───────────────

@pytest_asyncio.fixture(scope="session")
async def _engine():
    """全 session 共用：建引擎、建表、跑 RBAC+seed，仅一次。"""
    engine = create_async_engine(TEST_DSN, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    _Session = async_sessionmaker(engine, expire_on_commit=False)
    async with _Session() as db:
        await sync_rbac(db)
        from app.seed_categories import seed_categories
        await seed_categories(db)
        await run_all_seeds(db)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ─── function-scope: 每测试一条连接 + 事务回滚隔离 ────────────

@pytest_asyncio.fixture
async def _connection(_engine) -> AsyncGenerator[AsyncConnection, None]:
    """每个测试函数：一条连接 + 外层事务，测后回滚恢复到 seed 初始状态。"""
    async with _engine.connect() as conn:
        txn = await conn.begin()
        yield conn
        await txn.rollback()


def _add_savepoint_listener(async_session: AsyncSession) -> None:
    """让 session.commit() 释放 SAVEPOINT 后自动开启新 SAVEPOINT。

    这样 service 代码里的 db.commit() 只释放 SAVEPOINT 而非真正提交，
    且后续操作仍在 SAVEPOINT 保护下。
    """
    @event.listens_for(async_session.sync_session, "after_transaction_end")
    def restart_savepoint(session, transaction):  # type: ignore[no-untyped-def]
        if transaction.nested and not transaction._parent.nested:
            session.begin_nested()


@pytest_asyncio.fixture
async def db_session(_connection) -> AsyncGenerator[AsyncSession, None]:
    """绑定到测试连接的 session，SAVEPOINT 隔离。

    - flush() 或 commit() 都安全：commit 只释放 SAVEPOINT，listener 自动续建
    - 与 client 共享同一 _connection，数据互通
    """
    await _connection.begin_nested()
    session = AsyncSession(bind=_connection, expire_on_commit=False)
    _add_savepoint_listener(session)
    yield session
    await session.close()


@pytest_asyncio.fixture
async def client(_connection) -> AsyncGenerator[AsyncClient, None]:
    """HTTP 测试客户端，get_db 覆写为从测试连接拿 SAVEPOINT session。"""

    async def override_get_db():
        await _connection.begin_nested()
        session = AsyncSession(bind=_connection, expire_on_commit=False)
        _add_savepoint_listener(session)
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    app.dependency_overrides[get_db] = override_get_db
    login_rate_limiter.clear_all()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    login_rate_limiter.clear_all()


def _make_test_image(w: int = 300, h: int = 300) -> bytes:
    """生成最小合法测试图片(300x300 JPEG)。"""
    from io import BytesIO
    from PIL import Image
    img = Image.new("RGB", (w, h), (128, 128, 128))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


_TEST_PHONE_COUNTER = 700000000


def _next_phone() -> str:
    """每次调用生成唯一的坦桑手机号。"""
    global _TEST_PHONE_COUNTER
    _TEST_PHONE_COUNTER += 1
    return f"+255{_TEST_PHONE_COUNTER}"


async def register_buyer_tz(
    client,
    *,
    phone: str | None = None,
    password: str = "Aa123456789!",
    name: str = "Test User",
    company_name: str = "Test Shop",
    address: str = "Dar es Salaam",
    email: str | None = None,
    cat_code: str = "01",
) -> dict:
    """注册坦桑买方,返回 response JSON。

    默认使用 L1 品类 code "01",conftest 中 seed_categories 保证存在。
    """
    if phone is None:
        phone = _next_phone()
    img = _make_test_image()
    data = {
        "phone": phone,
        "password": password,
        "name": name,
        "company_name": company_name,
        "address": address,
        "business_category_codes": cat_code,
    }
    if email:
        data["email"] = email
    r = await client.post(
        "/api/v1/auth/register/buyer",
        data=data,
        files=[("storefront_images", ("shop.jpg", img, "image/jpeg"))],
    )
    return {"response": r, "phone": phone, "password": password, "email": email}


@pytest_asyncio.fixture
async def superadmin_headers(client) -> dict[str, str]:
    """引导管理员：登录 → 改密（清 must_change_password）→ 重登，返回可用 headers。

    v0.1 加固后 must_change_password=True 的账号调非豁免端点会 403/40007，
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

    # 2. 改密（豁免端点，must_change 期间可用）
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


