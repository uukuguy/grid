"""V315-CLI-IMPORT-FIX-01 — circular-import regression tests.

Pre-fix behaviour: importing ``eaasp_cli_v2.main`` first would succeed
but ``eaasp_cli_v2.cmd_memory`` (and the other cmd_* modules that did
``from . import main as _main`` at module top) would raise
``AttributeError: partially initialized module ... has no attribute
'app'`` because ``main.py`` imports them at module load time.

Post-fix: every cmd_* module uses the deferred-import helper pattern
(see ``cmd_flow.py`` for the canonical implementation). All 5 cmd_*
modules must import cleanly in any order without raising.
"""

from __future__ import annotations

import importlib
import sys

import pytest


# Always start each test with a clean import cache for the package,
# so previous test runs don't mask a fresh cycle.
@pytest.fixture(autouse=True)
def _reset_pkg_imports():
    pkg_prefix = "eaasp_cli_v2"
    to_drop = [k for k in sys.modules if k == pkg_prefix or k.startswith(pkg_prefix + ".")]
    for k in to_drop:
        del sys.modules[k]
    yield
    to_drop = [k for k in sys.modules if k == pkg_prefix or k.startswith(pkg_prefix + ".")]
    for k in to_drop:
        del sys.modules[k]


# ─── Per-module import smoke tests ──────────────────────────────────────────


@pytest.mark.parametrize(
    "module_name",
    [
        "eaasp_cli_v2.main",
        "eaasp_cli_v2.cmd_flow",
        "eaasp_cli_v2.cmd_memory",
        "eaasp_cli_v2.cmd_policy",
        "eaasp_cli_v2.cmd_skill",
        "eaasp_cli_v2.cmd_session",
    ],
)
def test_module_imports_without_error(module_name: str) -> None:
    """Every cmd_* module + main must import cleanly."""
    importlib.import_module(module_name)


def test_main_then_cmd_memory_order() -> None:
    """The historical failure mode: importing ``main`` then ``cmd_memory``.

    Pre-fix this raised ``AttributeError: partially initialized module
    'eaasp_cli_v2.cmd_memory' ... has no attribute 'app'`` because the
    top-level ``from . import main as _main`` in ``cmd_memory`` ran
    while ``main.py`` was still being initialised.
    """
    importlib.import_module("eaasp_cli_v2.main")
    importlib.import_module("eaasp_cli_v2.cmd_memory")


def test_cmd_memory_then_main_order() -> None:
    """Reverse order also must work (CLI bootstrap may load cmd first)."""
    importlib.import_module("eaasp_cli_v2.cmd_memory")
    importlib.import_module("eaasp_cli_v2.main")


def test_all_commands_registered() -> None:
    """After import, the typer app must expose all 5 subcommand groups."""
    main = importlib.import_module("eaasp_cli_v2.main")
    groups = {g.name for g in main.app.registered_groups}
    assert groups == {"session", "memory", "skill", "policy", "flow"}, groups
