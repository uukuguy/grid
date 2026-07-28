"""L5 Cowork CLI — ``eaasp-l5-cowork`` script entrypoint + subcommands.

v3.13.2 — EAASP Phase 5 — L5 Cowork 四卡 + 回溯闭环.

Subcommands:

- ``eaasp-l5-cowork serve`` — start the FastAPI backend.
- ``eaasp-l5-cowork trace <session_id>`` — RETROSPECTIVE-03.
  Print the four-card chain + cross_refs to stdout in
  human-readable form. Uses ``render_trace_human``.

The CLI does NOT depend on ``eaasp-cli-v2`` (D-37: no leg
coupling). It talks to the L5 Cowork backend over HTTP via
``httpx`` — same pattern L4 + L3 use, but the L5 CLI lives in
``eaasp-l5-cowork`` so D-30 (no shared crates) holds.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

import httpx

from .cowork import CoworkConfig, create_app
from .projection import CoworkProjection
from .retrospective import RetrospectiveTrace, render_trace_human
from .state import CoworkStateStore


def _default_base_url() -> str:
    host = os.environ.get("EAASP_L5_HOST", "127.0.0.1")
    port = os.environ.get("EAASP_L5_PORT", "18086")
    return f"http://{host}:{port}"


def _default_tenant() -> str:
    return os.environ.get(
        "EAASP_L5_TENANT",
        os.environ.get("EAASP_L5_DEFAULT_TENANT", "default"),
    )


async def _serve_async(args: argparse.Namespace) -> int:
    """Start the FastAPI backend via uvicorn (matches L4 pattern)."""
    import uvicorn

    cfg = CoworkConfig()
    app = create_app(config=cfg)
    host = args.host or os.environ.get("EAASP_L5_HOST", "127.0.0.1")
    port = args.port or cfg.port
    uvicorn.run(
        app, host=host, port=port, log_level="info", access_log=False
    )
    return 0


async def _trace_async(args: argparse.Namespace) -> int:
    """Print the retrospective chain for ``session_id`` to stdout.

    RETROSPECTIVE-03 — the CLI is the threshold-calibration
    equivalent for L5 (D-34). Two output modes:

    - ``--json`` — print the full chain as JSON (for piping).
    - default — print the human-readable rendering
      (render_trace_human).

    The CLI can also run offline by reading the local L2 / L3 /
    L4 DBs directly (when ``--offline`` is set). This is the
    Phase 0.5 MVP "executable floor" (D-34) — operators can
    trace a session without bringing up the L5 backend.
    """
    base_url = args.base_url or _default_base_url()
    tenant = args.tenant or _default_tenant()

    if args.offline:
        # Offline mode — read L2 / L3 / L4 DBs directly, run
        # RetrospectiveTrace in-process.
        proj = CoworkProjection()
        store = CoworkStateStore(
            os.environ.get("EAASP_L5_STATE_DB_PATH", "./data/cowork.db")
        )
        trace = RetrospectiveTrace(proj, state_store=store)
        chain = await trace.trace_session(
            args.session_id, tenant_id=tenant
        )
        if args.json:
            import json as _json

            print(_json.dumps(chain.to_dict(), indent=2))
        else:
            print(render_trace_human(chain))
        return 0

    # Online mode — HTTP GET against the L5 backend.
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            f"{base_url}/v1/cowork/trace/{args.session_id}",
            params={"tenant_id": tenant},
            headers={"X-Tenant-Id": tenant},
        )
        if r.status_code != 200:
            print(
                f"eaasp-l5-cowork: HTTP {r.status_code} "
                f"session_id={args.session_id} tenant={tenant}",
                file=sys.stderr,
            )
            try:
                print(r.text, file=sys.stderr)
            except Exception:
                pass
            return 1 if r.status_code >= 500 else 2

        if args.json:
            print(r.text)
        else:
            data = r.json()
            # Re-render via render_trace_human so the CLI output
            # matches the offline path exactly.
            from .cards import (
                ActionCard,
                ApprovalCard,
                EvidenceCard,
                EventCard,
            )
            from .retrospective import RetrospectiveChain

            chain = RetrospectiveChain(
                session_id=data["session_id"],
                tenant_id=data["tenant_id"],
                events=[EventCard(**{k: v for k, v in e.items() if k in EventCard.__dataclass_fields__})
                        for e in data["events"]],
                evidence=[EvidenceCard(**{k: v for k, v in e.items() if k in EvidenceCard.__dataclass_fields__})
                          for e in data["evidence"]],
                actions=[ActionCard(**{k: v for k, v in a.items() if k in ActionCard.__dataclass_fields__})
                         for a in data["actions"]],
                approvals=[ApprovalCard(**{k: v for k, v in ap.items() if k in ApprovalCard.__dataclass_fields__})
                           for ap in data["approvals"]],
            )
            # cross_refs — leave the dict form for re-render.
            from .retrospective import CrossRef as _CR

            chain.cross_refs = [
                _CR(
                    source_card_id=r["source_card_id"],
                    target_card_id=r["target_card_id"],
                    kind=r["kind"],
                    rationale=r.get("rationale", ""),
                )
                for r in data["cross_refs"]
            ]
            print(render_trace_human(chain))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eaasp-l5-cowork",
        description=(
            "EAASP v2.0 L5 Cowork backend + trace CLI "
            "(v3.13 — EAASP Phase 5)"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="Start the L5 Cowork backend")
    p_serve.add_argument("--host", default=None)
    p_serve.add_argument("--port", type=int, default=None)
    p_serve.set_defaults(_handler=_serve_async)

    p_trace = sub.add_parser(
        "trace",
        help=(
            "Print the retrospective chain for a session "
            "(RETROSPECTIVE-03)"
        ),
    )
    p_trace.add_argument("session_id")
    p_trace.add_argument(
        "--base-url", default=None, help="L5 backend URL (default: env)"
    )
    p_trace.add_argument(
        "--tenant",
        default=None,
        help="Tenant ID (X-Tenant-Id + ?tenant_id=)",
    )
    p_trace.add_argument(
        "--offline",
        action="store_true",
        help="Read L2/L3/L4 DBs in-process; do not call the L5 backend",
    )
    p_trace.add_argument(
        "--json",
        action="store_true",
        help="Print the full chain as JSON",
    )
    p_trace.set_defaults(_handler=_trace_async)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "_handler", None)
    if handler is None:
        parser.print_help()
        return 1
    coro = handler(args)
    try:
        return _run_async(coro)
    finally:
        if not coro.cr_running:
            coro.close()


def _run_async(coro):
    """Run ``coro`` on a fresh loop when no loop is running.

    When called from inside an existing event loop (e.g. a
    pytest async test), spin a fresh loop on a worker thread so
    ``asyncio.run`` doesn't fail with "asyncio.run() cannot be
    called from a running event loop".
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


if __name__ == "__main__":
    raise SystemExit(main())
