#!/usr/bin/env bash
# 起 standalone 产物,逐路径核对安全响应头。build 之后跑(本地或 CI)。
# 用途:next.config.mjs 的 headers()/poweredByHeader 没有单测框架可挂,这是它的自动化守门。
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .next/standalone/server.js ] || { echo "先 pnpm build"; exit 1; }
cp -r public .next/standalone/ 2>/dev/null || true
mkdir -p .next/standalone/.next && cp -r .next/static .next/standalone/.next/

PORT="${PORT:-3999}"
# 端口已有人监听就直接失败:否则 node 起不来、curl 却打到别的进程,守门变成空转
if curl -s -o /dev/null "http://127.0.0.1:$PORT/"; then
  echo "FAIL 端口 $PORT 已被占用,不能确认测的是本次构建"; exit 1
fi
SERVER_LOG=$(mktemp)
PORT=$PORT HOSTNAME=127.0.0.1 node .next/standalone/server.js >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true; rm -f "$SERVER_LOG"' EXIT
for _ in $(seq 1 30); do curl -sf -o /dev/null "http://127.0.0.1:$PORT/zh/login" && break; sleep 1; done
if ! kill -0 "$SERVER_PID" 2>/dev/null || ! curl -sf -o /dev/null "http://127.0.0.1:$PORT/zh/login"; then
  echo "FAIL standalone 未就绪,服务端输出:"; cat "$SERVER_LOG"; exit 1
fi

EXPECTED=(
  "x-content-type-options: nosniff"
  "x-frame-options: DENY"
  "content-security-policy: frame-ancestors 'none'"
  "referrer-policy: strict-origin-when-cross-origin"
  "permissions-policy: geolocation=(), camera=(), microphone=()"
)
# 200 页面 / 404 页面 / 根路径 307 重定向 / public 静态资源 / 构建产物 chunk,五类响应各取一条
CHUNK=$(cd .next/standalone/.next/static/chunks && ls *.js | head -1)
PATHS=(/zh/login /zh/does-not-exist / /icon.png "/_next/static/chunks/$CHUNK")

fail=0
for p in "${PATHS[@]}"; do
  hdrs=$(curl -sI "http://127.0.0.1:$PORT$p" | tr -d '\r' | tr 'A-Z' 'a-z')
  path_ok=1
  for e in "${EXPECTED[@]}"; do
    grep -qF "$(echo "$e" | tr 'A-Z' 'a-z')" <<<"$hdrs" || { echo "FAIL $p 缺 $e"; path_ok=0; }
  done
  grep -q "^x-powered-by:" <<<"$hdrs" && { echo "FAIL $p 仍有 X-Powered-By"; path_ok=0; }
  [ $path_ok = 1 ] && echo "ok  $p" || fail=1
done
exit $fail
