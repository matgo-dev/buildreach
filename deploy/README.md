# 部署指南

## 架构概览

```
本地开发 (macOS)
    │
    │  git push
    ▼
GitHub Actions ─── Build ─── 推送镜像到 GHCR
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
    部署 ECS (自动)        部署 OVH (手动审批)
    阿里云 · 测试环境       OVHcloud · 生产环境
    114.55.135.216          162.19.98.142
```

| 环境 | 机器 | 定位 | 反代 | 域名 |
|------|------|------|------|------|
| 本地 | macOS | 开发调试 | 无 | localhost |
| 测试 | 阿里云 ECS | 验证/预发 | 1Panel OpenResty | — |
| 生产 | OVHcloud | 线上 | 1Panel OpenResty | matgo.ai |

三台机器端口统一：前端 **7857**，后端 **17857**，宿主机 OpenResty 统一反代。

> **本文档只覆盖当前单机部署的操作。** 数据库、对象存储等的托管化演进（触发点 / 选型 / 迁移要点）见根 `README.md` 的《架构现状与演进》；真正迁移时，这里再补对应操作步骤。

---

## 日常部署

### 方式一：GitHub 网页（推荐）

1. 打开 GitHub 仓库 → **Actions** → 左边选 **"Build & Deploy"**
2. 右上角 **Run workflow** → 选分支 → 点 **Run**
3. 等 build 完成（约5分钟），ECS 自动部署
4. 去 ECS 验证功能
5. 没问题 → 回到 GitHub Actions 页面 → deploy-ovh 任务旁点 **"Review deployments"** → **Approve and deploy**

### 方式二：命令行

```bash
# 触发部署
gh workflow run "Build & Deploy" --repo matgo-dev/buildreach --ref main

# 查看进度
gh run watch
```

### 流程说明

| 步骤 | 谁触发 | 说明 |
|------|--------|------|
| 启动流程 | 你手动 | GitHub 页面或 `gh workflow run` |
| 迁移安全检查 | 自动 | 检测破坏性 migration |
| 构建镜像 + 推 GHCR | 自动 | 前后端并行构建 |
| 部署 ECS (staging) | 自动 | build 完成后自动执行 |
| 部署 OVH (production) | 你手动 | build 完成后等待审批，你点 approve 才执行 |

### 失败处理

| 失败环节 | 后果 |
|---------|------|
| 迁移检查不过 | 整个流程停止 |
| 构建失败 | 两个 deploy 都不跑 |
| ECS 部署失败 | deploy.sh 自动回滚；OVH 不受影响 |
| OVH 部署失败 | deploy.sh 自动回滚；ECS 不受影响 |

---

## deploy.sh 流程（两台机器共用）

```
1. 备份数据库 (pg_dump → gzip，保留7天)
2. 拉最新代码 (git fetch + reset)
3. 拉取镜像 (GHCR login + docker compose pull)
4. 记录旧镜像 (回滚用)
5. 启动容器 (docker compose up -d)
6. 健康检查 (backend /healthz + frontend HTTP 200，60秒超时)
   └── 失败自动回滚到上一版本
```

---

## 首次部署 Checklist

### 1. GitHub 配置（只做一次）

#### 1.1 创建 Environments

GitHub 仓库 → Settings → Environments：

| Environment | 保护规则 |
|-------------|---------|
| `staging` | 无（ECS 自动部署） |
| `production` | Required reviewer: 你自己 |

#### 1.2 配置 Secrets

GitHub 仓库 → Settings → Secrets and variables → Actions：

**ECS 相关：**

| Name | Value |
|------|-------|
| `ECS_HOST` | 阿里云 ECS 公网 IP |
| `ECS_USER` | SSH 用户名 |
| `ECS_SSH_KEY` | SSH 私钥全文（含 BEGIN/END） |

**OVH 相关：**

| Name | Value |
|------|-------|
| `OVH_HOST` | 162.19.98.142 |
| `OVH_USER` | root |
| `OVH_SSH_KEY` | SSH 私钥全文 |
| `OVH_PUBLIC_ORIGIN` | https://matgo.ai（或当前实际地址） |

