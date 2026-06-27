#!/bin/bash
# ============================================================
# 一键部署：加载镜像 → 启动服务 → 健康检查（在目标服务器运行）
#
# 用法:
#   bash deploy/deploy-offline.sh
#   bash deploy/deploy-offline.sh --env-file /path/to/.env.production
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PACK_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${PACK_ROOT}/.env.production"
COMPOSE_FILE="${PACK_ROOT}/docker-compose.yml"

# 参数解析
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)  ENV_FILE="$2"; shift 2 ;;
    *)           echo "未知参数: $1"; exit 1 ;;
  esac
done

# 前置检查
if [[ ! -f "$ENV_FILE" ]]; then
  echo "错误: 环境变量文件不存在: ${ENV_FILE}"
  echo "请先: cp .env.production.example .env.production && vi .env.production"
  exit 1
fi
if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "错误: compose 文件不存在: ${COMPOSE_FILE}"
  exit 1
fi

get_env_value() {
  local key="$1"
  grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- || true
}

require_env_value() {
  local key="$1"
  local value
  value="$(get_env_value "$key")"
  if [[ -z "$value" || "$value" == CHANGEME* || "$value" == *YOUR_* ]]; then
    echo "错误: ${key} 未填写真实值"
    exit 1
  fi
}

for key in RELEASE_TAG POSTGRES_PASSWORD JWT_SECRET_KEY SUPER_ADMIN_EMAIL SUPER_ADMIN_INITIAL_PASSWORD API_BASE_URL CORS_ORIGINS; do
  require_env_value "$key"
done

if [[ "$(get_env_value SEED_DEMO_ACCOUNTS)" == "true" ]]; then
  echo "错误: 生产离线部署不允许 SEED_DEMO_ACCOUNTS=true"
  exit 1
fi

if [[ "$(get_env_value API_BASE_URL)" == https://* && "$(get_env_value REFRESH_COOKIE_SECURE)" != "true" ]]; then
  echo "错误: HTTPS 公网入口必须设置 REFRESH_COOKIE_SECURE=true"
  exit 1
fi

echo ""
echo "=========================================="
echo " BuildLink EA 离线部署"
echo "=========================================="
echo ""

# ── 1/3 加载镜像 ──
echo "=== 1/3 加载 Docker 镜像 ==="
bash "${SCRIPT_DIR}/load-images.sh"

# ── 2/3 启动服务 ──
echo ""
echo "=== 2/3 启动服务 ==="
cd "$PACK_ROOT"
docker compose -f docker-compose.yml --env-file "$ENV_FILE" up -d

# ── 3/3 健康检查（循环等待，最多 120 秒）──
echo ""
echo "=== 3/3 健康检查 ==="

BACKEND_PORT=$(grep -E '^BACKEND_HOST_PORT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || true)
BACKEND_PORT="${BACKEND_PORT:-8001}"

MAX_WAIT=120
INTERVAL=5
ELAPSED=0

echo "等待后端就绪 (http://localhost:${BACKEND_PORT}/healthz)，最多 ${MAX_WAIT}s ..."
while [[ $ELAPSED -lt $MAX_WAIT ]]; do
  HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${BACKEND_PORT}/healthz" 2>/dev/null || echo "000")
  if [[ "$HTTP_CODE" == "200" ]]; then
    echo "  后端就绪 (${ELAPSED}s)"
    break
  fi
  echo "  等待中... (${ELAPSED}s, HTTP ${HTTP_CODE})"
  sleep "$INTERVAL"
  ELAPSED=$((ELAPSED + INTERVAL))
done

if [[ $ELAPSED -ge $MAX_WAIT ]]; then
  echo ""
  echo "[失败] 后端 ${MAX_WAIT}s 内未就绪，打印最近日志："
  docker compose -f docker-compose.yml logs --tail=50 backend
  echo ""
  echo "排查命令："
  echo "  docker compose -f docker-compose.yml ps"
  echo "  docker compose -f docker-compose.yml logs backend"
  echo "  docker compose -f docker-compose.yml logs db"
  exit 1
fi

# 检查前端
FRONTEND_PORT=$(grep -E '^FRONTEND_HOST_PORT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || true)
FRONTEND_PORT="${FRONTEND_PORT:-3001}"
FRONTEND_CODE=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${FRONTEND_PORT}" 2>/dev/null || echo "000")
echo "  前端: HTTP ${FRONTEND_CODE} (http://localhost:${FRONTEND_PORT})"

PUBLIC_ORIGIN="$(get_env_value CORS_ORIGINS | cut -d, -f1)"
PUBLIC_ORIGIN="${PUBLIC_ORIGIN%/}"
if [[ -n "$PUBLIC_ORIGIN" ]]; then
  PUBLIC_CODE=$(curl -s -o /dev/null -w '%{http_code}' "${PUBLIC_ORIGIN}/healthz" 2>/dev/null || echo "000")
  echo "  公网入口: HTTP ${PUBLIC_CODE} (${PUBLIC_ORIGIN}/healthz)"
  if [[ "$PUBLIC_CODE" != "200" ]]; then
    echo ""
    echo "[警告] 容器直连已就绪,但公网入口未通过。请检查宿主机 Nginx 的 proxy_pass 端口与 .env.production 中的 FRONTEND_HOST_PORT/BACKEND_HOST_PORT 是否一致。"
  fi
fi

echo ""
echo "=== 容器状态 ==="
docker compose -f docker-compose.yml ps

echo ""
echo "=========================================="
echo " 部署完成"
echo "=========================================="
echo "  公网首页:   ${PUBLIC_ORIGIN}"
echo "  运营后台:   ${PUBLIC_ORIGIN}/zh/operator"
echo "  健康检查:   ${PUBLIC_ORIGIN}/healthz"
echo "  本机前端:   http://localhost:${FRONTEND_PORT}"
echo "  本机后端:   http://localhost:${BACKEND_PORT}/healthz"
echo "  本机 API:   http://localhost:${BACKEND_PORT}/docs"
echo "=========================================="
