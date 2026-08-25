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
grep -Fqx 'gate: web' "$manifest" || fail 'dry-run manifest omits web gate'
grep -Fqx 'gate: cli_flow' "$manifest" || fail 'dry-run manifest omits CLI flow gate'
grep -Fqx 'gate: live_probe' "$manifest" || fail 'dry-run manifest omits live probe gate'
grep -Fqx 'command: make v3.10-spec-audit' "$manifest" || fail 'dry-run manifest omits spec audit command'

if V316_VERIFY_SELF_TEST=fail:cli_flow bash "$VERIFY" --dry-run >"$failure_output" 2>&1; then
  fail 'forced CLI flow failure unexpectedly passed'
fi
grep -Fqx 'gate: cli_flow' "$failure_output" || fail 'forced failure did not reach CLI flow gate'
grep -Fqx 'forced failure: cli_flow' "$failure_output" || fail 'forced failure hook did not report its gate'
if grep -Fqx 'gate: cli_session' "$failure_output"; then
  fail 'verifier executed a later gate after forced failure'
fi

printf 'PASS: v3.16 verifier manifest and fail-fast hook\n'
