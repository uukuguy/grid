#!/usr/bin/env python3
"""Audit the v3.16 OBSTACK ownership and deferral boundary."""

from __future__ import annotations

import ast
import re
import sys
from collections import Counter
from pathlib import Path


EXPECTED_L4_ROUTES = frozenset(
    {
        "GET /v1/business-flows/{key}/timeline",
        "GET /v1/business-flows/{key}/summary",
        "GET /v1/business-flows/{key}/events/stream",
        "GET /v1/business-flows/{key}/evaluation",
        "GET /v1/business-flows/{key}/sessions",
        "GET /v1/business-flows/list",
    }
)
DEFERRED_IDS = (
    "V316-MULTITENANT-OBSTACK-01",
    "V316-EVAL-OBSTACK-01",
    "V316-ECOSYSTEM-HEALTH-01",
)
HISTORICAL_PLAN = "docs/superpowers/plans/2026-08-09-obstack-v3-15-6-completion.md"
ACTIVE_PLAN_NAME = "2026-08-24-v316-obstack-product-surface.md"


def _read(root: Path, relative_path: str, failures: list[str]) -> str:
    path = root / relative_path
    if not path.is_file():
        failures.append(f"missing audit input: {relative_path}")
        return ""
    return path.read_text(encoding="utf-8")


def _parse_python(source: str, name: str, failures: list[str]) -> ast.Module | None:
    try:
        return ast.parse(source, filename=name)
    except SyntaxError as error:
        failures.append(f"cannot parse {name}: {error.msg}")
        return None


def _resolve_string(expression: ast.expr, constants: dict[str, str]) -> str | None:
    if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        return expression.value
    if isinstance(expression, ast.Name):
        return constants.get(expression.id)
    if isinstance(expression, ast.JoinedStr):
        parts: list[str] = []
        for value in expression.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue) and isinstance(value.value, ast.Name):
                resolved = constants.get(value.value.id)
                if resolved is None:
                    return None
                parts.append(resolved)
            else:
                return None
        return "".join(parts)
    return None


def _module_constants(module: ast.Module) -> dict[str, str]:
    constants: dict[str, str] = {}
    for statement in module.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        if not isinstance(statement.targets[0], ast.Name):
            continue
        value = _resolve_string(statement.value, constants)
        if value is not None:
            constants[statement.targets[0].id] = value
    return constants


def _executable_l4_routes(module: ast.Module) -> list[str]:
    constants = _module_constants(module)
    prefix = constants.get("_PREFIX", "")
    routes: list[str] = []
    for node in ast.walk(module):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not decorator.args:
                continue
            function = decorator.func
            if not (
                isinstance(function, ast.Attribute)
                and function.attr == "get"
                and isinstance(function.value, ast.Name)
                and function.value.id == "router"
            ):
                continue
            path = _resolve_string(decorator.args[0], constants)
            if path is not None:
                routes.append(f"GET {prefix}{path}")
    return routes


def _mounts_flow_router(module: ast.Module) -> bool:
    for node in ast.walk(module):
        if not isinstance(node, ast.Call) or len(node.args) != 1:
            continue
        if not (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "include_router"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "app"
        ):
            continue
        router = node.args[0]
        if (
            isinstance(router, ast.Attribute)
            and router.attr == "router"
            and isinstance(router.value, ast.Name)
            and router.value.id == "_flow_api"
        ):
            return True
    return False


def _strip_rust_comments(source: str) -> str:
    """Remove Rust comments while preserving quoted string literals."""
    output: list[str] = []
    index = 0
    in_string = False
    while index < len(source):
        character = source[index]
        if in_string:
            output.append(character)
            if character == "\\" and index + 1 < len(source):
                index += 1
                output.append(source[index])
            elif character == '"':
                in_string = False
            index += 1
        elif character == '"':
            in_string = True
            output.append(character)
            index += 1
        elif source.startswith("//", index):
            newline = source.find("\n", index)
            index = len(source) if newline == -1 else newline
        elif source.startswith("/*", index):
            end = source.find("*/", index + 2)
            index = len(source) if end == -1 else end + 2
        else:
            output.append(character)
            index += 1
    return "".join(output)


