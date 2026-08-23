#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
HYPOTHESIS_ID=${1:?usage: train.sh H-NNN}
STAMP=$(date +%Y%m%d-%H%M%S)
RUN_DIR="$ROOT/runs/climb/${STAMP}-${HYPOTHESIS_ID,,}"
mkdir -p "$RUN_DIR"
python3 - "$RUN_DIR/manifest.json" "$HYPOTHESIS_ID" "$(git rev-parse HEAD)" <<'PY'
import json, sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({"hypothesis_id": sys.argv[2], "git_head": sys.argv[3]}, indent=2) + "\n")
PY
echo "$RUN_DIR"
