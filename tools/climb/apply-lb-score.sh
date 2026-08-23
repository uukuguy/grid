#!/usr/bin/env bash
set -euo pipefail
echo "[climb] This adapter uses repository acceptance gates; no external LB score is accepted." >&2
exit 2
