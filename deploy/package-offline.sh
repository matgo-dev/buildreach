#!/bin/bash
# ============================================================
# 离线部署包打包脚本（在打包机运行，需要外网）
#
# 用法:
#   bash deploy/package-offline.sh --api-url https://your-domain.com --tag 20260623
#
# 产出:
#   buildlink-offline-<TAG>.tar.gz
# ============================================================
set -euo pipefail

# Apple Silicon / x86 打包机都统一用 BuildKit,避免旧构建器复用异构缓存导致平台不匹配。
export DOCKER_BUILDKIT="${DOCKER_BUILDKIT:-1}"
# macOS 上 shasum 依赖 Perl locale,固定 C locale 避免 C.UTF-8 不可用时 panic。
export LC_ALL=C
export LANG=C

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# ── 参数解析 ──
RELEASE_TAG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)      RELEASE_TAG="$2"; shift 2 ;;
    *)          echo "未知参数: $1"; exit 1 ;;
  esac
done

# ── 参数校验 ──
if [[ -z "$RELEASE_TAG" ]]; then
  echo "错误: 必须指定 --tag"
  echo "用法: bash deploy/package-offline.sh --tag 20260623"
  exit 1
fi

BACKEND_IMAGE="buildlink-backend:${RELEASE_TAG}"
FRONTEND_IMAGE="buildlink-frontend:${RELEASE_TAG}"
PG_IMAGE="postgres:16.4-alpine"

OUTPUT_DIR="${PROJECT_ROOT}/buildlink-offline"
IMAGES_DIR="${OUTPUT_DIR}/images"
ARCHIVE_NAME="buildlink-offline-${RELEASE_TAG}.tar.gz"

ensure_amd64_image() {
  local image="$1"
  local arch=""
  arch="$(docker image inspect --format '{{.Architecture}}' "$image" 2>/dev/null || true)"
  if [[ "$arch" == "amd64" ]]; then
    echo "  本地已有 amd64 镜像,跳过 pull: ${image}"
    return
  fi
  docker pull --platform linux/amd64 "$image"
}

# ── 前置工具检查 ──
for cmd in docker git tar; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "错误: 缺少必要工具: $cmd"
    exit 1
  fi
done

# ── 前端静态资产检查 ──
BANNER_PUBLIC_DIR="${PROJECT_ROOT}/frontend/public/banners"
FLOOR_PUBLIC_DIR="${PROJECT_ROOT}/frontend/public/images/floors"
BANNER_COUNT=$(find "$BANNER_PUBLIC_DIR" -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -o -name '*.webp' \) 2>/dev/null | wc -l | tr -d ' ')
if [[ "$BANNER_COUNT" == "0" ]]; then
  echo "错误: 未找到首页轮播图: ${BANNER_PUBLIC_DIR}"
  exit 1
fi
for f in tools.webp safety.webp fasteners.webp electrical.webp doors.webp decoration.webp; do
  if [[ ! -f "${FLOOR_PUBLIC_DIR}/${f}" ]]; then
    echo "错误: 缺少首页楼层背景图: ${FLOOR_PUBLIC_DIR}/${f}"
    exit 1
  fi
done

echo ""
echo "=========================================="
echo " BuildLink EA 离线部署包打包"
echo "=========================================="
echo "  Release Tag:  ${RELEASE_TAG}"
echo "  API URL:      运行时通过 .env 的 API_BASE_URL 配置"
echo "  Platform:     linux/amd64"
echo "=========================================="
echo ""

# ── 0/6 清理旧产物 ──
echo "=== 0/6 清理旧产物 ==="
rm -rf "${OUTPUT_DIR}"
rm -f "${PROJECT_ROOT}/${ARCHIVE_NAME}"

# ── 1/6 拉取 postgres 基础镜像（指定平台）──
echo ""
echo "=== 1/6 拉取 ${PG_IMAGE} (linux/amd64) ==="
ensure_amd64_image "${PG_IMAGE}"

# ── 2/6 构建后端镜像 ──
echo ""
echo "=== 2/6 构建后端镜像 → ${BACKEND_IMAGE} ==="
docker build --platform linux/amd64 \
  --build-arg BUILD_COMMIT="$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD)" \
  --build-arg BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -t "${BACKEND_IMAGE}" \
  "${PROJECT_ROOT}/backend"

# ── 3/6 构建前端镜像 ──
echo ""
echo "=== 3/6 构建前端镜像 → ${FRONTEND_IMAGE} ==="
docker build --platform linux/amd64 \
  -t "${FRONTEND_IMAGE}" \
  "${PROJECT_ROOT}/frontend"