def _rbac_entries(catalog: str) -> list[tuple[str, str]]:
    """Extract real ``route!`` invocations from the Rust catalog initializer."""
    start = catalog.find("pub static ROUTE_CATALOG")
    end = catalog.find("];", start)
    if start == -1 or end == -1:
        return []
    initializer = _strip_rust_comments(catalog[start:end])
    pattern = re.compile(
        r'\broute!\s*\(\s*(?:public|[A-Za-z_]\w*)\s*,\s*"(?P<method>[^"]+)"\s*,\s*"(?P<path>[^"]+)"\s*\)',
        flags=re.DOTALL,
    )
    return [(match["method"], match["path"]) for match in pattern.finditer(initializer)]


def _meaningful(value: str) -> bool:
    return any(character.isalnum() for character in value)


def _deferred_trigger_and_owner(row: str) -> tuple[str, str] | None:
    match = re.search(
        r"\*\*Trigger:\*\*\s*(.*?)\s+\*\*Owner:\*\*\s*(.*?)(?:\s*\||$)",
        row,
    )
    return None if match is None else (match.group(1).strip(), match.group(2).strip())


def _section(text: str, heading: str) -> str:
    start = text.find(heading)
    if start == -1:
        return ""
    end = text.find("\n## ", start + len(heading))
    return text[start:] if end == -1 else text[start:end]


def check(root: Path) -> list[str]:
    """Return every v3.16 OBSTACK boundary violation below ``root``."""
    root = Path(root)
    failures: list[str] = []
    flow_api = _read(root, "tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_api.py", failures)
    l4_api = _read(root, "tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/api.py", failures)
    catalog = _read(root, "crates/grid-server/src/rbac/catalog.rs", failures)
    ledger = _read(root, "docs/design/EAASP/DEFERRED_LEDGER.md", failures)
    historical_plan = _read(root, HISTORICAL_PLAN, failures)
    active_plan = _read(root, "docs/superpowers/plans/2026-08-24-v316-obstack-product-surface.md", failures)
    shared_models = _read(root, "tools/eaasp-common/src/eaasp_common/obstack_models.py", failures)

    flow_module = _parse_python(flow_api, "flow_api.py", failures)
    if flow_module is not None:
        constants = _module_constants(flow_module)
        if constants.get("_KEY_PATH_PARAM") != "key":
            failures.append("L4 business-flow path parameter must remain named key")
        if constants.get("_PREFIX") != "/v1/business-flows":
            failures.append("L4 business-flow prefix must remain /v1/business-flows")
        actual_routes = Counter(_executable_l4_routes(flow_module))
        for route in sorted(EXPECTED_L4_ROUTES):
            if actual_routes[route] == 0:
                failures.append(f"missing L4 route: {route}")
            elif actual_routes[route] > 1:
                failures.append(f"duplicate L4 route: {route}")
        for route in sorted(set(actual_routes) - EXPECTED_L4_ROUTES):
            failures.append(f"unexpected L4 route: {route}")

    api_module = _parse_python(l4_api, "api.py", failures)
    if api_module is not None and not _mounts_flow_router(api_module):
        failures.append("L4 api.py must mount _flow_api.router")

    entries = _rbac_entries(catalog)
    if len(entries) != 134:
        failures.append(f"grid-server RBAC catalog must contain exactly 134 entries (found {len(entries)})")
    if any(re.search(r"business[-_ ]?flows?", path, flags=re.IGNORECASE) for _, path in entries):
        failures.append("grid-server RBAC must not contain a business-flow entry")

    for deferred_id in DEFERRED_IDS:
        row = next((line for line in ledger.splitlines() if deferred_id in line), None)
        if row is None:
            failures.append(f"missing deferred item: {deferred_id}")
            continue
        trigger_owner = _deferred_trigger_and_owner(row)
        if trigger_owner is None or not all(map(_meaningful, trigger_owner)):
            failures.append(f"deferred item must declare a meaningful Trigger and Owner: {deferred_id}")

    marker = "**Superseded by active v3.16 plan:**"
    for phase in ("d", "e"):
        section = _section(historical_plan, f"## v3.15.6{phase}")
        if marker not in section or ACTIVE_PLAN_NAME not in section:
            failures.append(f"v3.15.6{phase} must name the active v3.16 replacement")
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
