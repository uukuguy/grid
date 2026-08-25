#!/usr/bin/env bash
# Focused closeout verification for the v3.16 OBSTACK product surface.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UV_CACHE_DIR="${UV_CACHE_DIR:-/private/tmp/grid-v316-uv-cache}"
export UV_CACHE_DIR

DRY_RUN=false
SELF_TEST="${V316_VERIFY_SELF_TEST:-}"
L4_PID=""
SSE_PID=""
PROBE_DIR=""
GATE_NAMES=(
  web cli_flow cli_session l4_business_key l4_event_engine
  l4_flow_api_controls boundary_unit boundary_audit rbac_audit spec_audit live_probe
)
FLOW_API_CONTROL_NODES=(
  tests/test_flow_api.py::test_timeline_malformed_key_returns_400
  tests/test_flow_api.py::test_timeline_empty_session_id_returns_400
  tests/test_flow_api.py::test_sse_stream_returns_streaming_response
  tests/test_flow_api.py::test_sse_stream_malformed_key_returns_400
)

usage() {
  printf 'usage: %s [--dry-run]\n' "${0##*/}" >&2
}

die() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  local status=$?
  trap - EXIT INT TERM
  if [[ -n "$SSE_PID" ]] && kill -0 "$SSE_PID" 2>/dev/null; then
    kill "$SSE_PID" 2>/dev/null || true
  fi
  if [[ -n "$L4_PID" ]] && kill -0 "$L4_PID" 2>/dev/null; then
    kill "$L4_PID" 2>/dev/null || true
  fi
  if [[ -n "$SSE_PID" ]]; then
    wait "$SSE_PID" 2>/dev/null || true
  fi
  if [[ -n "$L4_PID" ]]; then
    wait "$L4_PID" 2>/dev/null || true
  fi
  if [[ -n "$PROBE_DIR" ]]; then
    case "$PROBE_DIR" in
      /private/tmp/grid-v316-obstack-l4.*) rm -rf -- "$PROBE_DIR" ;;
      *) printf 'Refusing to clean unvalidated probe directory: %s\n' "$PROBE_DIR" >&2 ;;
    esac
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

run_gate() {
  local name=$1
  local manifest_command=$2
  shift 2

  printf 'gate: %s\n' "$name"
  if [[ "$SELF_TEST" == "fail:$name" ]]; then
    printf 'forced failure: %s\n' "$name" >&2
    return 1
  fi
  if "$DRY_RUN"; then
    printf 'command: %s\n' "$manifest_command"
    return 0
  fi
  "$@"
}

run_web() {
  (
    cd "$ROOT/web"
    npx vitest run src/test/v316-obstack-contract.test.ts src/test/v316-obstack-surface.test.tsx
    npm run build
  )
}

run_cli_flow() {
  (
    cd "$ROOT/tools/eaasp-cli-v2"
    PYTHONPATH="$ROOT/tools/eaasp-common/src${PYTHONPATH:+:$PYTHONPATH}" \
      uv run --extra dev pytest -q tests/test_v316_flow_commands.py
  )
}

run_cli_session() {
  (
    cd "$ROOT/tools/eaasp-cli-v2"
    PYTHONPATH="$ROOT/tools/eaasp-common/src${PYTHONPATH:+:$PYTHONPATH}" \
      uv run --extra dev pytest -q tests/test_v316_session_business_key.py
  )
}

run_l4_business_key() {
  (
    cd "$ROOT/tools/eaasp-l4-orchestration"
    uv run --extra dev pytest -q tests/test_v316_business_key_surface.py
  )
}

run_l4_event_engine() {
  (
    cd "$ROOT/tools/eaasp-l4-orchestration"
    uv run --extra dev pytest -q tests/test_event_engine.py tests/test_v316_live_flow_publish.py
  )
}

run_l4_flow_api_controls() {
  (
    cd "$ROOT/tools/eaasp-l4-orchestration"
    uv run --extra dev pytest -q "${FLOW_API_CONTROL_NODES[@]}"
  )
}

flow_api_manifest_command() {
  local node
  printf 'cd tools/eaasp-l4-orchestration && uv run --extra dev pytest -q'
  for node in "${FLOW_API_CONTROL_NODES[@]}"; do
    printf ' %s' "$node"
  done
}

run_boundary_unit() {
  (
    cd "$ROOT"
    python3 -m unittest scripts.tests.test_check_v316_obstack_boundaries
  )
}

