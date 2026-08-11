#!/bin/bash
# v315-obstack-demo.sh — End-to-end OBSTACK instance demo.
#
# Exercises all 5 OBSTACK dimensions (Observe / Trace / Evaluate /
# Optimize / Verify) against real running services.
#
# v3.15.6 6h — this script used to be able to "pass" without proving
# anything: the LLM step had a 30s timeout (shorter than one
# reasoning-model turn), its failure was non-fatal, five synthetic
# events were hand-POSTed to /v1/events/ingest to populate the
# timeline, and the Observe check grepped for log phrases that no
# longer existed and never failed. A run could therefore exit 0 with a
# dead metrics pipeline and a fabricated timeline. Fixed:
#   - the skill is seeded into the per-run registry (step 1b)
#   - the LLM step is load-bearing and fatal on failure (step 3)
#   - the synthetic ingest is gone (step 4)
#   - Observe parses the OTel JSON batches and fails on missing series
#     (step 9)
#
# Pre-conditions:
#   - target/debug/grid-runtime built (`cargo build -p grid-runtime`).
#   - LLM_PROVIDER + matching API key in `.env`. NOTE: an API key
#     exported in your shell SHADOWS `.env` (dotenvy does not override
#     existing env vars) — a stale exported key surfaces as a 401 from
#     the provider. `unset` it before running if unsure.
#   - EAASP_DEV_DISABLE_SCOPE_BINDING=1 on L4 (default for dev mode).
#
# Env knobs:
#   LLM_TIMEOUT               seconds for the agent turn (default 300)
#   EAASP_OTEL_INTERVAL_SECS  OTel export interval; lower it (e.g. 5)
#                             so metrics land before the run ends
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

# ─── 1b. Seed the skill into the per-run skill-registry ────────────────────
# v3.15.6 6h: each run gets a fresh $V315_DEMO_DATA_DIR/skill-registry, so
# the registry starts empty and L4's /v1/sessions/create handshake fails
# with `skill-registry:not_found`. Previously that failure was invisible:
# session-create still returned 200 (degraded), the LLM step was skipped,
# and the demo carried on with hand-ingested events — which is precisely
# why the timeline looked populated while nothing real had run.
echo ""
echo "=== 1b. Seed threshold-calibration into skill-registry ==="
python3 - > "$LOGDIR/draft.json" <<'PYEOF'
import json, pathlib
raw = pathlib.Path("examples/skills/threshold-calibration/SKILL.md").read_text()
parts = raw.split("---", 2)
fm, prose = (parts[1], parts[2]) if len(parts) >= 3 else ("", raw)
print(json.dumps({
    "id": "threshold-calibration",
    "name": "threshold-calibration",
    "description": "Transformer threshold calibration (demo skill)",
    "version": "0.1.0",
    "author": "eaasp-mvp",
    "source_dir": str(pathlib.Path("examples/skills/threshold-calibration").resolve()),
    "tags": ["demo"],
    "frontmatter_yaml": fm.strip(),
    "prose": prose.strip(),
}))
PYEOF
curl -fsS -X POST http://127.0.0.1:18081/skills/draft \
  -H "Content-Type: application/json" \
  -d @"$LOGDIR/draft.json" > "$LOGDIR/skill-seed.json" \
  && echo "  seeded: $(python3 -c "import json;d=json.load(open('$LOGDIR/skill-seed.json'));print(d['id'], d['version'], d['status'])")" \
  || { echo "  FATAL: skill seeding failed — the LLM step cannot run"; exit 1; }

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

