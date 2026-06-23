# 离线部署包方案

> 目标：在有网环境（开发机/CI）**预构建 linux/amd64 镜像**，打包为 tar，拿到任何一台 Linux x86_64 服务器，**不依赖外部网络**（ACR/GitHub/PyPI/npm），`docker load` + `docker compose up` 即部署。
>
> **离线 = 零网络依赖**：目标服务器上不允许出现 `docker pull`、`docker build`、`pnpm install`、`uv pip install` 等需要外网的命令。基础镜像、应用镜像、数据包必须一次带齐。

---

## 一、部署前提

| 条件 | 要求 |
|------|------|
| **打包机**（Mac / CI） | Docker Engine 24+，能访问外网（拉基础镜像 + 装依赖） |
| **目标服务器** | Linux x86_64，Docker Engine 24+ / Docker Compose V2 |
| 磁盘（目标服务器） | >= 5GB（镜像 ~2GB + 数据 ~500MB + DB + 日志 + 备份） |
| 网络（目标服务器） | **不需要外网**，镜像全部从 tar 加载 |
| 端口/安全组 | 默认需开放 `FRONTEND_HOST_PORT`（默认 3001）和 `BACKEND_HOST_PORT`（默认 8001）；生产环境强烈建议前置 Nginx/Caddy 反代到 80/443，仅开放 80/443 |

---

## 二、整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│  打包机（Mac / CI，有外网）                                        │
│                                                                    │
│  1. bash deploy/package-offline.sh                                 │
│     --api-url http://1.2.3.4:8001 --tag 20260623-1900             │
│                                                                    │
│     a. docker pull --platform linux/amd64 postgres:16.4-alpine     │
│     b. docker build --platform linux/amd64 backend/frontend 镜像   │
│     c. docker save → 导出 3 个 .tar（含 postgres）                 │
│     d. 白名单复制 data/ → 排除 .venv/.DS_Store/临时文件            │
│     e. 生成 manifest.json（tag/sha/时间/API URL/数据批次）         │
│     f. 打包 → buildlink-offline-20260623-1900.tar.gz               │
└──────────────────────────────────────────────────────────────────┘
                          ↓  scp / U盘
