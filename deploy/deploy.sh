#!/usr/bin/env bash
# ============================================================
# ECS 上的部署脚本
# 调用方:GitHub Actions(SSH 后跑此脚本)/ 应急时人工 SSH 后跑
#
# 流程:备份 DB → 拉代码 → 拉镜像 → 启动容器 → 健康检查 → 清理
#
# 镜像由 GitHub Actions 构建并推送到 ghcr.io，ECS 只拉取和重启。
# 回退（ghcr.io 不可用时）:
#   docker compose --env-file .env.production up -d --build
#
# 严禁修改成包含以下操作:
#   - docker compose down -v
#   - docker volume rm
#   - docker system prune --volumes
#   - rm -rf pgdata / git clean -fdx
# ============================================================

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/overseas-platform}"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-60}"
DEPLOY_REF="${DEPLOY_REF:-origin/main}"
BACKEND_HOST_PORT="${BACKEND_HOST_PORT:-8001}"
FRONTEND_HOST_PORT="${FRONTEND_HOST_PORT:-3001}"
IMAGE_TAG="${IMAGE_TAG:-main-latest}"
COMPOSE_FILE="docker-compose.production.yml"

cd "$APP_DIR"

echo "[deploy] =================================================="
echo "[deploy] 开始部署 $(date -Iseconds)"
echo "[deploy] APP_DIR=$APP_DIR"
echo "[deploy] IMAGE_TAG=$IMAGE_TAG"
echo "[deploy] COMPOSE_FILE=$COMPOSE_FILE"
echo "[deploy] =================================================="

# ---- 0. 校验 .env.production 存在 ----
if [ ! -f .env.production ]; then
    echo "[deploy] .env.production 不存在,无法部署"
    echo "[deploy]    首次部署请参考 deploy/README.md"
    exit 1
fi

# 加载 env(给后续 pg_dump 等用)
set -a
# shellcheck disable=SC1091
source .env.production
set +a

# 允许 CI / 手动部署在不改 ECS .env.production 的情况下覆盖本次发布参数。
if [ -n "${DEPLOY_CORS_ORIGINS:-}" ]; then
    export CORS_ORIGINS="$DEPLOY_CORS_ORIGINS"
fi
if [ -n "${DEPLOY_IMAGE_BASE_URL:-}" ]; then
    export IMAGE_BASE_URL="$DEPLOY_IMAGE_BASE_URL"
fi
export BACKEND_HOST_PORT FRONTEND_HOST_PORT IMAGE_TAG

