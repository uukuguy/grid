#!/usr/bin/env bash
# D108 — unified bats + shellcheck runner for all skill hook scripts.
# Usage:
#   scripts/test_hook_scripts.sh                  # shellcheck + bats (default)
#   scripts/test_hook_scripts.sh --lint-only       # shellcheck only
#   scripts/test_hook_scripts.sh --test-only       # bats only
#   scripts/test_hook_scripts.sh --verbose         # verbose bats output
#
# Discovers all *.bats and *.sh files under examples/skills/*/hooks/.
# Shellcheck runs on *.sh files; bats runs on *.bats files.
# Exits non-zero if any check fails and the tool is available.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="all"

# Parse flags
BATS_ARGS=()
for arg in "$@"; do
    case "$arg" in
        --lint-only) MODE="lint" ;;
        --test-only) MODE="test" ;;
        *)           BATS_ARGS+=("$arg") ;;
    esac
done

# ── Shellcheck pass ──
run_shellcheck() {
    if ! command -v shellcheck >/dev/null 2>&1; then
        echo "SKIP: shellcheck not installed. Install: brew install shellcheck" >&2
        return 0
    fi

    local sh_files=()
    while IFS= read -r -d '' f; do
        sh_files+=("$f")
    done < <(find "$REPO_ROOT/examples/skills" -name "*.sh" -print0 | sort -z)

    if [ "${#sh_files[@]}" -eq 0 ]; then
        echo "No .sh files found under examples/skills/ — nothing to lint."
        return 0
    fi

    echo "Shellcheck: linting ${#sh_files[@]} hook script(s)..."
    local failed=0
    for f in "${sh_files[@]}"; do
        if ! shellcheck -x "$f"; then
            failed=1
        fi
    done

    if [ "$failed" -eq 1 ]; then
        echo "ERROR: shellcheck found issues." >&2
        return 1
    fi
    echo "Shellcheck: all clear."
    return 0
}

# ── bats pass ──
run_bats() {
    local bats_files=()
    while IFS= read -r -d '' f; do
        bats_files+=("$f")
    done < <(find "$REPO_ROOT/examples/skills" -name "*.bats" -print0 | sort -z)

    if [ "${#bats_files[@]}" -eq 0 ]; then
        echo "SKIP: No .bats files found under examples/skills/"
        return 0
    fi

    if ! command -v bats >/dev/null 2>&1; then
        echo "SKIP: bats not installed. Install: brew install bats-core" >&2
        return 0
    fi

    echo "bats: running ${#bats_files[@]} suite(s)..."
    if [ "${#BATS_ARGS[@]}" -gt 0 ]; then
        bats "${BATS_ARGS[@]}" "${bats_files[@]}"
    else
        bats "${bats_files[@]}"
    fi
}

# ── Dispatch ──
case "$MODE" in
    lint)
        run_shellcheck
        ;;
    test)
        run_bats
        ;;
    all)
        run_shellcheck
        echo ""
        run_bats
        ;;
esac
