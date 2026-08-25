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
        "tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/api.py",
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

    def test_commented_out_l4_decorator_fails_the_audit(self) -> None:
        checker = load_checker()
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory) / "fixture"
            copy_boundary_fixture(fixture_root)
            flow_api = (
                fixture_root
                / "tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_api.py"
            )
            route = '@router.get(f"/{{{_KEY_PATH_PARAM}}}/summary")'
            flow_api.write_text(
                flow_api.read_text(encoding="utf-8").replace(route, f"# {route}", 1),
                encoding="utf-8",
            )

            failures = checker.check(fixture_root)

        self.assertIn("missing L4 route: GET /v1/business-flows/{key}/summary", failures)

    def test_extra_l4_route_fails_the_audit(self) -> None:
        checker = load_checker()
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory) / "fixture"
            copy_boundary_fixture(fixture_root)
            flow_api = (
                fixture_root
                / "tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_api.py"
            )
            flow_api.write_text(
                flow_api.read_text(encoding="utf-8")
                + '\n@router.get("/unexpected")\nasync def unexpected() -> None:\n    return None\n',
                encoding="utf-8",
            )

            failures = checker.check(fixture_root)

        self.assertIn("unexpected L4 route: GET /v1/business-flows/unexpected", failures)

    def test_extra_l4_post_route_fails_the_audit(self) -> None:
        checker = load_checker()
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory) / "fixture"
            copy_boundary_fixture(fixture_root)
            flow_api = (
                fixture_root
                / "tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_api.py"
            )
            flow_api.write_text(
                flow_api.read_text(encoding="utf-8")
                + '\n@router.post("/unexpected")\nasync def unexpected_post() -> None:\n    return None\n',
                encoding="utf-8",
            )

            failures = checker.check(fixture_root)

        self.assertIn("unexpected L4 route: POST /v1/business-flows/unexpected", failures)

    def test_extra_l4_trace_route_fails_the_audit(self) -> None:
        checker = load_checker()
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory) / "fixture"
            copy_boundary_fixture(fixture_root)
            flow_api = (
                fixture_root
                / "tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_api.py"
            )
            flow_api.write_text(
                flow_api.read_text(encoding="utf-8")
                + '\n@router.trace("/unexpected")\nasync def unexpected_trace() -> None:\n    return None\n',
                encoding="utf-8",
            )

            failures = checker.check(fixture_root)

        self.assertIn("unexpected L4 route: TRACE /v1/business-flows/unexpected", failures)

    def test_missing_l4_router_mount_fails_the_audit(self) -> None:
        checker = load_checker()
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory) / "fixture"
            copy_boundary_fixture(fixture_root)
            api = fixture_root / "tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/api.py"
            api.write_text(
                api.read_text(encoding="utf-8").replace(
                    "app.include_router(_flow_api.router)", "# L4 flow router removed", 1
                ),
                encoding="utf-8",
            )

            failures = checker.check(fixture_root)

        self.assertIn("L4 api.py must mount _flow_api.router", failures)

    def test_missing_deferred_id_fails_the_audit(self) -> None:
        checker = load_checker()
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory) / "fixture"
            copy_boundary_fixture(fixture_root)
            ledger = fixture_root / "docs/design/EAASP/DEFERRED_LEDGER.md"
            ledger.write_text(
                ledger.read_text(encoding="utf-8").replace(
                    "V316-EVAL-OBSTACK-01", "REMOVED-EVAL-OBSTACK-01"
                ),
                encoding="utf-8",
            )

            failures = checker.check(fixture_root)

        self.assertIn("missing deferred item: V316-EVAL-OBSTACK-01", failures)

    def test_empty_deferred_trigger_or_owner_fails_the_audit(self) -> None:
        checker = load_checker()
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory) / "fixture"
            copy_boundary_fixture(fixture_root)
            ledger = fixture_root / "docs/design/EAASP/DEFERRED_LEDGER.md"
            ledger.write_text(
                ledger.read_text(encoding="utf-8")
                .replace(
                    "**Trigger:** grid-eval publishes a versioned OBSTACK input/output contract backed by real evaluation records.",
                    "**Trigger:** —",
                    1,
                )
                .replace("**Owner:** EAASP ecosystem/marketplace.", "**Owner:** —", 1),
                encoding="utf-8",
            )

            failures = checker.check(fixture_root)

        self.assertIn(
            "deferred item must declare a meaningful Trigger and Owner: V316-EVAL-OBSTACK-01",
            failures,
        )
        self.assertIn(
            "deferred item must declare a meaningful Trigger and Owner: V316-ECOSYSTEM-HEALTH-01",
            failures,
        )

    def test_rbac_comments_do_not_count_as_entries(self) -> None:
        checker = load_checker()
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory) / "fixture"
            copy_boundary_fixture(fixture_root)
            catalog = fixture_root / "crates/grid-server/src/rbac/catalog.rs"
            catalog.write_text(
                catalog.read_text(encoding="utf-8")
                + '\n// route!(Read, "GET", "/api/v1/business-flows")\n',
                encoding="utf-8",
            )

            failures = checker.check(fixture_root)

        self.assertEqual(failures, [])

    def test_rbac_fake_entry_and_count_drift_fail_the_audit(self) -> None:
        checker = load_checker()
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory) / "fixture"
            copy_boundary_fixture(fixture_root)
            catalog = fixture_root / "crates/grid-server/src/rbac/catalog.rs"
            catalog.write_text(
                catalog.read_text(encoding="utf-8").replace(
                    "];\n\npub fn route_catalog",
                    '    route!(Read, "GET", "/api/v1/business-flows"),\n];\n\npub fn route_catalog',
                    1,
                ),
                encoding="utf-8",
            )

            failures = checker.check(fixture_root)

        self.assertIn("grid-server RBAC must not contain a business-flow entry", failures)
        self.assertIn("grid-server RBAC catalog must contain exactly 134 entries (found 135)", failures)

    def test_rbac_count_drift_fails_the_audit(self) -> None:
        checker = load_checker()
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory) / "fixture"
            copy_boundary_fixture(fixture_root)
            catalog = fixture_root / "crates/grid-server/src/rbac/catalog.rs"
            catalog.write_text(
                catalog.read_text(encoding="utf-8").replace(
                    '    route!(ManageConfig, "POST", "/api/v1/admin/reload"),\n', "", 1
                ),
                encoding="utf-8",
            )

            failures = checker.check(fixture_root)

        self.assertIn("grid-server RBAC catalog must contain exactly 134 entries (found 133)", failures)

    def test_each_historical_section_requires_its_own_supersession_marker(self) -> None:
        checker = load_checker()
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory) / "fixture"
            copy_boundary_fixture(fixture_root)
            plan = fixture_root / "docs/superpowers/plans/2026-08-09-obstack-v3-15-6-completion.md"
            section_start = plan.read_text(encoding="utf-8").index("## v3.15.6e")
            before, section = (
                plan.read_text(encoding="utf-8")[:section_start],
                plan.read_text(encoding="utf-8")[section_start:],
            )
            plan.write_text(
                before + section.replace("**Superseded by active v3.16 plan:**", "**Historical projection:**", 1),
                encoding="utf-8",
            )

            failures = checker.check(fixture_root)

        self.assertIn("v3.15.6e must name the active v3.16 replacement", failures)
