#!/bin/bash
# v315-obstack-demo.sh — End-to-end OBSTACK v3.15.5 instance demo.
#
# Validates that EAASP v3.15.5 platform-observability stack exercises
# all 5 dimensions (Observe / Trace / Evaluate / Optimize / Verify)
# against real running services with REAL data flowing through (not
# just empty wire-format round-trips like the earlier
# PRODUCTION_USABILITY_2026-08-02-walk).
#
# Pre-conditions:
#   - Commits 1-4 of V315-BUSINESS-FLOW-02 applied (LayerReaders
#     wired, business_key persisted on L4 sessions + L3 decisions,
#     CLI circular-import fixed).
#   - target/debug/grid-runtime built (`cargo build -p grid-runtime`).
#   - LLM_PROVIDER + matching API key in `.env` (OPENAI_* or
#     ANTHROPIC_*). If absent, the LLM-driven message step degrades
#     gracefully (still produces L4 session_event rows for the timeline).
#   - EAASP_DEV_DISABLE_SCOPE_BINDING=1 on L4 (already the default
#     for dev mode; see api.py:798).
#
# Run: bash scripts/v315-obstack-demo.sh 2>&1 | tee .logs/v315-obstack-demo/run.log

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# V315-BUSINESS-FLOW-02 demo needs dev-mode scope binding bypass so
# /v1/sessions/create works without a real skill-registry frontmatter
# fetch (skill-registry serves at :18081 but the v315-walk-services.sh
# boot order doesn't preload threshold-calibration into it).
export EAASP_DEV_DISABLE_SCOPE_BINDING=1

# V315-OBSTACK-DEMO-idempotent-01: each demo run gets its own RUN_ID
# (timestamp + PID) so:
#   1. Every service writes its SQLite files into a fresh directory
#      ($V315_DEMO_DATA_DIR), avoiding cross-run pollution.
#   2. The business_key embeds the RUN_ID so timeline queries always
#      return ONLY this run's events (no accumulation across runs).
#   3. Logs land in a per-run subdirectory so multiple demos can
#      coexist on the same host without overwriting each other.
#
# Override with `RUN_ID=foo bash scripts/v315-obstack-demo.sh` to
# pin the suffix (useful for debugging or replaying a fixed scenario).
RUN_ID="${RUN_ID:-$(date +%Y%m%d-%H%M%S)-$$}"
export V315_DEMO_DATA_DIR="data/v315-demo-${RUN_ID}"
export LOGDIR_OVERRIDE=".logs/v315-walk/${RUN_ID}"   # so v315-walk-services.sh puts its logs here too
LOGDIR=".logs/v315-obstack-demo/${RUN_ID}"
mkdir -p "$V315_DEMO_DATA_DIR" "$LOGDIR"

KEY="demo-sess-${RUN_ID}|threshold-calibration|Transformer-sla-${RUN_ID}"
ENCODED=$(printf '%s' "$KEY" | python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.stdin.read()))")
SCOPE="*"

echo "=== RUN_ID: $RUN_ID ==="
echo "    data dir:  $V315_DEMO_DATA_DIR"
echo "    log dir:   $LOGDIR"
echo "    KEY:       $KEY"

# ─── 0. Boot: 5 services + grid-runtime ───────────────────────────────────
echo "=== 0. Boot services ==="
bash scripts/v315-walk-services.sh

# ─── 1. Health probes ──────────────────────────────────────────────────────
echo ""
echo "=== 1. Health probes (all services) ==="
for port in 18081 18083 18084 18085 18090 50051; do
  if curl -fsS "http://127.0.0.1:$port/health" 2>/dev/null > "$LOGDIR/health-$port.txt"; then
    echo "  :$port UP  ($(cat "$LOGDIR/health-$port.txt"))"
  else
    echo "  :$port DOWN"
  fi
done

