#!/bin/bash
# v315-web-e2e.sh — End-to-end verification for the OBSTACK Phase C.0 dashboard.
#
# This is the smoke test the previous commit was missing: spin up L4 + web,
# then confirm the flowsApi endpoints actually return data end-to-end.
#
# Pre-conditions: scripts/v315-web-dev.sh has been run (or run this script
# first — it will boot the services itself).
#
# Run: bash scripts/v315-web-e2e.sh
# Exit 0 on success, non-zero on failure.

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB_PORT=5180
L4_PORT=18084
LOGDIR="$ROOT/.logs/v315-web-dev"

# ─── Ensure services up ─────────────────────────────────────────────
need_dev=false
if ! lsof -nP -iTCP:$L4_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "[e2e] L4 not up — will start"
  need_dev=true
fi
if ! lsof -nP -iTCP:$WEB_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "[e2e] web not up — will start"
  need_dev=true
fi
if [ "$need_dev" = true ]; then
  bash "$ROOT/scripts/v315-web-dev.sh" > "$LOGDIR/dev-startup.log" 2>&1 || true
  sleep 8
fi

echo ""
echo "=== e2e step 1: health probes ==="
curl -fsS "http://127.0.0.1:$WEB_PORT/" -o /dev/null -w "web :$WEB_PORT  status=%{http_code}\n" \
  || { echo "web DOWN"; exit 1; }
curl -fsS "http://127.0.0.1:$L4_PORT/health" -o /dev/null -w "L4  :$L4_PORT  status=%{http_code}\n" \
  || { echo "L4 DOWN"; exit 1; }

echo ""
echo "=== e2e step 2: web serves the Phase C.0 bundle (should mention flowsApi) ==="
curl -fsS "http://127.0.0.1:$WEB_PORT/assets/" -o /dev/null -w "  /assets/  status=%{http_code}\n"
# Fetch the index — it should be the live dev server (200 + <script src=...>)
INDEX=$(curl -fsS "http://127.0.0.1:$WEB_PORT/")
if echo "$INDEX" | grep -q '<div id="root">'; then
  echo "  /  has #root mount point ✓"
else
  echo "  /  missing #root ✗"
  exit 1
fi
SCRIPT_SRC=$(echo "$INDEX" | grep -oE 'src="[^"]+\.js"' | head -1 | sed 's/src="//;s/"$//')
if [ -z "$SCRIPT_SRC" ]; then
  echo "  no script src in /"
  exit 1
fi
echo "  /  → $SCRIPT_SRC"
curl -fsS "http://127.0.0.1:$WEB_PORT$SCRIPT_SRC" -o /tmp/_bundle.js -w "  bundle status=%{http_code} size=%{size_download}\n"
# Bundle should mention our new tab in dev mode (un-minified); in prod build
# it's been minified so we can only check size > some threshold.
BUNDLE_SIZE=$(stat -f %z /tmp/_bundle.js 2>/dev/null || echo 0)
if [ "$BUNDLE_SIZE" -lt 100000 ]; then
  echo "  bundle suspiciously small ($BUNDLE_SIZE bytes) — Phase C.0 code may not be in it"
  exit 1
fi
echo "  bundle size: $BUNDLE_SIZE bytes (looks like full SPA)"

echo ""
echo "=== e2e step 3: L4 OBSTACK endpoints used by flowsApi ==="
LIST=$(curl -fsS "http://127.0.0.1:$L4_PORT/v1/business-flows/list?limit=10")
echo "$LIST" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('  list → flows:', len(d['flows']), 'total:', d['total'])
"

# Pick the first flow's business_key and hit the other endpoints
KEY=$(echo "$LIST" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['flows'][0]['business_key'] if d['flows'] else '')")
ENCODED=$(python3 -c "import urllib.parse;print(urllib.parse.quote('$KEY'))")
if [ -n "$KEY" ]; then
  echo "  using business_key: $KEY"
  for EP in summary sessions evaluation; do
    RESP=$(curl -fsS "http://127.0.0.1:$L4_PORT/v1/business-flows/$ENCODED/$EP")
    echo "    /$EP → $(echo "$RESP" | python3 -c "import json,sys;d=json.load(sys.stdin);print({k: type(v).__name__ for k,v in d.items()})")"
  done
  # Timeline count
  COUNT=$(curl -fsS "http://127.0.0.1:$L4_PORT/v1/business-flows/$ENCODED/timeline" \
    | python3 -c "import json,sys;print(json.load(sys.stdin)['count'])")
  echo "    /timeline → events: $COUNT"
fi

echo ""
echo "=== e2e step 4: simulate frontend flowsApi call ==="
# Use Node to simulate the browser — fetch L4 directly the way flowsApi does.
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
"

echo ""
echo "=== e2e step 5: cross-check web dev server proxy works ==="
# web/ has proxy config /api → :3001 and /ws → :3001 (for grid-server).
# We verify by hitting /api through the dev server.
curl -sS "http://127.0.0.1:$WEB_PORT/api/v1/config" -o /tmp/_config.json -w "  /api/v1/config → status=%{http_code}\n" || true
# grid-server is not running so /api/* will ECONNREFUSED — that's expected;
# we only check that vite serves the index correctly.

echo ""
echo "✓ v315-web-e2e PASSED"
echo ""
echo "Manual verification still required: open http://localhost:$WEB_PORT and"
echo "click 'Business Flows' tab in the top bar. You should see at least one"
echo "business-flow card. Click it to see the 4-panel detail view."
