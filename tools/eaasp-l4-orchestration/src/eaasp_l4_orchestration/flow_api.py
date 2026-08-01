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

from fastapi import APIRouter, HTTPException, Path, Request
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


__all__ = ["router"]
