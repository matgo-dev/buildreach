#!/bin/bash
# ============================================================
# 初始化业务数据：品类 → 轮播图 → 商品（部署后手动跑一次）
#
# 用法:
#   bash deploy/init-data.sh                           # 全量初始化
#   bash deploy/init-data.sh --skip-products           # 跳过商品导入
#   bash deploy/init-data.sh --skip-banners            # 跳过轮播图
#   bash deploy/init-data.sh --skip-categories         # 跳过品类
#   bash deploy/init-data.sh --yes                     # 商品导入跳过确认
#   bash deploy/init-data.sh --batch data/xfs/<批次>   # 指定商品批次目录(可重复)
#   bash deploy/init-data.sh --batch-dir data/xfs      # 显式导入目录下所有 output_xfs_* 批次
#   bash deploy/init-data.sh --compose-file docker-compose.yml
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PACK_ROOT="$(dirname "$SCRIPT_DIR")"

# 默认值
COMPOSE_FILE="${PACK_ROOT}/docker-compose.offline.yml"
ENV_FILE="${PACK_ROOT}/.env.production"
DATA_DIR="${PACK_ROOT}/data"
BATCH_DIRS=()
BATCH_PARENT_DIR=""
SKIP_CATEGORIES=false
SKIP_BANNERS=false
SKIP_PRODUCTS=false
AUTO_YES=false

# 参数解析
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-categories)  SKIP_CATEGORIES=true; shift ;;
    --skip-banners)     SKIP_BANNERS=true; shift ;;
    --skip-products)    SKIP_PRODUCTS=true; shift ;;
    --yes)              AUTO_YES=true; shift ;;
    --batch)            BATCH_DIRS+=("$2"); shift 2 ;;
    --batch-dir)        BATCH_PARENT_DIR="$2"; shift 2 ;;
    --compose-file)     COMPOSE_FILE="$2"; shift 2 ;;
    --env-file)         ENV_FILE="$2"; shift 2 ;;
    *)                  echo "未知参数: $1"; exit 1 ;;
  esac
done

resolve_batch_path() {
  local batch_dir="$1"
  if [[ ! -d "$batch_dir" ]]; then
    echo "  [错误] 商品批次目录不存在: $batch_dir" >&2
    exit 1
  fi

  local data_abs batch_abs rel
  data_abs="$(cd "$DATA_DIR" && pwd -P)"
  batch_abs="$(cd "$batch_dir" && pwd -P)"
  case "${batch_abs}/" in
    "${data_abs}/"*)
      rel="${batch_abs#${data_abs}/}"
      ;;
    *)
      echo "  [错误] 商品批次目录必须位于 data/ 下: $batch_dir" >&2
      exit 1
      ;;
  esac
  echo "/data/${rel}"
}

append_batch_dir_candidates() {
  local parent_dir="$1"
  if [[ ! -d "$parent_dir" ]]; then
    echo "  [错误] --batch-dir 目录不存在: $parent_dir" >&2
    exit 1
  fi

  local found=false
  while IFS= read -r dir; do
    found=true
    BATCH_DIRS+=("$dir")
  done < <(
    find "$parent_dir" -maxdepth 1 -mindepth 1 -type d -name 'output_xfs_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9]' \
      | sort
  )

  if [[ "$found" == "false" ]]; then
    echo "  [错误] --batch-dir 未找到符合 output_xfs_YYYYMMDD_HHMMSS 规则的批次目录: $parent_dir" >&2
    exit 1
  fi
}

# compose 命令前缀
DC="docker compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE}"
BACKEND_CONTAINER=$(${DC} ps -q backend 2>/dev/null || true)
if [[ -z "$BACKEND_CONTAINER" ]]; then
  echo "错误: backend 容器未运行，请先启动服务"
  echo "  bash deploy/deploy-offline.sh"
  exit 1
fi

echo ""
echo "=========================================="
echo " BuildLink EA 数据初始化"
echo "=========================================="
echo ""

# ── 1/5 拷贝数据文件到容器 ──
echo "=== [1/5] 拷贝数据文件到容器 ==="
# import_categories_xfs.py 默认读 PROJECT_ROOT/data/xfs/categories_full_tree.json
# import_products_xfs.py --batch 读批次目录
# 两个脚本都基于 PROJECT_ROOT = backend 的上级目录
# 容器里 backend 代码在 /app，所以 PROJECT_ROOT = /app/..  → 数据拷到 /data
docker exec "${BACKEND_CONTAINER}" rm -rf /data 2>/dev/null || true
docker cp "${DATA_DIR}" "${BACKEND_CONTAINER}:/data"
echo "  数据已拷贝到容器 /data"

# ── 2/5 品类树（独立品类导入脚本） ──
if [[ "$SKIP_CATEGORIES" == "false" ]]; then
  echo ""
  echo "=== [2/5] 导入品类树 ==="
  docker exec "${BACKEND_CONTAINER}" python scripts/import_categories_xfs.py \
    --file /data/xfs/categories_full_tree.json
  echo "  品类导入完成"
else
  echo ""
  echo "=== [2/5] 跳过品类导入（--skip-categories）==="
fi

