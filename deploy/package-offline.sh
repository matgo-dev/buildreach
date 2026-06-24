#!/bin/bash
# ============================================================
# 离线部署包打包脚本（在打包机运行，需要外网）
#
# 用法:
#   bash deploy/package-offline.sh --api-url http://114.55.135.216:8001 --tag 20260623
#
# 产出:
#   buildlink-offline-<TAG>.tar.gz
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# ── 参数解析 ──
NEXT_PUBLIC_API_BASE_URL=""
RELEASE_TAG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-url)  NEXT_PUBLIC_API_BASE_URL="$2"; shift 2 ;;
    --tag)      RELEASE_TAG="$2"; shift 2 ;;
    *)          echo "未知参数: $1"; exit 1 ;;
  esac
done

# ── 参数校验 ──
if [[ -z "$NEXT_PUBLIC_API_BASE_URL" ]]; then
  echo "错误: 必须指定 --api-url"
  echo "用法: bash deploy/package-offline.sh --api-url http://1.2.3.4:8001 --tag 20260623"
  exit 1
fi
if [[ -z "$RELEASE_TAG" ]]; then
  echo "错误: 必须指定 --tag"
  echo "用法: bash deploy/package-offline.sh --api-url http://1.2.3.4:8001 --tag 20260623"
  exit 1
fi

BACKEND_IMAGE="buildlink-backend:${RELEASE_TAG}"
FRONTEND_IMAGE="buildlink-frontend:${RELEASE_TAG}"
PG_IMAGE="postgres:16.4-alpine"

OUTPUT_DIR="${PROJECT_ROOT}/buildlink-offline"
IMAGES_DIR="${OUTPUT_DIR}/images"
ARCHIVE_NAME="buildlink-offline-${RELEASE_TAG}.tar.gz"

# ── 前置工具检查 ──
for cmd in docker git tar; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "错误: 缺少必要工具: $cmd"
    exit 1
  fi
done

echo ""
echo "=========================================="
echo " BuildLink EA 离线部署包打包"
echo "=========================================="
echo "  API URL:      ${NEXT_PUBLIC_API_BASE_URL}"
echo "  Release Tag:  ${RELEASE_TAG}"
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
docker pull --platform linux/amd64 "${PG_IMAGE}"

# ── 2/6 构建后端镜像 ──
echo ""
echo "=== 2/6 构建后端镜像 → ${BACKEND_IMAGE} ==="
docker build --platform linux/amd64 \
  -t "${BACKEND_IMAGE}" \
  "${PROJECT_ROOT}/backend"

# ── 3/6 构建前端镜像 ──
echo ""
echo "=== 3/6 构建前端镜像 → ${FRONTEND_IMAGE} ==="
docker build --platform linux/amd64 \
  -t "${FRONTEND_IMAGE}" \
  --build-arg NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL}" \
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
cp "${PROJECT_ROOT}/docker-compose.offline.yml"  "${OUTPUT_DIR}/"
cp "${PROJECT_ROOT}/.env.production.example"      "${OUTPUT_DIR}/"
for f in load-images.sh deploy-offline.sh init-data.sh; do
  [[ -f "${PROJECT_ROOT}/deploy/${f}" ]] && cp "${PROJECT_ROOT}/deploy/${f}" "${OUTPUT_DIR}/deploy/"
done
[[ -f "${PROJECT_ROOT}/deploy/README-deploy.md" ]] && cp "${PROJECT_ROOT}/deploy/README-deploy.md" "${OUTPUT_DIR}/deploy/"

# 白名单复制 data/ — 排除 .venv、.DS_Store、__pycache__
DATA_SRC="${PROJECT_ROOT}/data"
DATA_DST="${OUTPUT_DIR}/data"

if [[ -d "${DATA_SRC}" ]]; then
  # 品类相关 CSV / JSON
  for f in categories.csv attr_templates.csv category_names_en.json floor_category_mapping.csv; do
    [[ -f "${DATA_SRC}/${f}" ]] && cp "${DATA_SRC}/${f}" "${DATA_DST}/"
  done

  # 轮播图（只复制图片文件）
  # 优先从 data/banners/，fallback 到 frontend/public/banners/
  BANNER_SRC="${DATA_SRC}/banners"
  if [[ ! -d "$BANNER_SRC" ]] || [[ -z "$(ls -A "$BANNER_SRC" 2>/dev/null)" ]]; then
    BANNER_SRC="${PROJECT_ROOT}/frontend/public/banners"
  fi
  if [[ -d "$BANNER_SRC" ]]; then
    mkdir -p "${DATA_DST}/banners"
    find "${BANNER_SRC}" -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -o -name '*.webp' \) \
      -exec cp {} "${DATA_DST}/banners/" \;
    echo "  轮播图来源: ${BANNER_SRC}"
  fi

  # XFS 商品批次（排除垃圾文件）
  if [[ -d "${DATA_SRC}/xfs" ]]; then
    # 用 rsync 排除不需要的文件；没有 rsync 则用 cp
    if command -v rsync &>/dev/null; then
      rsync -a --exclude='.DS_Store' --exclude='__pycache__' --exclude='.venv' \
        "${DATA_SRC}/xfs/" "${DATA_DST}/xfs/"
    else
      cp -r "${DATA_SRC}/xfs" "${DATA_DST}/"
      find "${DATA_DST}/xfs" -name '.DS_Store' -o -name '__pycache__' | xargs rm -rf 2>/dev/null || true
    fi
  fi
else
  echo "  警告: ${DATA_SRC} 不存在，跳过数据复制"
fi

# 生成 manifest.json
GIT_SHA="$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DATA_BATCHES_JSON="[]"
if [[ -d "${DATA_DST}/xfs" ]]; then
  DATA_BATCHES_JSON="["
  FIRST_BATCH=true
  while IFS= read -r batch_dir; do
    batch_name="$(basename "$batch_dir")"
    if [[ "$FIRST_BATCH" == "true" ]]; then
      FIRST_BATCH=false
    else
      DATA_BATCHES_JSON+=", "
    fi
    DATA_BATCHES_JSON+="\"${batch_name}\""
  done < <(
    find "${DATA_DST}/xfs" -maxdepth 2 -mindepth 1 -type d -name 'output_xfs_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9]' \
      | sort
  )
  DATA_BATCHES_JSON+="]"
fi

cat > "${OUTPUT_DIR}/manifest.json" <<MANIFEST
{
  "release_tag": "${RELEASE_TAG}",
  "git_sha": "${GIT_SHA}",
  "build_time": "${BUILD_TIME}",
  "api_base_url": "${NEXT_PUBLIC_API_BASE_URL}",
  "images": {
    "postgres": "${PG_IMAGE}",
    "backend": "${BACKEND_IMAGE}",
    "frontend": "${FRONTEND_IMAGE}"
  },
  "data_batches": ${DATA_BATCHES_JSON}
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
echo "=========================================="
