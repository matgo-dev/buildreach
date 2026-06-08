# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 项目简介

**BuildLink East Africa — 东非建筑工业品数字供应链平台**

连接中国建材供应商与东非买家的 B2B 数字供应链平台。平台作为第三方枢纽，集中采购、拼箱打包、统一报关发货。

平台核心能力:
1. **建材商城** —— 面向东非买方的 B2B 商城,9 大品类、品类导航、询价
2. **运营管控后台** —— 商品上架、询价管理、订单管理、拼箱物流
3. **i18n 多语言** —— 中英双语底座,分列存储 + 翻译状态机

**当前阶段**:
- ✅ 已完成：认证、RBAC、审计底座、i18n 底座
- 🚧 进行中：功能模块开发（商品中心、询价、订单等）

---

**遇到设计未覆盖时**:选**最简方案** + 代码标注 `TODO: 设计未覆盖,采用最简实现`，**绝不**自行扩展功能或发明新规则。

---

## 技术栈(已锁定,不要替换)

### 后端

| 类目 | 选型 |
|---|---|
| 语言 | Python 3.11+ |
| Web 框架 | FastAPI |
| ORM | SQLAlchemy 2.0(async) |
| 迁移 | Alembic |
| 数据库 | **PostgreSQL 16**(本机 brew 安装,端口 5433 — 避开 EnterpriseDB pg13 默认 5432)|
| 数据库 — dev 库 | `buildlink_ea_dev` |
| 数据库 — test 库 | `buildlink_ea_test` |
| 数据库驱动 | asyncpg(async)+ psycopg(alembic 同步用)|
| 校验 | Pydantic v2 |
| JWT | python-jose[cryptography] |
| 密码 | passlib[bcrypt] |
| 配置 | pydantic-settings |
| 测试 | pytest + httpx + pytest-asyncio |
| 包管理 | **uv** |

### 前端

| 类目 | 选型 |
|---|---|
| 框架 | Next.js (App Router) + TypeScript |
| UI | Tailwind CSS + Radix UI (shadcn 风格) |
| 状态 | Zustand |
| 表单 | react-hook-form + zod |
| 数据请求 | fetch + SWR |
| 包管理 | pnpm |

### 不允许引入的依赖

- ❌ MySQL / MongoDB(已选 PostgreSQL,不要再换)
- ❌ NextAuth.js(我们直接管 token)
- ❌ Prisma(后端是 FastAPI + SQLAlchemy)
- ❌ Redis(MVP 单机内存足够)
- ⚠️ OAuth / SSO / 2FA / 邮件 / 短信 — 当前不需要，后续如需邮箱验证等再按需引入
- ❌ K8s / Swarm / 镜像 registry(单机 compose 足够)
- ⚠️ Nginx / HTTPS / 域名 — 海外部署时需要，部署方案待定

**注**:Docker / docker-compose 已用于部署(见「部署架构」章节),
但**本地开发不要走 Docker**,仍用 `uvicorn --reload` + `pnpm dev`。

---

## 项目结构

```
buildlink-ea/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/               # config / security / i18n / locale / exceptions
│   │   ├── db/                 # ORM 模型 / i18n_mixin / 迁移
│   │   ├── schemas/            # Pydantic
│   │   ├── api/v1/             # 路由（按模块拆分）
│   │   ├── services/           # 业务逻辑 / 翻译服务
│   │   ├── rbac/               # 权限配置 / Guard / 同步
│   │   ├── audit/              # 审计中间件
│   │   └── seed.py             # 启动种子
│   ├── alembic/                # 数据库迁移
│   ├── tests/
│   └── scripts/
├── frontend/
│   ├── src/
│   │   ├── app/[locale]/       # 页面（next-intl 路由）
│   │   ├── components/         # UI 组件 / i18n 组件
│   │   ├── lib/                # API 封装 / 格式化工具
│   │   ├── i18n/               # 路由配置 / locale 映射
│   │   ├── stores/             # Zustand
│   │   └── middleware.ts
│   └── messages/               # zh.json / en.json
├── deploy/                     # 部署脚本
├── CLAUDE.md                   # 本文件
└── docker-compose.yml
```