# ─── 3. Send LLM-driven message (REAL agent loop — must succeed) ─────────
# v3.15.6 6h: this step is now load-bearing, not best-effort.
#
# Two changes from the v3.15.5 version:
#   1. Timeout 30s → $LLM_TIMEOUT (default 300s). 30s was shorter than a
#      single reasoning-model turn, so this step silently timed out on
#      every run and the demo fell through to hand-ingested events.
#   2. Failure is fatal. Previously a failed turn printed a note and the
#      demo continued, producing a "successful" run whose timeline was
#      entirely synthetic.
LLM_TIMEOUT="${LLM_TIMEOUT:-300}"
echo ""
echo "=== 3. Send LLM-driven message (real agent loop; ${LLM_TIMEOUT}s budget) ==="
# The prompt asks for a tool call so the run exercises the PreToolUse /
# PostToolUse path, not just text generation.
MSG_RESP=$(timeout "$LLM_TIMEOUT" curl -fsS -X POST "http://127.0.0.1:18084/v1/sessions/$SESSION_ID/message" \
  -H "Content-Type: application/json" \
  -H "X-Session-Scope: $SCOPE" \
  -H "X-Business-Key: $KEY" \
  -d '{"content":"Call the task_list tool now to list current tasks, then summarise the result in one sentence. Do not ask for confirmation."}' \
  2>"$LOGDIR/message-err.txt" || true)

if [ -z "$MSG_RESP" ]; then
  echo "  FATAL: LLM-driven message produced no response."
  echo "  This step is load-bearing — without it the timeline below would"
  echo "  contain no real agent-loop events and the run would prove nothing."
  echo "  See $LOGDIR/message-err.txt and .logs/v315-walk/grid-runtime.log"
  echo "  Common cause: a stale API key exported in the shell shadows .env"
  echo "  (dotenvy does not override existing env vars)."
  exit 1
fi
echo "$MSG_RESP" > "$LOGDIR/message.json"
# Summarise rather than `head` the JSON: a real turn streams hundreds of
# chunks, and piping that into `head` closes the pipe early — under
# `set -o pipefail` that surfaces as SIGPIPE (exit 141) and kills the run.
python3 - "$LOGDIR/message.json" <<'PYEOF'
import json, sys, collections
d = json.load(open(sys.argv[1]))
chunks = d.get("chunks", d if isinstance(d, list) else [])
kinds = collections.Counter(c.get("chunk_type", "?") for c in chunks)
print(f"  chunks: {len(chunks)}  ({', '.join(f'{k}={v}' for k, v in sorted(kinds.items()))})")
tools = [c.get("tool_name") for c in chunks if c.get("tool_name")]
print(f"  tool calls observed in stream: {sorted(set(tools)) or 'none'}")
PYEOF
echo "  (real agent loop drove L1 → L4; timeline below is its output)"

# ─── 4. (removed in v3.15.6 6h — was: hand-ingest 5 synthetic events) ────
# The v3.15.5 demo POSTed five fabricated events to /v1/events/ingest
# (PRE_TOOL_USE, POST_TOOL_USE, APPROVAL, REQUEST, MEMORY_WRITE) so the
# timeline below would look populated. That is what V315-WALK-01
# tracked: the 14-event timeline was mostly theatre, and it stayed
# convincing even when step 3 had silently timed out.
#
# Step 3 is now load-bearing and fatal on failure, so every event in
# the timeline is produced by the real agent loop. Nothing to fabricate.
echo ""
echo "=== 4. (no synthetic ingest — timeline is real agent-loop output) ==="

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
  > "$LOGDIR/timeline.json"
# Summarise instead of `head`-ing: with step 3 now driving a real turn
# the timeline is long, and `head` closing the pipe trips SIGPIPE under
# `set -o pipefail`. Also assert the timeline is non-empty — an empty
# timeline after a successful turn means the L1 → L4 event path broke.
python3 - "$LOGDIR/timeline.json" <<'PYEOF'
import json, sys, collections
d = json.load(open(sys.argv[1]))
events = d.get("events", d if isinstance(d, list) else [])
print(f"  timeline events: {len(events)}")
by_layer = collections.Counter(e.get("layer", "?") for e in events)
by_type = collections.Counter(e.get("event_type", "?") for e in events)
print(f"  by layer: {dict(sorted(by_layer.items()))}")
for t, n in sorted(by_type.items()):
    print(f"    {t}: {n}")
