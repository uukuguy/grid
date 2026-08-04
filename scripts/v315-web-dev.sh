#!/bin/bash
# v315-web-dev.sh — Start the OBSTACK Phase C.0 web dashboard cleanly.
#
# What this does:
#   1. Reap any leftover vite/web processes on port 5180.
#   2. Boot L4 OBSTACK backend on :18084 (EAASP_DEV_DISABLE_SCOPE_BINDING=1).
#   3. Boot vite dev server in web/ on :5180 (strictPort mode).
#   4. Write PIDs to .logs/v315-web-dev/pids.env for cleanup.
#
# Why all three:
#   - The Phase C.0 dashboard fetches /v1/business-flows/* directly from
#     L4 (see web/src/api/flows.ts L4_BASE_URL). If L4 is down, the
#     "Business Flows" tab shows a network error.
#   - web/vite needs cwd=web (running it from the repo root makes
#     vite scan the entire repo for .html and crashes esbuild).
#   - Port 5180 is also used by Claude Code's web sandbox; explicit
#     reap prevents "address already in use" surprises.
#
# Run: bash scripts/v315-web-dev.sh
# Then open http://localhost:5180 and click the "Business Flows" tab.
#
# Stop: bash scripts/v315-web-dev.sh stop

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGDIR="$ROOT/.logs/v315-web-dev"
mkdir -p "$LOGDIR"

WEB_PORT=5180
L4_PORT=18084

reap_port() {
  local port="$1"
  local pids
  pids=$(lsof -nP -iTCP:$port -sTCP:LISTEN -t 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "[v315-web-dev] Reaping leftover PIDs on :$port: $pids"
    kill -9 $pids 2>/dev/null || true
  fi
}

stop_all() {
  echo "[v315-web-dev] Stopping all services…"
  for pidfile in "$LOGDIR"/{web,l4}.pid; do
    [ -f "$pidfile" ] && kill -9 "$(cat "$pidfile")" 2>/dev/null || true
  done
  reap_port "$WEB_PORT"
  reap_port "$L4_PORT"
  echo "[v315-web-dev] Done."
  exit 0
}

if [ "${1:-}" = "stop" ]; then
  stop_all
fi

# ─── Reap leftover ports ───────────────────────────────────────────────
reap_port "$WEB_PORT"
reap_port "$L4_PORT"
sleep 2

# ─── 1. Start L4 ─────────────────────────────────────────────────────
echo "[v315-web-dev] Starting L4 on :$L4_PORT"
export EAASP_DEV_DISABLE_SCOPE_BINDING=1
nohup "$ROOT/tools/eaasp-l4-orchestration/.venv/bin/python" \
  -m eaasp_l4_orchestration.main --port "$L4_PORT" \
  > "$LOGDIR/l4.log" 2>&1 &
echo $! > "$LOGDIR/l4.pid"

# ─── 2. Start web (must cwd=web!) ────────────────────────────────────
echo "[v315-web-dev] Starting web dev on :$WEB_PORT (cwd=web)"
cd "$ROOT/web"
nohup ./node_modules/.bin/vite --port "$WEB_PORT" --strictPort \
  > "$LOGDIR/web.log" 2>&1 &
echo $! > "$LOGDIR/web.pid"

# ─── 3. Wait + verify ────────────────────────────────────────────────
sleep 8

echo ""
echo "[v315-web-dev] Ready:"
for port in "$WEB_PORT" "$L4_PORT"; do
  if lsof -nP -iTCP:$port -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "  :$port UP"
  else
    echo "  :$port DOWN (check $LOGDIR/*.log)"
  fi
done

echo ""
echo "[v315-web-dev] Open http://localhost:$WEB_PORT → click 'Business Flows' tab"
echo "[v315-web-dev] Stop with: bash scripts/v315-web-dev.sh stop"
