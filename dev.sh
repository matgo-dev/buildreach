#!/usr/bin/env bash
# BuildLink EA 一键启动脚本
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
echo "  BuildLink EA · 一键启动"
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

# ---- 2. PostgreSQL 16 ----
PG_PORT=5433

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
  # Linux 默认端口 5432
  PG_PORT=5432
  if ! sudo systemctl is-active --quiet postgresql; then
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
    sleep 2
  fi
fi

# 创建数据库（已存在则忽略）
if [ "$OS" = "mac" ]; then
  createdb -p $PG_PORT overseas_supply_dev 2>/dev/null || true
  createdb -p $PG_PORT overseas_supply_test 2>/dev/null || true
else
  sudo -u postgres createdb overseas_supply_dev 2>/dev/null || true
  sudo -u postgres createdb overseas_supply_test 2>/dev/null || true
  # 创建应用用户（密码和 .env 里一致）
  sudo -u postgres psql -c "CREATE USER overseas_app WITH PASSWORD 'overseas_app_dev';" 2>/dev/null || true
  sudo -u postgres psql -c "GRANT ALL ON DATABASE overseas_supply_dev TO overseas_app;" 2>/dev/null || true
  sudo -u postgres psql -c "GRANT ALL ON DATABASE overseas_supply_test TO overseas_app;" 2>/dev/null || true
fi
info "PostgreSQL 就绪 (端口 $PG_PORT)"

# ---- 3. Python + uv ----
if ! command -v uv &>/dev/null; then
  warn "正在安装 uv (Python 包管理)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
info "uv 就绪"

# ---- 4. Node.js + pnpm ----
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

# .env 文件
if [ ! -f .env ]; then
  cp .env.example .env
  JWT_KEY=$(openssl rand -hex 32)
  # 替换 JWT 密钥
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_KEY|" .env
  else
    sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_KEY|" .env
  fi
  # Linux 需要调整数据库连接端口
  if [ "$OS" != "mac" ]; then
    if [[ "$OSTYPE" != "darwin"* ]]; then
      sed -i "s|5433|5432|" .env
    fi
  fi
  info "已生成 .env 并自动填入 JWT 密钥"
fi

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
lsof -ti:8001 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true

# 启动后端
cd "$PROJECT_DIR/backend"
source .venv/bin/activate
uvicorn app.main:app --reload --port 8001 &
BACKEND_PID=$!

# 启动前端
cd "$PROJECT_DIR/frontend"
pnpm dev &
FRONTEND_PID=$!

sleep 3

echo ""
echo "========================================="
echo -e "  ${GREEN}启动成功！${NC}"
echo ""
echo "  前端: http://localhost:3000"
echo "  后端: http://localhost:8001"
echo "  API 文档: http://localhost:8001/docs"
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
