# BuildLink EA · 东非建材供应链平台

> 连接中国建材供应商与东非买家的 B2B 数字供应链平台。

## 一键启动

支持 macOS、Linux、Windows，打开终端运行：

```bash
bash dev.sh
```

**Windows 用户**：先安装 WSL，在 PowerShell（管理员）中执行 `wsl --install`，重启后在 Ubuntu 终端运行。

脚本会自动完成：安装 PostgreSQL / Python(uv) / Node.js(pnpm) → 创建数据库 → 执行迁移 → 启动前后端。

启动完成后：

| 服务 | 地址 |
|------|------|
| 前端页面 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |

按 `Ctrl+C` 停止所有服务。

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | Next.js 14 (App Router) + TypeScript + Tailwind CSS + next-intl |
| 后端 | FastAPI + SQLAlchemy 2.0 (async) + Alembic + PostgreSQL 16 |
| 认证 | JWT (access in memory + refresh in httpOnly cookie) |
| 部署 | Docker Compose + GitHub Actions |

## 已实现

### 底座

| 模块 | 说明 |
|------|------|
| **RBAC** | 4 角色 (BUYER / SUPPLIER / OPERATOR / ADMIN)、38 权限码、RouteGuard + PermissionGuard 双层拦截 |
| **认证** | 供应商注册 (3 步向导)、采购方注册、登录/登出、改密、token 自动刷新 |
| **审计** | Trace ID 全链路、敏感操作写库 |
| **i18n** | 分列多语言存储 (source_lang + trans_meta 状态机)、get_localized 按请求语言返回、normalize_locale BCP47 映射、message_key + message_params 系统消息、LocalizedFieldEditor 组件、locale-aware 格式化工具 |

### 业务模块

| 模块 | 说明 |
|------|------|
| **供应商注册** | 9 国注册规则、国别注册号校验、全量错误一次性返回 |
| **信用评估** | AI 评分引擎、雷达图、AI 对话 |
| **商品目录** | SPU+SKU 两层、v2 i18n 分列、阶梯价、图片、供货关系、属性(商品/SKU 维度) |
| **品类管理** | 三级分类 (13 L1 / 130 L2 / 853 L3)、44 条属性模板 |

## 初始化品类数据

品类树和属性模板不随服务启动自动种入，需手动执行：

```bash
cd backend
source .venv/bin/activate

# 预览（不连数据库，仅查看解析结果）
python scripts/seed_categories.py --dry-run

# 执行（upsert 写入数据库）
python scripts/seed_categories.py
```

数据源为 `data/categories.csv`（996 条三级品类）和 `data/attr_templates.csv`（44 条属性模板），英文名来自 `data/category_names_en.json`。脚本为 upsert 模式，重复运行安全，不影响已有商品数据。

## 目录结构

```
buildlink-ea/
├── dev.sh               一键启动脚本
├── data/                品类 CSV + 英文翻译 JSON（seed 数据源）
├── backend/
│   ├── app/
│   │   ├── core/        配置 / 安全 / 异常 / i18n / locale
│   │   ├── db/          ORM 模型 / i18n_mixin / 迁移
│   │   ├── api/v1/      路由（按模块拆分）
│   │   ├── services/    业务逻辑 / 翻译服务
│   │   ├── rbac/        权限配置 / Guard / 同步
│   │   └── audit/       审计中间件
│   ├── scripts/         手动执行脚本（seed 等）
│   └── tests/           pytest 测试
├── frontend/
│   ├── src/
│   │   ├── app/[locale]/ 页面（next-intl 路由）
│   │   ├── components/   UI 组件 / i18n 组件
│   │   ├── lib/          API 封装 / 格式化工具
│   │   └── i18n/         路由配置 / locale 映射
│   └── messages/         zh.json / en.json 翻译文件
├── deploy/               部署脚本
└── docker-compose.yml    生产部署编排
```
