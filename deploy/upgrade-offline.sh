#!/usr/bin/env bash
# ============================================================
# 离线包增量升级脚本（在目标服务器运行）
#
# 用法:
#   bash upgrade-offline.sh /opt/buildlink-offline-20260626-matgo.tar.gz
#
# 做什么:
#   1. 解压到临时目录
#   2. 替换镜像、部署脚本、compose、manifest、banners
#   3. 更新 .env.production 中的 RELEASE_TAG
#   4. 加载新镜像并重启容器
#   5. 健康检查
#   6. 清理临时目录
#
# 不碰什么:
#   - .env.production 中除 RELEASE_TAG 外的配置
#   - data/xfs/（商品数据）
#   - Docker volumes（数据库、上传文件）
# ============================================================

set -euo pipefail

# ── 参数校验 ──
ARCHIVE="${1:-}"
if [[ -z "$ARCHIVE" ]] || [[ ! -f "$ARCHIVE" ]]; then
    echo "用法: bash upgrade-offline.sh <离线包路径>"
    echo "示例: bash upgrade-offline.sh /opt/buildlink-offline-20260626-matgo.tar.gz"
    exit 1
fi

INSTALL_DIR="${INSTALL_DIR:-/opt/buildlink-offline}"
TMP_DIR="/opt/_buildlink-upgrade-tmp"

if [[ ! -d "$INSTALL_DIR" ]]; then
    echo "错误: 安装目录 $INSTALL_DIR 不存在，请先做首次部署"
    exit 1
fi

echo "========================================"
echo " 离线包增量升级"
echo "========================================"
echo "  包文件:   $ARCHIVE"
echo "  安装目录: $INSTALL_DIR"
echo "========================================"

# ── 1. 解压到临时目录 ──
echo ""
echo "=== 1/6 解压到临时目录 ==="
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"
tar xzf "$ARCHIVE" -C "$TMP_DIR"

# 自动检测是否多套了一层目录
SRC="$TMP_DIR"
if [[ -d "$TMP_DIR/buildlink-offline" ]]; then
    SRC="$TMP_DIR/buildlink-offline"
fi
echo "  解压源: $SRC"

# 校验 manifest
if [[ ! -f "$SRC/manifest.json" ]]; then
    echo "错误: 找不到 manifest.json，不是有效的离线包"
    rm -rf "$TMP_DIR"
    exit 1
fi

# 读取新 RELEASE_TAG
NEW_TAG=$(python3 -c "import json; print(json.load(open('$SRC/manifest.json'))['release_tag'])" 2>/dev/null || true)
echo "  新版本: ${NEW_TAG:-未知}"

# ── 2. 替换镜像和部署文件 ──
echo ""
echo "=== 2/6 替换镜像和部署文件 ==="

# 镜像
rm -rf "$INSTALL_DIR/images"
cp -r "$SRC/images" "$INSTALL_DIR/images"
echo "  ✓ images/"

# compose
cp "$SRC/docker-compose.yml" "$INSTALL_DIR/"
echo "  ✓ docker-compose.yml"

# 部署脚本
cp -r "$SRC/deploy" "$INSTALL_DIR/"
echo "  ✓ deploy/"

# manifest
cp "$SRC/manifest.json" "$INSTALL_DIR/"
echo "  ✓ manifest.json"

# banners（如果有）
if [[ -d "$SRC/data/banners" ]]; then
    mkdir -p "$INSTALL_DIR/data/banners"
    cp -r "$SRC/data/banners/." "$INSTALL_DIR/data/banners/"
    echo "  ✓ data/banners/"
fi

# 初始化数据文件（csv/json，不含 xfs）
for f in categories.csv attr_templates.csv category_names_en.json floor_category_mapping.csv; do
    if [[ -f "$SRC/data/$f" ]]; then
        cp "$SRC/data/$f" "$INSTALL_DIR/data/"
        echo "  ✓ data/$f"
    fi
done
if [[ -d "$SRC/data/xfs" ]] && [[ -f "$SRC/data/xfs/categories_full_tree.json" ]]; then
    mkdir -p "$INSTALL_DIR/data/xfs"
    cp "$SRC/data/xfs/categories_full_tree.json" "$INSTALL_DIR/data/xfs/"
    echo "  ✓ data/xfs/categories_full_tree.json"
fi

# ── 3. 更新 RELEASE_TAG ──
echo ""
echo "=== 3/6 更新 .env.production RELEASE_TAG ==="
if [[ -n "$NEW_TAG" ]]; then
    sed -i "s|^RELEASE_TAG=.*|RELEASE_TAG=$NEW_TAG|" "$INSTALL_DIR/.env.production"
    echo "  RELEASE_TAG=$NEW_TAG"
else
    echo "  ⚠️  无法读取 RELEASE_TAG，请手动检查"
fi

# ── 4. 加载镜像并重启 ──
echo ""
echo "=== 4/6 加载镜像并重启容器 ==="
cd "$INSTALL_DIR"
for f in images/*.tar; do
    echo "  加载 $(basename "$f") ..."
    docker load -i "$f"
done

source .env.production
docker compose -f docker-compose.yml --env-file .env.production up -d --remove-orphans

# ── 5. 健康检查 ──
echo ""
echo "=== 5/6 健康检查 ==="
BE_PORT="${BACKEND_HOST_PORT:-17857}"
FE_PORT="${FRONTEND_HOST_PORT:-7857}"

BE_OK=0
for i in $(seq 1 30); do
    if curl -fsS --max-time 5 "http://localhost:${BE_PORT}/healthz" > /dev/null 2>&1; then
        echo "  ✓ 后端健康 (${i}s)"
        BE_OK=1
        break
    fi
    sleep 2
done

FE_OK=0
for i in $(seq 1 30); do
    if curl -fsS --max-time 5 "http://localhost:${FE_PORT}" > /dev/null 2>&1; then
        echo "  ✓ 前端健康 (${i}s)"
        FE_OK=1
        break
    fi
    sleep 2
done

if [[ "$BE_OK" -ne 1 ]] || [[ "$FE_OK" -ne 1 ]]; then
    echo ""
    echo "  ❌ 健康检查失败 (backend=$BE_OK, frontend=$FE_OK)"
    echo "  请检查: docker compose -f docker-compose.yml logs --tail=30"
    exit 1
fi

# ── 6. 清理 ──
echo ""
echo "=== 6/6 清理临时目录 ==="
rm -rf "$TMP_DIR"
docker image prune -f --filter "dangling=true" > /dev/null 2>&1 || true
echo "  ✓ 清理完成"

echo ""
echo "========================================"
echo " 升级完成"
echo "  版本:   ${NEW_TAG:-未知}"
echo "  后端:   http://localhost:${BE_PORT}/healthz"
echo "  前端:   http://localhost:${FE_PORT}"
echo "========================================"
