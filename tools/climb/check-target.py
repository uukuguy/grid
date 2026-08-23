#!/usr/bin/env python3
"""Exit 10 when the deterministic local acceptance target is met."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "docs/status/climb/runs.csv"


def main() -> None:
    with RUNS.open(newline="") as handle:
        scores = [float(row["local_score"]) for row in csv.DictReader(handle) if row["local_score"]]
    current = max(scores, default=0.0)
    result = {"has_target": True, "met": current >= 100, "metric": "local", "current": current, "target": 100}
    print(json.dumps(result))
    raise SystemExit(10 if result["met"] else 0)


if __name__ == "__main__":
    main()