---

## 核心设计原则(贯穿全项目)

### 1. 最小可行性(MVP 第一原则)

- 设计文档没列出的功能**一律不实现**
- 不擅自扩展需求
- V1.0 / V2.0 增量功能**全部不做**

### 2. 角色与组织(详见 RBAC 文档)

**4 个系统角色**(固定):
- `BUYER` — 买方(挂 BuyerOrganization)
- `SUPPLIER` — 供应商(挂 SupplierOrganization)
- `OPERATOR` — 平台运营(不挂组织,业务管理员)
- `ADMIN` — 系统管理员(不挂组织,**不触碰业务数据**)

**2 个组织实体**:
- `BuyerOrganization` — 买方组织
- `SupplierOrganization` — 供应商组织

**关键约束**:
- 任何业务数据查询必须按 Organization 边界过滤(BUYER 查 `buyer_org_id`,SUPPLIER 查 `supplier_id`)
- OPERATOR 全平台业务数据可见,但不能改系统配置
- ADMIN 只能改系统配置,**不能**访问业务数据

### 3. RBAC 标准化(详见 RBAC 文档)

**5 张标准 RBAC0 表**:User / Role / Permission / UserRole / RolePermission

**权限点命名**:`resource:action`,小写冒号分隔(如 `user:read`、`supplier:approve`)

**权限校验三级**:
- 后端 API Guard(`require_permission(code)`,**安全底线**)
- 前端路由守卫(`middleware.ts`)
- 前端按钮显隐(`<PermissionGuard>` / `usePermissions().hasPermission()`)

**绝对禁止**:
- ❌ 在业务代码里 `if role == 'BUYER'` 写死判断
- ❌ 在 JWT payload 里塞 permissions
- ❌ 在登录响应里返回 permissions(必须通过 `/auth/me` 拿)

**Workspace 路由守卫(强制)**:
- 每个 workspace layout(`operator/`、`admin/`、`supplier/`、`buyer/`)必须有 `<RouteGuard allowRoles={[...]}>`
- 不能只靠权限点守路由(不同角色可能共享权限点如 `PRODUCT_READ`)

### 3.5 状态机(强制)

任何带 `status` 字段的实体(商品、SKU、订单、询价等),**从建模开始就必须定义状态机**,不允许裸 `update status`。

**强制要求**:
- 模型类上定义 `TRANSITIONS` 字典,明确合法转换路径
- Service 层 `update_status` 必须校验 `new_status in TRANSITIONS[current_status]`,不合法直接拒绝
- 可编辑性由状态决定(`EDITABLE` 集合),不可编辑状态下 PUT/POST/DELETE 写操作一律拒绝
- 前端按钮显隐严格跟 `TRANSITIONS` 走,不靠散落的 if/else

**商品状态机(已实施)**:

| 当前状态 | 可转到 | 可编辑 | 可删除 |
|---------|--------|--------|--------|
| DRAFT | ACTIVE | ✅ | ✅ |
| ACTIVE | INACTIVE | ❌(需先下架) | ❌ |
| INACTIVE | ACTIVE | ✅ | ✅ |

**绝对禁止**:
- ❌ 直接 `product.status = new_status` 不经状态机校验
- ❌ ACTIVE 状态下允许编辑(买方会看到改了一半的数据)
- ❌ 前端按钮跟状态机不一致(如 ACTIVE 还显示编辑按钮)

### 4. AI 能力的"留占位 + 可降级"

业务流程中潜在 AI 节点(资质 OCR、入驻 AI 初审、报价合理性提示等)优先级**靠后**,但**必须留占位**:

- 业务逻辑、数据结构、UI 展示位置预留
- Mock 实现填充,响应中带 `mock_ai: true` 标识
- 接入真实模型时只替换实现,不动业务流程

#### ⚠️ 外部慢调用(LLM / 网络)不得阻塞请求路径(红线)

LLM、Tavily、第三方 API 这类**慢、联网、可能失败**的调用,**绝不允许放在同步请求路径里**阻塞页面渲染或接口响应。基本的同步/异步隔离:

