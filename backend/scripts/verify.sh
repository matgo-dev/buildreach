#!/usr/bin/env bash
# verify.sh — 端到端 curl 自检。前提:后端运行在 http://localhost:8000
#
# 用法:bash scripts/verify.sh
set -u

BASE="${BASE:-http://localhost:8000}"
EMAIL="buyer.$(date +%s)@cscec3b.com"
PWD="Abcd1234"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}✓${NC} $*"; }
fail() { echo -e "${RED}✗${NC} $*"; exit 1; }
note() { echo -e "${YELLOW}→${NC} $*"; }

# --- 1. healthz ---
note "GET /healthz"
status=$(curl -s -o /tmp/v_health.json -w "%{http_code}" "$BASE/healthz")
[[ "$status" == "200" ]] && pass "healthz 200" || fail "healthz expected 200, got $status"

# --- 2. 注册 BUYER ---
note "POST /api/v1/auth/register/buyer ($EMAIL)"
status=$(curl -s -o /tmp/v_reg.json -w "%{http_code}" \
  -H "Content-Type: application/json" \
  -X POST "$BASE/api/v1/auth/register/buyer" \
  -d "{\"email\":\"$EMAIL\",\"name\":\"测试买家\",\"phone\":\"13800138000\",\"password\":\"$PWD\"}")
[[ "$status" == "200" ]] && pass "register/buyer 200" || fail "register expected 200, got $status (body: $(cat /tmp/v_reg.json))"

# --- 3. 错误密码登录 ---
note "POST /api/v1/auth/login (wrong password)"
status=$(curl -s -o /tmp/v_bad.json -w "%{http_code}" \
  -H "Content-Type: application/json" \
  -X POST "$BASE/api/v1/auth/login" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"WrongPass1\"}")
[[ "$status" == "401" ]] && pass "wrong password 401" || fail "expected 401, got $status"

# --- 4. 正确登录 ---
note "POST /api/v1/auth/login (correct)"
resp=$(curl -s -i -H "Content-Type: application/json" \
  -X POST "$BASE/api/v1/auth/login" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PWD\"}")
echo "$resp" | grep -qi '^x-trace-id:' && pass "login 响应头含 X-Trace-Id" || fail "缺少 X-Trace-Id 响应头"
TOKEN=$(echo "$resp" | grep -o '"access_token":"[^"]*"' | sed 's/"access_token":"\(.*\)"/\1/')
[[ -n "$TOKEN" ]] && pass "拿到 access_token" || fail "登录响应无 access_token"

# --- 5. /auth/me ---
note "GET /api/v1/auth/me"
status=$(curl -s -o /tmp/v_me.json -w "%{http_code}" \
  -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/auth/me")
[[ "$status" == "200" ]] && pass "/auth/me 200" || fail "/auth/me expected 200, got $status"
grep -q '"BUYER"' /tmp/v_me.json && pass "me.roles 含 BUYER" || fail "me 响应缺 BUYER 角色"
grep -q '"中建三局"' /tmp/v_me.json && pass "me.organization=中建三局" || fail "me 响应缺中建三局组织"

# --- 6. /test/buyer-only ---
note "GET /api/v1/test/buyer-only"
status=$(curl -s -o /tmp/v_bo.json -w "%{http_code}" \
  -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/test/buyer-only")
[[ "$status" == "200" ]] && pass "buyer-only 200" || fail "buyer-only expected 200, got $status"

# --- 7. /test/admin-only(BUYER 应被拒) ---
note "GET /api/v1/test/admin-only as BUYER"
status=$(curl -s -o /tmp/v_ao.json -w "%{http_code}" \
  -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/test/admin-only")
[[ "$status" == "403" ]] && pass "admin-only 拒绝 BUYER 403" || fail "expected 403, got $status"

echo
pass "全部检查通过 ✅"