┌──────────────────────────────────────────────────────────────────┐
│  目标服务器（Linux x86_64，无外网）                                 │
│                                                                    │
│  1. bash deploy/deploy-offline.sh                                  │
│     a. docker load < images/*.tar  ← 加载镜像 + 校验              │
│     b. docker compose up -d        ← 直接启动                     │
│     c. 循环健康检查 /healthz       ← 最多等 120s                  │
│                                                                    │
│     ├─ db         → PostgreSQL 16.4                                │
│     ├─ backend    → FastAPI (alembic + seed 自动跑)                │
│     └─ frontend   → Next.js                                       │
│                                                                    │
│  2. bash deploy/init-data.sh       ← 手动跑一次，初始化业务数据    │
│     ├─ 品类树 + 属性模板                                           │
│     ├─ 轮播图（文件 + DB 记录）                                    │
│     └─ 商品导入（XFS / 1688，含图片）                              │
└──────────────────────────────────────────────────────────────────┘
```

---

## 三、关键约束（务必通读）

### 3.1 三个 URL 必须互相匹配

> **`NEXT_PUBLIC_API_BASE_URL`、`CORS_ORIGINS`、`IMAGE_BASE_URL` 三者必须基于同一个服务器 IP/域名 + 端口组合，否则前端请求跨域失败、图片加载 404。**

| 变量 | 示例值 | 说明 |
|------|--------|------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://1.2.3.4:8001` | 前端 JS **构建时**注入，运行时不可改 |
| `CORS_ORIGINS` | `http://1.2.3.4:3001` | 后端 CORS 白名单，须与浏览器实际访问的前端 origin 一致 |
| `IMAGE_BASE_URL` | `http://1.2.3.4:8001/static` | 商品图片 URL 前缀 |

**如果用域名**，必须在打前端镜像前确定最终域名（因为 `NEXT_PUBLIC_API_BASE_URL` 构建后不可改）。先用 IP 包可以跑起来，后续切域名**必须重新打前端镜像**。

### 3.2 数据库密码不可随意更改

首次部署填写 `POSTGRES_PASSWORD` 后，PG 容器会在 volume 中初始化该密码。后续**不能直接改 `.env.production` 里的数据库密码**，否则新容器用新密码连不上旧 volume 中的 PG 用户。如需改密，须先进容器 `ALTER USER ... PASSWORD ...`，再改 `.env.production`。

### 3.3 NEXT_PUBLIC_API_BASE_URL 构建后不可改

`NEXT_PUBLIC_*` 变量在 Next.js `build` 时内联到 JS bundle，运行时修改 `.env.production` **无效**。更换 API 地址必须重新打前端镜像。

---

## 四、服务器上需要的文件清单

```
buildlink-offline/                              # 离线部署包（由 package-offline.sh 生成）
├── manifest.json                               # 发布元数据（tag/sha/时间/API URL/镜像名/数据批次）
├── images/                                     # 预构建的 Docker 镜像 tar（linux/amd64）
│   ├── postgres-16.4-alpine.tar                # ~90MB
│   ├── buildlink-backend-<TAG>.tar             # ~500MB
│   └── buildlink-frontend-<TAG>.tar            # ~200MB
├── data/                                       # 初始化数据（白名单复制，不含 .venv/.DS_Store）
│   ├── categories.csv                          # 品类树
│   ├── attr_templates.csv                      # 属性模板
│   ├── category_names_en.json                  # 英文品类名
│   ├── banners/                                # 轮播图原文件
│   │   ├── banner-construction.png
│   │   ├── banner-crane.png
│   │   └── banner-skyline.jpg
│   └── xfs/                                    # 商品批次数据（含图片）
│       └── output_xfs_20260623_023104/
├── docker-compose.offline.yml                  # 离线部署专用 compose（image: 不 build:）
├── .env.production.example                     # 配置模板（不含真实密钥）
└── deploy/
    ├── package-offline.sh                      # 打包机运行：构建 + 导出 + 组装
    ├── load-images.sh                          # 目标服务器：docker load + 校验
    ├── deploy-offline.sh                       # 目标服务器：load + start + 健康检查（一键）
    ├── init-data.sh                            # 目标服务器：品类 + 轮播 + 商品初始化
    └── README-deploy.md                        # 操作手册
```

> **注意**：发布包**不包含** `.env.production` 真实文件，只包含 `.env.production.example` 模板。真实配置在目标服务器上手动填写。

---

## 五、容器启动时自动做的事（不用管）

后端容器启动时 `docker-entrypoint.sh` 自动执行：

```
1. 等待数据库就绪（最多 2 分钟）
2. alembic upgrade head（建表 / 跑迁移）
3. seed.py 自动跑：
   ├─ 同步 RBAC 权限点 + 角色分配
   ├─ 创建 super admin（从 .env 读邮箱密码）
   ├─ 翻译术语表
   └─ 按 SEED_DEMO_ACCOUNTS 决定是否种 demo 账号
4. uvicorn 启动
```

这些全部幂等，重启容器不会重复创建。

---

## 六、部署后手动做的事（init-data.sh）

以下数据不放在容器启动脚本里，原因：
- 数据量可能大（XFS 批次 180MB+）
- 失败要看日志、人工确认
- 重跑需要人工判断

### 6.1 品类树

```bash
# 数据来源
data/xfs/categories_full_tree.json   # 鑫方盛全量品类树 JSON

# 脚本
backend/scripts/import_categories_xfs.py
# 默认读 PROJECT_ROOT/data/xfs/categories_full_tree.json
# 支持 --file 指定路径、--dry-run 预检
# 用 prepare_sync_url 把 async DATABASE_URL 转为同步连接

# 幂等策略
按 (name_zh, parent_code) 匹配现有节点，沿用 code；新节点取空号
append-only，永不物理删除品类
L1 short_name 三语人工映射，标记 manual
```

### 6.2 轮播图

```bash
# 数据来源
data/banners/*.png|*.jpg      # 图片文件

# 处理方式
1. docker cp → 容器 /app/uploads/banners/（持久化 volume）
2. 通过 seed_banners.py 插入 banner_slides 记录（幂等：先 SELECT COUNT 检查）
   banner_slides 是 i18n 表，seed_banners.py 走 ORM/业务 schema，
   正确填 source_lang、trans_meta、中英文标题
   ❌ 不用裸 SQL INSERT

# 图片存储
/app/uploads/banners/         # Docker Volume，不在镜像里
                              # 部署后可通过运营后台热更新
```

> 需新建 `backend/scripts/seed_banners.py`，走 ORM + i18n 规范。

### 6.3 商品导入

```bash
# 数据来源
data/xfs/output_xfs_20260623_023104/
├── run.json
├── categories_raw.json
└── categories/
    └── {品类路径}/offers/{product_id}/
        ├── offer.json          # 商品数据
        └── images/             # 商品图片
            ├── main_*.jpg
            └── detail_*.jpg

# 脚本
backend/scripts/import_products_xfs.py    # XFS 数据
backend/scripts/import_products_1688.py   # 1688 数据

# 执行方式
单线程串行，一个 DB 连接从头用到尾
逐条商品独立事务，一条失败不影响其他
默认 dry-run 模式（只预检不写入），正式导入必须加 --yes 参数

# 幂等策略
按 spu_code upsert，重跑会覆盖更新（属性/图片 delete+insert）

# 图片处理
脚本内 shutil.copy2 复制到 /app/uploads/products/{spu_code}/
图片在 Docker Volume 里，不在镜像里

# 日志
导入日志默认输出到 stdout（容器内可通过 docker logs 查看）
建议宿主机挂载 logs/ 目录持久化日志：
  docker compose exec backend python scripts/import_products_xfs.py ... 2>&1 | tee logs/import_$(date +%Y%m%d_%H%M%S).log
```

---

## 七、需要新建的文件

### 7.1 `deploy/package-offline.sh`（打包机运行）

在有网环境构建 **linux/amd64** 镜像并打包为离线部署包。

```bash
#!/bin/bash
# 在打包机（Mac / CI）运行，生成离线部署包
# 用法: bash deploy/package-offline.sh --api-url http://1.2.3.4:8001 --tag 20260623-1900
#        --api-url   目标服务器的前端 API 地址（必填）
#        --tag       发布标签（必填），建议 YYYYMMDD-HHMM 或 git short sha
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
  echo "错误: 必须指定 --api-url，例: --api-url http://1.2.3.4:8001"
  exit 1
fi
if [[ -z "$RELEASE_TAG" ]]; then
  echo "错误: 必须指定 --tag，例: --tag 20260623-1900 或 --tag $(git -C "$PROJECT_ROOT" rev-parse --short HEAD)"
  exit 1
fi

BACKEND_IMAGE="buildlink-backend:${RELEASE_TAG}"
FRONTEND_IMAGE="buildlink-frontend:${RELEASE_TAG}"
PG_IMAGE="postgres:16.4-alpine"

OUTPUT_DIR="${PROJECT_ROOT}/buildlink-offline"
IMAGES_DIR="${OUTPUT_DIR}/images"

# ── 0/6 清理旧产物 ──
echo "=== 0/6 清理旧产物 ==="
rm -rf "${OUTPUT_DIR}"

# ── 1/6 拉取 postgres 基础镜像（指定平台）──
echo "=== 1/6 拉取 ${PG_IMAGE} (linux/amd64) ==="
docker pull --platform linux/amd64 "${PG_IMAGE}"

# ── 2/6 构建后端镜像 ──
echo "=== 2/6 构建后端镜像 (linux/amd64) ==="
docker build --platform linux/amd64 \
  -t "${BACKEND_IMAGE}" \
  "${PROJECT_ROOT}/backend"

# ── 3/6 构建前端镜像 ──
echo "=== 3/6 构建前端镜像 (linux/amd64) ==="
docker build --platform linux/amd64 \
  -t "${FRONTEND_IMAGE}" \
  --build-arg NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL}" \
  "${PROJECT_ROOT}/frontend"

# ── 4/6 导出镜像为 tar ──
echo "=== 4/6 导出镜像为 tar ==="
mkdir -p "${IMAGES_DIR}"
docker save "${PG_IMAGE}"        -o "${IMAGES_DIR}/postgres-16.4-alpine.tar"
docker save "${BACKEND_IMAGE}"   -o "${IMAGES_DIR}/buildlink-backend-${RELEASE_TAG}.tar"
docker save "${FRONTEND_IMAGE}"  -o "${IMAGES_DIR}/buildlink-frontend-${RELEASE_TAG}.tar"

# ── 5/6 组装部署包 ──
echo "=== 5/6 组装部署包 ==="
mkdir -p "${OUTPUT_DIR}/deploy" "${OUTPUT_DIR}/data" "${OUTPUT_DIR}/logs"

# 复制部署文件
cp "${PROJECT_ROOT}/docker-compose.offline.yml"  "${OUTPUT_DIR}/"
cp "${PROJECT_ROOT}/.env.production.example"      "${OUTPUT_DIR}/"
cp "${PROJECT_ROOT}/deploy/init-data.sh"          "${OUTPUT_DIR}/deploy/"
cp "${PROJECT_ROOT}/deploy/load-images.sh"        "${OUTPUT_DIR}/deploy/"
cp "${PROJECT_ROOT}/deploy/deploy-offline.sh"     "${OUTPUT_DIR}/deploy/"
cp "${PROJECT_ROOT}/deploy/README-deploy.md"      "${OUTPUT_DIR}/deploy/"

# 白名单复制 data/ — 排除 .venv、临时输出、.DS_Store
DATA_SRC="${PROJECT_ROOT}/data"
DATA_DST="${OUTPUT_DIR}/data"
# 品类相关
for f in categories.csv attr_templates.csv category_names_en.json floor_category_mapping.csv; do
  [[ -f "${DATA_SRC}/${f}" ]] && cp "${DATA_SRC}/${f}" "${DATA_DST}/"
done
# 轮播图
if [[ -d "${DATA_SRC}/banners" ]]; then
  mkdir -p "${DATA_DST}/banners"
  find "${DATA_SRC}/banners" -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -o -name '*.webp' \) \
    -exec cp {} "${DATA_DST}/banners/" \;
fi
# XFS 商品批次
if [[ -d "${DATA_SRC}/xfs" ]]; then
  rsync -a --exclude='.DS_Store' --exclude='__pycache__' --exclude='.venv' \
    "${DATA_SRC}/xfs/" "${DATA_DST}/xfs/"
fi

# 生成 manifest.json
GIT_SHA="$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
# 获取数据批次目录名
DATA_BATCH=""
if [[ -d "${DATA_DST}/xfs" ]]; then
  DATA_BATCH="$(ls -1 "${DATA_DST}/xfs/" 2>/dev/null | head -1)"
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
  "data_batch": "${DATA_BATCH}"
}
MANIFEST

echo "manifest.json:"
cat "${OUTPUT_DIR}/manifest.json"

# ── 6/6 打包 ──
echo "=== 6/6 打包 ==="
ARCHIVE_NAME="buildlink-offline-${RELEASE_TAG}.tar.gz"
tar czf "${PROJECT_ROOT}/${ARCHIVE_NAME}" -C "$(dirname "$OUTPUT_DIR")" "$(basename "$OUTPUT_DIR")"

echo ""
echo "离线部署包已生成: ${ARCHIVE_NAME}"
ls -lh "${PROJECT_ROOT}/${ARCHIVE_NAME}"
echo ""
echo "下一步: scp ${ARCHIVE_NAME} user@server:/opt/"
```

### 7.2 `deploy/load-images.sh`（目标服务器运行）

```bash
#!/bin/bash
# 在目标服务器运行，加载预构建的 Docker 镜像并校验
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PACK_ROOT="$(dirname "$SCRIPT_DIR")"
IMAGES_DIR="${PACK_ROOT}/images"

if [[ ! -d "$IMAGES_DIR" ]]; then
  echo "错误: 镜像目录不存在: ${IMAGES_DIR}"
  exit 1
fi

echo "=== 加载 Docker 镜像 ==="
LOADED=0
FAILED=0
for tar in "${IMAGES_DIR}"/*.tar; do
  [[ ! -f "$tar" ]] && continue
  echo "  loading $(basename "$tar") ..."
  if docker load -i "$tar"; then
    ((LOADED++))
  else
    echo "  [失败] $(basename "$tar")"
    ((FAILED++))
  fi
done

echo ""
echo "=== 加载结果: 成功 ${LOADED}, 失败 ${FAILED} ==="

# 校验镜像是否存在
echo ""
echo "=== 校验已加载镜像 ==="

# 从 manifest.json 读取镜像名（如果存在）
MANIFEST="${PACK_ROOT}/manifest.json"
if [[ -f "$MANIFEST" ]] && command -v python3 &>/dev/null; then
  BACKEND_IMG=$(python3 -c "import json; print(json.load(open('${MANIFEST}'))['images']['backend'])")
  FRONTEND_IMG=$(python3 -c "import json; print(json.load(open('${MANIFEST}'))['images']['frontend'])")
  PG_IMG=$(python3 -c "import json; print(json.load(open('${MANIFEST}'))['images']['postgres'])")

  for img in "$PG_IMG" "$BACKEND_IMG" "$FRONTEND_IMG"; do
    if docker image inspect "$img" &>/dev/null; then
      echo "  [OK] $img"
    else
      echo "  [缺失] $img"
      FAILED=1
    fi
  done
else
  # 无 manifest，简单列出
  docker images | grep -E 'postgres|buildlink'
fi

if [[ "$FAILED" -gt 0 ]]; then
  echo ""
  echo "有镜像加载失败或缺失，请检查 tar 文件完整性"
  exit 1
fi

echo ""
echo "镜像加载完成"
```

### 7.3 `deploy/deploy-offline.sh`（目标服务器一键部署）

合并加载镜像 + 启动 + 健康检查，减少人工步骤。

```bash
#!/bin/bash
# 一键部署：加载镜像 → 启动服务 → 健康检查
# 用法: bash deploy/deploy-offline.sh [--env-file .env.production]
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

# 读取后端端口
BACKEND_PORT=$(grep -E '^BACKEND_HOST_PORT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "8001")
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
FRONTEND_PORT=$(grep -E '^FRONTEND_HOST_PORT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "3001")
FRONTEND_PORT="${FRONTEND_PORT:-3001}"
FRONTEND_CODE=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${FRONTEND_PORT}" 2>/dev/null || echo "000")
echo "  前端: HTTP ${FRONTEND_CODE} (http://localhost:${FRONTEND_PORT})"

echo ""
echo "=== 容器状态 ==="
docker compose -f docker-compose.offline.yml ps

echo ""
echo "部署完成"
echo "  前台首页:   http://<IP>:${FRONTEND_PORT}"
echo "  运营后台:   http://<IP>:${FRONTEND_PORT}/zh/operator"
echo "  API 文档:   http://<IP>:${BACKEND_PORT}/docs"
echo "  健康检查:   http://<IP>:${BACKEND_PORT}/healthz"
```

### 7.4 `docker-compose.offline.yml`

与现有 compose 文件的关系：

| 文件 | image 来源 | 场景 |
|------|-----------|------|
| `docker-compose.yml` | `build: ./backend` | 在线部署 / 本地预演 |
| `docker-compose.offline.yml` | **`image: buildlink-backend:<TAG>`**（docker load） | **离线部署（任意服务器）** |

与 `docker-compose.yml` 的主要区别：
- **用 `image:` 而非 `build:`** — 镜像由打包机预构建，目标服务器 `docker load` 后直接用
- **`db` 不暴露端口**，只 `expose: 5432`（安全）
- 端口通过环境变量配置，**带默认值**
- `restart: unless-stopped`（服务器重启后自动恢复）
- 日志滚动限制（防磁盘满）
- Volume 显式命名（防误删）

```yaml
# ============================================================
# BuildLink EA · 离线部署编排
#
# 使用方式:
#   docker compose -f docker-compose.offline.yml --env-file .env.production up -d
#
# 镜像来源: docker load（打包机预构建），不需要 build / pull
# ============================================================

x-logging: &default-logging
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"

services:
  db:
    image: postgres:16.4-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      TZ: UTC
      PGTZ: UTC
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 10
    # 不对外暴露 5432，只在 compose 内部网络可见
    expose:
      - "5432"
    logging: *default-logging

  backend:
    image: buildlink-backend:${RELEASE_TAG:-latest}
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
      JWT_ALGORITHM: ${JWT_ALGORITHM:-HS256}
      ACCESS_TOKEN_EXPIRE_MINUTES: ${ACCESS_TOKEN_EXPIRE_MINUTES:-15}
      REFRESH_TOKEN_EXPIRE_DAYS: ${REFRESH_TOKEN_EXPIRE_DAYS:-7}
      SUPER_ADMIN_EMAIL: ${SUPER_ADMIN_EMAIL}
      SUPER_ADMIN_INITIAL_PASSWORD: ${SUPER_ADMIN_INITIAL_PASSWORD}
      SEED_DEMO_ACCOUNTS: ${SEED_DEMO_ACCOUNTS:-false}
      CORS_ORIGINS: ${CORS_ORIGINS}
      CORS_ALLOW_CREDENTIALS: ${CORS_ALLOW_CREDENTIALS:-true}
      REFRESH_COOKIE_NAME: ${REFRESH_COOKIE_NAME:-refresh_token}
      REFRESH_COOKIE_PATH: ${REFRESH_COOKIE_PATH:-/api/v1/auth}
      REFRESH_COOKIE_MAX_AGE: ${REFRESH_COOKIE_MAX_AGE:-604800}
      REFRESH_COOKIE_SECURE: ${REFRESH_COOKIE_SECURE:-false}
      REFRESH_COOKIE_SAMESITE: ${REFRESH_COOKIE_SAMESITE:-lax}
      LOGIN_RATE_LIMIT_WINDOW_SECONDS: ${LOGIN_RATE_LIMIT_WINDOW_SECONDS:-60}
      LOGIN_RATE_LIMIT_MAX_FAILURES: ${LOGIN_RATE_LIMIT_MAX_FAILURES:-5}
      LOGIN_RATE_LIMIT_LOCK_SECONDS: ${LOGIN_RATE_LIMIT_LOCK_SECONDS:-300}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      ENABLE_DEBUG_API: ${ENABLE_DEBUG_API:-false}
      IMAGE_BASE_URL: ${IMAGE_BASE_URL:-http://localhost:8001/static}
      TRANSLATION_PROVIDER: ${TRANSLATION_PROVIDER:-mock}
      ALIYUN_TRANSLATE_ACCESS_KEY_ID: ${ALIYUN_TRANSLATE_ACCESS_KEY_ID:-}
      ALIYUN_TRANSLATE_ACCESS_KEY_SECRET: ${ALIYUN_TRANSLATE_ACCESS_KEY_SECRET:-}
      DASHSCOPE_API_KEY: ${DASHSCOPE_API_KEY:-}
    volumes:
      - uploads:/app/uploads
      - private_uploads:/app/private_uploads
    ports:
      - "${BACKEND_HOST_PORT:-8001}:8000"
    logging: *default-logging

  frontend:
    image: buildlink-frontend:${RELEASE_TAG:-latest}
    restart: unless-stopped
    depends_on:
      - backend
    ports:
      - "${FRONTEND_HOST_PORT:-3001}:3000"
    logging: *default-logging

volumes:
  pgdata:
    name: overseas_platform_pgdata
  uploads:
    name: overseas_platform_uploads
  private_uploads:
    name: overseas_platform_private_uploads
```

### 7.5 `deploy/init-data.sh`

数据初始化脚本，部署后手动跑一次。

```bash
#!/bin/bash
# 初始化业务数据：品类 → 轮播图 → 商品
# 用法:
#   bash deploy/init-data.sh                           # 全量初始化
#   bash deploy/init-data.sh --skip-products           # 跳过商品导入
#   bash deploy/init-data.sh --skip-banners            # 跳过轮播图
#   bash deploy/init-data.sh --skip-categories         # 跳过品类
#   bash deploy/init-data.sh --yes                     # 商品导入跳过确认（CI 用）
#   bash deploy/init-data.sh --batch data/xfs/<批次>   # 指定商品批次目录
#   bash deploy/init-data.sh --compose-file docker-compose.yml
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PACK_ROOT="$(dirname "$SCRIPT_DIR")"

# 默认值
COMPOSE_FILE="${PACK_ROOT}/docker-compose.offline.yml"
ENV_FILE="${PACK_ROOT}/.env.production"
DATA_DIR="${PACK_ROOT}/data"
BATCH_DIR=""
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
    --batch)            BATCH_DIR="$2"; shift 2 ;;
    --compose-file)     COMPOSE_FILE="$2"; shift 2 ;;
    --env-file)         ENV_FILE="$2"; shift 2 ;;
    *)                  echo "未知参数: $1"; exit 1 ;;
  esac
done

# compose 命令前缀
DC="docker compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE}"
BACKEND_CONTAINER=$(${DC} ps -q backend 2>/dev/null)
if [[ -z "$BACKEND_CONTAINER" ]]; then
  echo "错误: backend 容器未运行，请先启动服务"
  exit 1
fi

# 统计变量
STAT_CATEGORIES=0
STAT_ATTR_TEMPLATES=0
STAT_BANNERS=0
STAT_PRODUCTS=0
STAT_IMAGES=0
STAT_FAILURES=0

echo "=========================================="
echo " BuildLink EA 数据初始化"
echo "=========================================="
echo ""

# ── 1/5 拷贝数据文件到容器 ──
echo "=== [1/5] 拷贝数据文件到容器 /data ==="
# seed_categories.py 中 _DATA_DIR = Path(__file__).resolve().parents[2] / "data" → 容器内 /data
${DC} exec backend rm -rf /data 2>/dev/null || true
docker cp "${DATA_DIR}" "${BACKEND_CONTAINER}:/data"
echo "  数据已拷贝到容器 /data"

# ── 2/5 品类树 + 属性模板 ──
if [[ "$SKIP_CATEGORIES" == "false" ]]; then
  echo ""
  echo "=== [2/5] 导入品类树 + 属性模板 ==="
  ${DC} exec backend python scripts/seed_categories.py
  # 获取统计
  STAT_CATEGORIES=$(${DC} exec backend python -c "
from app.db.session import sync_engine
from sqlalchemy import text
with sync_engine.connect() as conn:
    r = conn.execute(text('SELECT COUNT(*) FROM categories WHERE deleted_at IS NULL'))
    print(r.scalar())
" 2>/dev/null || echo "?")
  echo "  品类数: ${STAT_CATEGORIES}"
else
  echo ""
  echo "=== [2/5] 跳过品类导入（--skip-categories）==="
fi

# ── 3/5 轮播图 ──
if [[ "$SKIP_BANNERS" == "false" ]]; then
  echo ""
  echo "=== [3/5] 初始化轮播图 ==="
  if [[ -d "${DATA_DIR}/banners" ]]; then
    # 复制图片到 uploads volume
    ${DC} exec backend mkdir -p /app/uploads/banners
    for img in "${DATA_DIR}"/banners/*.{png,jpg,jpeg,webp}; do
      [[ ! -f "$img" ]] && continue
      docker cp "$img" "${BACKEND_CONTAINER}:/app/uploads/banners/"
      ((STAT_BANNERS++))
    done
    # 运行 seed_banners.py（走 ORM，正确填 source_lang/trans_meta）
    ${DC} exec backend python scripts/seed_banners.py
    echo "  轮播图文件: ${STAT_BANNERS} 个"
  else
    echo "  跳过: data/banners/ 目录不存在"
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
  CAT_COUNT=$(${DC} exec backend python -c "
from app.db.session import sync_engine
from sqlalchemy import text
with sync_engine.connect() as conn:
    r = conn.execute(text('SELECT COUNT(*) FROM categories WHERE deleted_at IS NULL'))
    print(r.scalar())
" 2>/dev/null || echo "0")

  if [[ "$CAT_COUNT" == "0" ]]; then
    echo "  [错误] 品类表为空！请先导入品类（去掉 --skip-categories 重跑）"
    exit 1
  fi
  echo "  品类检查通过（${CAT_COUNT} 条）"

  # 确定批次目录
  if [[ -z "$BATCH_DIR" ]]; then
    # 自动查找 data/xfs/ 下第一个批次
    BATCH_DIR=$(find "${DATA_DIR}/xfs" -maxdepth 1 -mindepth 1 -type d | head -1)
  fi
  if [[ -z "$BATCH_DIR" || ! -d "$BATCH_DIR" ]]; then
    echo "  跳过: 未找到商品批次目录"
  else
    BATCH_NAME="$(basename "$BATCH_DIR")"
    echo "  批次目录: ${BATCH_NAME}"

    # dry-run 预检
    echo "  运行 dry-run 预检..."
    ${DC} exec backend python scripts/import_products_xfs.py \
      --data-dir "/data/xfs/${BATCH_NAME}" --dry-run 2>&1 | tail -5

    # 确认
    if [[ "$AUTO_YES" == "false" ]]; then
      echo ""
      read -rp "  确认正式导入？(y/N) " CONFIRM
      if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
        echo "  已取消商品导入"
        SKIP_PRODUCTS=true
      fi
    fi

    if [[ "$SKIP_PRODUCTS" == "false" ]]; then
      echo "  正式导入..."
      ${DC} exec backend python scripts/import_products_xfs.py \
        --data-dir "/data/xfs/${BATCH_NAME}" --yes 2>&1 | tee /dev/stderr
    fi
  fi
else
  echo ""
  echo "=== [4/5] 跳过商品导入（--skip-products）==="
fi

# ── 5/5 验证统计 ──
echo ""
echo "=== [5/5] 数据统计 ==="
${DC} exec backend python -c "
from app.db.session import sync_engine
from sqlalchemy import text

with sync_engine.connect() as conn:
    tables = {
        '品类':          'SELECT COUNT(*) FROM categories WHERE deleted_at IS NULL',
        '属性模板':      'SELECT COUNT(*) FROM category_attr_templates',
        '轮播图':        'SELECT COUNT(*) FROM banner_slides',
        '商品(SPU)':     'SELECT COUNT(*) FROM products WHERE deleted_at IS NULL',
        '商品图片':      'SELECT COUNT(*) FROM product_images WHERE deleted_at IS NULL',
    }
    for label, sql in tables.items():
        try:
            r = conn.execute(text(sql))
            print(f'  {label}: {r.scalar()}')
        except Exception as e:
            print(f'  {label}: 查询失败 ({e})')
" 2>/dev/null || echo "  统计查询失败（数据库可能未就绪）"

echo ""
echo "数据初始化完成"
```

### 7.6 `backend/scripts/seed_banners.py`

> 需新建。走 ORM + i18n 规范插入 banner_slides 记录，正确填 `source_lang`、`trans_meta`、中英文标题。幂等（先 SELECT COUNT 检查）。具体实现参考现有 `seed.py` 和 `I18nMixin` 用法。

---

## 八、完整部署步骤

```bash
# ══════════════════════════════════════════════════════
# A. 打包机（Mac / CI，有外网）— 每次发版执行
# ══════════════════════════════════════════════════════

# 构建镜像 + 打包（需传入目标服务器 API 地址 + 发布标签）
bash deploy/package-offline.sh \
  --api-url http://<服务器IP>:8001 \
  --tag 20260623-1900

# 传到目标服务器（scp / rsync / U 盘均可）
scp buildlink-offline-20260623-1900.tar.gz user@server:/opt/

# ══════════════════════════════════════════════════════
# B. 以下全部在目标服务器操作（不需要外网）
# ══════════════════════════════════════════════════════

# ════════════════════════════════════════
# 0. 解包
# ════════════════════════════════════════
cd /opt
tar xzf buildlink-offline-20260623-1900.tar.gz
cd buildlink-offline

# ════════════════════════════════════════
# 1. 配置环境变量
# ════════════════════════════════════════
cp .env.production.example .env.production
vi .env.production

# 必填项：
#   POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD
#   JWT_SECRET_KEY（openssl rand -hex 32）
#   SUPER_ADMIN_EMAIL / SUPER_ADMIN_INITIAL_PASSWORD
#   CORS_ORIGINS（前端地址，如 http://<IP>:3001）
#   IMAGE_BASE_URL（http://<服务器IP>:8001/static）
#   RELEASE_TAG（与打包时的 --tag 一致，如 20260623-1900）
#
# ⚠️ 三个 URL 必须匹配（见第三章）：
#   NEXT_PUBLIC_API_BASE_URL → 已在构建时注入，此处仅供参考
#   CORS_ORIGINS → 浏览器实际访问的前端 origin
#   IMAGE_BASE_URL → 与 NEXT_PUBLIC_API_BASE_URL 同 host:port + /static

# 如需 .env.production 补充 RELEASE_TAG：
echo "RELEASE_TAG=20260623-1900" >> .env.production

# ════════════════════════════════════════
# 2. 一键部署（加载镜像 + 启动 + 健康检查）
# ════════════════════════════════════════
bash deploy/deploy-offline.sh

# 脚本会依次执行：
# [1/3] docker load 三个镜像 + 校验
# [2/3] docker compose up -d
# [3/3] 循环等待 /healthz（最多 120 秒），失败自动打印日志

# ════════════════════════════════════════
# 3. 初始化业务数据（首次部署跑一次）
# ════════════════════════════════════════
bash deploy/init-data.sh

# 脚本会依次执行：
# [1/5] 拷贝数据文件到容器 /data
# [2/5] 导入品类树 + 属性模板
# [3/5] 初始化轮播图
# [4/5] 商品导入（先 dry-run 预检，确认后正式导入 —— CI 用 --yes 跳过确认）
# [5/5] 输出统计：品类数、属性模板数、轮播图数、商品数、图片数

# ════════════════════════════════════════
# 4. 浏览器验证
# ════════════════════════════════════════
# 前台首页：http://<IP>:<前端端口>
#   - 轮播图是否显示
#   - 品类导航是否正常
#   - 商品列表/详情/图片是否正常
#
# 运营后台：http://<IP>:<前端端口>/zh/operator
#   - 登录 super admin
#   - 商品管理列表
#   - Banner 管理
#
# API 文档：http://<IP>:<后端端口>/docs
```

---

## 九、后续更新部署

```bash
# ═══ 在打包机重新构建 ═══
bash deploy/package-offline.sh --api-url http://<服务器IP>:8001 --tag 20260624-1000
scp buildlink-offline-20260624-1000.tar.gz user@server:/opt/

# ═══ 在目标服务器更新 ═══
cd /opt

# 1. 数据库备份（更新前必做）
source /opt/buildlink-offline/.env.production
docker compose -f /opt/buildlink-offline/docker-compose.offline.yml \
  --env-file /opt/buildlink-offline/.env.production \
  exec -T db pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" \
  | gzip > "/opt/backups/db-backup-$(date +%Y%m%d_%H%M%S).sql.gz"

# 2. 解压新版本到带版本号的目录（不要直接覆盖旧目录）
tar xzf buildlink-offline-20260624-1000.tar.gz
# 解压后得到 buildlink-offline/，可重命名为带版本号
mv buildlink-offline buildlink-offline-20260624-1000

# 3. 复制旧的 .env.production（密钥不变）
cp /opt/buildlink-offline/.env.production /opt/buildlink-offline-20260624-1000/.env.production
# 更新 RELEASE_TAG
sed -i 's/^RELEASE_TAG=.*/RELEASE_TAG=20260624-1000/' /opt/buildlink-offline-20260624-1000/.env.production