| 必须 | 禁止 |
|---|---|
| 慢调用放后台任务(BackgroundTask / 队列)异步执行,结果**落库** | ❌ 在 GET 详情/列表接口里现场调 LLM/外部 API |
| 用户接口**只读库**,数据未就绪返回 `null` / `status=pending` | ❌ 用"首访懒生成"当借口把 LLM 调用塞进读接口 |
| 前端对"未就绪"态容错:骨架屏 / "生成中" / "暂无" | ❌ 让用户对着转圈等几十秒的 LLM/网络往返 |

**判断准则**:任何一次调用耗时不可控(>100ms 量级且依赖外部),就必须异步化 + 落库 + 读接口只读。

> 反面教材(2026-05-25 修复):信用评估详情接口 `GET /credit/companies/{id}` 曾在 `ai_summary is None` 时**同步调 qwen-plus 现生成 AI 评价**,导致真实评分的公司首次进详情页卡几十秒。修复:AI 评价改由评分后台任务异步生成落库,详情接口只读、未就绪返回 null。

### 5. 审计与可追溯

**Trace ID**(全链路):
- 每个请求由中间件生成 UUID,写入 `request.state.trace_id` 和 contextvar
- 所有日志格式带 `[trace=xxx]`
- 所有响应头带 `X-Trace-Id`
- 失败响应 body 也带 `trace_id`

**审计日志**(只记敏感操作,不记 GET):
- 登录成功/失败/锁定/登出
- 注册、创建内部用户
- 改密、角色分配/撤销
- 任何业务写操作(POST/PUT/DELETE/PATCH)
- 失败也要记

### 6. 数据库设计约定

- 主键统一 `Integer` 自增
- 时间字段统一 `DateTime`,**应用层强制 UTC 存储**
- 状态字段用 `VARCHAR` + 应用层 Enum 校验
- JSON 字段用 SQLAlchemy `JSON` 类型(PG 上自动落 JSONB)
- **禁止使用任何数据库特有语法**(如 `INSERT OR REPLACE` / SQLite-only / 厂商私有 PG 函数等),保持 ORM 抽象
- 时间字段:应用层 UTC,DB 列用 `TIMESTAMP WITHOUT TIME ZONE`,`_utcnow()` 返回 naive UTC datetime(避免 PG aware/naive 冲突)
- 表名:复数小写下划线(`users`、`buyer_organizations`)
- 不引入软删字段(MVP 不需要)

#### i18n 多语言约定（强制）

**建表**：用户可见的文本字段按语言分列存储，表上加行级元字段：

```
source_lang  VARCHAR(10) NOT NULL  -- 创建时取录入者语言偏好，创建后不可变
name_zh      VARCHAR(200)          -- 中文值
name_en      VARCHAR(200)          -- 英文值
trans_meta   JSONB NOT NULL DEFAULT '{}'  -- 译文状态（src/manual/stale/auto/pending/failed）
```

- 使用 `I18nMixin`（`app/db/i18n_mixin.py`）接入，不要手写 source_lang / trans_meta
- 长文本（description 等）用 TEXT，短文本 VARCHAR 留余量（译文会膨胀）
- 金额字段旁必须配 `currency VARCHAR(3)`（ISO 4217），货币不按 locale 换算

**写入**：所有多语言字段的写入**必须走 `app/core/i18n_write.py`**，不准在路由/服务里手写 trans_meta。

**读取**：统一用 `get_localized(obj, "name")` 按请求语言返回，回退到源语言列。

**前端 UI 文案**：next-intl，`[locale]` 路由，zh/en 双语。界面固定文字提取为翻译 key 放 `messages/*.json`，不允许硬编码。

**前端格式化**：数值/货币/日期用 `lib/formatters.ts` 的统一工具按 locale 格式化，不手写 toLocaleString。

**系统消息**：后端错误用 `MessageKey` 常量 + `message_params`，前端查消息文件做 ICU 插值。

### 7. 命名约定

