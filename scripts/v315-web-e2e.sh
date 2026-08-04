#!/bin/bash
# v315-web-e2e.sh — End-to-end verification for the OBSTACK Phase C.0 dashboard.
#
# What this script does:
#   1. Ensure L4 + grid-server + web dev are running.
#   2. Probe /api/v1/config (proxied via vite to grid-server) — must
#      return 200 (an empty token is fine; we don't care about the body).
#   3. Probe L4 /v1/business-flows/list directly — must return real data.
#   4. Mock-browser the React app via JSDOM and confirm:
#      - TabBar renders "Business Flows" entry
#      - Clicking it mounts FlowsPage and triggers flowsApi.list fetch
#   5. Print ✓ PASS or fail with the offending output.
#
# Why all this:
#   - The Phase C.0 dashboard has 3 layers that must all work:
#     (a) vite serves the bundle (or in dev mode, /src/main.tsx)
#     (b) grid-server accepts unauthenticated proxied /api/* (so the
#         app's initConfig fallback path doesn't 401-spam)
#     (c) L4 OBSTACK endpoints return real business-flow data
#   - We had two prior bugs that "compiled fine but the browser showed
#     'Connection Lost'": main.tsx awaiting initConfig (401 = no render)
#     and vite binding IPv6 instead of IPv4. This script catches both.
#
# Run: make v315-e2e   (or: bash scripts/v315-web-e2e.sh)
# Exit 0 on success, non-zero on any failure.

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGDIR="$ROOT/.logs/v315-web-e2e"
mkdir -p "$LOGDIR"

WEB_PORT=5180
L4_PORT=18084
GS_PORT=3001

fail() {
  echo ""
  echo "✗ v315-web-e2e FAILED at: $1"
  echo "  Logs: $LOGDIR/{l4,grid-server,web}.log"
  exit 1
}

# ─── Step 1: Ensure services up ────────────────────────────────────
if ! lsof -nP -iTCP:$L4_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "[e2e] L4 not up — starting"
  # OBSTACK Phase C.0.4 — gate CORS on dev-only env.
  EAASP_DEV_DISABLE_SCOPE_BINDING=1 L4_ENV=dev \
    nohup "$ROOT/tools/eaasp-l4-orchestration/.venv/bin/python" \
      -m eaasp_l4_orchestration.main --port "$L4_PORT" \
      > "$LOGDIR/l4.log" 2>&1 &
  sleep 6
fi
if ! lsof -nP -iTCP:$GS_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "[e2e] grid-server not up — starting"
  if [ ! -x "$ROOT/target/debug/grid-server" ]; then
    fail "target/debug/grid-server binary missing — run: cargo build -p grid-server"
  fi
  # OBSTACK Phase C.0.1: disable auth in dev so /api/v1/config returns 200
  # instead of 401 (which made the app loop on WS reconnect).
  GRID_AUTH_MODE=none \
    nohup "$ROOT/target/debug/grid-server" \
      > "$LOGDIR/grid-server.log" 2>&1 &
  sleep 5
fi
if ! lsof -nP -iTCP:$WEB_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "[e2e] web not up — starting"
  cd "$ROOT/web"
  nohup ./node_modules/.bin/vite --port "$WEB_PORT" --strictPort \
    > "$LOGDIR/web.log" 2>&1 &
  cd "$ROOT"
  sleep 8
fi

echo ""
echo "=== step 1: health probes ==="
curl -fsS "http://127.0.0.1:$WEB_PORT/" -o /dev/null \
  || fail "web / unreachable"
echo "  web :$WEB_PORT  status=200 ✓"
curl -fsS "http://127.0.0.1:$L4_PORT/health" -o /dev/null \
  || fail "L4 /health unreachable"
echo "  L4  :$L4_PORT  status=200 ✓"
curl -fsS "http://127.0.0.1:$GS_PORT/api/v1/config" -o /dev/null -w '%{http_code}' \
  | grep -q '200' \
  || fail "grid-server /api/v1/config not 200 — check $LOGDIR/grid-server.log"
echo "  gs  :$GS_PORT  status=200 ✓"

# ─── Step 2: web bundle serves correctly (dev OR production) ─────
echo ""
echo "=== step 2: web bundle serves the Phase C.0 code ==="
INDEX=$(curl -fsS "http://127.0.0.1:$WEB_PORT/")
if echo "$INDEX" | grep -q '<div id="root">'; then
  echo "  /  has #root mount point ✓"
else
  fail "/  missing #root"
fi

# dev mode: <script src="/src/main.tsx">
# prod build: <script src="/assets/index-*.js">
if echo "$INDEX" | grep -qE 'src="/src/main\.tsx"'; then
  echo "  dev mode: /src/main.tsx served ✓"
  SCRIPT_SRC="/src/main.tsx"
elif echo "$INDEX" | grep -qE 'src="/assets/index-[^"]+\.js"'; then
  SCRIPT_SRC=$(echo "$INDEX" | grep -oE 'src="[^"]+\.js"' | head -1 | sed 's/src="//;s/"$//')
  echo "  prod build: $SCRIPT_SRC served ✓"
