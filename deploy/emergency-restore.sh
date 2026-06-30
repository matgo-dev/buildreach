#!/usr/bin/env bash
# ============================================================
# BuildReach 紧急恢复脚本（简化版）
#
# 用途：部署失败时手动恢复服务
# 功能：状态查看、备份列表、恢复备份、重启服务
#
# 用法：
#   cd /opt/buildreach && bash deploy/emergency-restore.sh [命令]
#
# 命令：
#   status    - 显示当前状态（默认）
#   backups   - 列出备份文件
#   restore   - 恢复指定备份（需人工确认）
#   restart   - 重启所有服务
# ============================================================

set -euo pipefail

APP_DIR="/opt/buildreach"
BACKUP_DIR="$APP_DIR/backups"
COMPOSE_FILE="docker-compose.production.yml"

cd "$APP_DIR" || { echo "❌ 目录不存在: $APP_DIR"; exit 1; }

if [ ! -f ".env.production" ]; then
    echo "❌ .env.production 不存在"
    exit 1
fi

source .env.production

show_status() {
    echo ""
    echo "📊 系统状态"
    echo "============================================================"
    
    echo "容器状态:"
    docker compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null || echo "  (无运行中的容器)"
    
    echo ""
    echo "数据库:"
    if docker compose -f "$COMPOSE_FILE" exec -T db pg_isready -U "$POSTGRES_USER" 2>&1 | grep -q accepting; then
        echo "  ✅ 运行中"
        DB_SIZE=$(docker compose -f "$COMPOSE_FILE" exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c \
            "SELECT pg_size_pretty(pg_database_size('$POSTGRES_DB'));" 2>/dev/null | tr -d ' ')
        echo "  📏 大小: $DB_SIZE"
    else
        echo "  ❌ 未运行或未就绪"
    fi
    
    echo ""
    echo "健康检查:"
    for PORT in ${BACKEND_HOST_PORT:-17857} ${FRONTEND_HOST_PORT:-7857}; do
        if curl -fsS --max-time 2 "http://localhost:$PORT/" > /dev/null 2>&1; then
            echo "  ✅ 端口 $PORT 正常"
        else
            echo "  ❌ 端口 $PORT 异常"
        fi
    done
    
    echo ""
    echo "最新备份:"
    LATEST=$(ls -t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | head -1)
    if [ -n "$LATEST" ]; then
        echo "  📦 $(basename $LATEST) ($(du -h $LATEST | cut -f1))"
    else
        echo "  ⚠️  无备份"
    fi
    
    echo "============================================================"
}

list_backups() {
    echo ""
    echo "📦 数据库备份"
    echo "============================================================"
    
    if ! ls "$BACKUP_DIR"/*.sql.gz 1>/dev/null 2>&1; then
        echo "⚠️  无可用备份"
        return
    fi
    
    printf "%-35s %10s %s\n" "文件名" "大小" "时间"
    echo "------------------------------------------------------------"
    
    ls -lht "$BACKUP_DIR"/*.sql.gz 2>/dev/null | awk 'NR<=10 {
        size=$5
        time=$6" "$7" "$8
        gsub(/.*\//, "", $9)
        printf "  %-33s %8s %s\n", $9, size, time
    }'
    
    echo "------------------------------------------------------------"
    echo "提示: bash deploy/emergency-restore.sh restore <文件名>"
}

restore_backup() {
    local BACKUP_FILE="$1"
    
    if [ -z "$BACKUP_FILE" ]; then
        echo "用法: bash deploy/emergency-restore.sh restore <备份文件>"
        return 1
    fi
    
    if [[ "$BACKUP_FILE" != /* ]]; then
        BACKUP_FILE="$BACKUP_DIR/$BACKUP_FILE"
    fi
    
    if [ ! -f "$BACKUP_FILE" ]; then
        echo "❌ 文件不存在: $BACKUP_FILE"
        return 1
    fi
    
    echo ""
    echo "⚠️  即将恢复数据库！"
    echo "  来源: $(basename $BACKUP_FILE)"
    echo "  目标: $POSTGRES_DB"
    echo ""
    read -p "确认？(输入 YES 继续): " CONFIRM
    if [ "$CONFIRM" != "YES" ]; then
        echo "已取消"
        return
    fi
    
    echo "🔄 恢复中..."
    
    docker compose -f "$COMPOSE_FILE" stop backend frontend 2>/dev/null || true
    
    docker compose -f "$COMPOSE_FILE" exec -T db dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB" 2>/dev/null || true
    docker compose -f "$COMPOSE_FILE" exec -T db createdb -U "$POSTGRES_USER" "$POSTGRES_DB" 2>/dev/null || true
    
    if gunzip -c "$BACKUP_FILE" | docker compose -f "$COMPOSE_FILE" exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"; then
        echo "✅ 数据导入成功"
    else
        echo "❌ 导入失败"
        return 1
    fi
    
    docker compose -f "$COMPOSE_FILE" up -d backend frontend
    
    sleep 10
    
    show_status
    echo "✅ 恢复完成"
}

restart_services() {
    echo "🔄 重启所有服务..."
    docker compose -f "$COMPOSE_FILE" restart
    sleep 15
    show_status
    echo "✅ 重启完成"
}

case "${1:-status}" in
    status|st)
        show_status
        ;;
    backups|ls|list)
        list_backups
        ;;
    restore|r)
        restore_backup "${2:-}"
        ;;
    restart|re)
        restart_services
        ;;
    help|--help|-h)
        echo "用法: emergency-restore.sh [命令]"
        echo ""
        echo "命令:"
        echo "  status     显示系统状态（默认）"
        echo "  backups    列出备份文件"
        echo "  restore    恢复指定备份"
        echo "  restart    重启所有服务"
        echo "  help       显示帮助"
        ;;
    *)
        echo "未知命令: $1"
        echo "使用 'help' 查看帮助"
        exit 1
        ;;
esac