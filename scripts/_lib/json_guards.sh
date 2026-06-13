#!/usr/bin/env bash
# Shared jq validation guards for hook and verification scripts.
#
# Usage:
#   source "$(dirname "${BASH_SOURCE[0]}")/../_lib/json_guards.sh"
#
# Provides:
#   require_jq        — fail fast if jq is not installed
#   json_file_valid    — check if a JSON file exists and is non-empty
#   json_event_count   — count events in a JSON events file by event_type

set -euo pipefail

# Ensure jq is available; fail with a clear message if not.
require_jq() {
    if ! command -v jq >/dev/null 2>&1; then
        echo "ERROR: jq is required but not installed. Install: brew install jq" >&2
        exit 1
    fi
}

# Check if a JSON file exists and is non-empty.
# Usage: json_file_valid <path>
# Returns 0 if file exists and jq can parse it, non-zero otherwise.
json_file_valid() {
    local f="$1"
    [ -f "$f" ] && jq empty "$f" 2>/dev/null
}

# Count events in a JSON events file by event_type.
# Usage: json_event_count <path> <event_type>
# Returns the count as a number, or 0 on error.
json_event_count() {
    local f="$1" event_type="$2"
    jq --arg et "$event_type" '[.events[]? | select(.event_type==$et)] | length' "$f" 2>/dev/null || echo 0
}
