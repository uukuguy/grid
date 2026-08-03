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
#
# V315-OBSTACK-DEMO-idempotent-01: honours ``$V315_DEMO_DATA_DIR`` so
# the demo script can isolate each run in its own SQLite directory.
# When unset, services use the conventional ``data/`` defaults (the
# behaviour the original Phase 5.4 walkthrough relied on).

set -euo pipefail

cd "$(dirname "$0")/.."

# v3.15.5 demo convenience: dev-mode scope binding bypass so the
# /v1/sessions/create endpoint works without a real skill-registry
# frontmatter fetch (skill-registry serves at :18081 but the v315-walk
# boot order doesn't preload threshold-calibration into it).
export EAASP_DEV_DISABLE_SCOPE_BINDING="${EAASP_DEV_DISABLE_SCOPE_BINDING:-1}"

# V315-OBSTACK-DEMO-idempotent-01 — per-run data isolation.
# When the demo script sets V315_DEMO_DATA_DIR (e.g. data/v315-demo-20260802-…/),
# every service writes its SQLite file inside that directory so
# re-running the demo produces independent results without manual
# ``find data -name "*.db*" -delete`` wipe. When unset, services use
# the conventional ``data/`` defaults.
DEMO_DATA_DIR="${V315_DEMO_DATA_DIR:-data}"
mkdir -p "$DEMO_DATA_DIR"

LOGDIR="${LOGDIR_OVERRIDE:-.logs/v315-walk}"
mkdir -p "$LOGDIR"

# Reap any leftover PIDs from prior runs.
for port in 18081 18082 18083 18084 18085 18090 50051; do
  PIDS=$(lsof -nP -iTCP:$port -sTCP:LISTEN -t 2>/dev/null || true)
  if [ -n "$PIDS" ]; then
    echo "[v315-walk] Reaping leftover PIDs on :$port: $PIDS"
    kill -9 $PIDS 2>/dev/null || true
  fi
done

# Per-run DB paths (V315-OBSTACK-DEMO-idempotent-01). Override the
# EAASP_*_DB_PATH envvars before launching each service so each run
# gets its own fresh SQLite files.
SKILL_REGISTRY_DATA_DIR="$DEMO_DATA_DIR/skill-registry"
L2_DB_PATH="$DEMO_DATA_DIR/l2.db"
L3_DB_PATH="$DEMO_DATA_DIR/l3.db"
L4_DB_PATH="$DEMO_DATA_DIR/l4.db"
GRID_DB="$DEMO_DATA_DIR/grid-runtime.db"
mkdir -p "$SKILL_REGISTRY_DATA_DIR" "$(dirname "$L2_DB_PATH")" \
         "$(dirname "$L3_DB_PATH")" "$(dirname "$L4_DB_PATH")" \
         "$(dirname "$GRID_DB")"

echo "[v315-walk] data dir: $DEMO_DATA_DIR"
echo "[v315-walk]   L4=$L4_DB_PATH"
echo "[v315-walk]   L3=$L3_DB_PATH"
echo "[v315-walk]   L2=$L2_DB_PATH"
echo "[v315-walk]   grid=$GRID_DB"
echo "[v315-walk] log dir:  $LOGDIR"

echo "[v315-walk] Starting skill-registry on :18081"
nohup "$PWD/target/debug/eaasp-skill-registry" \
  --data-dir "$PWD/$SKILL_REGISTRY_DATA_DIR" \
  > "$LOGDIR/skill-registry.log" 2>&1 &
echo $! > "$LOGDIR/skill-registry.pid"

echo "[v315-walk] Starting L2 memory-engine on :18085"
EAASP_L2_DB_PATH="$L2_DB_PATH" \
nohup tools/eaasp-l2-memory-engine/.venv/bin/python -m eaasp_l2_memory_engine.main \
  --port 18085 > "$LOGDIR/l2.log" 2>&1 &
echo $! > "$LOGDIR/l2.pid"

echo "[v315-walk] Starting mock-scada SSE on :18090"
nohup tools/mock-scada/.venv/bin/python -m mock_scada.server \
  --port 18090 > "$LOGDIR/mock-scada.log" 2>&1 &
echo $! > "$LOGDIR/mock-scada.pid"

echo "[v315-walk] Starting L3 governance on :18083"
EAASP_L3_DB_PATH="$L3_DB_PATH" \
nohup tools/eaasp-l3-governance/.venv/bin/python -m eaasp_l3_governance.main \
  --port 18083 > "$LOGDIR/l3.log" 2>&1 &
echo $! > "$LOGDIR/l3.pid"

echo "[v315-walk] Starting L4 orchestration on :18084"
EAASP_L4_DB_PATH="$L4_DB_PATH" \
nohup tools/eaasp-l4-orchestration/.venv/bin/python -m eaasp_l4_orchestration.main \
  --port 18084 > "$LOGDIR/l4.log" 2>&1 &
echo $! > "$LOGDIR/l4.pid"

# v3.15.5 — V315-BUSINESS-FLOW-02 demo: also boot L1 grid-runtime
# so the demo can drive a real agent loop through the cross-layer
# pipeline. LLM_PROVIDER + matching API key must be set in the
# environment; if absent, the binary still starts but message calls
# fail — the demo degrades to ingest-only path.
echo "[v315-walk] Starting L1 grid-runtime on :50051 (best-effort)"
if [ -x "$PWD/target/debug/grid-runtime" ]; then
  nohup "$PWD/target/debug/grid-runtime" \
    --bind 127.0.0.1:50051 \
    --db "$PWD/$GRID_DB" \
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
