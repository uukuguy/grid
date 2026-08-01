"""Tests for flow_api.py — v3.15.4b business flow REST + SSE routes.

Covers:
- /timeline decodes the path key, calls the aggregator, returns events
- /summary returns the rollup
- /evaluation returns the evaluator report
- /events/stream is a StreamingResponse with text/event-stream
- Malformed business key returns 400
- Empty business key returns 400
- Reads layer readers from app.state.flow_layer_readers
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from eaasp_common.business_flow import BusinessKey
from eaasp_l4_orchestration.flow_api import router
from eaasp_l4_orchestration.flow_sse import reset_flow_event_bus
from eaasp_l4_orchestration.flow_timeline import BusinessFlowEvent


# ─── Test scaffolding ──────────────────────────────────────────────────────


def _build_app(layer_readers: dict | None = None) -> FastAPI:
    """Build a fresh FastAPI app for each test with the flow router."""
    app = FastAPI()
    if layer_readers is not None:
        app.state.flow_layer_readers = layer_readers
    app.include_router(router)
    return app


def _wire_reader(events: list[BusinessFlowEvent]):
    """Build a LayerReader that returns the given events."""
    async def _impl(key: BusinessKey) -> list[BusinessFlowEvent]:
        del key
        return events
    return _impl


# ─── timeline ──────────────────────────────────────────────────────────────


def test_timeline_returns_events() -> None:
    reader = _wire_reader([
        BusinessFlowEvent(ts=1000, layer="L4", component="session", event_type="session.created", payload={"k": 1}),
        BusinessFlowEvent(ts=1500, layer="L4", component="session", event_type="session.closed", payload={"status": "closed"}),
    ])
    app = _build_app({"L4_sessions": reader})
    client = TestClient(app)
    key = BusinessKey(session_id="s1", skill_id="k1", business_object_id="d1").to_header()
    resp = client.get(f"/v1/business-flows/{key}/timeline")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert body["business_key"] == key
    assert [e["event_type"] for e in body["events"]] == ["session.created", "session.closed"]
    assert body["events"][0]["ts"] == 1000
    assert body["events"][0]["payload"] == {"k": 1}


def test_timeline_empty_when_no_readers() -> None:
    app = _build_app()
    client = TestClient(app)
    key = BusinessKey(session_id="s1").to_header()
    resp = client.get(f"/v1/business-flows/{key}/timeline")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["events"] == []


def test_timeline_malformed_key_returns_400() -> None:
    app = _build_app()
    client = TestClient(app)
    # Only one field — not three pipe-separated
    resp = client.get("/v1/business-flows/only_one_field/timeline")
    assert resp.status_code == 400
    assert "malformed business key" in resp.json()["detail"]


def test_timeline_empty_session_id_returns_400() -> None:
    """``||`` decodes to session_id="" which the BusinessKey validator rejects."""
    app = _build_app()
    client = TestClient(app)
    resp = client.get("/v1/business-flows/%7C%7C/timeline")
    assert resp.status_code == 400


# ─── summary ───────────────────────────────────────────────────────────────


def test_summary_returns_rollup() -> None:
    reader = _wire_reader([
        BusinessFlowEvent(ts=1000, layer="L4", component="session", event_type="session.created", payload={}),
        BusinessFlowEvent(ts=1500, layer="L4", component="session", event_type="session.closed", payload={"status": "closed"}),
    ])
    app = _build_app({"L4_sessions": reader})
    client = TestClient(app)
    key = BusinessKey(session_id="s1").to_header()
    resp = client.get(f"/v1/business-flows/{key}/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["status"] == "succeeded"
    assert body["summary"]["event_count"] == 2
    assert body["summary"]["total_duration_ms"] == 500
    assert body["summary"]["layer_counts"] == {"L4": 2}


# ─── evaluation ────────────────────────────────────────────────────────────


def test_evaluation_returns_report() -> None:
    reader = _wire_reader([
        BusinessFlowEvent(ts=1000, layer="L4", component="session", event_type="session.created", payload={}),
        BusinessFlowEvent(ts=1500, layer="L4", component="session", event_type="session.closed", payload={"status": "closed"}),
    ])
    app = _build_app({"L4_sessions": reader})
    client = TestClient(app)
    key = BusinessKey(session_id="s1").to_header()
    resp = client.get(f"/v1/business-flows/{key}/evaluation")
    assert resp.status_code == 200
    body = resp.json()
    # Single-flow evaluation: total_flows=1 < min_sample_size → info hint
    assert body["report"]["total_flows"] == 1
    assert any(h["severity"] == "info" for h in body["report"]["hints"])


# ─── SSE stream ────────────────────────────────────────────────────────────


def test_sse_stream_returns_streaming_response() -> None:
    """Verify the SSE route is registered with the right media type.

    We don't iterate the long-lived SSE generator (TestClient would
    block until the generator exits). Instead we look up the
    registered ``APIRoute`` and verify the endpoint source contains
    the expected ``StreamingResponse`` + ``text/event-stream``
    markers — a static check that's enough to confirm the contract.

    Per-event delivery is covered separately by ``test_flow_sse``.
    """
    import inspect

    from fastapi.routing import APIRoute

    route = None
    for r in router.routes:
        if isinstance(r, APIRoute) and r.path.endswith("/events/stream"):
            route = r
            break
    assert route is not None, "SSE route not registered"
    src = inspect.getsource(route.endpoint)
    assert "StreamingResponse" in src
    assert "text/event-stream" in src


def test_sse_stream_malformed_key_returns_400() -> None:
    app = _build_app()
    client = TestClient(app)
    resp = client.get("/v1/business-flows/just_one_part/events/stream")
    assert resp.status_code == 400
