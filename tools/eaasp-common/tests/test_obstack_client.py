"""eaasp-obstack-client tests — verify the Python client wraps the
L4 /v1/business-flows/* surface 1:1 and raises ObstackClientError on
non-2xx.

Phase D.2 (eaasp-obstack-client extraction). These tests don't hit
a real L4 — they mock the HTTP getter so they can run in CI without
the EAASP backend up.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from eaasp_common import (
    BusinessFlowListResponse,
    BusinessFlowSummary,
    EvaluationReport,
    EvaluationResponse,
    FlowListParams,
    ObstackClient,
    ObstackClientError,
    SessionRef,
    SessionsResponse,
    SummaryBlock,
    SummaryResponse,
    TimelineEvent,
    TimelineResponse,
)


# ─── Mock HTTP helper ─────────────────────────────────────────


def _make_fake_getter(responses: dict[str, Any]):
    """Return an ``http_getter`` that maps URL → canned response body.

    Any URL not in the map raises a KeyError so the test fails loudly
    on a typo.
    """

    def fake_get(url: str, headers: dict[str, str]) -> dict[str, Any]:
        if url not in responses:
            raise KeyError(f"unexpected URL: {url}")
        return responses[url]

    return fake_get


# ─── Models parse correctly ────────────────────────────────────


def test_business_flow_summary_from_dict() -> None:
    raw = {
        "business_key": "sess-1|skill-x|obj-z",
        "business_object_id": "obj-z",
        "skill_id": "skill-x",
        "session_id": "sess-1",
        "session_count": 3,
        "finished_count": 2,
        "failed_count": 1,
        "last_started_at": 1000,
        "last_completed_at": 2000,
        "last_duration_ms": 1000,
        "status": "closed",
    }
    s = BusinessFlowSummary(**raw)
    assert s.business_key == "sess-1|skill-x|obj-z"
    assert s.status == "closed"
    assert s.session_count == 3


def test_timeline_event_and_response() -> None:
    ev = TimelineEvent(
        ts=1700000000, layer="L4", component="session",
        event_type="session.created", payload={"intent": "calibrate"},
    )
    resp = TimelineResponse(
        business_key="k", events=[ev], count=1,
    )
    assert resp.count == 1
    assert resp.events[0].ts == 1700000000


def test_evaluation_report_parses() -> None:
    from eaasp_common import OptimizationHint
    raw = {
        "window_seconds": 3600,
        "total_flows": 5,
        "status_counts": {"closed": 4, "failed": 1},
        "completion_rate": 0.8,
        "interruption_heatmap": {"L3": 1},
        "hints": [
            OptimizationHint(
                layer="L3",
                metric="opa.decision.duration",
                severity="warn",
                recommendation="scale OPA",
                evidence={"p99": 0.8},
            )
        ],
    }
    rep = EvaluationReport(**raw)
    assert rep.completion_rate == 0.8
    assert rep.hints[0].layer == "L3"


# ─── ObstackClient list ─────────────────────────────────────────


def test_list_business_flows_returns_parsed_models() -> None:
    body = {
        "flows": [
            {
                "business_key": "k1|skill|obj1",
                "business_object_id": "obj1",
                "skill_id": "skill",
                "session_id": "k1",
                "session_count": 1,
                "finished_count": 1,
                "failed_count": 0,
                "last_started_at": 1700000000,
                "last_completed_at": 1700000030,
                "last_duration_ms": 30_000,
                "status": "closed",
            }
        ],
        "total": 1,
    }
    getter = _make_fake_getter(
        {"http://x/v1/business-flows/list?limit=20": body}
    )
    c = ObstackClient("http://x", http_getter=getter)
    resp = c.list_business_flows()
    assert isinstance(resp, BusinessFlowListResponse)
    assert resp.total == 1
    assert resp.flows[0].business_object_id == "obj1"


def test_list_business_flows_with_filter_passes_query_params() -> None:
    captured: list[str] = []
    def getter(url, headers):
        captured.append(url)
        return {"flows": [], "total": 0}
    c = ObstackClient("http://x", http_getter=getter)
    c.list_business_flows(
        FlowListParams(limit=5, business_object_id="Transformer-1", status="closed")
    )
    # URL must contain all three query params (order-insensitive).
    assert "limit=5" in captured[0]
    assert "business_object_id=Transformer-1" in captured[0]
    assert "status=closed" in captured[0]


# ─── Single-flow endpoints ────────────────────────────────────


def test_get_timeline_encodes_business_key() -> None:
    captured: list[str] = []
    def getter(url, headers):
        captured.append(url)
        return {
            "business_key": "sess|skill|obj",
            "events": [],
            "count": 0,
        }
    c = ObstackClient("http://x", http_getter=getter)
    resp = c.get_timeline("sess|skill|obj")
    # Pipe is percent-encoded in URL path segments.
    assert "sess%7Cskill%7Cobj" in captured[0]
    assert isinstance(resp, TimelineResponse)
    assert resp.count == 0


def test_get_summary_uses_summary_block() -> None:
    body = {
        "business_key": "k",
        "summary": {
            "status": "running",
            "started_at": 1000,
            "completed_at": None,
            "total_duration_ms": None,
            "event_count": 5,
            "layer_counts": {"L4": 5},
            "interrupted_layer": None,
        },
    }
    c = ObstackClient("http://x", http_getter=_make_fake_getter(
        {"http://x/v1/business-flows/k/summary": body}
    ))
    resp = c.get_summary("k")
    assert isinstance(resp, SummaryResponse)
    assert isinstance(resp.summary, SummaryBlock)
    assert resp.summary.status == "running"


def test_get_sessions_returns_session_ref_list() -> None:
    body = {
        "business_key": "k",
        "session_ids": [
            {"session_id": "s1", "status": "closed", "created_at": 1000},
            {"session_id": "s2", "status": "failed", "created_at": 2000},
        ],
        "count": 2,
    }
    c = ObstackClient("http://x", http_getter=_make_fake_getter(
        {"http://x/v1/business-flows/k/sessions": body}
    ))
    resp = c.get_sessions("k")
    assert isinstance(resp, SessionsResponse)
    assert len(resp.session_ids) == 2
    assert resp.session_ids[0] is not None
    assert resp.session_ids[0].session_id == "s1"


def test_get_evaluation_parses_report() -> None:
    body = {
        "business_key": "k",
        "report": {
            "window_seconds": 3600,
            "total_flows": 3,
            "status_counts": {"closed": 3},
            "completion_rate": 1.0,
            "interruption_heatmap": {},
            "hints": [],
        },
    }
    c = ObstackClient("http://x", http_getter=_make_fake_getter(
        {"http://x/v1/business-flows/k/evaluation": body}
    ))
    resp = c.get_evaluation("k")
    assert isinstance(resp, EvaluationResponse)
    assert resp.report.completion_rate == 1.0


# ─── Error path ────────────────────────────────────────────────


def test_raises_obstack_client_error_on_non_2xx() -> None:
    """When the injected getter raises HTTPError, the client must
    convert that into ObstackClientError so callers can branch on
    status without parsing strings.
    """
    def getter(url, headers):
        import urllib.error
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    # Inject the raising getter; the client wraps the call in
    # try/except and re-raises as ObstackClientError.
    c = ObstackClient("http://x", http_getter=getter)
    with pytest.raises(ObstackClientError) as exc:
        c.list_business_flows()
    assert exc.value.status == 404
    assert "404" in str(exc.value)
