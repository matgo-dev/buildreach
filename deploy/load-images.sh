#!/bin/bash
# ============================================================
# 加载预构建的 Docker 镜像（在目标服务器运行）
#
# 用法: bash deploy/load-images.sh
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PACK_ROOT="$(dirname "$SCRIPT_DIR")"
IMAGES_DIR="${PACK_ROOT}/images"

if [[ ! -d "$IMAGES_DIR" ]]; then
  echo "错误: 镜像目录不存在: ${IMAGES_DIR}"
  exit 1
fi

# sha256 校验（如果有校验文件）
CHECKSUMS="${IMAGES_DIR}/sha256sums.txt"
if [[ -f "$CHECKSUMS" ]]; then
  echo "=== 校验镜像完整性 ==="
  if (cd "${IMAGES_DIR}" && shasum -a 256 -c sha256sums.txt); then
    echo "  校验通过"
  else
    echo "  [错误] 镜像文件损坏，请重新传输"
    exit 1
  fi
  echo ""
fi

echo "=== 加载 Docker 镜像 ==="
LOADED=0
FAILED=0
for tar in "${IMAGES_DIR}"/*.tar; do
  [[ ! -f "$tar" ]] && continue
  echo "  loading $(basename "$tar") ..."
  if docker load -i "$tar"; then
    LOADED=$((LOADED + 1))
  else
    echo "  [失败] $(basename "$tar")"
    FAILED=$((FAILED + 1))
  fi
done

echo ""
echo "=== 加载结果: 成功 ${LOADED}, 失败 ${FAILED} ==="

# 校验镜像是否存在
echo ""
echo "=== 校验已加载镜像 ==="

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
  docker images | grep -E 'postgres|buildlink' || true
fi

if [[ "$FAILED" -gt 0 ]]; then
  echo ""
  echo "有镜像加载失败或缺失，请检查 tar 文件完整性"
  exit 1
fi

echo ""
echo "镜像加载完成"
