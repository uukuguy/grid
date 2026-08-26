#!/usr/bin/env bash
# Shell-level regression checks for the v3.16 aggregate verifier.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERIFY="$ROOT/scripts/v316-obstack-surface-verify.sh"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

manifest="$(mktemp "${TMPDIR:-/tmp}/v316-obstack-manifest.XXXXXX")"
failure_output="$(mktemp "${TMPDIR:-/tmp}/v316-obstack-failure.XXXXXX")"
trap 'rm -f "$manifest" "$failure_output"' EXIT

bash "$VERIFY" --dry-run >"$manifest"
for gate in web cli_flow cli_session l4_business_key l4_event_engine \
  l4_flow_api_controls boundary_unit boundary_audit rbac_audit spec_audit live_probe; do
  [[ "$(grep -Fxc "gate: $gate" "$manifest")" == 1 ]] \
    || fail "dry-run manifest must contain gate $gate exactly once"
done
grep -Fqx 'command: make v3.10-spec-audit' "$manifest" || fail 'dry-run manifest omits spec audit command'
for node in \
  'tests/test_flow_api.py::test_timeline_malformed_key_returns_400' \
  'tests/test_flow_api.py::test_timeline_empty_session_id_returns_400' \
  'tests/test_flow_api.py::test_sse_stream_returns_streaming_response' \
  'tests/test_flow_api.py::test_sse_stream_malformed_key_returns_400' \
  'tests/test_flow_api.py::test_list_business_flows_uses_latest_row_and_filters_before_limit'; do
  grep -Fq "$node" "$manifest" || fail "dry-run manifest omits flow API node $node"
done
if grep -Eq '(^|[[:space:]])make[[:space:]]+test($|[[:space:]])|cargo[[:space:]]+test[[:space:]]+--workspace|pytest[[:space:]]+-q[[:space:]]+tests/?($|[[:space:]])' "$manifest"; then
  fail 'dry-run manifest contains a broad test command'
fi

if V316_VERIFY_SELF_TEST=fail:cli_flow bash "$VERIFY" --dry-run >"$failure_output" 2>&1; then
  fail 'forced CLI flow failure unexpectedly passed'
fi
grep -Fqx 'gate: cli_flow' "$failure_output" || fail 'forced failure did not reach CLI flow gate'
grep -Fqx 'forced failure: cli_flow' "$failure_output" || fail 'forced failure hook did not report its gate'
if grep -Fqx 'gate: cli_session' "$failure_output"; then
  fail 'verifier executed a later gate after forced failure'
fi

if V316_VERIFY_SELF_TEST=fail:not_a_gate bash "$VERIFY" --dry-run >"$failure_output" 2>&1; then
  fail 'unknown forced-failure gate unexpectedly passed'
fi
grep -Fq 'unknown gate' "$failure_output" || fail 'unknown forced-failure gate was not rejected'

printf 'PASS: v3.16 verifier manifest and fail-fast hook\n'