# ── 4/6 导出镜像为 tar ──
echo ""
echo "=== 4/6 导出镜像为 tar ==="
mkdir -p "${IMAGES_DIR}"
docker save "${PG_IMAGE}"        -o "${IMAGES_DIR}/postgres-16.4-alpine.tar"
echo "  → postgres-16.4-alpine.tar"
docker save "${BACKEND_IMAGE}"   -o "${IMAGES_DIR}/buildlink-backend-${RELEASE_TAG}.tar"
echo "  → buildlink-backend-${RELEASE_TAG}.tar"
docker save "${FRONTEND_IMAGE}"  -o "${IMAGES_DIR}/buildlink-frontend-${RELEASE_TAG}.tar"
echo "  → buildlink-frontend-${RELEASE_TAG}.tar"

# 生成 sha256 校验文件
echo "  生成 sha256 校验..."
(cd "${IMAGES_DIR}" && shasum -a 256 *.tar > sha256sums.txt)
cat "${IMAGES_DIR}/sha256sums.txt" | sed 's/^/    /'

# ── 5/6 组装部署包 ──
echo ""
echo "=== 5/6 组装部署包 ==="
mkdir -p "${OUTPUT_DIR}/deploy" "${OUTPUT_DIR}/data" "${OUTPUT_DIR}/logs"

# 部署文件
# 包内统一用 docker-compose.yml，部署时直接 docker compose up -d
cp "${PROJECT_ROOT}/docker-compose.offline.yml"  "${OUTPUT_DIR}/docker-compose.yml"
cp "${PROJECT_ROOT}/.env.production.example"      "${OUTPUT_DIR}/"
for f in load-images.sh deploy-offline.sh init-data.sh nginx-host.conf.example; do
  [[ -f "${PROJECT_ROOT}/deploy/${f}" ]] && cp "${PROJECT_ROOT}/deploy/${f}" "${OUTPUT_DIR}/deploy/"
done
[[ -f "${PROJECT_ROOT}/deploy/README-deploy.md" ]] && cp "${PROJECT_ROOT}/deploy/README-deploy.md" "${OUTPUT_DIR}/deploy/"

# 白名单复制轻量 data/ — 大体积商品批次不进入应用离线包。
DATA_SRC="${PROJECT_ROOT}/data"
DATA_DST="${OUTPUT_DIR}/data"

# 首页轮播图进入应用离线包,用于 OpenResty 直接 serve /banners/ 与后端扫描 /srv/banners。
mkdir -p "${DATA_DST}/banners"
cp -R "${BANNER_PUBLIC_DIR}/." "${DATA_DST}/banners/"

if [[ -d "${DATA_SRC}" ]]; then
  # 品类相关 CSV / JSON
  for f in categories.csv attr_templates.csv category_names_en.json floor_category_mapping.csv; do
    [[ -f "${DATA_SRC}/${f}" ]] && cp "${DATA_SRC}/${f}" "${DATA_DST}/"
  done

  # 品类导入脚本依赖 categories_full_tree.json;商品批次 output_xfs_* 单独打资产包上传。
  if [[ -f "${DATA_SRC}/xfs/categories_full_tree.json" ]]; then
    mkdir -p "${DATA_DST}/xfs"
    cp "${DATA_SRC}/xfs/categories_full_tree.json" "${DATA_DST}/xfs/"
  fi
else
  echo "  警告: ${DATA_SRC} 不存在，跳过数据复制"
fi

# 生成 manifest.json
GIT_SHA="$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cat > "${OUTPUT_DIR}/manifest.json" <<MANIFEST
{
  "release_tag": "${RELEASE_TAG}",
  "git_sha": "${GIT_SHA}",
  "build_time": "${BUILD_TIME}",
  "api_base_url": "runtime (.env API_BASE_URL)",
  "images": {
    "postgres": "${PG_IMAGE}",
    "backend": "${BACKEND_IMAGE}",
    "frontend": "${FRONTEND_IMAGE}"
  },
  "included_data": [
    "data/banners/",
    "data/categories.csv",
    "data/attr_templates.csv",
    "data/category_names_en.json",
    "data/floor_category_mapping.csv",
    "data/xfs/categories_full_tree.json"
  ],
  "external_data_required": [
    "data/xfs/output_xfs_YYYYMMDD_HHMMSS/"
  ],
  "nginx_template": "deploy/nginx-host.conf.example"
}
MANIFEST

echo "  manifest.json:"
cat "${OUTPUT_DIR}/manifest.json" | sed 's/^/    /'

# ── 6/6 打包 ──
echo ""
echo "=== 6/6 打包 ==="
tar czf "${PROJECT_ROOT}/${ARCHIVE_NAME}" -C "$(dirname "$OUTPUT_DIR")" "$(basename "$OUTPUT_DIR")"

echo ""
echo "=========================================="
echo " 离线部署包已生成"
echo "=========================================="
echo "  文件: ${ARCHIVE_NAME}"
ls -lh "${PROJECT_ROOT}/${ARCHIVE_NAME}" | awk '{print "  大小: "$5}'
echo ""
echo "  下一步:"
echo "    scp ${ARCHIVE_NAME} user@server:/opt/"
echo "    # 服务器上 .env.production 的 RELEASE_TAG 必须填: ${RELEASE_TAG}"
echo "=========================================="
