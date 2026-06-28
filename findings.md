# Findings: CI/CD Unification Research

## Current State Analysis (2026-06-27)

### Registry
- 当前双推 GHCR + ACR（阿里云杭州区）
- ACR 地址硬编码在 docker-compose.production.yml 和 deploy.sh 中
- ECS 从 ACR 拉取（同区快），但 OVH（法国）拉 ACR 会跨洲很慢
- GHCR 对两台机器都可接受

### Nginx 容器冗余
- docker-compose.production.yml 包含 nginx service
- 但 ECS 和 OVH 都已装 1Panel + OpenResty
- 142 的 OpenResty 反代规则已配好（/api/ → 17857, /static/ → 17857, / → 7857）
- ECS 也装了 1Panel，确认可以用同样方式管理

### deploy.sh 7步流程
1. DB 备份（pg_dump）
2. 拉代码（git fetch + reset）
3. 拉镜像（docker login ACR + compose pull）
4. 记录旧镜像（回滚用）
5. 启动容器（compose up）
6. 健康检查（backend + frontend + nginx 三端点）
7. 清理（prune dangling images）

其中 step 2.5 有 banner 同步（copy 到 nginx 目录），step 6 有 nginx 健康检查 — 去掉 nginx 后需要调整

### deploy-offline.sh 3步流程
1. docker load 镜像
2. compose up
3. 健康检查（仅 backend）

统一后这个脚本在主流程不再使用，保留在 buildlink-offline/ 供客户交付

### GitHub Actions Secrets
当前配置：
- ECS_HOST, ECS_USER, ECS_SSH_KEY — ECS 连接
- ACR_USERNAME, ACR_PASSWORD — ACR 登录
- GITHUB_TOKEN — GHCR 登录（自动提供）

需要新增：
- OVH_HOST, OVH_USER, OVH_SSH_KEY — OVH 连接

可以移除（统一后不再使用）：
- ACR_USERNAME, ACR_PASSWORD

### Port Convention
两台机器统一：frontend 7857, backend 17857
docker-compose 中 backend 绑 127.0.0.1:17857:8000, frontend 绑 127.0.0.1:7857:3000

### GHCR Image Path
`ghcr.io/matgo-dev/buildreach/{backend,frontend}:{branch}-{sha}`

### OVH 服务器 deploy 目录
需要确认：OVH 上代码放在哪个目录？当前 ECS 用 /opt/buildreach
