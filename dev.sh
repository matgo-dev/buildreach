#!/usr/bin/env bash
# BuildReach 一键启动脚本
# 支持 macOS / Ubuntu / Debian / CentOS
# 用法: bash dev.sh
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
fail()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo ""
echo "========================================="
echo "  BuildReach · 一键启动"
echo "========================================="
echo ""

# ---- 检测操作系统 ----
OS="unknown"
if [[ "$OSTYPE" == "darwin"* ]]; then
  OS="mac"
elif [ -f /etc/debian_version ]; then
  OS="debian"
elif [ -f /etc/redhat-release ]; then
  OS="redhat"
else
  fail "不支持的操作系统，仅支持 macOS / Ubuntu / Debian / CentOS"
fi
info "检测到系统: $OS"

# ---- 1. 系统包管理器 ----
install_pkg() {
  case "$OS" in
    mac)
      if ! command -v brew &>/dev/null; then
        warn "正在安装 Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        [ -f /opt/homebrew/bin/brew ] && eval "$(/opt/homebrew/bin/brew shellenv)"
      fi
      brew install "$@" 2>/dev/null || true
      ;;
    debian)
      sudo apt-get update -qq
      sudo apt-get install -y -qq "$@"
      ;;
    redhat)
      sudo yum install -y -q "$@"
      ;;
  esac
}

# ---- 2. PostgreSQL ----
# Mac: brew postgresql@16, 默认 5433
# Linux/WSL: 系统 PG 或自装, 从 .env 读端口

if [ "$OS" = "mac" ]; then
  if ! brew list postgresql@16 &>/dev/null; then
    warn "正在安装 PostgreSQL 16..."
    brew install postgresql@16
  fi
  export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
  if ! brew services list | grep postgresql@16 | grep -q started; then
    brew services start postgresql@16
    sleep 2
  fi
else
  if ! command -v psql &>/dev/null; then
    warn "正在安装 PostgreSQL..."
    if [ "$OS" = "debian" ]; then
      sudo apt-get update -qq
      sudo apt-get install -y -qq postgresql postgresql-client
    else
      sudo yum install -y -q postgresql-server postgresql
      sudo postgresql-setup --initdb 2>/dev/null || true
    fi
  fi
  # 尝试启动系统 PG 服务（WSL 下可能没有 systemctl，忽略错误）
  if command -v systemctl &>/dev/null; then
    sudo systemctl start postgresql 2>/dev/null || true
    sudo systemctl enable postgresql 2>/dev/null || true
    sleep 1
  fi
fi

# ---- 确保 backend/.env 存在（建库需要从中读连接信息）----
cd "$PROJECT_DIR/backend"
if [ ! -f .env ]; then
  if [ ! -f .env.example ]; then
    fail "backend/.env.example 不存在，无法生成 .env"
  fi
  cp .env.example .env
  JWT_KEY=$(openssl rand -hex 32)
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_KEY|" .env
  else
    sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_KEY|" .env
  fi
  # Linux/WSL: .env.example 里默认端口是 5433(Mac)，自动改成 5432
  if [ "$OS" != "mac" ]; then
    if [[ "$OSTYPE" != "darwin"* ]]; then
      sed -i "s|localhost:5433|localhost:5432|" .env
    fi
  fi
  info "已生成 backend/.env 并自动填入 JWT 密钥"
fi
cd "$PROJECT_DIR"

# ---- 从 backend/.env 解析数据库连接信息 ----
_parse_db_url() {
  local env_file="$PROJECT_DIR/backend/.env"
  local raw
  raw=$(grep -E '^DATABASE_URL=' "$env_file" | head -1 | sed 's/^DATABASE_URL=//')
  if [ -n "$raw" ]; then
    # 去掉 driver 前缀 postgresql+asyncpg://
    local clean
    clean=$(echo "$raw" | sed -E 's|^postgresql(\+[a-z]+)?://||')
    DB_PG_USER=$(echo "$clean" | sed -E 's/@.*//' | cut -d: -f1)
    DB_PG_PASS=$(echo "$clean" | sed -E 's/@.*//' | grep -o ':.*' | sed 's/^://' || true)
    DB_PG_HOST=$(echo "$clean" | sed -E 's/^[^@]+@//' | sed -E 's|/.*||' | cut -d: -f1)
    DB_PG_PORT=$(echo "$clean" | sed -E 's/^[^@]+@//' | sed -E 's|/.*||' | grep -o ':[0-9]*' | sed 's/^://' || true)
    DB_PG_NAME=$(echo "$clean" | sed -E 's|^.*/||' | sed -E 's|\?.*||')
  fi
  # 兜底默认值
  DB_PG_USER="${DB_PG_USER:-postgres}"
  DB_PG_PASS="${DB_PG_PASS:-}"
  DB_PG_HOST="${DB_PG_HOST:-localhost}"
  DB_PG_PORT="${DB_PG_PORT:-5432}"
  DB_PG_NAME="${DB_PG_NAME:-overseas_supply_dev}"
}
_parse_db_url