run_boundary_audit() {
  (
    cd "$ROOT"
    python3 scripts/check-v316-obstack-boundaries.py
  )
}

free_localhost_port() {
  python3 - <<'PY'
import socket

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
}

match_sse_probe_frame() {
  local sse_output=$1
  local nonce=$2
  python3 - "$sse_output" "$nonce" <<'PY'
import json
import sys
from pathlib import Path

output_path, expected_nonce = sys.argv[1:]
for line in Path(output_path).read_text(encoding="utf-8", errors="replace").splitlines():
    if not line.startswith("data:"):
        continue
    try:
        event = json.loads(line.removeprefix("data:").strip())
    except json.JSONDecodeError:
        continue
    payload = event.get("payload")
    if (
        event.get("event_type") == "v316.live.probe"
        and event.get("component") == "v316_verify"
        and isinstance(payload, dict)
        and payload.get("origin") == "v316_verifier"
        and payload.get("nonce") == expected_nonce
    ):
        print(json.dumps(event, sort_keys=True, separators=(",", ":")))
        raise SystemExit(0)
raise SystemExit(1)
PY
}

run_live_probe() {
  local port base db_path log_path malformed_body malformed_status
  local session_id business_key sse_output sse_headers ingest_body attempt
  local launch_attempt ready nonce matched_frame

  PROBE_DIR="$(mktemp -d /private/tmp/grid-v316-obstack-l4.XXXXXX)"
  case "$PROBE_DIR" in
    /private/tmp/grid-v316-obstack-l4.*) ;;
    *) die "mktemp returned an unvalidated probe directory" ;;
  esac
  [[ -d "$PROBE_DIR" ]] || die "mktemp did not create probe directory"

  ready=false
  for launch_attempt in $(seq 1 3); do
    db_path="$PROBE_DIR/l4-$launch_attempt.db"
    [[ ! -e "$db_path" ]] || die "probe database path unexpectedly exists"
    log_path="$PROBE_DIR/l4-$launch_attempt.log"
    port="$(free_localhost_port)"
    [[ "$port" =~ ^[0-9]+$ ]] || die "failed to allocate a localhost port"
    base="http://127.0.0.1:$port"

    (
      cd "$ROOT/tools/eaasp-l4-orchestration"
      exec env EAASP_L4_DB_PATH="$db_path" EAASP_L4_HOST=127.0.0.1 EAASP_L4_PORT="$port" \
        PYTHONPATH="$ROOT/tools/eaasp-common/src${PYTHONPATH:+:$PYTHONPATH}" \
        uv run --extra dev python -m eaasp_l4_orchestration.main
    ) >"$log_path" 2>&1 &
    L4_PID=$!

    for attempt in $(seq 1 80); do
      if curl --silent --show-error --connect-timeout 1 --max-time 1 \
        --fail "$base/health" >/dev/null 2>&1; then
        ready=true
        break
      fi
      if ! kill -0 "$L4_PID" 2>/dev/null; then
        break
      fi
      sleep 0.1
    done
    if "$ready"; then
      break
    fi
    if kill -0 "$L4_PID" 2>/dev/null; then
      kill "$L4_PID" 2>/dev/null || true
    fi
    wait "$L4_PID" 2>/dev/null || true
    L4_PID=""
  done
  "$ready" || die "owned L4 did not become healthy after bounded launch retries (last log: $log_path)"

  session_id="v316-live-session"
  business_key="v316-live-session|v316-live-skill|v316-live-object"
  python3 - "$db_path" "$session_id" "$business_key" <<'PY'
import sqlite3
import sys
import time