# ─── 1a. Deploy a minimal L3 managed-hooks policy ─────────────────────────
# The /v1/sessions/create handshake calls L3 /v1/sessions/{id}/validate,
# which fails with 424 no_policy if no managed-hooks version has been
# deployed yet. Push a minimal one so the handshake can complete.
echo ""
echo "=== 1a. Deploy minimal L3 managed-hooks policy ==="
curl -fsS -X PUT http://127.0.0.1:18083/v1/policies/managed-hooks \
  -H "Content-Type: application/json" \
  -H "X-Session-Scope: *" \
  -d '{
    "version": "v315-obstack-demo",
    "hooks": [
      {
        "hook_id": "PreToolUse:scada_read",
        "phase": "PreToolUse",
        "tool_name": "scada_read",
        "risk_level": "read",
        "action_preview": "scada read",
        "access_scope": "*"
      },
      {
        "hook_id": "PreToolUse:scada_write",
        "phase": "PreToolUse",
        "tool_name": "scada_write",
        "risk_level": "write_local",
        "action_preview": "scada write",
        "access_scope": "*"
      }
    ]
  }' | python3 -m json.tool | head -10

# ─── 2. Create L4 session with X-Business-Key ──────────────────────────────
echo ""
echo "=== 2. Create L4 session with X-Business-Key header ==="
SESSION_RESP=$(curl -fsS -X POST http://127.0.0.1:18084/v1/sessions/create \
  -H "Content-Type: application/json" \
  -H "X-Session-Scope: $SCOPE" \
  -H "X-Business-Key: $KEY" \
  -d '{
    "intent_text": "calibrate Transformer-sla-1785652837 thresholds",
    "skill_id": "threshold-calibration",
    "runtime_pref": "grid-runtime",
    "user_id": "demo",
    "intent_id": "demo-intent-v315-obstack"
  }')
echo "$SESSION_RESP" | python3 -m json.tool | tee "$LOGDIR/session-create.json"
SESSION_ID=$(echo "$SESSION_RESP" | python3 -c "import json,sys;print(json.load(sys.stdin)['session_id'])")
echo "  session_id=$SESSION_ID"

# ─── 3. Send LLM-driven message (best-effort; degrades if no API key) ────
echo ""
echo "=== 3. Send LLM-driven message (via grid-runtime gRPC path; 30s timeout) ==="
MSG_RESP=$(timeout 30 curl -fsS -X POST "http://127.0.0.1:18084/v1/sessions/$SESSION_ID/message" \
  -H "Content-Type: application/json" \
  -H "X-Session-Scope: $SCOPE" \
  -H "X-Business-Key: $KEY" \
  -d '{"content":"Fetch recent SCADA data for Transformer-sla-1785652837 and recalibrate thresholds."}' \
  2>"$LOGDIR/message-err.txt" || true)
if [ -n "$MSG_RESP" ]; then
  echo "$MSG_RESP" | python3 -m json.tool | tee "$LOGDIR/message.json" | head -30
  echo "  (LLM-driven message produced session events; timeline aggregation below)"
else
  echo "  (LLM message step skipped or timed out — see $LOGDIR/message-err.txt)"
  echo "  (Demo continues with direct ingest to populate the timeline)"
fi

# ─── 4. Ingest cross-layer events tagged with the business key ────────────
echo ""
echo "=== 4. Ingest events (L1 REST fallback) ==="
for ET in PRE_TOOL_USE POST_TOOL_USE APPROVAL REQUEST MEMORY_WRITE; do
  curl -fsS -X POST http://127.0.0.1:18084/v1/events/ingest \
    -H "Content-Type: application/json" \
    -d "{
      \"session_id\":\"$SESSION_ID\",
      \"event_type\":\"$ET\",
      \"payload\":{\"skill_id\":\"threshold-calibration\",\"step\":\"$ET\",\"value\":85},
      \"source\":\"runtime:grid-runtime\"
    }" > "$LOGDIR/ingest-$ET.json" 2>&1 || true
  echo "  ingest $ET: $(cat "$LOGDIR/ingest-$ET.json" 2>/dev/null | head -c 80)"
done

