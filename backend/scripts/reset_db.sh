#!/usr/bin/env bash
# 重置 PostgreSQL dev 库:drop → create → alembic upgrade。**仅开发环境**。
#
# 假设:本机 brew postgresql@16 跑在 5433,DB 用户 = $USER。
set -e

cd "$(dirname "$0")/.."

DB_NAME="${DB_NAME:-overseas_supply_dev}"
PG_PORT="${PG_PORT:-5433}"
PG_USER="${PG_USER:-$USER}"
PSQL_BIN="${PSQL_BIN:-/opt/homebrew/opt/postgresql@16/bin}"

echo "→ dropdb $DB_NAME"
"$PSQL_BIN/dropdb" -p "$PG_PORT" -U "$PG_USER" --if-exists "$DB_NAME"

echo "→ createdb $DB_NAME"
"$PSQL_BIN/createdb" -p "$PG_PORT" -U "$PG_USER" "$DB_NAME"

# 不再自动删除 uploads — 图片文件与 DB 无事务关系，
# 重置库后残留文件无害，但误删文件不可恢复。
# 如确需清理孤儿文件，手动执行: rm -rf uploads/products/*
echo "→ 跳过 uploads 清理（图片文件保留，避免误删）"

echo "→ alembic upgrade head"
alembic upgrade head

echo "✓ 数据库已重置。下次启动 uvicorn 将自动 sync RBAC + 种子。"