# ---- 1. 备份数据库(只在 DB 容器已运行时备份)----
mkdir -p "$BACKUP_DIR"
# 兼容旧 compose 和新 production compose，检查两种可能的容器名
if docker compose -f "$COMPOSE_FILE" ps db --status running 2>/dev/null | grep -q db \
   || docker compose ps db --status running 2>/dev/null | grep -q db; then
    BACKUP_FILE="$BACKUP_DIR/$(date +%Y%m%d-%H%M%S).sql.gz"
    echo "[deploy] [1/6] 备份数据库 → $BACKUP_FILE"
    # 用当前运行的 compose 配置来 exec
    if docker compose -f "$COMPOSE_FILE" ps db --status running 2>/dev/null | grep -q db; then
        docker compose -f "$COMPOSE_FILE" exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_FILE"
    else
        docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_FILE"
    fi
    # 清理 7 天前的备份
    find "$BACKUP_DIR" -name "*.sql.gz" -mtime "+$RETENTION_DAYS" -delete 2>/dev/null || true
    echo "[deploy]       当前备份目录("$(du -sh "$BACKUP_DIR" | cut -f1)"):"
    ls -lh "$BACKUP_DIR"/*.sql.gz 2>/dev/null | tail -5 | sed 's/^/         /'
else
    echo "[deploy] [1/6] DB 容器未运行,跳过备份(首次部署)"
fi

# ---- 2. 拉最新代码 ----
echo "[deploy] [2/6] 拉取最新代码"
git fetch origin
PREV_SHA=$(git rev-parse HEAD)
git reset --hard "$DEPLOY_REF"
NEW_SHA=$(git rev-parse HEAD)
if [ "$PREV_SHA" = "$NEW_SHA" ]; then
    echo "[deploy]       无更新($NEW_SHA)"
else
    echo "[deploy]       $PREV_SHA → $NEW_SHA"
    git log --oneline "$PREV_SHA..$NEW_SHA" | sed 's/^/         /'
fi

# ---- 3. 拉取镜像 ----
echo "[deploy] [3/6] 拉取镜像(IMAGE_TAG=$IMAGE_TAG)"
# 登录阿里云 ACR（凭证从 .env.production 读取）
if [ -n "${ACR_USERNAME:-}" ] && [ -n "${ACR_PASSWORD:-}" ]; then
    echo "[deploy]       登录阿里云 ACR..."
    echo "$ACR_PASSWORD" | docker login --username "$ACR_USERNAME" --password-stdin registry.cn-hangzhou.aliyuncs.com
fi
docker compose -f "$COMPOSE_FILE" --env-file .env.production pull backend frontend

# ---- 4. 启动容器 ----
echo "[deploy] [4/6] 启动容器"
docker compose -f "$COMPOSE_FILE" --env-file .env.production up -d --remove-orphans

# ---- 5. 健康检查 ----
echo "[deploy] [5/6] 等待 backend 健康(最多 ${HEALTH_TIMEOUT_SECONDS}s)..."
HEALTHY=0
for i in $(seq 1 $((HEALTH_TIMEOUT_SECONDS / 2))); do
    if curl -fsS "http://localhost:${BACKEND_HOST_PORT}/healthz" > /dev/null 2>&1; then
        echo "[deploy]       backend healthy(第 ${i} 次,$((i * 2))s)"
        HEALTHY=1
        break
    fi
    sleep 2
done
if [ "$HEALTHY" -ne 1 ]; then
    echo "[deploy] backend 健康检查超时"
    echo "[deploy]    docker compose logs --tail=50 backend"
    docker compose -f "$COMPOSE_FILE" logs --tail=50 backend
    exit 1
fi

echo "[deploy] 等待 frontend 健康..."
HEALTHY=0
for i in $(seq 1 $((HEALTH_TIMEOUT_SECONDS / 2))); do
    if curl -fsS "http://localhost:${FRONTEND_HOST_PORT}" > /dev/null 2>&1; then
        echo "[deploy]       frontend healthy(第 ${i} 次,$((i * 2))s)"
        HEALTHY=1
        break
    fi
    sleep 2
done
if [ "$HEALTHY" -ne 1 ]; then
    echo "[deploy] frontend 健康检查超时"
    echo "[deploy]    docker compose logs --tail=50 frontend"
    docker compose -f "$COMPOSE_FILE" logs --tail=50 frontend
    exit 1
fi

# ---- 6. 清理 ----
echo "[deploy] [6/6] 清理 dangling 镜像 + 构建缓存(保留 volume)"
# 注意:严禁 prune volumes!只清 dangling images + build cache
docker image prune -f --filter "dangling=true" 2>&1 | tail -3 | sed 's/^/         /'
docker builder prune -f --keep-storage=500MB 2>&1 | tail -3 | sed 's/^/         /'

echo "[deploy] =================================================="
echo "[deploy] 部署成功 $(date -Iseconds)"
echo "[deploy]    ref       → $DEPLOY_REF"
echo "[deploy]    image_tag → $IMAGE_TAG"
echo "[deploy]    backend   → http://localhost:${BACKEND_HOST_PORT}/healthz"
echo "[deploy]    frontend  → http://localhost:${FRONTEND_HOST_PORT}"
echo "[deploy] =================================================="