| 对象 | 规则 | 例子 |
|---|---|---|
| 权限点 | `resource:action` 小写冒号 | `user:read`、`supplier:approve` |
| AuditResourceType | 小写下划线,与表名单数对齐 | `user`、`buyer_org` |
| AuditAction | 大写下划线 | `LOGIN_SUCCESS`、`PASSWORD_CHANGE` |
| 数据库表 | 复数小写下划线 | `users`、`buyer_organizations` |
| Python 类 | 大驼峰 | `User`、`BuyerOrganization` |
| Python 函数/变量 | 小写下划线 | `get_current_user` |
| API 路径 | `/api/v1/<resource>/...`,小写连字符 | `/api/v1/admin/users` |
| TypeScript 组件 | 大驼峰 | `PermissionGuard` |
| TypeScript Hook | `use` 前缀小驼峰 | `usePermissions` |

### 8. 前端视觉规范

**视觉参考**：`docs/east-Africa/` 目录下的 Demo 截图。公共组件的色值和样式参照截图封装，但不要求每个页面像素级 1:1 复刻，**先跑通功能**。

#### 8.1 色值约定

| 端 | 元素 | 色值 |
|---|---|---|
| 买方前台 | 主色 | 深 Teal `#0D4D4D` |
| 买方前台 | 辅色 | Teal `#1A6B6B` |
| 运营后台 | 侧边栏 | 深蓝灰 `#0A1929` |
| 运营后台 | 主色 | 蓝色 `#3B82F6` |
| 运营后台 | 页面背景 | 浅灰 `#F4F6F9` |

#### 8.2 公共组件样式

- 卡片：白色、`rounded-lg`、轻阴影
- 表格：表头灰底 `bg-slate-50`、交替行底色、悬停高亮
- 状态徽章：pill 圆角（绿/灰/红等语义色）
- 筛选栏：搜索框 + 下拉筛选，紧凑排列
- 分页：`显示 1-20 / 共 N 条` + 页码按钮

#### 8.3 通用规则

- 新组件基于上述公共样式封装，保持风格统一
- 颜色用 Tailwind 自定义色值，不用近似色凑合

---

## 接口约定

### 统一响应格式

**成功**:
```json
{ "code": 0, "message": "ok", "data": { ... } }
```

**失败**:
```json
{ "code": 40001, "message": "Invalid credentials", "data": null, "trace_id": "abc-123" }
```

- HTTP 状态码同步设置(200 / 400 / 401 / 403 / 404 / 422 / 429 / 500)
- `code` 为业务码,0 = 成功,非 0 = 失败
- 所有响应带 `X-Trace-Id` 响应头
- 失败响应 body 包含 `trace_id`,成功响应不重复(已在 header)

### API 路径

- 统一前缀 `/api/v1/`
- 资源用复数:`/api/v1/users`、`/api/v1/suppliers`
- 子资源嵌套:`/api/v1/orders/{id}/milestones`
- 动作类用动词后缀:`/api/v1/users/{id}/disable`

### 错误处理

- 错误信息**不暴露内部细节**
- 登录失败统一返回"Invalid credentials"(不区分用户不存在/密码错,防枚举)
- 数据查询无权限/数据不存在统一返回 404(不暴露存在性)

---

## 常用命令

### 后端

```bash
cd backend

# 依赖管理
uv venv                                    # 创建虚拟环境
source .venv/bin/activate                  # 激活
uv pip install -e .                        # 安装项目(可编辑模式)
uv pip install -e ".[dev]"                 # 安装含开发依赖

# 数据库
alembic revision --autogenerate -m "..."   # 生成迁移
alembic upgrade head                       # 应用迁移
alembic downgrade -1                       # 回滚一步
bash scripts/reset_db.sh                   # 重置数据库(drop + recreate overseas_supply_dev + 重跑迁移 + seed)

# 开发
uvicorn app.main:app --reload --port 8000  # 启动开发服务器
pytest                                     # 跑测试
pytest -k test_auth                        # 跑特定测试
pytest --cov=app                           # 覆盖率
bash scripts/verify.sh                     # curl 验证脚本

# 访问
# - API 文档: http://localhost:8000/docs
# - 健康检查: http://localhost:8000/healthz
```

### 前端

