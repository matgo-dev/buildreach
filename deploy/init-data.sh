#!/bin/bash
# ============================================================
# 初始化业务数据：品类 → 商品（部署后手动跑一次）
#
# 用法:
#   bash deploy/init-data.sh                           # 全量初始化
#   bash deploy/init-data.sh --skip-products           # 跳过商品导入
#   bash deploy/init-data.sh --skip-categories         # 跳过品类
#   bash deploy/init-data.sh --yes                     # 商品导入跳过确认
#   bash deploy/init-data.sh --batch data/xfs/<批次>   # 指定一个商品批次目录,可重复传
#   bash deploy/init-data.sh --batch-dir data/xfs      # 扫描目录下所有 output_xfs_* 批次
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
BATCH_ROOT=""
SKIP_CATEGORIES=false
SKIP_PRODUCTS=false
AUTO_YES=false

# 参数解析
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-categories)  SKIP_CATEGORIES=true; shift ;;
    --skip-products)    SKIP_PRODUCTS=true; shift ;;
    --yes)              AUTO_YES=true; shift ;;
    --batch)            BATCH_DIRS+=("$2"); shift 2 ;;
    --batch-dir)        BATCH_ROOT="$2"; shift 2 ;;
    --compose-file)     COMPOSE_FILE="$2"; shift 2 ;;
    --env-file)         ENV_FILE="$2"; shift 2 ;;
    *)                  echo "未知参数: $1"; exit 1 ;;
  esac
done

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

# ── 1/4 拷贝数据文件到容器 ──
echo "=== [1/4] 拷贝数据文件到容器 ==="
# import_categories_xfs.py 默认读 PROJECT_ROOT/data/xfs/categories_full_tree.json
# import_products_xfs.py --batch 读批次目录
# 两个脚本都基于 PROJECT_ROOT = backend 的上级目录
# 容器里 backend 代码在 /app，所以 PROJECT_ROOT = /app/..  → 数据拷到 /data
docker exec "${BACKEND_CONTAINER}" rm -rf /data 2>/dev/null || true
docker cp "${DATA_DIR}" "${BACKEND_CONTAINER}:/data"
echo "  数据已拷贝到容器 /data"

# ── 2/4 品类树（独立品类导入脚本） ──
if [[ "$SKIP_CATEGORIES" == "false" ]]; then
  echo ""
  echo "=== [2/4] 导入品类树 ==="
  docker exec "${BACKEND_CONTAINER}" python scripts/import_categories_xfs.py \
    --file /data/xfs/categories_full_tree.json
  echo "  品类导入完成"
else
  echo ""
  echo "=== [2/4] 跳过品类导入（--skip-categories）==="
fi

# ── 3/4 商品导入 ──
if [[ "$SKIP_PRODUCTS" == "false" ]]; then
  echo ""
  echo "=== [3/4] 商品导入 ==="

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

  # 确定批次目录。生产导入必须显式指定,避免目录里多个批次时误导。
  if [[ -n "$BATCH_ROOT" ]]; then
    while IFS= read -r dir; do
      BATCH_DIRS+=("$dir")
    done < <(find "$BATCH_ROOT" -maxdepth 1 -mindepth 1 -type d -name 'output_xfs_*' 2>/dev/null | sort)
  fi

  if [[ "${#BATCH_DIRS[@]}" -eq 0 ]]; then
    echo "  [错误] 未指定商品批次。请使用:"
    echo "    bash deploy/init-data.sh --batch data/xfs/<批次目录>"
    echo "    bash deploy/init-data.sh --batch-dir data/xfs --yes"
    echo "  商品批次通常来自独立资产包,请先在服务器解压到 data/xfs/ 下。"
    echo ""
    echo "  当前可用批次:"
    find "${DATA_DIR}/xfs" -maxdepth 1 -mindepth 1 -type d -name 'output_xfs_*' 2>/dev/null | sort | sed 's/^/    /' || true
    exit 1
  else
    echo "  将导入以下批次:"
    for batch_dir in "${BATCH_DIRS[@]}"; do
      if [[ ! -d "$batch_dir" ]]; then
        echo "  [错误] 批次目录不存在: ${batch_dir}"
        exit 1
      fi
      echo "    - $(basename "$batch_dir")"
    done

    if [[ "$AUTO_YES" == "false" ]]; then
      echo ""
      read -rp "  确认正式导入以上批次？(y/N) " CONFIRM
      if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
        echo "  已取消商品导入"
        SKIP_PRODUCTS=true
      fi
    fi

    if [[ "$SKIP_PRODUCTS" == "false" ]]; then
      for batch_dir in "${BATCH_DIRS[@]}"; do
        BATCH_NAME="$(basename "$batch_dir")"
        echo ""
        echo "  批次目录: ${BATCH_NAME}"

        echo "  运行 dry-run 预检..."
        docker exec "${BACKEND_CONTAINER}" python scripts/import_products_xfs.py \
          --batch "/data/xfs/${BATCH_NAME}" --dry-run 2>&1 | tail -10

        echo "  正式导入..."
        docker exec "${BACKEND_CONTAINER}" python scripts/import_products_xfs.py \
          --batch "/data/xfs/${BATCH_NAME}" 2>&1
      done
    fi
  fi
else
  echo ""
  echo "=== [3/4] 跳过商品导入（--skip-products）==="
fi

# ── 4/4 验证统计 ──
echo ""
echo "=== [4/4] 数据统计 ==="
docker exec "${BACKEND_CONTAINER}" python -c "
from sqlalchemy import create_engine, text
from app.core.config import settings
from app.db.url import prepare_sync_url

engine = create_engine(prepare_sync_url(str(settings.DATABASE_URL)))
tables = {
    '品类':          'SELECT COUNT(*) FROM categories WHERE is_active = true',
    '属性模板':      'SELECT COUNT(*) FROM category_attr_templates',
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
