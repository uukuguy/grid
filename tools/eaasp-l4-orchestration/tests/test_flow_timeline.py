"""Tests for flow_timeline.py — v3.15.2 cross-layer timeline aggregation.

Covers:
- _infer_status: succeeded / failed / aborted / running / unknown
- summarize_business_flow: duration calc, layer counts, status mapping
- assemble_business_flow_timeline: merges across layer readers, sorted
- _row_to_event: payload parsing (string vs dict, bad JSON)
- _read_l4_sessions default stub returns empty list
"""

from __future__ import annotations

import json

from eaasp_common.business_flow import BusinessKey
from eaasp_l4_orchestration.flow_timeline import (
    BusinessFlowEvent,
    _infer_status,
    _parse_json_payload,
    _row_to_event,
    assemble_business_flow_summary,
    assemble_business_flow_timeline,
    summarize_business_flow,
)


# ─── _infer_status ──────────────────────────────────────────────────────────


def test_infer_unknown_empty() -> None:
    assert _infer_status([]) == ("unknown", None)


def test_infer_running_no_terminal() -> None:
    events = [
        BusinessFlowEvent(ts=1000, layer="L4", component="session", event_type="session.created", payload={}),
        BusinessFlowEvent(ts=1100, layer="L3", component="governance", event_type="governance.decision", payload={"decision": "allow"}),
    ]
    assert _infer_status(events) == ("running", None)


def test_infer_succeeded_on_close() -> None:
    events = [
        BusinessFlowEvent(ts=1000, layer="L4", component="session", event_type="session.created", payload={}),
        BusinessFlowEvent(ts=1500, layer="L4", component="session", event_type="session.closed", payload={"status": "closed"}),
    ]
    status, layer = _infer_status(events)
    assert status == "succeeded"
    assert layer is None


def test_infer_failed_on_close() -> None:
    events = [
        BusinessFlowEvent(ts=1000, layer="L4", component="session", event_type="session.created", payload={}),
        BusinessFlowEvent(ts=1500, layer="L4", component="session", event_type="session.closed", payload={"status": "failed"}),
    ]
    status, layer = _infer_status(events)
    assert status == "failed"
    assert layer == "L4"


def test_infer_aborted_on_deny() -> None:
    """A deny decision at the tail with no follow-up counts as aborted."""
    events = [
        BusinessFlowEvent(ts=1000, layer="L4", component="session", event_type="session.created", payload={}),
        BusinessFlowEvent(
            ts=1500,
            layer="L3",
            component="governance",
            event_type="governance.decision",
            payload={"decision": "deny"},
        ),
    ]
    status, layer = _infer_status(events)
    assert status == "aborted"
    assert layer == "L3"


# ─── summarize_business_flow ────────────────────────────────────────────────


def test_summarize_empty() -> None:
    s = summarize_business_flow([])
    assert s.status == "unknown"
    assert s.started_at is None
    assert s.completed_at is None
    assert s.total_duration_ms is None
    assert s.event_count == 0
    assert s.layer_counts == {}


def test_summarize_duration() -> None:
    events = [
        BusinessFlowEvent(ts=1000, layer="L4", component="session", event_type="a", payload={}),
        BusinessFlowEvent(ts=2500, layer="L3", component="governance", event_type="b", payload={}),
    ]
    s = summarize_business_flow(events)
    assert s.total_duration_ms == 1500
    assert s.event_count == 2
    assert s.layer_counts == {"L4": 1, "L3": 1}


def test_summarize_layer_counts() -> None:
    events = [
        BusinessFlowEvent(ts=1000, layer="L2", component="memory", event_type="x", payload={}),
        BusinessFlowEvent(ts=1100, layer="L2", component="memory", event_type="x", payload={}),
        BusinessFlowEvent(ts=1200, layer="L3", component="governance", event_type="y", payload={}),
        BusinessFlowEvent(ts=1300, layer="L4", component="session", event_type="z", payload={}),
    ]
    s = summarize_business_flow(events)
    assert s.layer_counts == {"L2": 2, "L3": 1, "L4": 1}


# ─── assemble_business_flow_timeline ────────────────────────────────────────


async def _reader(rows: list[BusinessFlowEvent]):
    """Build a LayerReader that returns the given events."""
    async def _impl(key: BusinessKey) -> list[BusinessFlowEvent]:
        del key
        return rows
    return _impl


