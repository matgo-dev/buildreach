# UT 性能优化工单

## 现状诊断

| 指标 | 当前值 | 目标 |
|---|---|---|
| 测试总数 | 508 | 不变 |
| 运行时间 | **5:20** (318s) | **< 90s** |
| schema 操作 | 每测试 drop_all + create_all (×508) | 全 session 仅 1 次 |
| RBAC + seed | 每个 `client` fixture 跑一次 (×275) | 全 session 仅 1 次 |
| 隔离方式 | 物理重建 schema | SAVEPOINT/ROLLBACK |

## 根因

1. **`test_engine` fixture 是 function scope** — 每个测试函数都执行 `drop_all` → `create_all` → 测后 `drop_all`，508 次 DDL 操作，每次 ~200ms+
2. **`client` fixture 每次都跑 `sync_rbac` + `seed_categories`(996 条) + `run_all_seeds`** — 每次 ~2s，275 个依赖 client 的测试 = ~550s 纯 seed 开销
3. **引擎 `poolclass=None` + 缺正确 dispose** — 产生协程 cancel warning

## 改造方案：session-scope schema + per-test SAVEPOINT

### 核心思路

```
session 开始
  ├── create_async_engine (一次)
  ├── Base.metadata.create_all (一次)
  ├── sync_rbac + seed_categories + run_all_seeds (一次)
  │
  ├── test_1: BEGIN → SAVEPOINT → 跑测试 → ROLLBACK TO SAVEPOINT → ROLLBACK
  ├── test_2: BEGIN → SAVEPOINT → 跑测试 → ROLLBACK TO SAVEPOINT → ROLLBACK
  ├── ...
  └── test_508: ...
  │
  └── Base.metadata.drop_all (一次)
      engine.dispose()
```

### 详细改造步骤（只改 `tests/conftest.py`）

#### Step 1 — session-scope engine + schema + seed

```python
@pytest_asyncio.fixture(scope="session")
async def _engine(event_loop):
    """session 级：建引擎、建表、跑 seed，全程仅一次。"""
    engine = create_async_engine(TEST_DSN, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # seed 一次
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as db:
        await sync_rbac(db)
        from app.seed_categories import seed_categories
        await seed_categories(db)
        await run_all_seeds(db)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

#### Step 2 — function-scope connection + SAVEPOINT 隔离

```python
@pytest_asyncio.fixture
async def _connection(_engine):
    """每个测试函数：一条连接 + 外层事务，测后回滚恢复到 seed 初始状态。"""
    async with _engine.connect() as conn:
        txn = await conn.begin()
        yield conn
        await txn.rollback()


@pytest_asyncio.fixture
async def db_session(_connection):
    """绑定到测试连接的 session，内部用 SAVEPOINT 再嵌套。"""
    session = AsyncSession(bind=_connection, expire_on_commit=False)
    nested = await _connection.begin_nested()  # SAVEPOINT
    try:
        yield session
    finally:
        if nested.is_active:
            await nested.rollback()
        await session.close()
```

#### Step 3 — client fixture 共享同一连接

```python
@pytest_asyncio.fixture
async def client(_connection) -> AsyncGenerator[AsyncClient, None]:
    """HTTP 测试客户端，get_db 覆写为从测试连接拿 session。"""

    async def override_get_db():
        session = AsyncSession(bind=_connection, expire_on_commit=False)
        nested = await _connection.begin_nested()
        try:
            yield session
        finally:
            if nested.is_active:
                await nested.rollback()
            await session.close()

    app.dependency_overrides[get_db] = override_get_db
    login_rate_limiter.clear_all()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    login_rate_limiter.clear_all()
```

#### Step 4 — 保留 `test_engine` 兼容 alias（给特殊测试用）

`test_seed_demo_switch.py` 等需要**全新 schema + 自行 seed** 的测试，不能用 SAVEPOINT 隔离（因为它们要测 seed 行为本身）。为这类测试保留一个 **function-scope 的干净引擎**：

```python
@pytest_asyncio.fixture
async def test_engine():
    """兼容旧签名：独立引擎 + 独立 schema，用于测 seed 行为等特殊场景。
    只有 test_seed_demo_switch.py 等少数文件引用。"""
    engine = create_async_engine(TEST_DSN, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
```

### 需要注意的坑

| 坑 | 解法 |
|---|---|
| `client` 内部请求走 `get_db` 拿到的 session 做了 `commit` | SAVEPOINT 下 `commit()` 实际只释放当前 SAVEPOINT，不会真正提交；需要确认 SQLAlchemy `begin_nested` + `commit` 的语义是否正确传导 |
| `db_session` 和 `client` 在同一个测试里混用时看不到彼此写入 | 两者必须绑定同一个 `_connection`，且 `client` 的 `override_get_db` 也用 `begin_nested` |
| `test_seed_demo_switch.py` 用 `monkeypatch` 改 settings 后重新 seed | 保留独立的 `test_engine` fixture，这 3 个测试走老路径 |
| session-scope fixture 内 `event_loop` 要匹配 | 已有 `scope="session"` 的 `event_loop` fixture |
| 并发跑 pytest-xdist 时 session-scope 冲突 | 本次不引入 xdist，单 worker 先优化到 90s 内；后续如需再加 xdist 用独立 DB per worker |

### 预期收益

- **schema DDL**: 508 次 → 1 次 ≈ 节省 ~100s
- **seed**: 275 次 → 1 次 ≈ 节省 ~200s+
- **SAVEPOINT/ROLLBACK**: 每次 < 1ms，508 次 ≈ 忽略不计
- **预计总耗时**: 318s → **60-90s**

### 验证标准

1. `pytest` 全量通过，0 error 0 fail
2. 运行时间 < 90s
3. 无 `RuntimeWarning: coroutine ... was never awaited`
4. `test_seed_demo_switch.py` 3 个测试仍然独立跑 seed，不受 session-scope 影响

### 实现范围

- **只改** `tests/conftest.py`
- 测试文件签名不变（`client`、`db_session`、`test_engine`、`superadmin_headers` 都保留）
- 零侵入，不改任何测试文件
