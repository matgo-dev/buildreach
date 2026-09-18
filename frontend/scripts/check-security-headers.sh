#!/usr/bin/env bash
# 起 standalone 产物,逐路径核对安全响应头。build 之后跑(本地或 CI)。
# 用途:next.config.mjs 的 headers()/poweredByHeader 没有单测框架可挂,这是它的自动化守门。
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .next/standalone/server.js ] || { echo "先 pnpm build"; exit 1; }
cp -r public .next/standalone/ 2>/dev/null || true
mkdir -p .next/standalone/.next && cp -r .next/static .next/standalone/.next/

PORT="${PORT:-3999}"
PORT=$PORT HOSTNAME=127.0.0.1 node .next/standalone/server.js >/dev/null 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do curl -sf -o /dev/null "http://127.0.0.1:$PORT/zh/login" && break; sleep 1; done

EXPECTED=(
  "x-content-type-options: nosniff"
  "x-frame-options: DENY"
  "content-security-policy: frame-ancestors 'none'"
  "referrer-policy: strict-origin-when-cross-origin"
  "permissions-policy: geolocation=(), camera=(), microphone=()"
)
# 200 页面 / 404 页面 / 根路径 307 重定向 / 静态资源,四类响应各取一条
PATHS=(/zh/login /zh/does-not-exist / /icon.png)

fail=0
for p in "${PATHS[@]}"; do
  hdrs=$(curl -sI "http://127.0.0.1:$PORT$p" | tr -d '\r' | tr 'A-Z' 'a-z')
  for e in "${EXPECTED[@]}"; do
    grep -qF "$(echo "$e" | tr 'A-Z' 'a-z')" <<<"$hdrs" || { echo "FAIL $p 缺 $e"; fail=1; }
  done
  grep -q "^x-powered-by:" <<<"$hdrs" && { echo "FAIL $p 仍有 X-Powered-By"; fail=1; }
  echo "ok  $p"
done
exit $fail