# ── 3/5 轮播图 ──
if [[ "$SKIP_BANNERS" == "false" ]]; then
  echo ""
  echo "=== [3/5] 初始化轮播图 ==="
  BANNER_FILES=$(find "${DATA_DIR}/banners" -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -o -name '*.webp' \) 2>/dev/null)
  if [[ -n "$BANNER_FILES" ]]; then
    docker exec "${BACKEND_CONTAINER}" mkdir -p /app/uploads/banners
    BANNER_COUNT=0
    while IFS= read -r img; do
      docker cp "$img" "${BACKEND_CONTAINER}:/app/uploads/banners/"
      BANNER_COUNT=$((BANNER_COUNT + 1))
    done <<< "$BANNER_FILES"
    echo "  轮播图文件已复制: ${BANNER_COUNT} 个"

    # 运行 seed_banners.py（如果存在）
    if docker exec "${BACKEND_CONTAINER}" test -f scripts/seed_banners.py; then
      docker exec "${BACKEND_CONTAINER}" python scripts/seed_banners.py
      echo "  轮播图 DB 记录已初始化"
    else
      echo "  警告: scripts/seed_banners.py 不存在，跳过 DB 记录插入"
      echo "  可通过运营后台手动添加轮播图"
    fi
  else
    echo "  跳过: data/banners/ 目录不存在或无图片文件"
  fi
else
  echo ""
  echo "=== [3/5] 跳过轮播图（--skip-banners）==="
fi

# ── 4/5 商品导入 ──
if [[ "$SKIP_PRODUCTS" == "false" ]]; then
  echo ""
  echo "=== [4/5] 商品导入 ==="

  # 前置检查：品类是否已存在
  CAT_COUNT=$(docker exec "${BACKEND_CONTAINER}" python -c "
from sqlalchemy import create_engine, text
from app.core.config import settings
from app.db.url import prepare_sync_url
engine = create_engine(prepare_sync_url(str(settings.DATABASE_URL)))
with engine.connect() as conn:
    r = conn.execute(text('SELECT COUNT(*) FROM categories WHERE is_active = true'))
    print(r.scalar())
" 2>/dev/null || echo "0")

  if [[ "$CAT_COUNT" == "0" ]]; then
    echo "  [错误] 品类表为空！请先导入品类（去掉 --skip-categories 重跑）"
    exit 1
  fi
  echo "  品类检查通过（${CAT_COUNT} 条）"

  if [[ -n "$BATCH_PARENT_DIR" ]]; then
    append_batch_dir_candidates "$BATCH_PARENT_DIR"
  fi

  if [[ "${#BATCH_DIRS[@]}" -eq 0 ]]; then
    echo "  [错误] 商品导入必须显式指定批次，禁止自动选择目录。"
    echo "        单批次: bash deploy/init-data.sh --batch data/xfs/output_xfs_YYYYMMDD_HHMMSS"
    echo "        多批次: bash deploy/init-data.sh --batch data/xfs/output_xfs_A --batch data/xfs/output_xfs_B"
    echo "        扫目录: bash deploy/init-data.sh --batch-dir data/xfs"
    exit 1
  fi

  echo "  将导入以下 ${#BATCH_DIRS[@]} 个商品批次:"
  for batch_dir in "${BATCH_DIRS[@]}"; do
    echo "    - $(basename "$batch_dir")"
  done

  if [[ "$AUTO_YES" == "false" ]]; then
    echo ""
    read -rp "  确认按以上顺序导入？(y/N) " CONFIRM
    if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
      echo "  已取消商品导入"
      SKIP_PRODUCTS=true
    fi
  fi

  if [[ "$SKIP_PRODUCTS" == "false" ]]; then
    for BATCH_DIR in "${BATCH_DIRS[@]}"; do
      BATCH_NAME="$(basename "$BATCH_DIR")"
      CONTAINER_BATCH_DIR="$(resolve_batch_path "$BATCH_DIR")"
      echo ""
      echo "  批次目录: ${BATCH_NAME}"

      # dry-run 预检
      echo "  运行 dry-run 预检..."
      docker exec "${BACKEND_CONTAINER}" python scripts/import_products_xfs.py \
        --batch "${CONTAINER_BATCH_DIR}" --dry-run 2>&1 | tail -10

      echo "  正式导入..."
      docker exec "${BACKEND_CONTAINER}" python scripts/import_products_xfs.py \
        --batch "${CONTAINER_BATCH_DIR}" 2>&1
    done
  fi
else
  echo ""
  echo "=== [4/5] 跳过商品导入（--skip-products）==="
fi

# ── 5/5 验证统计 ──
echo ""
echo "=== [5/5] 数据统计 ==="
docker exec "${BACKEND_CONTAINER}" python -c "
from sqlalchemy import create_engine, text
from app.core.config import settings
from app.db.url import prepare_sync_url

engine = create_engine(prepare_sync_url(str(settings.DATABASE_URL)))
tables = {
    '品类':          'SELECT COUNT(*) FROM categories WHERE is_active = true',
    '属性模板':      'SELECT COUNT(*) FROM category_attr_templates',
    '轮播图':        'SELECT COUNT(*) FROM banner_slides',
    '商品(SPU)':     'SELECT COUNT(*) FROM products WHERE deleted_at IS NULL',
    '商品图片':      'SELECT COUNT(*) FROM product_images WHERE deleted_at IS NULL',
}
for label, sql in tables.items():
    try:
        with engine.connect() as conn:
            r = conn.execute(text(sql))
            print(f'  {label}: {r.scalar()}')
    except Exception:
        print(f'  {label}: -')
" 2>/dev/null || echo "  统计查询失败（数据库可能未就绪）"

echo ""
echo "=========================================="
echo " 数据初始化完成"
echo "=========================================="
