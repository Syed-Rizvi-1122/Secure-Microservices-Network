#!/bin/bash
# =============================================================================
# init-gateway.sh — Idempotent Post-Startup APISIX Gateway Configuration
# =============================================================================
# Run ONCE after `docker compose up -d`. Safe to run multiple times.
# Usage: bash init-gateway.sh
# =============================================================================

# Note: no 'set -e' — we want the script to continue through all steps

APISIX_ADMIN="http://localhost:9180"
API_KEY="edd1c9f034335f136f87ad84b625c8f1"
CERTS_DIR="./certs"

api_call() {
  local method="$1" endpoint="$2" data="$3"
  local http_code
  http_code=$(curl -s -o /tmp/apisix_resp.json -w "%{http_code}" \
    -X "$method" "${APISIX_ADMIN}${endpoint}" \
    -H "X-API-KEY: ${API_KEY}" -H "Content-Type: application/json" \
    -d "$data" 2>/dev/null)
  [[ "$http_code" =~ ^2[0-9][0-9]$ ]]
}

echo "============================================"
echo " APISIX Gateway Initialization"
echo "============================================"

# --- STEP 1: Register TLS Certificate ---
echo ""
echo "[Step 1/6] Registering APISIX TLS certificate..."
APISIX_CERT=$(awk '{printf "%s\\n", $0}' "${CERTS_DIR}/apisix.crt")
APISIX_KEY=$(awk '{printf "%s\\n", $0}' "${CERTS_DIR}/apisix.key")

if api_call PUT "/apisix/admin/ssls/1" "{\"cert\":\"${APISIX_CERT}\",\"key\":\"${APISIX_KEY}\",\"snis\":[\"localhost\",\"apisix\"]}"; then
  echo "  ✓ TLS certificate registered"
else
  echo "  ✗ FAILED to register TLS certificate"
fi

# --- STEP 2: Register Upstreams with mTLS ---
echo ""
echo "[Step 2/6] Registering upstreams..."
CLIENT_CERT=$(awk '{printf "%s\\n", $0}' "${CERTS_DIR}/apisix.crt")
CLIENT_KEY=$(awk '{printf "%s\\n", $0}' "${CERTS_DIR}/apisix.key")

for SVC in users products orders auth; do
  if api_call PUT "/apisix/admin/upstreams/${SVC}_upstream" \
    "{\"type\":\"roundrobin\",\"nodes\":{\"${SVC}:5000\":1},\"retries\":2,\"retry_timeout\":2,\"scheme\":\"https\",\"tls\":{\"client_cert\":\"${CLIENT_CERT}\",\"client_key\":\"${CLIENT_KEY}\"},\"pass_host\":\"node\"}"; then
    echo "  ✓ ${SVC}_upstream (mTLS)"
  else
    echo "  ✗ FAILED ${SVC}_upstream"
  fi
done

# --- STEP 3: Public Auth Routes ---
echo ""
echo "[Step 3/6] Registering public auth routes..."
RATE='{"count":100,"time_window":60,"rejected_code":429,"key":"remote_addr","policy":"local"}'

api_call PUT "/apisix/admin/routes/auth_token" \
  "{\"name\":\"auth_token\",\"uri\":\"/auth/token\",\"methods\":[\"POST\"],\"upstream_id\":\"auth_upstream\",\"plugins\":{\"limit-count\":${RATE}}}" \
  && echo "  ✓ /auth/token" || echo "  ✗ /auth/token"

api_call PUT "/apisix/admin/routes/auth_verify" \
  "{\"name\":\"auth_verify\",\"uri\":\"/auth/verify\",\"methods\":[\"GET\"],\"upstream_id\":\"auth_upstream\",\"plugins\":{\"limit-count\":${RATE}}}" \
  && echo "  ✓ /auth/verify" || echo "  ✗ /auth/verify"

api_call PUT "/apisix/admin/routes/auth_wildcard" \
  "{\"name\":\"auth_wildcard\",\"uri\":\"/auth/*\",\"upstream_id\":\"auth_upstream\",\"plugins\":{\"proxy-rewrite\":{\"regex_uri\":[\"^/auth/(.*)\",\"/auth/\$1\"]}}}" \
  && echo "  ✓ /auth/*" || echo "  ✗ /auth/*"

# --- STEP 4: JWT Consumer ---
echo ""
echo "[Step 4/6] Registering JWT consumer..."
api_call PUT "/apisix/admin/consumers/nps_user" \
  "{\"username\":\"nps_user\",\"plugins\":{\"jwt-auth\":{\"key\":\"nps-jwt-key\",\"secret\":\"nps-project-secret-2026\",\"algorithm\":\"HS256\"}}}" \
  && echo "  ✓ Consumer nps_user" || echo "  ✗ Consumer"

# --- STEP 5: Protected Routes (with JWT sub extraction via Lua) ---
echo ""
echo "[Step 5/7] Registering protected routes..."

