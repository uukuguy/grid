"""``eaasp flow`` subcommand — v3.15.4d business-flow access.

Per PLATFORM_OBSERVABILITY_DESIGN.md §3.5 / §3.6. Provides the
end-user CLI surface for the cross-layer business-flow module:

- ``eaasp flow timeline --key <key>`` — print the cross-layer timeline
- ``eaasp flow summary --key <key>`` — print the flow rollup
- ``eaasp flow watch --key <key>`` — SSE subscribe; print each new event
- ``eaasp flow evaluate --key <key>`` — single-flow evaluation report

The CLI is a thin wrapper over the L4 REST API (see
``eaasp-l4-orchestration/flow_api.py``). The wire format for the
business key is the same ``"session|skill|object"`` format used by
the ``X-Business-Key`` header.

Implementation follows the existing CLI command pattern (sync
``typer`` entrypoint wraps an ``async def _do()`` that uses
``run_async`` from ``main.py``). The SSE-based ``watch`` is a
special case — it uses ``httpx.stream`` and exits on Ctrl-C.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import typer

from .client import CliError
from .config import CliConfig
from .output import print_error, print_json, print_table


def _run_async(coro: Any) -> Any:
    """Local wrapper that defers the ``main`` import to call time.

    Importing ``main`` at module top causes a circular import (main
    imports all cmd_* modules to register them on the typer app).
    The deferred lookup happens at command invocation time, by
    which point the package is fully initialized.
    """
    from . import main as _main

    return _main.run_async(coro)

app = typer.Typer(
    name="flow",
    help="Business-flow timeline / summary / SSE watch / evaluation",
    no_args_is_help=True,
)


def _key_callback(value: str) -> str:
    """Trim the value; the wire format itself is validated by the L4 server."""
    if not value or not value.strip():
        raise typer.BadParameter("business key must be non-empty")
    return value.strip()


_KEY_ARG = typer.Option(
    ...,
    "--key",
    "-k",
    help='Wire-encoded business key: "session_id|skill_id|business_object_id"',
    callback=_key_callback,
)


def _format_event_row(ev: dict[str, Any]) -> dict[str, Any]:
    return {
        "ts": ev.get("ts"),
        "layer": ev.get("layer"),
        "component": ev.get("component"),
        "event_type": ev.get("event_type"),
        "duration_ms": ev.get("duration_ms"),
        "error": ev.get("error"),
    }


async def _fetch_timeline(cfg: CliConfig, key: str) -> list[dict[str, Any]]:
    from . import main as _main

    client = _main.make_client(cfg)
    url = f"{cfg.l4_url.rstrip('/')}/v1/business-flows/{key}/timeline"
    body = await client.call("GET", url)
    return list(body.get("events", []))


async def _fetch_json(cfg: CliConfig, key: str, sub: str) -> Any:
    from . import main as _main

    client = _main.make_client(cfg)
    url = f"{cfg.l4_url.rstrip('/')}/v1/business-flows/{key}/{sub}"
    body = await client.call("GET", url)
    return body


@app.command("timeline")
def timeline(key: str = _KEY_ARG) -> None:
    """Print the cross-layer timeline for one business key."""
    cfg = CliConfig.from_env()

    async def _do() -> list[dict[str, Any]]:
        return await _fetch_timeline(cfg, key)

    events = _run_async(_do())
    if not events:
        typer.echo(f"(no events for {key})")
        raise typer.Exit(0)
    print_table(
        f"Business flow timeline: {key}",
        [_format_event_row(e) for e in events],
        ["ts", "layer", "component", "event_type", "duration_ms", "error"],
    )


@app.command("summary")
def summary(key: str = _KEY_ARG) -> None:
    """Print the flow summary (status, duration, layer counts)."""
    cfg = CliConfig.from_env()

    async def _do() -> Any:
        return await _fetch_json(cfg, key, "summary")

    body = _run_async(_do())
    print_json(body.get("summary", {}))


@app.command("evaluate")
def evaluate(key: str = _KEY_ARG) -> None:
    """Print the single-flow evaluation report (with optimization hints)."""
    cfg = CliConfig.from_env()

    async def _do() -> Any:
        return await _fetch_json(cfg, key, "evaluation")

    body = _run_async(_do())
    print_json(body.get("report", {}))


@app.command("watch")
def watch(
    key: str = _KEY_ARG,
    base_url: str = typer.Option(
        None,
        "--url",
        help="Override the L4 base URL (default: from CLI config)",
    ),
) -> None:
    """Subscribe to the SSE channel for a business key and print each new event.

    Blocks until Ctrl-C. Each ``data:`` line is parsed as JSON and
    printed as a one-line summary. Connection errors are surfaced
    via ``print_error`` and the process exits with a non-zero code.
    """
    cfg = CliConfig.from_env()
    url = (base_url or cfg.l4_url).rstrip("/")
    sse_url = f"{url}/v1/business-flows/{key}/events/stream"
    typer.echo(f"# subscribing to {sse_url} (Ctrl-C to quit)")
    try:
        with httpx.stream("GET", sse_url, timeout=None) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload = line[len("data: "):].strip()
                if not payload:
                    continue
                try:
                    obj = json.loads(payload)
                except json.JSONDecodeError:
                    typer.echo(line)
                    continue
                row = _format_event_row(obj)
                typer.echo(
                    f"[{row['ts']}] {row['layer']}/{row['component']} "
                    f"{row['event_type']} dur={row['duration_ms']}"
                )
    except KeyboardInterrupt:
        typer.echo("\n# interrupted")
    except httpx.HTTPError as exc:
        print_error(CliError(1, f"SSE connection failed: {exc}"))
        raise typer.Exit(1) from exc