db_path, session_id, business_key = sys.argv[1:]
connection = sqlite3.connect(db_path)
try:
    connection.execute(
        """
        INSERT INTO sessions (
            session_id, intent_id, skill_id, runtime_id, user_id,
            status, payload_json, created_at, business_key
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            "v316-live-intent",
            "v316-live-skill",
            "grid-runtime",
            "v316-verifier",
            "active",
            "{}",
            int(time.time()),
            business_key,
        ),
    )
    connection.commit()
finally:
    connection.close()
PY

  malformed_body="$PROBE_DIR/malformed.json"
  malformed_status="$(curl --silent --show-error --connect-timeout 2 --max-time 3 \
    --output "$malformed_body" --write-out '%{http_code}' \
    "$base/v1/business-flows/not-a-canonical-key/timeline")"
  [[ "$malformed_status" == "400" ]] || die "malformed business-key timeline returned HTTP $malformed_status, expected 400"

  sse_output="$PROBE_DIR/sse.out"
  sse_headers="$PROBE_DIR/sse.headers"
  curl --no-buffer --silent --show-error --connect-timeout 2 --max-time 10 \
    --dump-header "$sse_headers" --output "$sse_output" \
    "$base/v1/business-flows/$business_key/events/stream" &
  SSE_PID=$!
  for attempt in $(seq 1 40); do
    if grep -Eq '^HTTP/[0-9.]+ 200' "$sse_headers" 2>/dev/null; then
      break
    fi
    if ! kill -0 "$SSE_PID" 2>/dev/null; then
      die "owned curl SSE subscription exited before receiving HTTP 200"
    fi
    sleep 0.1
  done
  grep -Eq '^HTTP/[0-9.]+ 200' "$sse_headers" \
    || die "owned curl SSE subscription did not establish HTTP 200"

  ingest_body="$PROBE_DIR/ingest.json"
  nonce="$(python3 - <<'PY'
import uuid
print(uuid.uuid4().hex)
PY
)"
  for attempt in $(seq 1 20); do
    curl --silent --show-error --fail-with-body --connect-timeout 2 --max-time 3 \
      --header 'Content-Type: application/json' \
      --data "{\"session_id\":\"$session_id\",\"event_type\":\"v316.live.probe\",\"payload\":{\"origin\":\"v316_verifier\",\"nonce\":\"$nonce\"},\"source\":\"v316_verify\"}" \
      --output "$ingest_body" \
      "$base/v1/events/ingest" >/dev/null
    for _ in $(seq 1 4); do
      if matched_frame="$(match_sse_probe_frame "$sse_output" "$nonce")"; then
        printf 'live probe: malformed timeline=400; matched nonce=%s frame=%s\n' \
          "$nonce" "$matched_frame"
        return 0
      fi
      sleep 0.1
    done
    if ! kill -0 "$SSE_PID" 2>/dev/null; then
      break
    fi
  done
  die "owned curl SSE subscription did not capture the matching nonce after repeated /v1/events/ingest (log: $log_path)"
}

if [[ $# -gt 1 ]]; then
  usage
  exit 2
fi
if [[ $# -eq 1 ]]; then
  if [[ "$1" != "--dry-run" ]]; then
    usage
    exit 2
  fi
  DRY_RUN=true
fi
if [[ -n "$SELF_TEST" ]]; then
  [[ "$SELF_TEST" == fail:* ]] || die 'V316_VERIFY_SELF_TEST only accepts fail:<named_gate>'
  self_test_gate="${SELF_TEST#fail:}"
  for gate in "${GATE_NAMES[@]}"; do
    [[ "$self_test_gate" == "$gate" ]] && break
  done
  [[ "$self_test_gate" == "$gate" ]] || die "V316_VERIFY_SELF_TEST unknown gate: $self_test_gate"
fi

run_gate web 'cd web && npx vitest run src/test/v316-obstack-contract.test.ts src/test/v316-obstack-surface.test.tsx && npm run build' run_web
run_gate cli_flow 'cd tools/eaasp-cli-v2 && PYTHONPATH=../eaasp-common/src uv run --extra dev pytest -q tests/test_v316_flow_commands.py' run_cli_flow
run_gate cli_session 'cd tools/eaasp-cli-v2 && PYTHONPATH=../eaasp-common/src uv run --extra dev pytest -q tests/test_v316_session_business_key.py' run_cli_session
run_gate l4_business_key 'cd tools/eaasp-l4-orchestration && uv run --extra dev pytest -q tests/test_v316_business_key_surface.py' run_l4_business_key
run_gate l4_event_engine 'cd tools/eaasp-l4-orchestration && uv run --extra dev pytest -q tests/test_event_engine.py tests/test_v316_live_flow_publish.py' run_l4_event_engine
run_gate l4_flow_api_controls "$(flow_api_manifest_command)" run_l4_flow_api_controls
run_gate boundary_unit 'python3 -m unittest scripts.tests.test_check_v316_obstack_boundaries' run_boundary_unit
run_gate boundary_audit 'python3 scripts/check-v316-obstack-boundaries.py' run_boundary_audit
run_gate rbac_audit 'make rbac-audit' make -C "$ROOT" rbac-audit
run_gate spec_audit 'make v3.10-spec-audit' make -C "$ROOT" v3.10-spec-audit
run_gate live_probe 'own L4 + real curl SSE + POST /v1/events/ingest' run_live_probe

printf 'PASS: v3.16 OBSTACK surface verification\n'
