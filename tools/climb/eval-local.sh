#!/usr/bin/env bash
set -u

ROOT=$(git rev-parse --show-toplevel)
RUN_DIR=${1:?usage: eval-local.sh RUN_DIR}
OUT="$RUN_DIR/eval.json"

run_gate() {
  local name=$1 weight=$2 command=$3
  if /bin/zsh -lc "cd '$ROOT' && $command" >"$RUN_DIR/${name}.log" 2>&1; then
    printf '%s %s\n' "$name" "$weight"
  else
    printf '%s 0\n' "$name"
  fi
}

{
  run_gate dashboard 30 "cd web && npx vitest run src/test/v316-obstack-contract.test.ts src/test/v316-obstack-surface.test.tsx && npm run build"
  run_gate cli 25 "cd tools/eaasp-cli-v2 && PYTHONPATH=../eaasp-common/src uv run --extra dev pytest -q tests/test_v316_flow_commands.py"
  run_gate business_key 20 "cd tools/eaasp-l4-orchestration && uv run --extra dev pytest -q tests/test_v316_business_key_surface.py && cd ../eaasp-cli-v2 && PYTHONPATH=../eaasp-common/src uv run --extra dev pytest -q tests/test_v316_session_business_key.py"
  run_gate scope_integrity 10 "python3 scripts/check-v316-obstack-boundaries.py"
  run_gate verification 15 "bash scripts/v316-obstack-surface-verify.sh"
} >"$RUN_DIR/gates.txt"

python3 - "$RUN_DIR/gates.txt" "$OUT" <<'PY'
import json, sys
from pathlib import Path
scores = {}
for line in Path(sys.argv[1]).read_text().splitlines():
    name, score = line.split()
    scores[name] = int(score)
Path(sys.argv[2]).write_text(json.dumps({"total": sum(scores.values()), "per_task": scores}, indent=2) + "\n")
PY
cat "$OUT"
