#!/usr/bin/env bash
# Gateway integration tests — run with: bash gateway/test.sh
# Requires full stack running: make dev

set -euo pipefail

GATEWAY="http://localhost:8080"
PASS=0
FAIL=0

ok() { echo "  PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

assert_status() {
    local desc="$1" expected="$2" actual="$3"
    if [[ "$actual" == "$expected" ]]; then ok "$desc → $actual"; else fail "$desc → expected $expected, got $actual"; fi
}

assert_contains() {
    local desc="$1" needle="$2" haystack="$3"
    if echo "$haystack" | grep -q "$needle"; then ok "$desc → contains '$needle'"; else fail "$desc → '$needle' not found in response"; fi
}

echo ""
echo "=== RiskCore Gateway Tests ==="
echo ""

# 1. Gateway health — no auth
echo "--- [1] Gateway health ---"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$GATEWAY/health/")
assert_status "GET /health/ → 200" "200" "$STATUS"
BODY=$(curl -s "$GATEWAY/health/")
assert_contains "health body has 'gateway'" "gateway" "$BODY"

# 2. Sin JWT → 401
echo "--- [2] No JWT → 401 ---"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$GATEWAY/api/policies/policies/")
assert_status "GET /api/policies/ without JWT → 401" "401" "$STATUS"
BODY=$(curl -s "$GATEWAY/api/policies/policies/")
assert_contains "401 body has UNAUTHORIZED code" "UNAUTHORIZED" "$BODY"
assert_contains "401 body has request_id" "request_id" "$BODY"

# 3. Token obtain
echo "--- [3] Obtain JWT ---"
TOKEN_RESP=$(curl -s -X POST "$GATEWAY/api/auth/token/" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"admin"}')  # pragma: allowlist secret
ACCESS=$(echo "$TOKEN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access',''))" 2>/dev/null || echo "")
if [[ -n "$ACCESS" && "$ACCESS" != "None" ]]; then
    ok "POST /api/auth/token/ → access token obtained"
else
    fail "POST /api/auth/token/ → no access token (response: $TOKEN_RESP)"
fi

# 4. Con JWT válido → acceso permitido
echo "--- [4] Valid JWT → 200 ---"
if [[ -n "$ACCESS" && "$ACCESS" != "None" ]]; then
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $ACCESS" \
        "$GATEWAY/api/policies/policies/")
    assert_status "GET /api/policies/ with JWT → 200" "200" "$STATUS"
fi

# 5. JWT inválido → 401
echo "--- [5] Invalid JWT → 401 ---"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer invalid.token.here" \
    "$GATEWAY/api/policies/policies/")
assert_status "GET /api/policies/ with bad JWT → 401" "401" "$STATUS"

# 6. X-Request-ID presente en respuesta
echo "--- [6] X-Request-ID propagation ---"
HEADERS=$(curl -s -i "$GATEWAY/health/" 2>&1)
if echo "$HEADERS" | grep -qi "x-request-id"; then
    ok "X-Request-ID header present in response"
else
    fail "X-Request-ID header missing from response"
fi

# 7. Rate limit — 25 requests anónimos rápidos (zona api_anon: 20r/m, burst 5 nodelay)
echo "--- [7] Rate limiting (anon zone: /api/auth/token/) ---"
RATE_429=0
for i in $(seq 1 25); do
    CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$GATEWAY/api/auth/token/" -H "Content-Type: application/json" -d '{}')
    if [[ "$CODE" == "429" ]]; then RATE_429=$((RATE_429+1)); fi
done
if [[ "$RATE_429" -gt 0 ]]; then
    ok "Rate limit triggered: $RATE_429/25 requests returned 429"
else
    fail "Rate limit not triggered after 25 rapid requests (expected some 429s)"
fi

# 8. 429 response body has RATE_LIMIT_EXCEEDED
echo "--- [8] Rate limit error format ---"
# Send many POST requests to /api/auth/token/ to trigger the limit and capture a 429 body
for i in $(seq 1 30); do
    BODY=$(curl -s -X POST "$GATEWAY/api/auth/token/" -H "Content-Type: application/json" -d '{}')
    if echo "$BODY" | grep -q "RATE_LIMIT_EXCEEDED"; then
        ok "429 body has RATE_LIMIT_EXCEEDED code"
        break
    fi
    if [[ "$i" == "30" ]]; then fail "Never got RATE_LIMIT_EXCEEDED in response body"; fi
done

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
echo ""
[[ "$FAIL" -eq 0 ]] || exit 1
