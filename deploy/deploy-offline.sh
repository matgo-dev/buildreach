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
COMPOSE_FILE="${PACK_ROOT}/docker-compose.offline.yml"

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
docker compose -f docker-compose.offline.yml --env-file "$ENV_FILE" up -d

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
  docker compose -f docker-compose.offline.yml logs --tail=50 backend
  echo ""
  echo "排查命令："
  echo "  docker compose -f docker-compose.offline.yml ps"
  echo "  docker compose -f docker-compose.offline.yml logs backend"
  echo "  docker compose -f docker-compose.offline.yml logs db"
  exit 1
fi

# 检查前端
FRONTEND_PORT=$(grep -E '^FRONTEND_HOST_PORT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || true)
FRONTEND_PORT="${FRONTEND_PORT:-3001}"
FRONTEND_CODE=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${FRONTEND_PORT}" 2>/dev/null || echo "000")
echo "  前端: HTTP ${FRONTEND_CODE} (http://localhost:${FRONTEND_PORT})"

echo ""
echo "=== 容器状态 ==="
docker compose -f docker-compose.offline.yml ps

echo ""
echo "=========================================="
echo " 部署完成"
echo "=========================================="
echo "  前台首页:   http://<IP>:${FRONTEND_PORT}"
echo "  运营后台:   http://<IP>:${FRONTEND_PORT}/zh/operator"
echo "  API 文档:   http://<IP>:${BACKEND_PORT}/docs"
echo "  健康检查:   http://<IP>:${BACKEND_PORT}/healthz"
echo "=========================================="