# 4. 停旧服务（volume 不删）
cd /opt/buildlink-offline
docker compose -f docker-compose.offline.yml --env-file .env.production down

# 5. 切换到新版本
cd /opt/buildlink-offline-20260624-1000
bash deploy/deploy-offline.sh

# 6. 可选：备份旧包、建立 current 软链
ln -sfn /opt/buildlink-offline-20260624-1000 /opt/buildlink-current

# 不需要重跑 init-data.sh（数据已在 volume 里）
# 除非有新的商品批次要导入：
# bash deploy/init-data.sh --skip-categories --skip-banners \
#   --batch data/xfs/<新批次目录> --yes
```

---

## 十、数据持久化说明

```
Docker Volumes（跨部署持久化，重建容器不丢）：
├── overseas_platform_pgdata          → 数据库（品类/商品/用户/订单...）
├── overseas_platform_uploads         → 商品图片 + 轮播图 + 上传文件
└── overseas_platform_private_uploads → 私有附件（报价文档等）

绝对禁止：
  docker compose down -v          ← 会删除所有 volume！
  docker volume rm                ← 会删除指定 volume！
  docker system prune --volumes   ← 会删除未使用的 volume！

备份提醒：
  pg_dump 只备份数据库，不包含 uploads/private_uploads 里的文件！
  图片和附件的备份见「十四、备份与恢复」章节。
