#!/bin/bash
# v315-walk-services.sh — Boot EAASP minimum subset for v3.15.5 walkthrough.
# Avoids the leftovers that block the full dev-eaasp.sh (Phase 5.4
# services may still be resident from prior sessions).
#
# Services: skill-registry + L2 + L3 + L4 + mock-scada SSE + L1 grid-runtime.
#
# v3.15.5 V315-BUSINESS-FLOW-02 demo: also boots L1 grid-runtime on
# :50051 so the demo can drive real LLM traffic through the
# cross-layer business-flow pipeline.

set -euo pipefail

cd "$(dirname "$0")/.."

# v3.15.5 demo convenience: dev-mode scope binding bypass so the
# /v1/sessions/create endpoint works without a pre-loaded skill
# registry frontmatter. Production must NEVER set this.
export EAASP_DEV_DISABLE_SCOPE_BINDING="${EAASP_DEV_DISABLE_SCOPE_BINDING:-1}"

LOGDIR=".logs/v315-walk"
mkdir -p "$LOGDIR"

# Reap any leftover PIDs from prior runs.
for port in 18081 18082 18083 18084 18085 18090 50051; do
  PIDS=$(lsof -nP -iTCP:$port -sTCP:LISTEN -t 2>/dev/null || true)
  if [ -n "$PIDS" ]; then
    echo "[v315-walk] Reaping leftover PIDs on :$port: $PIDS"
    kill -9 $PIDS 2>/dev/null || true
  fi
done

echo "[v315-walk] Starting skill-registry on :18081"
nohup "$PWD/target/debug/eaasp-skill-registry" \
  --data-dir "$PWD/data/dev-skill-registry" \
  > "$LOGDIR/skill-registry.log" 2>&1 &
echo $! > "$LOGDIR/skill-registry.pid"

echo "[v315-walk] Starting L2 memory-engine on :18085"
nohup tools/eaasp-l2-memory-engine/.venv/bin/python -m eaasp_l2_memory_engine.main \
  --port 18085 > "$LOGDIR/l2.log" 2>&1 &
echo $! > "$LOGDIR/l2.pid"

echo "[v315-walk] Starting mock-scada SSE on :18090"
nohup tools/mock-scada/.venv/bin/python -m mock_scada.server \
  --port 18090 > "$LOGDIR/mock-scada.log" 2>&1 &
echo $! > "$LOGDIR/mock-scada.pid"

echo "[v315-walk] Starting L3 governance on :18083"
nohup tools/eaasp-l3-governance/.venv/bin/python -m eaasp_l3_governance.main \
  --port 18083 > "$LOGDIR/l3.log" 2>&1 &
echo $! > "$LOGDIR/l3.pid"

echo "[v315-walk] Starting L4 orchestration on :18084"
nohup tools/eaasp-l4-orchestration/.venv/bin/python -m eaasp_l4_orchestration.main \
  --port 18084 > "$LOGDIR/l4.log" 2>&1 &
echo $! > "$LOGDIR/l4.pid"

# v3.15.5 — V315-BUSINESS-FLOW-02 demo: also boot L1 grid-runtime
# so the demo can drive a real agent loop through the cross-layer
# pipeline. LLM_PROVIDER + matching API key must be set in the
# environment; if absent, the binary still starts but message calls
# fail — the demo degrades to ingest-only path.
echo "[v315-walk] Starting L1 grid-runtime on :50051 (best-effort)"
GRID_DB="$PWD/data/v315-walk-grid.db"
mkdir -p "$(dirname "$GRID_DB")"
if [ -x "$PWD/target/debug/grid-runtime" ]; then
  nohup "$PWD/target/debug/grid-runtime" \
    --bind 127.0.0.1:50051 \
    --db "$GRID_DB" \
    > "$LOGDIR/grid-runtime.log" 2>&1 &
  echo $! > "$LOGDIR/grid-runtime.pid"
else
  echo "[v315-walk] WARNING: target/debug/grid-runtime missing — run: cargo build -p grid-runtime"
fi

echo "[v315-walk] All services started. Wait ~10s, then check ports:"
sleep 12
for port in 18081 18082 18083 18084 18085 18090 50051; do
  timeout 1 bash -c "echo > /dev/tcp/127.0.0.1/$port" 2>/dev/null \
    && echo "  :$port UP" || echo "  :$port down"
done
echo "[v315-walk] PIDs:"
for f in "$LOGDIR"/*.pid; do
  echo "  $(basename $f .pid): PID=$(cat $f)"
done