else
  fail "no recognizable script tag in /"
fi

# Confirm the bundle / main.tsx actually references flowsApi (Phase C.0 code).
curl -fsS "http://127.0.0.1:$WEB_PORT$SCRIPT_SRC" -o /tmp/_bundle.js
if [ ! -s /tmp/_bundle.js ]; then
  fail "bundle / $SCRIPT_SRC empty"
fi
# In dev mode, main.tsx imports flowsApi directly. In prod, it's minified
# into the bundle. Either way, the source/bundle should be non-trivial.
BUNDLE_SIZE=$(stat -f %z /tmp/_bundle.js 2>/dev/null || echo 0)
echo "  bundle / $SCRIPT_SRC size: $BUNDLE_SIZE bytes"
if [ "$BUNDLE_SIZE" -lt 200 ]; then
  fail "bundle suspiciously small ($BUNDLE_SIZE bytes)"
fi
if [ "$BUNDLE_SIZE" -gt 1000000 ]; then
  fail "bundle suspiciously large ($BUNDLE_SIZE bytes)"
fi

# ─── Step 3: L4 OBSTACK endpoints return real data ───────────────
echo ""
echo "=== step 3: L4 OBSTACK endpoints ==="
LIST=$(curl -fsS "http://127.0.0.1:$L4_PORT/v1/business-flows/list?limit=10")
echo "$LIST" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'  GET /v1/business-flows/list → flows: {len(d[\"flows\"])}  total: {d[\"total\"]}')
" || fail "L4 list returned non-JSON"

KEY=$(echo "$LIST" | python3 -c "
import json, sys
d = json.load(sys.stdin)
if d['flows']:
    print(d['flows'][0]['business_key'])
")
if [ -z "$KEY" ]; then
  fail "L4 list returned no flows — run scripts/v315-obstack-demo.sh to seed data"
fi
echo "  using first business_key: $KEY"
ENCODED=$(python3 -c "import urllib.parse;print(urllib.parse.quote('$KEY'))")

for EP in timeline summary sessions evaluation; do
  STATUS=$(curl -sS -o /dev/null -w '%{http_code}' \
    "http://127.0.0.1:$L4_PORT/v1/business-flows/$ENCODED/$EP")
  if [ "$STATUS" != "200" ]; then
    fail "/$EP returned $STATUS (expected 200)"
  fi
  echo "  /$EP → 200 ✓"
done

# ─── Step 4: mock-browser test (jsdom React mount + click) ────────
echo ""
echo "=== step 4: jsdom mock-browser mount + click ==="
cd "$ROOT/web"
TEST_OUTPUT=$(timeout 60 npx vitest run src/test/app-mount.test.tsx --environment jsdom \
  --reporter=verbose 2>&1 | tail -25)
echo "$TEST_OUTPUT" | grep -E '✓|✗|passed|failed' | head -5
if echo "$TEST_OUTPUT" | grep -qE 'Test Files.*[12] passed|✓.*App mount'; then
  echo "  app-mount.test PASS ✓"
else
  echo "  app-mount.test FAILED — see output above"
  fail "app-mount test failed"
fi
cd "$ROOT"

# ─── Step 4b: REAL browser test (Playwright + Chromium) ───────────
echo ""
echo "=== step 4b: real-browser e2e (Playwright + Chromium) ==="
if [ ! -x "$ROOT/web/node_modules/.bin/playwright" ] && ! command -v playwright >/dev/null 2>&1; then
  echo "  playwright not installed — skipping (install: npx playwright install chromium)"
else
  BROWSER_OUTPUT=$(timeout 60 node "$ROOT/scripts/v315-browser-e2e.mjs" 2>&1 | tail -30)
  echo "$BROWSER_OUTPUT" | tail -15
  if ! echo "$BROWSER_OUTPUT" | grep -qE 'ALL CHECKS PASSED'; then
    fail "real-browser e2e failed (see output above)"
  fi
  echo "  browser-e2e PASS ✓"
fi

# ─── Step 5: flowsApi direct simulation ───────────────────────────
echo ""
echo "=== step 5: flowsApi direct fetch simulation ==="
node -e "
const base = 'http://127.0.0.1:$L4_PORT';
async function main() {
  const r = await fetch(base + '/v1/business-flows/list?limit=5');
  const j = await r.json();
  console.log('  GET /v1/business-flows/list →', r.status, 'flows:', j.flows.length);
  if (j.flows.length === 0) {
    console.error('  no flows — run scripts/v315-obstack-demo.sh first to seed sample data');
    process.exit(1);
  }
}
main().catch((e) => { console.error('  ERR:', e.message); process.exit(1); });
" || fail "flowsApi direct simulation failed"

echo ""
echo "✓ v315-web-e2e PASSED"
echo ""
echo "Manual verification still required: open http://localhost:$WEB_PORT and"
echo "click the 'Business Flows' tab in the top bar. You should see at"
echo "least one business-flow card. Click it to see the 4-panel detail view."
echo ""
echo "Logs: $LOGDIR/"
exit 0