```

---

## 十一、回滚

如果新版本有问题，需要回滚到上一版：

```bash
# 1. 停止当前版本
cd /opt/buildlink-offline-20260624-1000
docker compose -f docker-compose.offline.yml --env-file .env.production down

# 2. 重新加载旧版本镜像
cd /opt/buildlink-offline  # 旧版本目录
bash deploy/load-images.sh

# 3. 启动旧版本
docker compose -f docker-compose.offline.yml --env-file .env.production up -d

# 4. 验证
curl http://localhost:8001/healthz
```

**数据库迁移注意**：
- `alembic upgrade head` 是自动的（容器启动时执行），但 **downgrade 不会自动执行**
- 如果新版本的 alembic 迁移已经跑过（加了表/列），回滚到旧版本代码后，数据库里的新表/列仍然存在
- 大部分情况下旧代码能兼容（多出来的列不影响），但如果遇到不兼容：
  - 方案 A：从备份恢复数据库（见下一章）
  - 方案 B：手动进容器跑 `alembic downgrade -1`（需确认目标 revision）

---

## 十二、备份与恢复

### 12.1 数据库备份

```bash
# 在目标服务器执行
cd /opt/buildlink-offline  # 或 /opt/buildlink-current

# 加载环境变量
source .env.production

# 备份
mkdir -p /opt/backups
docker compose -f docker-compose.offline.yml --env-file .env.production \
  exec -T db pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" \
  | gzip > "/opt/backups/db-backup-$(date +%Y%m%d_%H%M%S).sql.gz"

