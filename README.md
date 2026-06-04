# BuildLink EA · 东非供应链平台

> 面向东非市场的 B2B 供应链管理平台。

## 一键启动

支持 macOS、Linux、Windows，打开终端运行：

```bash
bash dev.sh
```

**Windows 用户**：先安装 WSL，在 PowerShell（管理员）中执行：

```powershell
wsl --install
```

重启后打开 Ubuntu 终端，进入项目目录再运行 `bash dev.sh`。

脚本会自动完成以下事项（已安装的会跳过）：

1. 安装系统包管理器（macOS 装 Homebrew，Linux 用 apt/yum）
2. 安装并启动 PostgreSQL
3. 安装 Python 包管理器 uv
4. 安装 Node.js 和 pnpm
5. 安装前后端所有依赖
6. 创建数据库并执行迁移
7. 启动前端和后端服务

启动完成后：

| 服务 | 地址 |
|------|------|
| 前端页面 | http://localhost:3000 |
| 后端 API | http://localhost:8001 |
| API 文档 | http://localhost:8001/docs |

按 `Ctrl+C` 停止所有服务。

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | Next.js 14 + TypeScript + Tailwind CSS |
| 后端 | FastAPI + SQLAlchemy 2.0 + PostgreSQL 16 |
| 认证 | JWT (access in memory + refresh in httpOnly cookie) |

## 已实现功能

### 底座

| 模块 | 说明 |
|------|------|
| **RBAC** | 4 角色 (BUYER / SUPPLIER / OPERATOR / ADMIN)、35 权限码、RouteGuard + PermissionGuard 双层拦截 |
| **认证** | 供应商注册 (3 步向导)、采购方注册、登录/登出、改密、token 自动刷新 |
| **i18n** | 多语言支持、语言偏好持久化 |
| **审计** | Trace ID 全链路、敏感操作写库 |

### 业务模块

| 模块 | 说明 |
|------|------|
| **供应商注册** | 9 国注册规则、国别注册号校验、全量错误一次性返回 |
| **信用评估** | AI 评分引擎、雷达图、AI 对话 |
| **品类管理** | 三级分类级联选择器 |

## 目录结构

```
buildlink-ea/
├── dev.sh            一键启动脚本
├── backend/          FastAPI 后端
├── frontend/         Next.js 前端
├── deploy/           部署脚本
└── docker-compose.yml  生产部署编排
```