**通用：**

| Name | Value |
|------|-------|
| `GHCR_TOKEN` | GitHub PAT（服务器拉取 GHCR 私有镜像用） |

### 2. 服务器准备（ECS 和 OVH 都要做）

```bash
# SSH 到目标服务器
ssh user@<IP>

# 创建部署目录
sudo mkdir -p /opt/buildreach && sudo chown $USER:$USER /opt/buildreach

# 克隆代码
cd /opt/buildreach
git clone git@github.com:matgo-dev/buildreach.git .

# 配置环境变量
cp .env.production.example .env.production
vim .env.production    # 填真实值：
                       #   POSTGRES_PASSWORD = openssl rand -base64 24
                       #   JWT_SECRET_KEY    = openssl rand -hex 32
                       #   API_BASE_URL      = https://YOUR_DOMAIN
                       #   CORS_ORIGINS      = https://YOUR_DOMAIN
chmod 600 .env.production

# 首次部署
bash deploy/deploy.sh
```

### 3. 配置 1Panel OpenResty 反代（两台都要做）

在 1Panel 面板 → 网站 → 反向代理，添加以下规则：

| 名称 | 前端路径 | 后端地址 | 缓存 |
|------|---------|---------|------|
| api | /api/ | http://127.0.0.1:17857 | 禁用 |
| static | /static/ | http://127.0.0.1:17857 | 7天 |
| env-js | /__env.js | http://127.0.0.1:7857 | 禁用 |
| healthz | /healthz | http://127.0.0.1:17857 | 禁用 |
| next-static | /_next/static/ | http://127.0.0.1:7857 | 365天 |
| root | / | http://127.0.0.1:7857 | 禁用 |

### 4. 初始化品类数据（首次部署必做）

```bash
cd /opt/buildreach
source .env.production

# 拷数据进容器
docker cp data/. $(docker compose -f docker-compose.production.yml --env-file .env.production ps -q backend):/data/

# 执行品类 seed
docker compose -f docker-compose.production.yml --env-file .env.production exec -T backend python -c "
import asyncio
from app.seed_categories import seed_categories
from app.db.session import AsyncSessionLocal

async def run():
    async with AsyncSessionLocal() as session:
        await seed_categories(session)
        await session.commit()

asyncio.run(run())
"
```

---

## 日常运维

### 查看日志

```bash
cd /opt/buildreach
docker compose -f docker-compose.production.yml logs -f backend
docker compose -f docker-compose.production.yml logs -f frontend
docker compose -f docker-compose.production.yml logs -f db
```

### 进容器

```bash
docker compose -f docker-compose.production.yml exec backend bash
docker compose -f docker-compose.production.yml exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

### 手动备份

```bash
source .env.production
docker compose -f docker-compose.production.yml exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > backups/manual-$(date +%Y%m%d-%H%M).sql.gz
```

自动备份每次部署都会做，保留 7 天。

---

## 应急

### 部署失败 → 手动 SSH 重跑

```bash
ssh user@<IP>
cd /opt/buildreach
bash deploy/deploy.sh
```

### 回滚到上一版

```bash
cd /opt/buildreach
git log --oneline -10              # 找到上一版 commit
git reset --hard <commit-sha>
bash deploy/deploy.sh
```

### 数据库恢复

```bash
cd /opt/buildreach
source .env.production
ls backups/                        # 找最近备份
gunzip -c backups/YYYYMMDD-HHMMSS.sql.gz | docker compose -f docker-compose.production.yml exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

### 破坏性迁移

CI 自动拦截含 `drop_column` / `drop_table` 的 migration。确实需要执行时：

1. **commit message 加标记**：`feat(db): xxx [allow-destructive-migration]`
2. **手动 SSH 执行**：跳过 CI，直接 `bash deploy/deploy.sh`

---

## 安全约束（必须遵守）

| 项 | 要求 |
|---|---|
| `.env.production` | 服务器上 `chmod 600`，**严禁入 Git** |
| `docker compose down -v` | **任何脚本/文档不能出现**，会删 volume |
| `docker volume rm` | 同上 |
| `docker system prune --volumes` | 同上 |