```bash
cd frontend

pnpm install               # 安装依赖
pnpm dev                   # 开发模式(http://localhost:3000)
pnpm build                 # 构建
pnpm lint                  # ESLint
```

### Docker(部署用,本地开发不用)

```bash
# 本地预演生产镜像(debug 用)
cp .env.production.example .env.production    # 填实际值
docker compose --env-file .env.production up -d --build

# 部署:手动触发(代码提交 / 合并 main 不会自动部署)
gh workflow run "Deploy to ECS"               # 推荐:命令行一条
gh run watch                                  # 查看进度
# 或网页:GitHub Actions tab → "Deploy to ECS" → Run workflow

# 应急:SSH 到 ECS 手动跑
ssh user@<ECS-IP>
cd /opt/overseas-platform && bash deploy/deploy.sh

# 日志 / 进容器
docker compose logs -f backend
docker compose exec backend bash
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"

# 备份 / 恢复
source .env.production
docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > backup.sql.gz
gunzip -c backup.sql.gz | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

---

## 部署架构

### 本地开发(不变,不要用 Docker 跑开发)

- 后端:`cd backend && uvicorn app.main:app --reload --port 8000`
- 前端:`cd frontend && pnpm dev`
- 数据库:本机 brew PostgreSQL @5433

### 演示 / 生产部署(Docker compose)

| 文件 | 用途 |
|---|---|
| `docker-compose.yml` | 三服务编排(db + backend + frontend) |
| `backend/Dockerfile` | 多阶段构建,uv 装依赖,非 root 运行 |
| `frontend/Dockerfile` | 多阶段构建,pnpm + Next.js standalone |
| `backend/docker-entrypoint.sh` | 等 DB → alembic upgrade → 启动应用(lifespan 自动跑 seed) |
| `deploy/deploy.sh` | ECS 上由 CI 触发的部署脚本 |
| `deploy/check-migration-safety.sh` | CI 拦截破坏性迁移 |
| `.github/workflows/deploy.yml` | 手动触发(workflow_dispatch),代码合 main 不会自动部署 |
| `.env.production` | ECS 上维护,**不入 Git** |
| `.env.production.example` | 入 Git 的模板 |

### 部署触发链路

```
你手动触发(gh workflow run "Deploy to ECS" 或网页点 Run)
      ↓
GitHub Actions:check-migration → SSH 到 ECS → bash deploy/deploy.sh
      ↓
ECS:pg_dump 备份 → git pull → docker compose up -d --build → 健康检查
```

### 数据持久化约束(必须遵守)

- ✅ DB 数据落在 named volume `overseas_platform_pgdata`(显式 name)
- ✅ 每次部署前自动 `pg_dump`,留 7 天
- ❌ **严禁** 任何脚本 / CI / 文档出现 `docker compose down -v`、`docker volume rm`、`docker system prune --volumes`
- ❌ **严禁** entrypoint 跑 `alembic downgrade` / `drop` / `truncate`
- ❌ **严禁** seed.py 用 `delete + insert` 模式,必须先查后写(已实现)

### 镜像与日志约束(必须遵守)

- ✅ 所有镜像 tag **精确到 minor**(如 `postgres:16.4-alpine`、`node:20.18-alpine`、`python:3.11.10-slim`)
- ✅ 所有服务挂 `logging` 限制:`max-size: 10m`、`max-file: 3`(每服务 30MB,防磁盘塞满)
- ✅ Dockerfile 内 apt / apk / pip / npm 源**都换国内镜像**(国内 build 必备,昨天踩过 48 分钟卡 apt 的坑)
- ❌ **严禁** 用 `pnpm@latest` / `node:20-alpine` / `:latest` / 任何浮动 tag

### 迁移安全

- 含 `drop_column` / `drop_table` / `alter_column type_=` / raw `DROP|TRUNCATE|DELETE` 的 migration → CI 自动拦截
- 确实要执行 → commit message 加 `[allow-destructive-migration]` 或手动 SSH 跑 deploy.sh

详细部署指南见 `deploy/README.md`。

---

## 环境变量

### 后端 `.env`

```bash
# 数据库
DATABASE_URL=postgresql+asyncpg://<your_user>@localhost:5433/buildlink_ea_dev

