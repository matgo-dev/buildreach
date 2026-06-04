#!/usr/bin/env bash
# 审计日志速查工具(MVP 阶段没 UI,临时用)
#
# 用法:
#   bash scripts/audit_query.sh                  最近 20 条
#   bash scripts/audit_query.sh fail             仅失败
#   bash scripts/audit_query.sh login            登录相关
#   bash scripts/audit_query.sh user u@x.com     某用户的全部
#   bash scripts/audit_query.sh trace abc-123    某 trace 全链路
#   bash scripts/audit_query.sh detail 42        某条审计的完整内容(含 extra JSON)
set -u

cd "$(dirname "$0")/.."
DB=dev.db

case "${1:-}" in
  fail)
    sqlite3 "$DB" -header -column "
      SELECT id, datetime(created_at) AS time, action, user_email,
             ip, error_message, substr(trace_id,1,8) AS trace
      FROM audit_logs WHERE status='FAILED'
      ORDER BY id DESC LIMIT 50;"
    ;;
  login)
    sqlite3 "$DB" -header -column "
      SELECT id, datetime(created_at) AS time, action, status, user_email,
             ip, substr(trace_id,1,8) AS trace
      FROM audit_logs WHERE resource_type='auth'
      ORDER BY id DESC LIMIT 50;"
    ;;
  user)
    EMAIL=${2:-}
    [[ -z "$EMAIL" ]] && { echo "用法: $0 user <email>"; exit 1; }
    sqlite3 "$DB" -header -column "
      SELECT id, datetime(created_at) AS time, action, status, method, path
      FROM audit_logs WHERE user_email='$EMAIL'
      ORDER BY id DESC LIMIT 50;"
    ;;
  trace)
    TRACE=${2:-}
    [[ -z "$TRACE" ]] && { echo "用法: $0 trace <trace_id>"; exit 1; }
    sqlite3 "$DB" -header -column "
      SELECT id, datetime(created_at) AS time, action, status, user_email, path
      FROM audit_logs WHERE trace_id LIKE '$TRACE%'
      ORDER BY id;"
    ;;
  detail)
    ID=${2:-}
    [[ -z "$ID" ]] && { echo "用法: $0 detail <id>"; exit 1; }
    sqlite3 "$DB" -line "SELECT * FROM audit_logs WHERE id=$ID;"
    ;;
  *)
    sqlite3 "$DB" -header -column "
      SELECT id, datetime(created_at) AS time, action, status, user_email,
             ip, substr(trace_id,1,8) AS trace
      FROM audit_logs ORDER BY id DESC LIMIT 20;"
    ;;
esac
