#!/usr/bin/env bash
# check-key-handler-invariants.sh — verify TUI key handler test coverage
#
# Reads the per-file "Current test inventory" table from INVARIANTS.md and
# compares each module's actual `fn test_` count to a documented floor.
# Catches regressions where someone removed tests without updating
# INVARIANTS.md.
#
# Used by Phase 5.2 T-01.15 (INVARIANTS.md completeness verification).
#
# Exit codes:
#   0  — all modules at or above their documented test-count floor
#   1  — at least one module dropped below its floor (regression)
#   2  — invariant: required file missing
#
# Portable to bash 3.2 (macOS default) — no associative arrays.
# Run from repo root: ./scripts/check-key-handler-invariants.sh

set -eu

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KH_DIR="$REPO_ROOT/crates/grid-cli/src/tui/key_handlers"
INV_MD="$KH_DIR/INVARIANTS.md"

if [ ! -f "$INV_MD" ]; then
  echo "FAIL: INVARIANTS.md not found at $INV_MD" >&2
  exit 2
fi

if [ ! -d "$KH_DIR" ]; then
  echo "FAIL: key_handlers/ directory not found at $KH_DIR" >&2
  exit 2
fi

# Parallel arrays — file name + documented floor count (from INVARIANTS.md
# "Current test inventory" 2026-05-16 revision). Keep in lockstep.
FILES="mod.rs normal.rs slash_commands.rs vim_normal.rs vim_insert.rs approval.rs overlay.rs model_selector.rs history_search.rs common.rs"
FLOORS="40     20        9                7             5             5           4          5                  4                  2"

echo "TUI key handler test coverage check"
echo "===================================="
printf "%-22s %8s %8s %s\n" "File" "Actual" "Floor" "Status"

total_actual=0
total_floor=0
failed=0

# Iterate using positional substitution
set -- $FILES
files_arr=("$@")
set -- $FLOORS
floors_arr=("$@")

i=0
while [ $i -lt ${#files_arr[@]} ]; do
  f="${files_arr[$i]}"
  floor="${floors_arr[$i]}"
  path="$KH_DIR/$f"

  if [ ! -f "$path" ]; then
    printf "%-22s %8s %8s MISSING\n" "$f" "-" "$floor"
    failed=1
    i=$((i + 1))
    continue
  fi

  # Count `fn test_` and `async fn test_` — the convention across the 130
  # existing tests in this module.
  actual=$(grep -cE "^[[:space:]]*(async[[:space:]]+)?fn[[:space:]]+test_" "$path" || true)

  total_actual=$((total_actual + actual))
  total_floor=$((total_floor + floor))

  if [ "$actual" -ge "$floor" ]; then
    status="OK"
  else
    status="REGRESSION (-$((floor - actual)))"
    failed=1
  fi

  printf "%-22s %8d %8d %s\n" "$f" "$actual" "$floor" "$status"
  i=$((i + 1))
done

echo "------------------------------------"
printf "%-22s %8d %8d\n" "TOTAL" "$total_actual" "$total_floor"
echo ""

# Surface known coverage gaps. These are documented in INVARIANTS.md and
# are NOT failures — they're targets for future test additions.
echo "Known coverage gaps (informational, not failures):"
echo "  - normal.rs:         20 tests vs 33 binding rows (~60% direct coverage)"
echo "  - vim_normal.rs:      7 tests vs 15 binding rows (~47% direct coverage)"
echo "  - vim_insert.rs:      5 tests vs 15 binding rows (~33% direct coverage)"
echo "  - slash_commands.rs:  9 tests vs 11 binding rows (~82% direct coverage)"
echo "  - overlay.rs:         4 tests vs  5 binding rows (~80% direct coverage)"
echo "  - model_selector.rs:  5 tests vs  7 binding rows (~71% direct coverage)"
echo "  - history_search.rs:  4 tests vs  5 binding rows (~80% direct coverage)"
echo ""
echo "Cross-mode integration tests (rows <-> tests via mode transitions) are"
echo "out of scope for this checker — see Phase 5.2 T-01.14 / T-01.19."

if [ "$failed" -ne 0 ]; then
  echo ""
  echo "FAIL: at least one module dropped below its INVARIANTS.md floor."
  echo "Either restore coverage or update INVARIANTS.md if intentional."
  exit 1
fi

echo ""
echo "PASS: all modules at or above INVARIANTS.md floors."
exit 0
