#!/usr/bin/env python3
"""Audit the v3.16 OBSTACK ownership and deferral boundary."""

from __future__ import annotations

import re
import sys
from pathlib import Path


REQUIRED_ROUTES = (
    ("GET /v1/business-flows/{key}/timeline", '@router.get(f"/{{{_KEY_PATH_PARAM}}}/timeline")'),
    ("GET /v1/business-flows/{key}/summary", '@router.get(f"/{{{_KEY_PATH_PARAM}}}/summary")'),
    (
        "GET /v1/business-flows/{key}/events/stream",
        '@router.get(f"/{{{_KEY_PATH_PARAM}}}/events/stream")',
    ),
    (
        "GET /v1/business-flows/{key}/evaluation",
        '@router.get(f"/{{{_KEY_PATH_PARAM}}}/evaluation")',
    ),
    ("GET /v1/business-flows/{key}/sessions", '@router.get(f"/{{{_KEY_PATH_PARAM}}}/sessions")'),
    ("GET /v1/business-flows/list", '@router.get("/list")'),
)

DEFERRED_IDS = (
    "V316-MULTITENANT-OBSTACK-01",
    "V316-EVAL-OBSTACK-01",
    "V316-ECOSYSTEM-HEALTH-01",
)


def _read(root: Path, relative_path: str, failures: list[str]) -> str:
    path = root / relative_path
    if not path.is_file():
        failures.append(f"missing audit input: {relative_path}")
        return ""
    return path.read_text(encoding="utf-8")


def check(root: Path) -> list[str]:
    """Return every v3.16 OBSTACK boundary violation below ``root``."""
    root = Path(root)
    failures: list[str] = []
    flow_api = _read(
        root,
        "tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_api.py",
        failures,
    )
    catalog = _read(root, "crates/grid-server/src/rbac/catalog.rs", failures)
    ledger = _read(root, "docs/design/EAASP/DEFERRED_LEDGER.md", failures)
    historical_plan = _read(
        root,
        "docs/superpowers/plans/2026-08-09-obstack-v3-15-6-completion.md",
        failures,
    )
    active_plan = _read(
        root,
        "docs/superpowers/plans/2026-08-24-v316-obstack-product-surface.md",
        failures,
    )
    shared_models = _read(
        root,
        "tools/eaasp-common/src/eaasp_common/obstack_models.py",
        failures,
    )

    if '_KEY_PATH_PARAM = "key"' not in flow_api:
        failures.append("L4 business-flow path parameter must remain named key")
    if '_PREFIX = "/v1/business-flows"' not in flow_api:
        failures.append("L4 business-flow prefix must remain /v1/business-flows")
    for route_name, declaration in REQUIRED_ROUTES:
        if declaration not in flow_api:
            failures.append(f"missing L4 route: {route_name}")

    if re.search(r"business[-_ ]flow", catalog, flags=re.IGNORECASE):
        failures.append("grid-server RBAC must not contain a business-flow entry")

    for deferred_id in DEFERRED_IDS:
        row = next((line for line in ledger.splitlines() if deferred_id in line), None)
        if row is None:
            failures.append(f"missing deferred item: {deferred_id}")
        elif "Trigger:" not in row or "Owner:" not in row:
            failures.append(
                f"deferred item must declare Trigger and Owner: {deferred_id}"
            )

    superseded_marker = "**Superseded by active v3.16 plan:**"
    active_plan_name = "2026-08-24-v316-obstack-product-surface.md"
    if historical_plan.count(superseded_marker) < 2 or active_plan_name not in historical_plan:
        failures.append("historical v3.15.6d/6e text must name the active v3.16 replacement")
    if "# v3.16 OBSTACK 产品面收口实施计划" not in active_plan or "## Task 5:" not in active_plan:
        failures.append("v3.16 OBSTACK product-surface plan must remain the active replacement")

    if "L4 Python is the server owner." not in shared_models:
        failures.append("shared OBSTACK models must identify L4 Python as server owner")
    if "``web/src/api/obstack_types.ts`` is the TypeScript mirror." not in shared_models:
        failures.append("shared OBSTACK models must identify the TypeScript mirror")

    return failures


def main() -> int:
    failures = check(Path(__file__).resolve().parents[1])
    if failures:
        print("v3.16 OBSTACK boundary audit failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("v3.16 OBSTACK boundary audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