# 建议：部署更新前、定期（cron 每日）备份
```

### 12.2 数据库恢复

```bash
# 停止后端（避免写入冲突）
docker compose -f docker-compose.offline.yml --env-file .env.production stop backend frontend

# 恢复
gunzip -c /opt/backups/db-backup-20260623_190000.sql.gz \
  | docker compose -f docker-compose.offline.yml --env-file .env.production \
    exec -T db psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"

# 重启
docker compose -f docker-compose.offline.yml --env-file .env.production up -d
```

### 12.3 上传文件备份

> **pg_dump 不包含 Docker volume 里的图片和附件。** 商品图片、轮播图、私有附件存在 `overseas_platform_uploads` 和 `overseas_platform_private_uploads` 两个 volume 中，需要单独备份。

```bash
# 备份 uploads volume
docker run --rm \
  -v overseas_platform_uploads:/data \
  -v /opt/backups:/backup \
  alpine tar czf /backup/uploads-$(date +%Y%m%d).tar.gz -C /data .

# 备份 private_uploads volume
docker run --rm \
  -v overseas_platform_private_uploads:/data \
  -v /opt/backups:/backup \
  alpine tar czf /backup/private_uploads-$(date +%Y%m%d).tar.gz -C /data .

# 恢复 uploads volume（慎用，会覆盖现有文件）
docker run --rm \
  -v overseas_platform_uploads:/data \
  -v /opt/backups:/backup \
  alpine sh -c "cd /data && tar xzf /backup/uploads-20260623.tar.gz"