async def test_assemble_merges_and_sorts() -> None:
    r1 = await _reader([
        BusinessFlowEvent(ts=1100, layer="L3", component="governance", event_type="g1", payload={}),
    ])
    r2 = await _reader([
        BusinessFlowEvent(ts=1000, layer="L4", component="session", event_type="s1", payload={}),
        BusinessFlowEvent(ts=1200, layer="L2", component="memory", event_type="m1", payload={}),
    ])
    timeline = await assemble_business_flow_timeline(
        BusinessKey(session_id="s1"),
        layer_readers={"r1": r1, "r2": r2},
    )
    assert [e.ts for e in timeline] == [1000, 1100, 1200]
    assert [e.layer for e in timeline] == ["L4", "L3", "L2"]


async def test_assemble_handles_empty_readers() -> None:
    timeline = await assemble_business_flow_timeline(
        BusinessKey(session_id="s1"),
        layer_readers={},
    )
    assert timeline == []


async def test_assemble_skips_unwired_layers() -> None:
    """When a layer has no reader, its events are simply absent (not
    a 500). The caller (API layer) decides whether to error."""
    timeline = await assemble_business_flow_timeline(
        BusinessKey(session_id="s1"),
        layer_readers={},  # no readers wired
    )
    assert timeline == []


async def test_assemble_summary_integration() -> None:
    r1 = await _reader([
        BusinessFlowEvent(ts=1000, layer="L4", component="session", event_type="session.created", payload={}),
        BusinessFlowEvent(ts=1500, layer="L4", component="session", event_type="session.closed", payload={"status": "closed"}),
    ])
    s = await assemble_business_flow_summary(
        BusinessKey(session_id="s1"),
        layer_readers={"L4": r1},
    )
    assert s.status == "succeeded"
    assert s.total_duration_ms == 500
    assert s.event_count == 2


# ─── _row_to_event ──────────────────────────────────────────────────────────


def test_row_to_event_default_fields() -> None:
    row = {
        "seq": 1,
        "session_id": "s1",
        "event_type": "session.created",
        "payload_json": json.dumps({"x": 1}),
        "created_at": 1700000000000,
    }
    ev = _row_to_event(row, layer="L4", component="session")
    assert ev.ts == 1700000000000
    assert ev.layer == "L4"
    assert ev.component == "session"
    assert ev.event_type == "session.created"
    assert ev.payload == {"x": 1}


def test_row_to_event_payload_already_dict() -> None:
    row = {
        "event_type": "x",
        "payload_json": {"k": "v"},
        "created_at": 1000,
    }
    ev = _row_to_event(row, layer="L4", component="c")
    assert ev.payload == {"k": "v"}


def test_row_to_event_bad_json_keeps_raw() -> None:
    row = {
        "event_type": "x",
        "payload_json": "not json {",
        "created_at": 1000,
    }
    ev = _row_to_event(row, layer="L4", component="c")
    assert ev.payload.get("_raw") is not None


def test_row_to_event_missing_ts_uses_now() -> None:
    row = {"event_type": "x", "payload_json": "{}"}
    ev = _row_to_event(row, layer="L4", component="c")
    assert ev.ts > 0


def test_row_to_event_duration_field() -> None:
    row = {
        "event_type": "x",
        "payload_json": "{}",
        "created_at": 1000,
        "duration_ms": 250,
    }
    ev = _row_to_event(row, layer="L3", component="governance", duration_field="duration_ms")
    assert ev.duration_ms == 250


def test_row_to_event_error_field() -> None:
    row = {
        "event_type": "x",
        "payload_json": "{}",
        "created_at": 1000,
        "error": "boom",
    }
    ev = _row_to_event(row, layer="L3", component="governance", error_field="error")
    assert ev.error == "boom"


# ─── _parse_json_payload ────────────────────────────────────────────────────


def test_parse_json_payload_dict_passthrough() -> None:
    assert _parse_json_payload({"a": 1}) == {"a": 1}


def test_parse_json_payload_string() -> None:
    assert _parse_json_payload('{"a": 2}') == {"a": 2}


def test_parse_json_payload_empty() -> None:
    assert _parse_json_payload("") == {}
    assert _parse_json_payload(None) == {}


def test_parse_json_payload_bytes() -> None:
    assert _parse_json_payload(b'{"a": 3}') == {"a": 3}


def test_parse_json_payload_invalid_keeps_raw() -> None:
    out = _parse_json_payload("{invalid")
    assert "_raw" in out