# JWT
JWT_SECRET_KEY=<openssl rand -hex 32 生成>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# 初始超级管理员(种子)
SUPER_ADMIN_EMAIL=superadmin@platform.local
SUPER_ADMIN_INITIAL_PASSWORD=ChangeMe123

# 日志
LOG_LEVEL=INFO

# CORS
CORS_ORIGINS=http://localhost:3000
```

### 前端 `.env.local`

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

**密钥规则**:
- ⚠️ 真实密钥**绝不**进 Git
- `.env.example` 只放结构和示例值
- `JWT_SECRET_KEY` 必须用 `openssl rand -hex 32` 生成

---

## 禁止事项(常见踩坑)

❌ **不要**换数据库 —— 已锁定 PostgreSQL,不要再切 MySQL / MongoDB / SQLite
❌ **不要**用 mock 数据替代真实 DB —— 所有列表必须从数据库查
❌ **不要**用数据库特有/厂商私有语法 —— 保持 ORM 抽象
❌ **不要**在登录响应里塞 permissions —— 必须通过 `/auth/me` 拿
❌ **不要**在 JWT payload 里塞 permissions —— 权限变更需即时生效
❌ **不要**把权限判断写死在业务代码里(`if role == 'BUYER'`)—— 必须走 `require_permission`
❌ **不要**让 ADMIN 拥有业务数据权限 —— 严格职责分离
❌ **不要**让注册接口自动登录 —— 注册和登录是两个独立动作
❌ **不要**让 `POST /admin/users` 能创建 BUYER/SUPPLIER —— 业务用户走自助注册
❌ **不要**引入 NextAuth、Prisma —— 后端是 FastAPI,前端只做轻量 token 管理
❌ **不要**做用户头像生成、邮件、短信、OAuth、2FA、找回密码
❌ **不要**做 PWA / SSG / ISR —— 一律动态渲染
❌ **不要**把品牌名硬编码 —— 暂留 TODO 占位
❌ **不要**写测试代码以外的次要功能 —— 不在 prompt 清单的一律不做
❌ **不要**用裸 SQL,优先 ORM —— 跨数据库兼容
❌ **不要**在前端硬编码 4 个角色对应权限点的判断 —— 必须用 `hasPermission('xxx:yyy')`
❌ **不要**让 GET 请求写审计日志 —— 噪音大,价值低

---

## 提交规范

### Commit 信息

格式:`<type>(<scope>): <subject>`

常用 type:
- `feat` — 新功能
- `fix` — 修复 bug
- `refactor` — 重构(不影响功能)
- `docs` — 文档
- `test` — 测试
- `chore` — 构建、依赖

例:
- `feat(auth): add buyer registration endpoint`
- `fix(rbac): admin should not access business data`
- `docs(rbac): update Q22 decision`

### 分支

- `main` — 主分支(受保护,**不允许直接 commit / push**)
- `feat/<name>` — 功能分支
- `fix/<name>` — 修复分支

**强制工作流(每次开发前必须遵守):**

1. 动手任何代码改动前,先确认当前分支:`git rev-parse --abbrev-ref HEAD`
2. 如果在 `main` → **立即切分支**:`git checkout -b feat/<descriptive-name>`(基于最新 main)
3. 在 feat/fix 分支上开发、自测、commit
4. 推分支:`git push -u origin feat/<name>`
5. 开 PR:`gh pr create`(commit 标题落到 main 时自动带 `(#NN)`)
6. PR 合并后再回 main pull

**绝对禁止:**
- ❌ 直接在 local main 上 commit(哪怕只是一行小改)
- ❌ 直接 `git push origin main`(项目所有变更都走 PR,看 `git log` 每条都带 `(#NN)`)
- ❌ 把多个不相关功能塞一个分支,一个分支一件事

**例外**:仅文档微调且不打算 commit / 本地实验脚本可不切分支。

---

## 待团队拍板的设计决策

代码中遇到以下决策点,**按当前临时方案落地 + 标注 TODO**:

| 编号 | 决策 | 当前方案 |
|---|---|---|
| Q22 | 角色-权限关系定义方式 | 配置文件 + 启动同步(`app/rbac/permissions_config.py`)|
| Q23 | Role.scope 字段 | 引入字段,MVP 仅用 `GLOBAL` |
| Q24 | OPERATOR 是否细分 | 不细分 |
| Q25 | ADMIN 能否访问业务数据 | 严格分离 |
| Q26 | super admin 密码策略 | 环境变量注入 + 强制改密 |
| Q27 | 何时切换 PostgreSQL | ✅ **已切**(2026-05-18,brew @16 端口 5433) |
| Q28 | 是否容器化部署 | ✅ **已切**(2026-05-20,Docker compose + GitHub Actions 手动触发部署,详见「部署架构」) |


---

## 实施风格

写代码时:

1. **先读本文件相关章节,再动手**
2. **遇到模糊点 → 选最简方案 + 标 TODO**
3. **类型注解齐全**(Python 用类型提示,TypeScript 不用 any)
4. **错误处理显式**,不吞异常
5. **关键业务逻辑写注释**,说明"为什么"而不是"做了什么"
6. **TODO 注释带编号**(如 `TODO(Q22): ...`),便于追溯
7. **提交前自测**:后端 `pytest` + `verify.sh`,前端手动跑一遍登录流程

---

## Bug 修复纪律 ⭐

修 bug 前**必须先理解错误的根本原因**,不为了改而改、不靠"改一下试试看"。

每次修 bug 必须能讲清楚这 3 件事(写进 commit message 或 PR 描述):

1. **现象**:用户看到的错误表现是什么(报错文本 / 异常截图 / 数据状态)
2. **根因**:为什么会发生 — 从现象沿调用链反推到代码层面的具体原因
   - 不能停在"加这个字段就好了"这种表层结论
   - 要回答"为什么这个字段缺了"、"为什么这条逻辑没走通"
3. **修复**:为什么这个改动能解决根因 — 改动跟根因之间的逻辑关系要清晰

**反模式(禁止)**:
- ❌ "试着加个 try/except 看会不会好" → 没定位就盖问题
- ❌ "把这个字段改成可选" → 没确认为什么这个字段会空
- ❌ "改一下数据让它过 → 不动代码" → 数据修复 ≠ bug 修复,逻辑可能还错
- ❌ "把限制宽放一下让通过" → 限制本来对不对都不知道就放宽

**正确示范(commit message 模板)**:
```
fix(xxx): <一句话现象>

现象:用户在 /credit/companies/N 详情页看到 '暂无工商基本信息'
根因:Pydantic v2 + from_attributes=True 只读已声明字段。BasicData
     schema 没声明 id,所以 model_validate(ORM row) 后 basic.id 永远是
     None;ScoringEngine 写 snapshot 时 basic_data_id 也是 None;
     详情页 if snapshot.basic_data_id is None: skip。
修:三个 Pydantic schema 都加 id 字段,model_validate 就会把 ORM 的 id
   拉过来,FK 链路通了。
```

如果一时找不到根因,**先记 TODO + 不动代码** 比 "随便改一刀让它先过" 强得多。

---

## 前端表单 UX 基本规则（强制）

每个表单页面必须满足以下条件，不需要被提醒：

1. **表单数据不能丢** — 用 sessionStorage/localStorage 缓存草稿，刷新/报错都不能清空用户已填的数据。提交成功后清除缓存。
2. **错误定位到字段** — 哪个字段/卡片出错就在那里高亮+内联提示，不要只扔在页面底部或用全局 alert。
3. **错误信息走 i18n** — 后端返回 `message_key` 必须翻译成当前语言展示，回退到 `message`，绝不直接显示英文原文。
4. **多步提交要断点续传** — 串行调多个接口（如 SPU→SKU→图片→状态），已成功的步骤要记住（ref/state），重试时跳过已完成的，不能重复创建。
5. **UI 元素必须可见** — 用 Tailwind 自定义色阶时确认色值在 `tailwind.config.ts` 中存在，写完 UI 必须肉眼确认按钮/链接渲染正常。

---

*文档结束*