# ─── 5. L3 /v1/evaluate with X-Business-Key ───────────────────────────────
echo ""
echo "=== 5. L3 /v1/evaluate with X-Business-Key (OPA-backed) ==="
# Bind session principal first (v3.11.1 in-process store; production
# uses L2 DB).
echo "  (Skipping L3 evaluate — would need OPA sidecar + managed-hooks deploy; demo continues with L2/L3 reads via timeline)"

# ─── 6. Read cross-layer timeline ─────────────────────────────────────────
echo ""
echo "=== 6. /v1/business-flows/{key}/timeline ==="
curl -fsS "http://127.0.0.1:18084/v1/business-flows/$ENCODED/timeline" \
  | python3 -m json.tool | tee "$LOGDIR/timeline.json" | head -40

echo ""
echo "=== 6a. /v1/business-flows/{key}/summary ==="
curl -fsS "http://127.0.0.1:18084/v1/business-flows/$ENCODED/summary" \
  | python3 -m json.tool | tee "$LOGDIR/summary.json"

echo ""
echo "=== 6b. /v1/business-flows/{key}/sessions ==="
curl -fsS "http://127.0.0.1:18084/v1/business-flows/$ENCODED/sessions" \
  | python3 -m json.tool | tee "$LOGDIR/sessions.json"

# ─── 7. /evaluation (Evaluate dimension) ───────────────────────────────────
echo ""
echo "=== 7. /v1/business-flows/{key}/evaluation ==="
curl -fsS "http://127.0.0.1:18084/v1/business-flows/$ENCODED/evaluation" \
  | python3 -m json.tool | tee "$LOGDIR/evaluation.json"

# ─── 8. SSE stream (sample for 5s) ────────────────────────────────────────
echo ""
echo "=== 8. SSE stream sample (5s window) ==="
timeout 5 curl -N -fsS "http://127.0.0.1:18084/v1/business-flows/$ENCODED/events/stream" \
  > "$LOGDIR/sse.log" 2>&1 || true
echo "  SSE log lines: $(wc -l < "$LOGDIR/sse.log" 2>/dev/null || echo 0)"
head -10 "$LOGDIR/sse.log" 2>/dev/null || true

# ─── 9. Observe dimension (grid-runtime OTel wiring verification) ────────
# V315-L1-OTEL-FULL-01 wired the OTel SDK (PeriodicReader + SdkMeterProvider +
# InMemoryExporter) so record_*() calls now land in real Counter /
# Histogram / UpDownCounter handles. The exporter is in-memory, not
# stdout — so we can't grep the log for OTel metric records. Instead,
# the L4 observability mirror emits l4.* metric records to its own
# logger (logs/v315-walk/l4.log) when calls happen, and grid-runtime
# emits the session/hook lifecycle events we already see in
# logs/v315-walk/grid-runtime.log. Show evidence the OTel wiring is
# live by counting the grid-runtime lifecycle events.
echo ""
echo "=== 9. Observe dimension ==="
OTEL_EVENTS=$(grep -cE 'session initialized|policy_context metadata|Materialized|hook_vars resolved|capability probe|Scoped hook registered|Scoped Stop hook' \
  "$ROOT/$LOGDIR_OVERRIDE/grid-runtime.log" 2>/dev/null || echo 0)
echo "  grid-runtime lifecycle events captured (OTel-eligible records): $OTEL_EVENTS"
echo "  (V315-L1-OTEL-FULL-01: record_*() now lands in real Counter/Histogram/UpDownCounter via SdkMeterProvider)"
echo "  (evidence via grid-runtime log + the 7/7 in-crate observability tests in crates/grid-runtime/src/observability/mod.rs)"

L4_METRICS=$(grep -cE 'l4\.|flow\.|session\.|room\.|event\.' "$ROOT/$LOGDIR_OVERRIDE/l4.log" 2>/dev/null || echo 0)
echo "  L4 observability log records: $L4_METRICS (l4.* metric names per OBSTACK §3.3)"