PG_PORT="$DB_PG_PORT"
info "数据库连接: ${DB_PG_USER}@${DB_PG_HOST}:${PG_PORT}/${DB_PG_NAME}"

# 检查 PG 是否可达
if command -v pg_isready &>/dev/null; then
  if ! pg_isready -h "$DB_PG_HOST" -p "$PG_PORT" -U "$DB_PG_USER" -q 2>/dev/null; then
    fail "PostgreSQL 未就绪(${DB_PG_HOST}:${PG_PORT})，请先启动数据库"
  fi
fi

# 建库（如不存在）— 统一用 psql + PGPASSWORD，Mac/Linux/WSL 通用
export PGPASSWORD="${DB_PG_PASS}"
DB_EXISTS=$(psql -h "$DB_PG_HOST" -p "$PG_PORT" -U "$DB_PG_USER" -tAc \
  "SELECT 1 FROM pg_database WHERE datname='${DB_PG_NAME}'" postgres 2>/dev/null || true)
if [ "$DB_EXISTS" != "1" ]; then
  warn "数据库 ${DB_PG_NAME} 不存在，正在创建..."
  createdb -h "$DB_PG_HOST" -p "$PG_PORT" -U "$DB_PG_USER" "$DB_PG_NAME"
  info "数据库 ${DB_PG_NAME} 已创建"
fi
unset PGPASSWORD
info "PostgreSQL 就绪 (端口 $PG_PORT)"

# ---- 3. Python + uv ----
if ! command -v uv &>/dev/null; then
  warn "正在安装 uv (Python 包管理)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
info "uv 就绪"

# ---- 4. Node.js + pnpm ----
if [ -s "$HOME/.nvm/nvm.sh" ]; then
  # 非交互 shell 不会自动加载 nvm;本地开发优先使用 Node 20+。
  # shellcheck source=/dev/null
  . "$HOME/.nvm/nvm.sh"
  nvm use --silent 20 >/dev/null 2>&1 || nvm use --silent --lts >/dev/null 2>&1 || true
fi

if ! command -v node &>/dev/null; then
  warn "正在安装 Node.js..."
  if [ "$OS" = "mac" ]; then
    brew install node
  elif [ "$OS" = "debian" ]; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y -qq nodejs
  else
    curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
    sudo yum install -y -q nodejs
  fi
fi

if ! command -v pnpm &>/dev/null; then
  warn "正在安装 pnpm..."
  npm install -g pnpm
fi
info "Node.js + pnpm 就绪"

# ---- 5. 后端依赖 ----
cd "$PROJECT_DIR/backend"
if [ ! -d .venv ]; then
  uv venv
fi
source .venv/bin/activate
uv pip install -e ".[dev]" --quiet

# .env 已在前面确保生成，此处无需重复

alembic upgrade head
info "后端依赖 + 数据库迁移就绪"

# ---- 6. 前端依赖 ----
cd "$PROJECT_DIR/frontend"
if [ ! -f .env.local ]; then
  cp .env.local.example .env.local
fi
pnpm install --frozen-lockfile 2>/dev/null || pnpm install
info "前端依赖就绪"

# ---- 7. 启动服务 ----
echo ""
echo "========================================="
echo "  正在启动服务..."
echo "========================================="
echo ""

# 清理旧进程
lsof -ti:17857 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:7857 2>/dev/null | xargs kill -9 2>/dev/null || true
# 兼容清理历史本地端口
lsof -ti:8001 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true

# 启动后端
cd "$PROJECT_DIR/backend"
source .venv/bin/activate
python -m uvicorn app.main:app --reload --port 17857 &
BACKEND_PID=$!

# 启动前端
cd "$PROJECT_DIR/frontend"
./node_modules/.bin/next dev -p 7857 &
FRONTEND_PID=$!

sleep 3

echo ""
echo "========================================="
echo -e "  ${GREEN}启动成功！${NC}"
echo ""
echo "  前端: http://localhost:7857"
echo "  后端: http://localhost:17857"
echo "  API 文档: http://localhost:17857/docs"
echo ""
echo "  按 Ctrl+C 停止所有服务"
echo "========================================="
echo ""

cleanup() {
  echo ""
  info "正在停止服务..."
  kill $BACKEND_PID 2>/dev/null || true
  kill $FRONTEND_PID 2>/dev/null || true
  wait 2>/dev/null
  info "已停止"
}
trap cleanup EXIT INT TERM

wait