python3 - "$APISIX_ADMIN" "$API_KEY" <<'PYEOF'
import sys, json, requests

ADMIN = sys.argv[1]
KEY = sys.argv[2]
HEADERS = {"X-API-KEY": KEY, "Content-Type": "application/json"}

# Lua code to extract JWT 'sub' claim before hide_credentials strips the header
LUA_CODE = '''return function(conf, ctx)
    local auth = ngx.req.get_headers()["Authorization"] or ""
    local token = auth:match("Bearer%s+(.+)")
    if token then
        local _, payload_b64 = token:match("([^.]+)%.([^.]+)")
        if payload_b64 then
            local rem = #payload_b64 % 4
            if rem > 0 then payload_b64 = payload_b64 .. ("="):rep(4 - rem) end
            local payload = ngx.decode_base64(payload_b64)
            if payload then
                local sub = payload:match('"sub"%s*:%s*"([^"]+)"')
                if sub then ngx.req.set_header("X-Authenticated-User", sub) end
            end
        end
    end
end'''

RATE = {"count": 200, "time_window": 60, "rejected_code": 429, "key": "remote_addr", "policy": "local"}

for svc in ["users", "products", "orders"]:
    # Root route
    root = {
        "name": f"{svc}_root", "uri": f"/{svc}", "methods": ["POST", "GET"],
        "upstream_id": f"{svc}_upstream",
        "plugins": {
            "jwt-auth": {"hide_credentials": True},
            "serverless-pre-function": {"phase": "rewrite", "functions": [LUA_CODE]},
            "limit-count": RATE
        }
    }
    r = requests.put(f"{ADMIN}/apisix/admin/routes/{svc}_root", headers=HEADERS, json=root, timeout=5)
    print(f"  {'✓' if r.ok else '✗'} /{svc} (root) — HTTP {r.status_code}")

    # Wildcard route
    wild = {
        "name": f"{svc}_wildcard", "uri": f"/{svc}/*",
        "upstream_id": f"{svc}_upstream",
        "plugins": {
            "jwt-auth": {"hide_credentials": True},
            "serverless-pre-function": {"phase": "rewrite", "functions": [LUA_CODE]},
            "proxy-rewrite": {"regex_uri": [f"^/{svc}/(.*)", "/$1"]},
            "limit-count": RATE
        }
    }
    r = requests.put(f"{ADMIN}/apisix/admin/routes/{svc}_wildcard", headers=HEADERS, json=wild, timeout=5)
    print(f"  {'✓' if r.ok else '✗'} /{svc}/* (wildcard) — HTTP {r.status_code}")
PYEOF

# --- STEP 6: Public Health Routes (no JWT) ---
echo ""
echo "[Step 6/7] Registering public health routes..."
for SVC in users products orders auth; do
  api_call PUT "/apisix/admin/routes/${SVC}_health" \
    "{\"name\":\"${SVC}_health\",\"uri\":\"/${SVC}/health\",\"upstream_id\":\"${SVC}_upstream\",\"priority\":10,\"plugins\":{\"proxy-rewrite\":{\"regex_uri\":[\"^/${SVC}/health\$\",\"/health\"]}}}" \
    && echo "  ✓ /${SVC}/health (public)" || echo "  ✗ /${SVC}/health"
done

# --- STEP 7: Static Firewall ---
echo ""
echo "[Step 7/7] Applying static firewall CIDR blocklist..."
CIDRS='["203.0.113.0/24","198.51.100.0/24","100.64.0.0/10"]'

for SVC in users products orders; do
  for V in root wildcard; do
    RID="${SVC}_${V}"
    CUR=$(curl -s "${APISIX_ADMIN}/apisix/admin/routes/${RID}" -H "X-API-KEY: ${API_KEY}" 2>/dev/null)
    UPD=$(echo "$CUR" | python3 -c "
import sys,json
try:
  d=json.load(sys.stdin)
  p=d.get('value',d.get('node',{}).get('value',d)).get('plugins',{})
  p['ip-restriction']={'blacklist':${CIDRS},'message':'Blocked by firewall'}
  print(json.dumps({'plugins':p}))
except:
  print(json.dumps({'plugins':{'ip-restriction':{'blacklist':${CIDRS},'message':'Blocked by firewall'}}}))
" 2>/dev/null)
    api_call PATCH "/apisix/admin/routes/${RID}" "$UPD" \
      && echo "  ✓ Firewall on ${RID}" || echo "  ✗ ${RID}"
  done
done

echo ""
echo "============================================"
echo " Gateway initialization complete!"
echo "============================================"
echo "  HTTPS: curl -k https://localhost:9443/users/health"
echo "  HTTP:  curl http://localhost:9080/users/health"
echo "  Token: curl -X POST http://localhost:9080/auth/token -H 'Content-Type: application/json' -d '{\"username\":\"alice\",\"password\":\"password123\"}'"
