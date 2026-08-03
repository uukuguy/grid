"""Business Flow REST + SSE API — v3.15.4b.

Per OBSTACK_DESIGN.md §3.5 / §3.6. Three endpoints:

- ``GET  /v1/business-flows/{key}/timeline`` — full cross-layer timeline
  (JSON array of ``BusinessFlowEvent``)
- ``GET  /v1/business-flows/{key}/summary``  — flow rollup (status, duration,
  layer counts, interrupted layer)
- ``GET  /v1/business-flows/{key}/events/stream`` — SSE channel that
  pushes new events for the key in real time

Wiring
------

The router is a plain ``fastapi.APIRouter`` so the L4 ``api.py`` can
``app.include_router(flow_api.router)`` once. The router pulls layer
readers from ``app.state.flow_layer_readers`` (a dict) and the
``FlowEventBus`` singleton from ``flow_sse.get_flow_event_bus()``.

The ``business_key`` URL path is the wire-encoded string
(``"session|skill|object"``). The router decodes via
``eaasp_common.business_flow.parse_business_key_header`` — the same
parser used by the in-process helpers — so the wire format is
defined in exactly one place.

Strict-by-default (per ADR-V2-028): no silent fallback when the
business key is missing or malformed; the endpoint returns 400 with
a clear error. The L4 server has no concept of "an anonymous
business flow" (that would defeat the whole point of the design).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse

from eaasp_common.business_flow import (
    BusinessKey,
    parse_business_key_header,
)

from .flow_evaluator import FlowEvaluationReport, evaluate_business_flows
from .flow_sse import FlowEventBus, get_flow_event_bus, subscribe_to_business_flow
from .flow_timeline import (
    BusinessFlowEvent,
    LayerReader,
    assemble_business_flow_summary,
    assemble_business_flow_timeline,
)

logger = logging.getLogger(__name__)

# Path parameter name — matches the wire-format of the business key
# (3 pipe-separated fields; see eaasp_common.business_flow).
_KEY_PATH_PARAM = "key"

# URL prefix — kept identical to the L4 server's /v1 namespace.
_PREFIX = "/v1/business-flows"


# ─── Helpers ────────────────────────────────────────────────────────────────


def _decode_key(raw: str) -> BusinessKey:
    """Decode a path-parameter business key, or raise HTTP 400.

    The key is the same wire format used by the ``X-Business-Key``
    header (``"session|skill|object"``). Decoding in one place keeps
    the parser a single source of truth.
    """
    try:
        parsed = parse_business_key_header(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"malformed business key: {exc}",
        ) from exc
    if parsed is None:
        raise HTTPException(
            status_code=400,
            detail="business key is empty",
        )
    return parsed


def _get_layer_readers(request: Request) -> dict[str, LayerReader]:
    """Pull the per-layer readers wired by the L4 app at boot."""
    readers = getattr(request.app.state, "flow_layer_readers", None)
    if readers is None:
        return {}
    return dict(readers)


# ─── Routes ─────────────────────────────────────────────────────────────────


router = APIRouter(prefix=_PREFIX, tags=["business-flow"])


@router.get(f"/{{{_KEY_PATH_PARAM}}}/timeline")
async def get_business_flow_timeline(
    request: Request,
    key: str = Path(..., description="Wire-encoded business key: session\\|skill\\|object"),
) -> dict[str, Any]:
    """Return the cross-layer timeline for one business key.

    The response body is a JSON object with two fields:
    - ``events``: ordered list of ``BusinessFlowEvent`` dicts
    - ``count``: number of events returned (convenience for clients)
    """
    business_key = _decode_key(key)
    readers = _get_layer_readers(request)
    events = await assemble_business_flow_timeline(business_key, layer_readers=readers)
    return {
        "business_key": business_key.to_header(),
        "events": [e.to_dict() for e in events],
        "count": len(events),
    }


@router.get(f"/{{{_KEY_PATH_PARAM}}}/summary")
async def get_business_flow_summary(
    request: Request,
    key: str = Path(..., description="Wire-encoded business key: session\\|skill\\|object"),
) -> dict[str, Any]:
    """Return the flow summary (status / duration / layer counts)."""
    business_key = _decode_key(key)
    readers = _get_layer_readers(request)
    summary = await assemble_business_flow_summary(business_key, layer_readers=readers)
    return {
        "business_key": business_key.to_header(),
        "summary": summary.to_dict(),
    }


@router.get(f"/{{{_KEY_PATH_PARAM}}}/events/stream")
async def stream_business_flow_events(
    key: str = Path(..., description="Wire-encoded business key: session\\|skill\\|object"),
) -> StreamingResponse:
    """SSE channel for one business key.

    Subscribes to the process-wide ``FlowEventBus`` and forwards each
    event to the wire as ``data: <json>\\n\\n`` lines. The client
    disconnects by closing the connection (the generator's
    ``finally`` cleans up the bus subscription).

    The endpoint is intentionally minimal — no auth, no rate limit,
    no event filtering. Auth is added at the L4 gateway level (per
    the existing v3.13 contract) and event filtering is a v3.16+
    follow-on.
    """
    business_key = _decode_key(key)
    bus: FlowEventBus = get_flow_event_bus()

    async def event_stream() -> AsyncIterator[bytes]:
        async with subscribe_to_business_flow(bus, business_key) as sub:
            try:
                while True:
                    # ``wait_for`` keeps the connection responsive to
                    # client disconnect; a 30s heartbeat would be a
                    # v3.16+ follow-on.
                    event: BusinessFlowEvent = await sub.queue.get()
                    payload = json.dumps(event.to_dict(), default=str)
                    yield f"data: {payload}\n\n".encode("utf-8")
            except asyncio.CancelledError:
                # Client disconnected — let the context manager clean up.
                raise

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get(f"/{{{_KEY_PATH_PARAM}}}/evaluation")
async def get_business_flow_evaluation(
    request: Request,
    key: str = Path(..., description="Wire-encoded business key: session\\|skill\\|object"),
) -> dict[str, Any]:
    """Return the cross-layer evaluation report for this business key.

    Aggregates the timeline into a ``BusinessFlowSummary`` and runs
    the evaluator on it. The report includes completion rate,
    per-layer interruption heatmap, and ranked optimization hints.
    """
    business_key = _decode_key(key)
    readers = _get_layer_readers(request)
    summary = await assemble_business_flow_summary(business_key, layer_readers=readers)
    # The evaluator works on a sequence; one-flow evaluation is just
    # that sequence of length 1. This is the most useful "what does
    # the platform think of this single business request?" view.
    report: FlowEvaluationReport = evaluate_business_flows([summary])
    return {
        "business_key": business_key.to_header(),
        "report": report.to_dict(),
    }


@router.get(f"/{{{_KEY_PATH_PARAM}}}/sessions")
async def get_sessions_for_business_flow(
    request: Request,
    key: str = Path(..., description="Wire-encoded business key: session\\|skill\\|object"),
) -> dict[str, Any]:
    """Return the list of session_ids tagged with this business key.

    V315-BUSINESS-FLOW-02: enables callers to correlate a timeline
    back to its constituent sessions. Reads directly from the L4
    ``sessions`` table via the lifespan-wired ``l4_db_conn`` (so the
    route works even when LayerReader aggregation is skipped).
    """
    import aiosqlite

    business_key = _decode_key(key)
    wire = business_key.to_header()
    conn = getattr(request.app.state, "l4_db_conn", None)
    if conn is None:
        # No DB wired (e.g. test app without lifespan). Return empty.
        return {
            "business_key": wire,
            "session_ids": [],
            "count": 0,
        }
    try:
        cur = await conn.execute(
            "SELECT session_id, status, created_at FROM sessions "
            "WHERE business_key = ? ORDER BY created_at",
            (wire,),
        )
        rows = await cur.fetchall()
    except aiosqlite.OperationalError:
        # Column missing on a pre-migration DB; return empty so the
        # endpoint stays useful (timeline readers still surface events).
        return {
            "business_key": wire,
            "session_ids": [],
            "count": 0,
        }
    session_ids = [
        {
            "session_id": r["session_id"],
            "status": r["status"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    return {
        "business_key": wire,
        "session_ids": session_ids,
        "count": len(session_ids),
    }


@router.get("/list")
async def list_business_flows(
    request: Request,
    limit: int = Query(default=20, ge=1, le=200),
    business_object_id: str | None = Query(
        default=None,
        description="Optional filter — match the third pipe-segment of business_key",
    ),
    status: str | None = Query(
        default=None,
        description="Optional filter — session status (created/active/closed/failed)",
    ),
) -> dict[str, Any]:
    """List all distinct business flows across the L4 sessions table.

    Phase C.0 — V315-OBSTACK-DEMO Phase C.0 (dashboard 入口):
    Phase C 路线图第一步 — 让运营者打开浏览器就能看到所有业务流,
    不需要先有 business_key 也不用 `eaasp flow` CLI。

    返回每个 distinct business_key 的摘要(最近一次 session 的状态 +
    event_count + duration)。多租户升级路径:加 ``tenant_id`` 参数即可,
    当前 schema 不变。
    """
    import aiosqlite

    conn = getattr(request.app.state, "l4_db_conn", None)
    if conn is None:
        # No DB wired (e.g. test app without lifespan). Return empty.
        return {"flows": [], "total": 0}

    # Build WHERE clauses dynamically (parameterized).
    where_clauses: list[str] = ["business_key IS NOT NULL"]
    params: list[Any] = []
    # Note: business_object_id filter is applied in Python (after the
    # SQL fetch) because SQLite's INSTR() doesn't accept a 3rd arg for
    # the second-separator offset. Dataset is bounded by ``limit`` <= 200
    # so the Python-side filter is fast enough for dashboard use.
    if status is not None:
        where_clauses.append("status = ?")
        params.append(status)

    where_sql = " AND ".join(where_clauses)
    sql = (
        "SELECT business_key, "
        "COUNT(*) AS session_count, "
        "MAX(created_at) AS last_started_at, "
        "MAX(closed_at) AS last_completed_at, "
        "SUM(CASE WHEN status IN ('closed', 'failed') THEN 1 ELSE 0 END) AS finished_count, "
        "SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_count "
        f"FROM sessions WHERE {where_sql} "
        "GROUP BY business_key "
        "ORDER BY last_started_at DESC "
        "LIMIT ?"
    )
    params.append(limit)

    try:
        cur = await conn.execute(sql, tuple(params))
        rows = await cur.fetchall()
    except aiosqlite.OperationalError:
        # Column missing on a pre-migration DB; return empty so the
        # endpoint stays useful (timeline readers still surface events).
        return {"flows": [], "total": 0}

    flows: list[dict[str, Any]] = []
    for r in rows:
        bk = r["business_key"]
        last_started = r["last_started_at"]
        last_completed = r["last_completed_at"]
        # Parse the wire format (session|skill|object) once per row.
        parts = bk.split("|", 2) if bk else ["", "", ""]
        row_object_id = parts[2] if len(parts) >= 3 else ""

        # Python-side filter on business_object_id (avoids the SQLite
        # INSTR 3-arg limitation; dataset is bounded by ``limit`` <= 200
        # so this is fast enough for the dashboard use case).
        if business_object_id is not None and row_object_id != business_object_id:
            continue

        flows.append({
            "business_key": bk,
            "business_object_id": row_object_id,
            "skill_id": parts[1] if len(parts) >= 2 else "",
            "session_id": parts[0] if len(parts) >= 1 else "",
            "session_count": r["session_count"],
            "finished_count": r["finished_count"],
            "failed_count": r["failed_count"],
            "last_started_at": last_started,
            "last_completed_at": last_completed,
            "last_duration_ms": (
                (last_completed - last_started) * 1000
                if last_started is not None and last_completed is not None
                else None
            ),
            # Per-row status: dominant status across all sessions for
            # this business_key (simplified — clients can drill into
            # /sessions for exact per-session status).
            "status": (
                "failed" if r["failed_count"] > 0
                else "closed" if r["finished_count"] > 0
                else "active"
            ),
        })

    # Total = sum of session_count across rows (not row count) — gives
    # operators the absolute number of business-flow instances seen.
    total_sessions = sum(f["session_count"] for f in flows)
    return {"flows": flows, "total": total_sessions}


__all__ = ["router"]
