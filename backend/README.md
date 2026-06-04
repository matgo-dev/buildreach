# Backend · 认证 / RBAC / 审计底座

> FastAPI + SQLAlchemy 2.0(async) + Alembic + **PostgreSQL 16** + uv

## 快速开始

```bash
# 0. PostgreSQL(本机 brew @16,端口 5433 避开 EnterpriseDB pg13)
brew install postgresql@16
brew services start postgresql@16
# 改 /opt/homebrew/var/postgresql@16/postgresql.conf 里 port=5433,然后重启
/opt/homebrew/opt/postgresql@16/bin/createdb -p 5433 overseas_supply_dev
/opt/homebrew/opt/postgresql@16/bin/createdb -p 5433 overseas_supply_test

cd backend

# 1. 装依赖(uv)
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env:必须生成 JWT_SECRET_KEY,可改 SUPER_ADMIN_*
#   openssl rand -hex 32

# 3. 跑迁移
alembic upgrade head

# 4. 启动
uvicorn app.main:app --reload --port 8000
# 文档:http://localhost:8000/docs
# 健康:http://localhost:8000/healthz
```

启动时会自动:
- 同步 Role / Permission / RolePermission(来自 `app/rbac/permissions_config.py`)
- 创建 super admin(若不存在,`must_change_password=true`,**始终种入**)
- 当 `SEED_DEMO_ACCOUNTS=true` 时,额外种入:
  - 中建三局 BuyerOrganization(占位信用代码 `91420100MA4KXXXX01`)
  - demo ADMIN `admin@platform.local` / OPERATOR `operator@platform.local`
  - demo BUYER `buyer@cscec3b.local`(挂在中建三局下)

### `SEED_DEMO_ACCOUNTS` 开关

| 环境 | 取值 | 说明 |
|---|---|---|
| 本地开发 | `true`(推荐) | 一键拉起所有 demo 账号,方便逐角色体验 |
| 生产部署 | `false`(**必须**) | 杜绝 demo 账号入网;super admin 仍会种入 |

#### 误种了 demo 数据怎么清?

部署到生产前若 `SEED_DEMO_ACCOUNTS` 曾被打开,手工清理 SQL:

```sql
DELETE FROM audit_logs WHERE user_email IN
  ('admin@platform.local','operator@platform.local','buyer@cscec3b.local');
DELETE FROM user_roles WHERE user_id IN (
  SELECT id FROM users WHERE email IN
    ('admin@platform.local','operator@platform.local','buyer@cscec3b.local')
);
DELETE FROM buyer_members WHERE user_id IN (
  SELECT id FROM users WHERE email = 'buyer@cscec3b.local'
);
DELETE FROM users WHERE email IN
  ('admin@platform.local','operator@platform.local','buyer@cscec3b.local');
DELETE FROM buyer_organizations WHERE code = 'CSCEC3B';
```

## 测试

```bash
pytest                 # 全部
pytest -k auth         # 子集
pytest --cov=app       # 覆盖率
```

测试连 `overseas_supply_test` 库,每个测试函数 drop+create,完全隔离 `overseas_supply_dev`。

## curl 自检

```bash
# 服务启动后另起终端
bash scripts/verify.sh
```

## 数据库重置(只用于开发)

```bash
bash scripts/reset_db.sh   # drop + create overseas_supply_dev → 重跑迁移
```

## 关键设计

| 维度 | 实现 |
|---|---|
| 数据库 | PostgreSQL 16 + asyncpg(本机 brew 端口 5433)。**禁止厂商特有语法**,保 ORM 抽象。 |
| 时间 | 应用层强制 UTC(`datetime.now(timezone.utc)`)|
| 密码 | bcrypt(passlib),规则 11-50 位 + 数字/大写/小写/特殊字符至少 3 类(PRD v1.4 Δ1)|
| JWT | HS256,access 15min / refresh 7d,**不放 permissions**(走 `/auth/me`)|
| 限流 | 进程内 dict,`(email, ip)` 维度,60s 内 5 次失败锁 5 分钟 |
| RBAC | 配置文件(`app/rbac/permissions_config.py`)+ 启动同步到数据库(TODO(Q22))|
| 审计 | 只记敏感写操作 + 登录相关,GET 不记 |
| Trace ID | `X-Trace-Id` 中间件 + contextvar,所有日志和审计自动带 |

## 接口速览

| Method | Path | 权限 |
|---|---|---|
| POST | `/api/v1/auth/register/buyer` | public |
| POST | `/api/v1/auth/register/supplier` | public |
| POST | `/api/v1/auth/login` | public |
| GET | `/api/v1/auth/me` | 任意登录 |
| POST | `/api/v1/auth/logout` | `auth:logout` |
| POST | `/api/v1/auth/change-password` | 任意登录 |
| POST | `/api/v1/admin/users` | `user:create`(ADMIN)|
| GET | `/api/v1/admin/users` | `user:read`(ADMIN/OPERATOR)|
| GET | `/api/v1/test/{role}-only` | 对应角色 |

## 统一响应

成功:
```json
{ "code": 0, "message": "ok", "data": { ... } }
```

失败:
```json
{ "code": 40001, "message": "Invalid credentials", "data": null, "trace_id": "abc-123" }
```

任一响应都带 `X-Trace-Id` 响应头。

## 目录结构

```
app/
├── core/         配置 / 安全 / 异常 / 依赖 / 日志
├── db/           Base / Session / models(10 张表)
├── schemas/      Pydantic
├── api/v1/       路由(auth / admin_users / test_rbac)
├── services/     业务逻辑(auth / user / 限流)
├── rbac/         constants / permissions_config / guards / sync
├── audit/        constants / middleware / logger / context
├── seed.py       中建三局 + super admin
└── main.py       FastAPI 装配
```

## 待团队拍板的设计决策(代码中已 `TODO(Qxx)` 标注)

| 决策点 | 当前方案 | 位置 |
|---|---|---|
| Q22 角色-权限关系定义方式 | 配置文件 + 启动同步 | `app/rbac/permissions_config.py` |
| Q23 Role.scope 字段 | 引入字段,MVP 仅 GLOBAL | `app/db/models/role.py` |
| Q24 OPERATOR 是否细分 | 不细分 | `app/rbac/permissions_config.py` |
| Q25 ADMIN 业务数据访问 | 严格分离 | `app/rbac/permissions_config.py` |
| Q26 super admin 密码策略 | 环境变量注入 + 强制改密 | `app/seed.py` |
| Q27 何时切 PostgreSQL | ✅ 已切(2026-05-18) | `app/db/session.py` |
