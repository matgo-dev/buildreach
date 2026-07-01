# BuildReach · 东非建材供应链平台

> 连接中国建材供应商与东非买家的 B2B 数字供应链平台。主要客户为东非建材批发商 / 个体经营者，以及在东非有项目的央企。

## 一键启动

支持 macOS、Linux、Windows（WSL），打开终端运行：

```bash
bash dev.sh
```

**Windows 用户**：先在 PowerShell（管理员）执行 `wsl --install`，重启后在 Ubuntu 终端运行。

脚本自动完成：安装 PostgreSQL / Python(uv) / Node.js(pnpm) → **生成 `.env` / `.env.local`（含随机 JWT 密钥）** → 建库 → 迁移 → 启动前后端。本地开发**无需手动配置环境变量**即可跑通；AI、机器翻译、SMTP 邮件等外部能力默认留空，需要时再填对应 key（见 `backend/.env.example`）。

| 服务 | 地址 |
|------|------|
| 前端页面 | http://localhost:7857 |
| 后端 API / 文档 | http://localhost:17857 · `/docs` |

按 `Ctrl+C` 停止所有服务。

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | Next.js 14 (App Router) + TypeScript + Tailwind + next-intl + SWR + zustand |
| 后端 | FastAPI + SQLAlchemy 2.0 (async) + Alembic + PostgreSQL 16 |
| 认证 | JWT（access 内存 + refresh httpOnly cookie）+ bcrypt |
| AI | 通义千问 `qwen-plus`（DashScope OpenAI 兼容端点）+ Tavily 联网检索（仅测试使用，线上未配置）|
| i18n | Google Cloud / 阿里云机器翻译 + APScheduler 后台补译 |
| 部署 | Docker Compose + GitHub Actions（手动触发）|

## 功能模块

### 底座

| 模块 | 说明 |
|------|------|
| **RBAC** | 4 角色 (BUYER / SUPPLIER / OPERATOR / ADMIN)、38 权限码、前端 RouteGuard + PermissionGuard 双层、后端权限依赖注入 |
| **认证** | 供应商 3 步注册向导（9 国注册规则）、采购方注册、登录/登出/改密/找回、验证码、token 自动刷新 |
| **审计** | Trace ID 全链路中间件、敏感操作写库 |
| **i18n** | 分列多语言存储（source_lang + trans_meta 状态机）、按请求语言返回、后台自动补译扫描、术语表缓存 |

### 业务

| 模块 | 说明 |
|------|------|
| **商品目录** | SPU+SKU 两层、i18n 分列、多图、商品/SKU 双维属性 |
| **品类管理** | 三级分类 (13 L1 / 130 L2 / 853 L3)、44 条属性模板、pg_trgm 模糊搜索 |
| **询价 / 报价 (RFQ)** | 买方建询价单 → 运营/供应商报价（含成本项、阶梯）→ WeasyPrint 生成 PDF 报价单 |
| **购物车 / 询价篮** | 买方选品与批量询价入口 |
| **信用评估** | AI 评分引擎（多维度规则 + 快照）、Tavily 数据采集、AI 综合评价 + AI 对话追问、雷达图 |
| **运营后台** | 商品 / RFQ / 买家 / Banner 管理、数据分析、审计日志、用户与权限矩阵 |
| **买方前台 (Mall)** | 商城首页楼层、商品列表/详情、供应商列表、帮助中心、下单追踪、AI 助手 |

规模参考：约 20 个 API 路由模块、51 张数据模型、64 个 Alembic 迁移。

## 初始化品类数据

品类树和属性模板不随服务启动自动种入，需手动执行：

```bash
cd backend && source .venv/bin/activate

python scripts/seed_categories.py --dry-run   # 预览（不连库）
python scripts/seed_categories.py             # 执行（upsert，可重复运行）
```

数据源：`data/categories.csv`（三级品类）、`data/attr_templates.csv`（属性模板）、`data/category_names_en.json`（英文名）。

## 目录结构

```
buildreach/
├── dev.sh                     一键启动脚本
├── data/                      品类 CSV + 英文翻译 JSON（seed 数据源）
├── backend/app/
│   ├── core/                  配置 / 安全 / 异常 / i18n / locale
│   ├── db/models/             ORM 模型；alembic/versions 迁移
│   ├── api/v1/                路由（按模块拆分）
│   ├── services/              业务逻辑（含 llm/ 与 credit/ AI 子模块）
│   ├── rbac/                  权限配置 / Guard / 同步
│   └── audit/                 审计中间件
├── frontend/src/
│   ├── app/[locale]/          页面（next-intl 路由：buyer / operator / admin / mall）
│   ├── components/            UI 组件
│   ├── lib/                   API 封装 / 权限 / 格式化
│   └── i18n/ · messages/      路由配置与 zh/en 翻译
├── deploy/                    部署与运维脚本
└── docker-compose*.yml        本地 / 生产 / 离线编排
```

## 部署

GitHub Actions 手动触发（`Actions → Build & Deploy → Run workflow`）：构建镜像 → 推送 GHCR + 阿里云 ACR → 部署。

| 环境 | 主机 | 镜像源 | 说明 |
|------|------|--------|------|
| 测试 / 预发 | 阿里云 ECS | ACR | Docker + Nginx |
| 生产 | OVHcloud（海外） | GHCR | Docker Compose |

流水线含迁移安全检查（破坏性迁移需 commit 带 `[allow-destructive-migration]` 显式授权）。当前生产为**单实例**：`db`（postgres:16.4）+ `backend` + `frontend`，图片存 Docker 卷（`uploads` / `private_uploads`）。

## 架构现状与演进

当前为单实例部署，**限流、缓存、i18n 调度均为单进程内存态**，简单可靠但限制横向扩容。演进按需触发：

| 演进项 | 触发条件 | 要点 |
|--------|----------|------|
| **对象存储 (OVH S3)** | 近期 | 图片从 Docker 卷迁至 S3；`services/storage.py` 已是 Protocol 抽象，契约见 `docs/xfs_s3_image_upload_contract.md` |
| **Redis** | 后端需多实例时 | 承接分布式限流与共享缓存（内存态方案多实例即失效），并作 AI agent 任务队列 |
| **Kubernetes** | 需高可用 / 弹性扩缩容时 | 前置：先完成 Redis + S3 让服务无状态 |

## 开发约定

- **严禁直接在 `main` 上 commit / push**，一律走分支 + PR。
- 安全与性能为当前保障重点。