```

---

## 十三、HTTPS 切换说明

### 13.1 前置条件

- 域名已解析到服务器 IP
- SSL 证书已准备（Let's Encrypt / 购买证书）
- Nginx 或 Caddy 已安装

### 13.2 Nginx 反代配置要点

```nginx
server {
    listen 80;
    server_name your.domain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name your.domain.com;

    ssl_certificate     /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # 前端
    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 后端静态文件（图片）
    location /static/ {
        proxy_pass http://127.0.0.1:8001;
    }
}
```

### 13.3 切换后必须修改的环境变量

切到 HTTPS 后，修改 `.env.production`：

```bash
# Cookie 安全策略
REFRESH_COOKIE_SECURE=true        # HTTP 时为 false，HTTPS 必须改 true
REFRESH_COOKIE_SAMESITE=strict    # HTTP 时为 lax（跨端口需要），HTTPS 可收紧为 strict

# URL 全部改为 https
CORS_ORIGINS=https://your.domain.com
IMAGE_BASE_URL=https://your.domain.com/static
# NEXT_PUBLIC_API_BASE_URL=https://your.domain.com  # ⚠️ 需要重新打前端镜像！
```

> **重要**：`NEXT_PUBLIC_API_BASE_URL` 是构建时注入的，切 HTTPS 后必须用新域名**重新打前端镜像**。

### 13.4 安全组调整

切 HTTPS 后：
- 开放 80（重定向）、443（HTTPS）
- 关闭 3001、8001 的公网访问（只允许 127.0.0.1 访问）

---

## 十四、端口与安全组

| 端口 | 服务 | 公网访问 | 说明 |
|------|------|---------|------|
| `FRONTEND_HOST_PORT`（默认 3001） | 前端 | HTTP 模式需开放 | HTTPS 模式关闭，走 Nginx 443 |
| `BACKEND_HOST_PORT`（默认 8001） | 后端 API | HTTP 模式需开放 | HTTPS 模式关闭，走 Nginx 443 |
| 5432 | PostgreSQL | **永不开放** | 只在 Docker 内部网络暴露 |
| 80 | Nginx | HTTPS 模式开放 | 重定向到 443 |
| 443 | Nginx | HTTPS 模式开放 | SSL 终结 |

**生产建议**：始终使用 Nginx/Caddy 反代，不直接暴露应用端口。

---

## 十五、已有 vs 要建 汇总

| 内容 | 状态 | 说明 |
|------|------|------|
| `docker-compose.yml` | ✅ 已有 | 在线部署用，不动 |
| **`docker-compose.offline.yml`** | **要建** | 离线部署，`image:` + `restart: unless-stopped` + 日志限制 + expose |
| **`deploy/package-offline.sh`** | **要建** | 打包机：`--platform linux/amd64` + release tag + 白名单 data + manifest.json |
| **`deploy/load-images.sh`** | **要建** | 目标服务器：docker load + 校验镜像存在 |
| **`deploy/deploy-offline.sh`** | **要建** | 目标服务器：load + start + 循环健康检查（一键） |
| **`deploy/init-data.sh`** | **要建** | 品类 + 轮播 + 商品，支持 `--skip-*` + `--yes` + 前置检查 + 统计输出 |
| **`deploy/README-deploy.md`** | **要建** | 操作手册 |
| **`backend/scripts/seed_banners.py`** | **要建** | 走 ORM + i18n 规范插入 banner 记录，不用裸 SQL |
| **`manifest.json`**（自动生成） | **要建** | package-offline.sh 自动生成：tag/sha/时间/API URL/镜像名/数据批次 |
| `deploy/deploy.sh` | ✅ 已有 | CI/CD 在线部署用，不动 |
| `backend/docker-entrypoint.sh` | ✅ 已有 | 不动 |
| `backend/app/seed.py` | ✅ 已有 | 容器启动自动跑，不动 |
| `backend/scripts/seed_categories.py` | ✅ 已有 | 幂等，直接用 |
| `backend/scripts/import_products_xfs.py` | ✅ 已有 | 幂等，需支持 `--dry-run` 和 `--yes` 参数 |
| `backend/scripts/import_products_1688.py` | ✅ 已有 | 幂等，直接用 |
| `data/categories.csv` | ✅ 已有 | 品类数据 |
| `data/attr_templates.csv` | ✅ 已有 | 属性模板 |
| `data/xfs/` | ✅ 已有 | XFS 商品批次数据 |
| **`data/banners/`** | **要建** | 从 `frontend/public/banners/` 复制 |

---

## 十六、配置项清单（.env.production）

> `.env.production.example` 需补齐离线部署必填项。特别是 `NEXT_PUBLIC_API_BASE_URL`（构建后不可改）和 `RELEASE_TAG`。此处列出完整清单。

| 变量 | 必填 | 示例 | 说明 |
|------|------|------|------|
| `POSTGRES_DB` | 是 | `buildlink_ea` | 数据库名 |
| `POSTGRES_USER` | 是 | `buildlink` | 数据库用户 |
| `POSTGRES_PASSWORD` | 是 | `<强密码>` | 数据库密码。**首次设置后不可随意更改**（见 3.2） |
| `JWT_SECRET_KEY` | 是 | `openssl rand -hex 32` | JWT 签名密钥 |
| `SUPER_ADMIN_EMAIL` | 是 | `admin@company.com` | 初始管理员邮箱 |
| `SUPER_ADMIN_INITIAL_PASSWORD` | 是 | `<强密码>` | 初始管理员密码（首登强制改） |
| `CORS_ORIGINS` | 是 | `http://IP:3001` | 前端地址。**必须与浏览器实际访问的 origin 一致** |
| `IMAGE_BASE_URL` | 是 | `http://IP:8001/static` | 图片 URL 前缀。**必须与 NEXT_PUBLIC_API_BASE_URL 同 host:port** |
| `NEXT_PUBLIC_API_BASE_URL` | 是 | `http://IP:8001` | **前端构建时注入**（package-offline.sh --api-url 传入），运行时不可改 |
| `RELEASE_TAG` | 是 | `20260623-1900` | 发布标签，与打包时 --tag 一致，compose 用于指定镜像版本 |
| `BACKEND_HOST_PORT` | 选填 | `8001` | 后端暴露端口（默认 8001） |
| `FRONTEND_HOST_PORT` | 选填 | `3001` | 前端暴露端口（默认 3001） |
| `SEED_DEMO_ACCOUNTS` | 选填 | `false` | 是否种 demo 账号（离线部署默认 false） |
| `REFRESH_COOKIE_SECURE` | 选填 | `false` | HTTP 部署用 false，**HTTPS 后改 true** |
| `REFRESH_COOKIE_SAMESITE` | 选填 | `lax` | HTTP 部署用 lax，**HTTPS 后可改 strict** |
| `TRANSLATION_PROVIDER` | 选填 | `mock` | 翻译服务（离线环境用 mock） |
| `ALIYUN_TRANSLATE_ACCESS_KEY_ID` | 选填 | | 阿里翻译 AK（用 aliyun 时必填） |
| `ALIYUN_TRANSLATE_ACCESS_KEY_SECRET` | 选填 | | 阿里翻译 SK |
| `DASHSCOPE_API_KEY` | 选填 | | 通义千问 API Key（AI 功能用） |
| `LOG_LEVEL` | 选填 | `INFO` | 日志级别 |
| `ENABLE_DEBUG_API` | 选填 | `false` | 调试 API 开关（生产 false） |

---

## 十七、商品导入日志查看

```bash
# 方式 1：实时查看容器日志
docker compose -f docker-compose.offline.yml --env-file .env.production \
  logs -f backend

# 方式 2：init-data.sh 执行时 tee 到宿主机
bash deploy/init-data.sh 2>&1 | tee logs/init-data-$(date +%Y%m%d_%H%M%S).log

# 方式 3：单独跑商品导入并保存日志
mkdir -p logs
docker compose -f docker-compose.offline.yml --env-file .env.production \
  exec backend python scripts/import_products_xfs.py \
  --data-dir /data/xfs/output_xfs_20260623_023104 --yes \
  2>&1 | tee logs/import-$(date +%Y%m%d_%H%M%S).log
```