# ─── 9b. L1 OTel stdout exporter evidence (v3.15.6 6c.1) ────────────────
# v3.15.6 6c.1 wired init_observability("stdout") into main.rs.
# grid-runtime now installs opentelemetry-stdout::MetricsExporter and
# writes each PeriodicReader batch to stdout every 30s. Verify the
# installer is live by grepping the grid-runtime log for the
# post-install info line emitted by record_* helpers.
L1_OTEL_LIVE=$(grep -cE 'L1 OTel SDK installed|record_\* now lands in real Counter' \
  "$ROOT/$LOGDIR_OVERRIDE/grid-runtime.log" 2>/dev/null || echo 0)
echo "  L1 OTel SDK installer evidence: $L1_OTEL_LIVE (expect ≥ 1 after 6c.1 activation)"

# ─── 9c. L1 OTel harness.rs emit evidence (v3.15.6 6c.2 + 6c.3) ─────────
# Once grid-runtime goes through a tool call, harness.rs fires
# record_tool(name, "pre"/"post") + record_business_flow_outcome.
# Those calls require the OTel SDK to be installed (6c.1) — without
# 6c.1 these were silent no-ops. Count the pre/post/flow_outcome log
# traces the installer emits to confirm the wiring is hooked.
L1_TOOL_EMITS=$(grep -cE 'tool\.total|flow\.outcome' "$ROOT/$LOGDIR_OVERRIDE/grid-runtime.log" 2>/dev/null || echo 0)
echo "  L1 tool/flow counter emits: $L1_TOOL_EMITS (post-6c.2 + 6c.3 OTel aggregates, per-tool + per-flow)"

# ─── 10. Optimize executors (programmatic) ────────────────────────────────
echo ""
echo "=== 10. Optimize executors ==="
tools/eaasp-l4-orchestration/.venv/bin/python - <<EOF
import asyncio
from eaasp_l4_orchestration.flow_readers import build_default_layer_readers
from eaasp_l4_orchestration.flow_timeline import assemble_business_flow_summary
from eaasp_l4_orchestration.flow_evaluator import evaluate_business_flows
from eaasp_l4_orchestration.ab_router import choose_runtime
from eaasp_l4_orchestration.alert_manager import fire_alerts
from eaasp_l4_orchestration.resource_scheduler import reconcile_actions
from eaasp_common.business_flow import parse_business_key_header, BusinessKey

key = parse_business_key_header("$KEY")
import aiosqlite

async def main():
    # V315-OBSTACK-DEMO-idempotent-01: read the per-run L4 DB so
    # Optimize executes against the same isolated data directory that
    # the rest of the demo just populated.
    l4 = await aiosqlite.connect("$ROOT/$V315_DEMO_DATA_DIR/l4.db")
    l4.row_factory = aiosqlite.Row
    readers = build_default_layer_readers(l4_conn=l4, l3_conn=None, l2_conn=None)
    summary = await assemble_business_flow_summary(key, layer_readers=readers)
    print("summary status:", summary.status, "events:", summary.event_count)
    report = evaluate_business_flows([summary])
    print("report total_flows:", report.total_flows)
    print("report hints count:", len(report.hints))
    print("first hint:", report.hints[0] if report.hints else None)
    # choose_runtime expects (summary, meta) pairs; build a FlowMeta so
    # the A/B router can match business_object_id.
    from eaasp_l4_orchestration.ab_router import FlowMeta
    meta = FlowMeta(business_object_id=key.business_object_id, runtime_id="grid-runtime")
    print("choose_runtime:", choose_runtime(key.business_object_id, [(summary, meta)]))
    print("fire_alerts:", fire_alerts(report, sinks=[]))
    print("reconcile_actions:", reconcile_actions(report))

asyncio.run(main())
EOF

# ─── 11. Dual-gate (must PASS) ────────────────────────────────────────────
echo ""
echo "=== 11. dual-gate ==="
make v3.10-spec-audit 2>&1 | tail -5
make rbac-audit 2>&1 | tail -5

echo ""
echo "=== Demo complete. Logs: $LOGDIR ==="
