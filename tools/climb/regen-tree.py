#!/usr/bin/env python3
"""Deterministically render the v3.16 climb resume summary."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "docs/status/climb"


def load_json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def main() -> None:
    hypotheses = load_json(STATE / "hypotheses.yaml", {"hypotheses": []})["hypotheses"]
    session = load_json(STATE / "session-state.json", {})
    with (STATE / "runs.csv").open(newline="") as handle:
        runs = list(csv.DictReader(handle))
    best = max((float(row["local_score"]) for row in runs if row["local_score"]), default=0.0)
    lines = [
        "# Research Tree — v3.16 OBSTACK product surface",
        "",
        f"> Deterministic summary; {len(runs)} cycles logged. Do not edit manually.",
        "",
        f"**Best local acceptance score:** {best:.0f}/100",
        f"**Phase:** {session.get('phase', 'unknown')}",
        f"**Last cycle:** {session.get('last_cycle', 0)}",
        f"**Next hypothesis:** {session.get('next_hypothesis', 'none')}",
        f"**Next action:** {session.get('next_action', 'none')}",
        "",
        "## Active hypotheses",
        "",
    ]
    for item in sorted(hypotheses, key=lambda row: -float(row["ranking"])):
        lines.append(
            f"- **{item['id']}** [{item['status']}] ({item['parent_paradigm']}): {item['description']}"
        )
    lines.extend(["", "## Cycle ladder", "", "| run | hypothesis | score | decision | verdict |", "|---|---|---:|---|---|"])
    for row in runs:
        lines.append(
            f"| {row['run_id']} | {row['hypothesis_id']} | {row['local_score']} | {row['push_decision']} | {row['verdict']} |"
        )
    falsified = session.get("falsified_routes", [])
    lines.extend(["", "## Negative cache", ""] + [f"- {item}" for item in falsified] + [""])
    (STATE / "research-tree.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
