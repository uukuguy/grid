"""Business Flow Timeline — vertical cross-layer aggregation.

Per v3.15.2 (OBSTACK_DESIGN.md §3.5). Given a
``BusinessKey``, walk every cross-layer table and assemble a single
chronological timeline of events, plus a summary that surfaces the
business-flow status (running / succeeded / failed / aborted) and
the layer where it stopped (when applicable).

Cross-layer tables queried:

- ``sessions`` (L4) — the session row, plus its first ``created_at``
  and any ``closed_at`` as flow boundary events
- ``session_events`` (L4) — append-only session event log
- ``event_room_events`` (L4) — multi-session Event Room events
- ``governance_decisions`` (L3) — read via the L3 DB path; the L4
  process does not own this table, so we accept an injected reader
- ``memory_files`` (L2) — read via the L2 DB path; same pattern

The module is **injection-friendly**: every DB access is a callable
parameter so tests can run without standing up a real L2/L3 backend
and the production wiring composes the readers at app boot.

The timeline query is intentionally simple — straight SQL with
``ORDER BY created_at`` on the source table, then a Python merge
since different tables have different ``created_at`` granularity
(seconds vs milliseconds). For high-volume flows, the v3.16+ index
on ``(business_key, created_at)`` is the next step; for v3.15 the
expected flow volume (one flow = one user request = O(100) events)
is well within sequential-merge budget.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable, Sequence

from eaasp_common.business_flow import BusinessKey

# Type alias for an async event-source reader. Each reader is a
# callable that takes a ``BusinessKey`` and returns a list of
# already-mapped ``BusinessFlowEvent`` rows. Readers are responsible
# for doing the row-to-event translation for their layer; the
# timeline aggregator only sorts + counts.
LayerReader = Callable[[BusinessKey], Awaitable[Sequence["BusinessFlowEvent"]]]


# ─── Domain model ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BusinessFlowEvent:
    """One event on a business-flow timeline.

    Fields:
    - ``ts`` — Unix epoch milliseconds (the common denominator across
      L2/L3/L4 tables; the source layer's monotonic clock is *not*
      used — we always store wall-clock for cross-layer merge).
    - ``layer`` — ``"L2"`` / ``"L3"`` / ``"L4"`` / etc.
    - ``component`` — domain-specific (e.g. ``"memory"``,
      ``"governance"``, ``"session"``, ``"event_room"``).
    - ``event_type`` — short string identifying the event subtype
      (e.g. ``"memory.write_file"``, ``"governance.decision"``).
    - ``payload`` — event-specific data. Kept as a plain dict for
      JSON round-trip.
    - ``duration_ms`` — optional, when the source row carries it.
    - ``error`` — optional, when the source row carries a failure.
    """

    ts: int
    layer: str
    component: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    duration_ms: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "layer": self.layer,
            "component": self.component,
            "event_type": self.event_type,
            "payload": self.payload,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass(frozen=True)
class BusinessFlowSummary:
    """Aggregate summary of a business flow.

    Fields:
    - ``status`` — ``"running"`` / ``"succeeded"`` / ``"failed"`` /
      ``"aborted"`` / ``"unknown"``. ``"unknown"`` is returned when
      no source layer has any event for the key (caller decides
      whether to 404 or treat as empty).
    - ``started_at`` / ``completed_at`` — wall-clock ms.
    - ``total_duration_ms`` — ``completed_at - started_at`` (None
      when still running or unknown).
    - ``event_count`` — total number of events across all layers.
    - ``layer_counts`` — per-layer event count (e.g. ``{"L2": 3,
      "L3": 5, "L4": 8}``).
    - ``interrupted_layer`` — when ``status`` is ``"failed"`` /
      ``"aborted"``, the layer where the failure was first observed.
    """

    status: str
    started_at: int | None
    completed_at: int | None
    total_duration_ms: int | None
    event_count: int
    layer_counts: dict[str, int]
    interrupted_layer: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration_ms": self.total_duration_ms,
            "event_count": self.event_count,
            "layer_counts": self.layer_counts,
            "interrupted_layer": self.interrupted_layer,
        }


# ─── Status inference ───────────────────────────────────────────────────────
#
# Status is inferred from the *last* event in the timeline. The
# terminal event types below are the contract; L2/L3/L4 writers
# should emit one of these when ending a flow.
#
# - ``session.closed`` with payload ``status="closed"`` → succeeded
# - ``session.closed`` with payload ``status="failed"`` → failed
# - ``governance.decision`` with ``decision="deny"`` and no follow-up
#   → aborted (denied before any further work)
# - otherwise → running

_TERMINAL_STATUS_EVENTS = {
    "session.closed",
    "session.failed",
    "business_flow.ended",
}


def _infer_status(events: Sequence[BusinessFlowEvent]) -> tuple[str, str | None]:
    """Walk the timeline tail to determine the flow status.

    Returns ``(status, interrupted_layer)`` where ``interrupted_layer``
    is the layer where the terminal event was observed, or None for
    "running" / "succeeded" / "unknown".
    """
    if not events:
        return "unknown", None

    last = events[-1]
    if last.event_type == "session.closed":
        # Caller wrote the session status into the payload.
        inner_status = str(last.payload.get("status", ""))
        if inner_status == "closed":
            return "succeeded", None
        if inner_status == "failed":
            return "failed", last.layer
        return "aborted", last.layer
    if last.event_type == "session.failed":
        return "failed", last.layer
    if last.event_type == "business_flow.ended":
        inner = str(last.payload.get("status", ""))
        if inner in ("succeeded", "failed", "aborted"):
            return inner, last.layer
    # Look back for a deny decision that has no follow-up.
    for ev in reversed(events[-5:]):
        if (
            ev.event_type == "governance.decision"
            and ev.payload.get("decision") == "deny"
        ):
            return "aborted", ev.layer
    return "running", None


def _build_layer_counts(events: Iterable[BusinessFlowEvent]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ev in events:
        counts[ev.layer] = counts.get(ev.layer, 0) + 1
    return counts


# ─── Row → event mapping (per layer) ────────────────────────────────────────


def _parse_json_payload(raw: Any) -> dict[str, Any]:
    """Best-effort parse of a JSON payload column.

    SQLite rows may carry the payload as a string (TEXT column) or
    already-parsed dict (aiosqlite ``row_factory``). Handle both.
    """
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {"_raw": str(raw)[:200]}
    return parsed if isinstance(parsed, dict) else {"_raw": parsed}


def _row_to_event(
    row: dict[str, Any],
    *,
    layer: str,
    component: str,
    event_type_field: str = "event_type",
    ts_field: str = "created_at",
    payload_field: str = "payload_json",
    duration_field: str | None = None,
    error_field: str | None = None,
) -> BusinessFlowEvent:
    """Map a single source-table row to a ``BusinessFlowEvent``.

    The default field names match the L4 ``session_events`` /
    ``event_room_events`` schema. For other layers, the caller passes
    custom field names.
    """
    ts_value = row.get(ts_field)
    if not isinstance(ts_value, (int, float)):
        # Defensive: bad data shouldn't crash the timeline; treat as
        # "now" so the event is still surfaced.
        ts_value = int(time.time() * 1000)
    payload = _parse_json_payload(row.get(payload_field))
    duration = None
    if duration_field is not None and row.get(duration_field) is not None:
        try:
            duration = int(row[duration_field])
        except (TypeError, ValueError):
            duration = None
    error = None
    if error_field is not None and row.get(error_field) is not None:
        error = str(row[error_field])
    return BusinessFlowEvent(
        ts=int(ts_value),
        layer=layer,
        component=component,
        event_type=str(row.get(event_type_field, "unknown")),
        payload=payload,
        duration_ms=duration,
        error=error,
    )


# ─── Default readers (L4 tables) ────────────────────────────────────────────
#
# These are the L4-internal readers. L2/L3 readers are passed in by
# the API layer when wiring the FastAPI app — see ``api.py``.


async def _read_l4_sessions(key: BusinessKey) -> list[BusinessFlowEvent]:
    """Placeholder: real implementation lives in ``api.py`` where the
    aiosqlite connection is available. This stub returns an empty
    list so the timeline aggregation is always safe to call.
    """
    del key  # unused; real reader is injected at app boot
    return []


# Reference symbols that may be unused at runtime in some call sites
# but are part of the public surface and exported for tests / wiring.
_ = _read_l4_sessions
_ = _TERMINAL_STATUS_EVENTS
_ = _row_to_event


# Default readers map. Callers can override any layer.
DEFAULT_L4_READERS: dict[str, LayerReader] = {
    "L4_sessions": _read_l4_sessions,
}


# ─── Timeline + summary assembly ───────────────────────────────────────────


async def assemble_business_flow_timeline(
    key: BusinessKey,
    *,
    layer_readers: dict[str, LayerReader] | None = None,
) -> list[BusinessFlowEvent]:
    """Read every cross-layer table and return a single sorted timeline.

    The function is the canonical entry point for the v3.15.2 timeline
    API. Callers wire their own readers (e.g. from ``api.py`` where
    the aiosqlite connection lives). Missing readers are silently
    skipped (so partial wiring still works during staged rollout).
    """
    readers = {**DEFAULT_L4_READERS, **(layer_readers or {})}
    all_events: list[BusinessFlowEvent] = []
    for reader in readers.values():
        rows = await reader(key)
        all_events.extend(rows)
    # Sort by wall-clock ts. Stable sort so events with the same ts
    # (e.g. two rows inserted in the same millisecond) preserve the
    # layer-read order.
    all_events.sort(key=lambda e: e.ts)
    return all_events


def summarize_business_flow(
    events: Sequence[BusinessFlowEvent],
) -> BusinessFlowSummary:
    """Compute the flow summary from a sorted timeline."""
    if not events:
        return BusinessFlowSummary(
            status="unknown",
            started_at=None,
            completed_at=None,
            total_duration_ms=None,
            event_count=0,
            layer_counts={},
            interrupted_layer=None,
        )
    status, interrupted = _infer_status(events)
    started = events[0].ts
    completed = events[-1].ts
    total_ms = completed - started if completed >= started else None
    return BusinessFlowSummary(
        status=status,
        started_at=started,
        completed_at=completed,
        total_duration_ms=total_ms,
        event_count=len(events),
        layer_counts=_build_layer_counts(events),
        interrupted_layer=interrupted,
    )


async def assemble_business_flow_summary(
    key: BusinessKey,
    *,
    layer_readers: dict[str, LayerReader] | None = None,
) -> BusinessFlowSummary:
    """Convenience: build the summary directly (timeline + summary)."""
    events = await assemble_business_flow_timeline(key, layer_readers=layer_readers)
    return summarize_business_flow(events)


# ─── Re-exports ─────────────────────────────────────────────────────────────

__all__ = [
    "BusinessFlowEvent",
    "BusinessFlowSummary",
    "LayerReader",
    "assemble_business_flow_summary",
    "assemble_business_flow_timeline",
    "summarize_business_flow",
]