if not events:
    print("  FAIL: timeline empty after a successful agent turn —")
    print("  the L1 → L4 event path is broken.")
    sys.exit(1)
PYEOF

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

# ─── 9. Observe dimension — assert the L1 OTel series actually moved ─────
# v3.15.6 6h: this check used to grep grid-runtime.log for phrases like
# "tool.total" and "L1 OTel SDK installed". That was worthless twice
# over: the phrases stopped appearing once 6c.1 switched to the stdout
# exporter, and the check printed its count without ever failing. It
# reported 0 on a run where the metrics pipeline was completely dead
# and the demo still exited 0.
#
# Now we parse the stdout exporter's JSON batches and assert that the
# expected series are present with non-zero values. If the pipeline is
# dead, or the emits regress to an unreachable code path, this fails
# the run.
echo ""
echo "=== 9. Observe dimension (L1 OTel series assertions) ==="
python3 - "$ROOT/$LOGDIR_OVERRIDE/grid-runtime.log" <<'PYEOF'
import json, sys, pathlib

log = pathlib.Path(sys.argv[1])
if not log.exists():
    print(f"  FAIL: {log} missing"); sys.exit(1)

batches = [json.loads(l) for l in log.read_text(encoding="utf-8", errors="replace").splitlines()
           if l.startswith('{"resourceMetrics"')]
print(f"  OTel batches exported: {len(batches)}")
if not batches:
    print("  FAIL: no metric batches — the exporter never ran"); sys.exit(1)

# Take the last-seen value per series. Counters here are cumulative, so
# the newest batch already holds the running total; gauges must use the
# newest value too (folding with max would report a gauge's peak and
# make a settled in_flight look like a leak).
seen = {}
for b in batches:
    for sm in b["resourceMetrics"].get("scopeMetrics", []):
        for m in sm.get("metrics", []):
            data = m.get("sum") or m.get("gauge") or m.get("histogram") or {}
            for dp in data.get("dataPoints", []):
                attrs = {a["key"]: list(a["value"].values())[0] for a in dp.get("attributes", [])}
                val = dp.get("value", dp.get("asInt", dp.get("count", 0)))
                seen[(m["name"], json.dumps(attrs, sort_keys=True))] = val or 0

for (name, attrs), val in sorted(seen.items()):
    print(f"    {name} {attrs} = {val}")

# A real agent-loop turn must move these. `errors.total` is deliberately
# NOT required — a clean run has no errors, and demanding one would push
# the demo toward manufacturing failures.
required = [
    "l1.runtime.requests.total",   # RPC dispatch (6h layer)
    "l1.runtime.llm.total",        # model round-trip
    "l1.runtime.tool.total",       # PreToolUse / PostToolUse
    "l1.runtime.flow.outcome",     # terminal outcome
]
present = {name for (name, _) in seen}
missing = [r for r in required if r not in present]
if missing:
    print("  FAIL: expected series absent after a real turn:")
    for m in missing:
        print(f"    - {m}")
    print("  This is the V315-WALK-01 / V315-L1-OTEL-FULL-01 failure mode:")
    print("  the run completed but the metrics it claims to prove never moved.")
    sys.exit(1)

# in_flight must return to 0 — a leak means a turn was never closed out.
for (name, attrs), val in seen.items():
    if name == "l1.runtime.in_flight" and val not in (0, None):
        print(f"  WARN: in_flight did not settle to 0 ({attrs} = {val})")

print(f"  PASS: {len(required)}/{len(required)} required L1 series emitted by the real agent loop")
PYEOF
OBSERVE_RC=$?
if [ "$OBSERVE_RC" -ne 0 ]; then
  echo "  === Observe dimension FAILED — see above ==="
  exit 1
fi

L4_METRICS=$(grep -cE 'l4\.|flow\.|session\.|room\.|event\.' "$ROOT/$LOGDIR_OVERRIDE/l4.log" 2>/dev/null || true)
echo "  L4 observability log records: ${L4_METRICS:-0} (l4.* metric names per OBSTACK §3.3)"

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
