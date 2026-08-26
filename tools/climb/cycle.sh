#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
STATE="$ROOT/docs/status/climb"
HYPOTHESIS_ID=${1:?usage: cycle.sh H-NNN}
RUN_DIR=$("$ROOT/tools/climb/train.sh" "$HYPOTHESIS_ID")
"$ROOT/tools/climb/eval-local.sh" "$RUN_DIR" >/dev/null

python3 - "$ROOT" "$HYPOTHESIS_ID" "$RUN_DIR" <<'PY'
import csv, json, sys
from pathlib import Path
root, hypothesis_id, run_dir = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
state = root / "docs/status/climb"
pool_path = state / "hypotheses.yaml"
pool = json.loads(pool_path.read_text())
item = next(row for row in pool["hypotheses"] if row["id"] == hypothesis_id)
evaluation = json.loads((run_dir / "eval.json").read_text())
session_path = state / "session-state.json"
session = json.loads(session_path.read_text())
cycle = int(session.get("last_cycle", 0)) + 1
gate_by_hypothesis = {
    "H-001": ("dashboard", 30),
    "H-002": ("cli", 25),
    "H-003": ("business_key", 20),
    "H-004": ("scope_integrity", 10),
    "H-005": ("verification", 15),
}
gate, required = gate_by_hypothesis[hypothesis_id]
gate_score = evaluation["per_task"].get(gate, 0)
verdict = "confirmed" if gate_score >= required else "falsified"
previous_scores = []
runs_path = state / "runs.csv"
with runs_path.open(newline="") as handle:
    for previous in csv.DictReader(handle):
        if previous.get("local_score"):
            previous_scores.append(float(previous["local_score"]))
best_before = max(previous_scores, default=0.0)
decision = "PUSH" if verdict == "confirmed" and evaluation["total"] > best_before else "SKIP"
item["status"] = verdict
item["results"].append({"session": session["session"], "cycle": cycle, "run": run_dir.name, "local": evaluation["total"], "verdict": verdict})
pending = [row for row in pool["hypotheses"] if row["status"] == "pending"]
session.update({"phase": "executing", "last_cycle": cycle, "next_hypothesis": pending[0]["id"] if pending else None, "next_action": "Dispatch the next ranked pending hypothesis" if pending else "Run final verification and close the target"})
pool_path.write_text(json.dumps(pool, indent=2) + "\n")
session_path.write_text(json.dumps(session, indent=2) + "\n")
row = {
    "run_id": run_dir.name, "cycle": cycle, "session": session["session"], "hypothesis_id": hypothesis_id,
    "paradigm": item["parent_paradigm"], "parent_run": "", "pushed_at": "", "lb_landed_at": "",
    "local_score": evaluation["total"], "local_dashboard": evaluation["per_task"].get("dashboard", 0),
    "local_cli": evaluation["per_task"].get("cli", 0), "local_business_key": evaluation["per_task"].get("business_key", 0),
    "local_scope_integrity": evaluation["per_task"].get("scope_integrity", 0), "local_verification": evaluation["per_task"].get("verification", 0),
    "online_score": "", "gap": "", "push_decision": decision,
    "decision_reason": f"{gate}={gate_score}/{required}; best_before={best_before:g}",
    "verdict": verdict, "train_cost_h": item["cost_h"], "manifest_path": str(run_dir.relative_to(root) / "manifest.json"),
}
with (state / "runs.csv").open("a", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=row.keys(), lineterminator="\n")
    writer.writerow(row)
(run_dir / "decision.txt").write_text(decision + "\n")
PY

if [ "$(cat "$RUN_DIR/decision.txt")" = "PUSH" ]; then
  "$ROOT/tools/climb/push.sh" "$RUN_DIR"
fi
python3 "$ROOT/tools/climb/regen-tree.py"
if python3 "$ROOT/tools/climb/check-target.py"; then
  echo "[climb] continuing"
else
  code=$?
  if [ "$code" -eq 10 ]; then
    echo "[climb] target met — hard pause"
  else
    exit "$code"
  fi
fi
