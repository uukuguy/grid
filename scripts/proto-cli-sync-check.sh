#!/usr/bin/env bash
# proto-cli-sync-check.sh — invoke `grid doctor`'s proto-sync check from CI
#
# Phase 5.2 T-01.18.
#
# Grid stores per-session `.sync` markers under `~/.config/grid/proto/`
# (path: `state.grid_root.project_data_dir().join("proto")`). `grid doctor`
# inspects this directory via `check_proto_sync` (see
# `crates/grid-cli/src/commands/doctor.rs:280`):
#
#   - directory absent or empty       → Pass    (clean state)
#   - >= 1 `*.sync` marker present    → Warn    (orphan from kill non-purge)
#
# This script is a POSIX-ergonomic wrapper that:
#   1. Locates a `grid` binary (release if built, else builds it on the fly)
#   2. Runs `grid doctor` and inspects its output
#   3. Maps Pass/Warn → script exit codes per Phase 5.2 PLAN
#
# Exit codes:
#   0   — proto sync clean (Pass)
#   73  — EXIT_SYNC: sync markers present (Warn / Fail)
#   2   — invariant violation: binary unbuildable or doctor format changed
#
# Scope NOTE: PLAN T-01.18 also alludes to "compare CLI proto file versions
# against disk". grid-cli does NOT embed/extract proto files — proto schema
# is compiled in via tonic-build at build time. A separate concern (proto
# codegen drift, where regenerated .rs files don't match committed source)
# is OUT OF SCOPE here.
#
# Run from repo root: ./scripts/proto-cli-sync-check.sh

set -eu

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GRID_BIN_REL="$REPO_ROOT/target/release/grid"
GRID_BIN_DBG="$REPO_ROOT/target/debug/grid"

# Pick the freshest existing binary; build debug if neither exists.
if [ -x "$GRID_BIN_REL" ]; then
  GRID_BIN="$GRID_BIN_REL"
elif [ -x "$GRID_BIN_DBG" ]; then
  GRID_BIN="$GRID_BIN_DBG"
else
  echo "info: no grid binary found, building (this may take a minute) ..." >&2
  if ! (cd "$REPO_ROOT" && cargo build -p grid-cli --bin grid >&2); then
    echo "error: failed to build grid-cli binary" >&2
    exit 2
  fi
  GRID_BIN="$GRID_BIN_DBG"
fi

if [ ! -x "$GRID_BIN" ]; then
  echo "error: grid binary not executable: $GRID_BIN" >&2
  exit 2
fi

echo "proto-cli-sync-check: invoking $GRID_BIN doctor"
echo "------------------------------------------------"

# `grid doctor` returns 0 even on Warn (warnings aren't failures), so we
# parse the output for the Proto Sync row.
out=$("$GRID_BIN" doctor 2>&1) || true

echo "$out"
echo "------------------------------------------------"

# `check_proto_sync` (doctor.rs:280) emits exactly one of these messages:
#   "No proto sync markers found (clean state)"        → Pass
#   "N proto sync marker(s) found (may need cleanup)"  → Warn
#
# Any other text → doctor changed format → script needs updating.
if printf '%s\n' "$out" | grep -qE "proto sync marker.*found.*may need cleanup"; then
  echo ""
  echo "FAIL: proto sync markers present — orphan session state detected."
  echo "Fix: run 'grid session kill --purge <session-id>' to clean up,"
  echo "     or 'rm -rf \$(grid root project-data)/proto' to nuke all markers."
  exit 73   # EXIT_SYNC
fi

if printf '%s\n' "$out" | grep -qE "No proto sync markers found"; then
  echo ""
  echo "PASS: proto sync directory clean."
  exit 0
fi

echo ""
echo "error: 'grid doctor' output did not include a recognizable Proto Sync row." >&2
echo "       script may need updating to match new doctor output format." >&2
exit 2
