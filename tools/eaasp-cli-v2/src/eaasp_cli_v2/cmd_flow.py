"""``eaasp flow`` subcommand — v3.15.4d business-flow access.

Per OBSTACK_DESIGN.md §3.5 / §3.6. Provides the
end-user CLI surface for the cross-layer business-flow module:

- ``eaasp flow timeline --key <key>`` — print the cross-layer timeline
- ``eaasp flow summary --key <key>`` — print the flow rollup
- ``eaasp flow watch --key <key>`` — SSE subscribe; print each new event
- ``eaasp flow evaluate --key <key>`` — single-flow evaluation report

Phase D.4 — this subcommand now uses the shared eaasp-obstack-client
(tools/eaasp-common/eaasp_common/obstack_client.py) instead of
hand-rolled URL composition. The 1:1 mirror with the web's
ObstackClient (web/src/api/obstack_types.ts) means CLI and web are
guaranteed to use the same wire format / query semantics.

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

from eaasp_common import FlowListParams, ObstackClientError

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

_MAX_FLOW_LIMIT = 200


def _limit_callback(value: int) -> int:
    """Validate the bounded list window accepted by the L4 flow API."""
    if not 1 <= value <= _MAX_FLOW_LIMIT:
        raise typer.BadParameter("limit must be between 1 and 200")
    return value


_LIMIT_OPT = typer.Option(
    20,
    "--limit",
    min=1,
    max=_MAX_FLOW_LIMIT,
    callback=_limit_callback,
    help="Maximum number of rows to display (1-200)",
)

_FLOW_COLUMNS = [
    "business_key",
    "status",
    "failed_count",
    "last_started_at",
    "last_duration_ms",
]


def _format_event_row(ev: dict[str, Any]) -> dict[str, Any]:
    return {
        "ts": ev.get("ts"),
        "layer": ev.get("layer"),
        "component": ev.get("component"),
        "event_type": ev.get("event_type"),
        "duration_ms": ev.get("duration_ms"),
        "error": ev.get("error"),
    }


def _format_flow_row(flow: Any) -> dict[str, Any]:
    """Flatten a shared-client business-flow summary for table rendering."""
    return {
        "business_key": flow.business_key,
        "status": flow.status,
        "failed_count": flow.failed_count,
        "last_started_at": flow.last_started_at,
        "last_duration_ms": flow.last_duration_ms,
    }


async def _fetch_flows(
    cfg: CliConfig,
    params: FlowListParams,
) -> list[Any]:
    """Fetch flow rows through the shared OBSTACK client."""
    from . import main as _main
    from eaasp_common import ObstackClient as _ObstackClient
    import asyncio

    getter = getattr(_main, "_obstack_http_getter", None)
    client = _ObstackClient(
        base_url=cfg.l4_url,
        auth_token=None,
        http_getter=getter,
    )
    try:
        response = await asyncio.to_thread(client.list_business_flows, params)
    except ObstackClientError as exc:
        if 400 <= exc.status < 500:
            exit_code = 2
        elif exc.status >= 500:
            exit_code = 4
        else:
            exit_code = 3
        raise CliError(exit_code, exc.message) from exc
    return response.flows


async def _fetch_timeline(cfg: CliConfig, key: str) -> list[dict[str, Any]]:
    """Phase D.4 — use the shared eaasp-obstack-client instead of
    hand-rolled URL composition.

    The client is sync; we run it in a worker thread so the asyncio
    loop isn't blocked. The install_mock fixture can also inject a
    custom ``_obstack_http_getter`` on ``cli_main`` to intercept the
    network call (the ObstackClient accepts an injectable
    http_getter for tests).
    """
    from . import main as _main
    from eaasp_common import ObstackClient as _ObstackClient
    import asyncio
    getter = getattr(_main, "_obstack_http_getter", None)
    client = _ObstackClient(
        base_url=cfg.l4_url,
        auth_token=None,
        http_getter=getter,
    )
    resp = await asyncio.to_thread(client.get_timeline, key)
    return [
        {
            "ts": ev.ts,
            "layer": ev.layer,
            "component": ev.component,
            "event_type": ev.event_type,
            "payload": ev.payload,
            "duration_ms": ev.duration_ms,
            "error": ev.error,
        }
        for ev in resp.events
    ]


async def _fetch_json(cfg: CliConfig, key: str, sub: str) -> Any:
    """Phase D.4 — same shared client; the ``sub`` segment picks
    which endpoint the dispatcher returns. Sync client called via
    asyncio.to_thread (the client itself is sync; we keep the CLI
    async-shape so existing handlers stay ``async def``).
    """
    from . import main as _main
    from eaasp_common import ObstackClient as _ObstackClient
    import asyncio
    getter = getattr(_main, "_obstack_http_getter", None)
    client = _ObstackClient(
        base_url=cfg.l4_url,
        auth_token=None,
        http_getter=getter,
    )
    if sub == "summary":
        resp = await asyncio.to_thread(client.get_summary, key)
        return {"summary": resp.summary.__dict__}
    if sub == "evaluation":
        resp = await asyncio.to_thread(client.get_evaluation, key)
        return {"report": resp.report.__dict__}
    if sub == "sessions":
        resp = await asyncio.to_thread(client.get_sessions, key)
        return {
            "session_ids": [s.__dict__ for s in resp.session_ids],
            "count": resp.count,
        }
    raise ValueError(f"unsupported sub: {sub}")


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


@app.command("list")
def list_flows(
    limit: int = _LIMIT_OPT,
    status: str | None = typer.Option(None, "--status"),
    business_object_id: str | None = typer.Option(None, "--business-object-id"),
) -> None:
    """List business flows, optionally filtering by status or object ID."""
    cfg = CliConfig.from_env()

    async def _do() -> list[Any]:
        return await _fetch_flows(
            cfg,
            FlowListParams(
                limit=limit,
                status=status,
                business_object_id=business_object_id,
            ),
        )

    flows = _run_async(_do())
    if not flows:
        typer.echo("(no business flows)")
        raise typer.Exit(0)
    print_table("Business flows", [_format_flow_row(flow) for flow in flows], _FLOW_COLUMNS)


@app.command("top-failed")
def top_failed(limit: int = _LIMIT_OPT) -> None:
    """Show the most failure-prone flows from the bounded candidate window."""
    cfg = CliConfig.from_env()

    async def _do() -> list[Any]:
        return await _fetch_flows(
            cfg,
            FlowListParams(limit=_MAX_FLOW_LIMIT, status="failed"),
        )

    flows = _run_async(_do())
    ranked = sorted(
        flows,
        key=lambda flow: (flow.failed_count, flow.last_started_at or -1),
        reverse=True,
    )[:limit]
    if not ranked:
        typer.echo("(no failed flows)")
        raise typer.Exit(0)
    print_table(
        "Top failed business flows",
        [_format_flow_row(flow) for flow in ranked],
        _FLOW_COLUMNS,
    )


@app.command("top-slow")
def top_slow(limit: int = _LIMIT_OPT) -> None:
    """Show the slowest flows with a measured most-recent duration."""
    cfg = CliConfig.from_env()

    async def _do() -> list[Any]:
        return await _fetch_flows(cfg, FlowListParams(limit=_MAX_FLOW_LIMIT))

    flows = _run_async(_do())
    ranked = sorted(
        (flow for flow in flows if flow.last_duration_ms is not None),
        key=lambda flow: flow.last_duration_ms,
        reverse=True,
    )[:limit]
    if not ranked:
        typer.echo("(no slow flows)")
        raise typer.Exit(0)
    print_table(
        "Top slow business flows",
        [_format_flow_row(flow) for flow in ranked],
        _FLOW_COLUMNS,
    )


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
