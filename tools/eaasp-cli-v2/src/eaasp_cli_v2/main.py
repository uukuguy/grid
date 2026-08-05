"""Typer root app for the EAASP v2.0 developer CLI."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

import typer

from . import cmd_flow, cmd_memory, cmd_policy, cmd_session, cmd_skill
from .client import CliError, ServiceClient
from .config import CliConfig
from .output import print_error

app = typer.Typer(
    name="eaasp",
    help="EAASP v2.0 Developer CLI",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(cmd_session.app, name="session", help="Session lifecycle commands")
app.add_typer(cmd_memory.app, name="memory", help="L2 memory engine queries")
app.add_typer(cmd_skill.app, name="skill", help="Skill registry commands")
app.add_typer(cmd_policy.app, name="policy", help="L3 policy management")
app.add_typer(cmd_flow.app, name="flow", help="Business flow timeline / summary / watch / evaluate")


# ─── Client factory injection ─────────────────────────────────────────────
# Tests monkeypatch this to swap in a client that wraps an httpx.MockTransport.

_ClientFactory = Callable[[CliConfig], ServiceClient]
_client_factory: _ClientFactory = ServiceClient.from_config

# Phase D.4 — ObstackClient (shared with web) also accepts an
# injectable http_getter. Tests use the same MockTransport via
# ``_obstack_http_getter``; production leaves it None and the client
# falls back to its built-in urllib transport.
_obstack_http_getter: "Any | None" = None


def set_client_factory(factory: _ClientFactory) -> None:
    """Install a ServiceClient factory (used by tests)."""
    global _client_factory
    _client_factory = factory


def make_client(cfg: CliConfig | None = None) -> ServiceClient:
    """Return a new ServiceClient bound to the given config (or env)."""
    return _client_factory(cfg or CliConfig.from_env())


def run_async(coro: Any) -> Any:
    """Execute an async coroutine and map ``CliError`` to ``typer.Exit``."""
    try:
        return asyncio.run(coro)
    except CliError as err:
        print_error(err)
        raise typer.Exit(err.exit_code) from err
