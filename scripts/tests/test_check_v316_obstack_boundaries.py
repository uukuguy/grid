"""Regression tests for the v3.16 OBSTACK ownership-boundary audit."""

from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = REPO_ROOT / "scripts/check-v316-obstack-boundaries.py"


def load_checker() -> ModuleType:
    assert CHECKER_PATH.is_file(), "v3.16 boundary checker has not been implemented"
    spec = importlib.util.spec_from_file_location("v316_obstack_boundaries", CHECKER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def copy_boundary_fixture(destination: Path) -> None:
    """Copy only the inputs examined by the checker into a disposable repo."""
    for relative_path in (
        "tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_api.py",
        "crates/grid-server/src/rbac/catalog.rs",
        "docs/design/EAASP/DEFERRED_LEDGER.md",
        "docs/superpowers/plans/2026-08-09-obstack-v3-15-6-completion.md",
        "docs/superpowers/plans/2026-08-24-v316-obstack-product-surface.md",
        "tools/eaasp-common/src/eaasp_common/obstack_models.py",
    ):
        source = REPO_ROOT / relative_path
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


class V316ObstackBoundaryCheckerTests(unittest.TestCase):
    def test_current_repository_satisfies_boundary_contract(self) -> None:
        checker = load_checker()

        self.assertEqual(checker.check(REPO_ROOT), [])

    def test_missing_l4_route_fails_the_audit(self) -> None:
        checker = load_checker()
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory) / "fixture"
            copy_boundary_fixture(fixture_root)
            flow_api = (
                fixture_root
                / "tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_api.py"
            )
            route = '@router.get(f"/{{{_KEY_PATH_PARAM}}}/timeline")'
            flow_api.write_text(
                flow_api.read_text(encoding="utf-8").replace(route, "# route removed", 1),
                encoding="utf-8",
            )

            failures = checker.check(fixture_root)

        self.assertIn("missing L4 route: GET /v1/business-flows/{key}/timeline", failures)

    def test_missing_deferred_id_fails_the_audit(self) -> None:
        checker = load_checker()
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory) / "fixture"
            copy_boundary_fixture(fixture_root)
            ledger = fixture_root / "docs/design/EAASP/DEFERRED_LEDGER.md"
            ledger.write_text(
                ledger.read_text(encoding="utf-8").replace(
                    "V316-EVAL-OBSTACK-01", "REMOVED-EVAL-OBSTACK-01", 1
                ),
                encoding="utf-8",
            )

            failures = checker.check(fixture_root)

        self.assertIn("missing deferred item: V316-EVAL-OBSTACK-01", failures)
