"""Cross-layer business-flow readers — OBSTACK §3.5 timeline aggregation.

V315-BUSINESS-FLOW-02 (lands in v3.15.5 walkthrough evidence):
five concrete ``LayerReader`` implementations, one per cross-layer
table that carries ``business_key``. Each reader is a standalone
async function so tests can inject a fresh ``aiosqlite.Connection``
and assert row → ``BusinessFlowEvent`` mapping without standing up
the L4 FastAPI app.

Tables covered:

- L4 ``sessions`` + ``session_events`` — session lifecycle + event log
- L4 ``event_room_events`` — multi-session Event Room fan-out
- L3 ``governance_decisions`` — cross-process read via injected conn
- L3 ``telemetry_events`` — cross-process read via injected conn
- L2 ``memory_files`` — cross-process read via injected conn

The reader functions are **thin**: they issue SQL, then call the
shared ``_row_to_event`` helper in ``flow_timeline.py`` for the
column-name → event-field translation. This keeps the row-mapping
logic DRY across layers.
"""

from __future__ import annotations

from typing import Any

import aiosqlite

from eaasp_common.business_flow import BusinessKey

from .flow_timeline import BusinessFlowEvent, _row_to_event


# ─── L4 readers (live in L4's own DB) ───────────────────────────────────────


async def read_l4_sessions(
    conn: aiosqlite.Connection, key: BusinessKey,
) -> list[BusinessFlowEvent]:
    """Read ``sessions`` rows tagged with ``business_key`` and emit
    one ``session.created`` event per row, plus a ``session.closed``
    event for rows whose status is terminal. The session_events
    log is folded in via UNION ALL so the timeline includes the
    agent-loop append-only events as well.
    """
    wire = key.to_header()
    events: list[BusinessFlowEvent] = []
    async with conn.execute(
        """
        SELECT session_id, 'session.created' AS event_type,
               created_at AS ts, payload_json, NULL AS duration_ms,
               NULL AS error
          FROM sessions
         WHERE business_key = ?
        UNION ALL
        SELECT session_id, 'session.closed' AS event_type,
               COALESCE(closed_at, created_at) AS ts,
               json_object('status', status) AS payload_json,
               NULL, NULL
          FROM sessions
         WHERE business_key = ? AND status IN ('closed', 'failed')
         ORDER BY ts
        """,
        (wire, wire),
    ) as cur:
        async for row in cur:
            events.append(
                _row_to_event(
                    dict(row),
                    layer="L4",
                    component="session",
                    ts_field="ts",
                    payload_field="payload_json",
                ),
            )
    return events


async def read_l4_event_room_events(
    conn: aiosqlite.Connection, key: BusinessKey,
) -> list[BusinessFlowEvent]:
    """Read ``event_room_events`` rows tagged with ``business_key``.

    Each row represents a single fan-out dispatch (NOT one per
    recipient; SSE consumers fan out per the canonical schema).
    Mapped to ``event_room.event`` with the raw event_type preserved
    in ``payload``.
    """
    wire = key.to_header()
    events: list[BusinessFlowEvent] = []
    async with conn.execute(
        """
        SELECT room_id, session_id, event_type, payload_json, created_at
          FROM event_room_events
         WHERE business_key = ?
         ORDER BY created_at
        """,
        (wire,),
    ) as cur:
        async for row in cur:
            d = dict(row)
            # Prefix the event_type so the timeline aggregator can
            # distinguish event_room events from session events.
            d["event_type"] = f"event_room.{d['event_type']}"
            events.append(
                _row_to_event(
                    d,
                    layer="L4",
                    component="event_room",
                    ts_field="created_at",
                ),
            )
    return events


async def read_l4_session_events(
    conn: aiosqlite.Connection, key: BusinessKey,
) -> list[BusinessFlowEvent]:
    """Read ``session_events`` for sessions whose ``business_key`` matches.

    Sibling of ``read_l4_sessions`` but returns the per-session event
    log (SESSION_CREATED, PRE_TOOL_USE, POST_TOOL_USE, etc.) rather
    than the session row itself. Useful for agents that need the
    step-by-step audit trail of one business flow.
    """
    wire = key.to_header()
    events: list[BusinessFlowEvent] = []
    async with conn.execute(
        """
        SELECT se.session_id, se.event_type, se.payload_json,
               se.created_at, se.event_id, se.source
          FROM session_events se
          JOIN sessions s ON s.session_id = se.session_id
         WHERE s.business_key = ?
         ORDER BY se.created_at, se.seq
        """,
        (wire,),
    ) as cur:
        async for row in cur:
            events.append(
                _row_to_event(
                    dict(row),
                    layer="L4",
                    component="session_event",
                    ts_field="created_at",
                ),
            )
    return events


# ─── L3 readers (cross-DB; conn is the L3 DB connection) ────────────────────


async def read_l3_governance_decisions(
    conn: aiosqlite.Connection, key: BusinessKey,
) -> list[BusinessFlowEvent]:
    """Read ``governance_decisions`` rows tagged with ``business_key``.

    Each row is one OPA / policy-engine decision (allow/approve/deny/
    gate_request/await_human per v3.12 CHECK widening). Mapped to
    ``governance.decision`` event_type for the timeline.
    """
    wire = key.to_header()
    events: list[BusinessFlowEvent] = []
    async with conn.execute(
        """
        SELECT decision_id, session_id, hook_id, tool_name, risk_level,
               decision, approver, rationale, stage, created_at
          FROM governance_decisions
         WHERE business_key = ?
         ORDER BY created_at
        """,
        (wire,),
    ) as cur:
        async for row in cur:
            d = dict(row)
            events.append(
                _row_to_event(
                    d,
                    layer="L3",
                    component="governance",
                    event_type_field="decision",
                    ts_field="created_at",
                    payload_field="payload",
                ),
            )
    return events


async def read_l3_telemetry_events(
    conn: aiosqlite.Connection, key: BusinessKey,
) -> list[BusinessFlowEvent]:
    """Read ``telemetry_events`` rows tagged with ``business_key``.

    L3 telemetry is the async-write sink for skill-usage counters
    and request metrics. Each row becomes a ``telemetry.<event_type>``
    timeline event.
    """
    wire = key.to_header()
    events: list[BusinessFlowEvent] = []
    async with conn.execute(
        """
        SELECT event_type, payload_json, created_at, source, tiebreaker
          FROM telemetry_events
         WHERE business_key = ?
         ORDER BY created_at, tiebreaker
        """,
        (wire,),
    ) as cur:
        async for row in cur:
            d = dict(row)
            et = d.get("event_type") or "telemetry.unknown"
            # Prefix to keep distinct from session events.
            d["event_type"] = f"telemetry.{et}" if not et.startswith("telemetry.") else et
            events.append(
                _row_to_event(
                    d,
                    layer="L3",
                    component="telemetry",
                    ts_field="created_at",
                ),
            )
    return events


# ─── L2 readers (cross-DB; conn is the L2 memory DB connection) ─────────────


async def read_l2_memory_files(
    conn: aiosqlite.Connection, key: BusinessKey,
) -> list[BusinessFlowEvent]:
    """Read ``memory_files`` rows tagged with ``business_key``.

    v3.15.1 added ``business_key`` to ``memory_files`` (and
    ``anchors``) so the L2 ledger can be joined into the cross-layer
    business-flow timeline. We emit one event per memory row,
    distinct event_type per status (agent_suggested → proposed,
    confirmed → confirmed, archived → archived).
    """
    wire = key.to_header()
    events: list[BusinessFlowEvent] = []
    async with conn.execute(
        """
        SELECT memory_id, version, scope, category, status,
               content, created_at, updated_at
          FROM memory_files
         WHERE business_key = ?
         ORDER BY created_at
        """,
        (wire,),
    ) as cur:
        async for row in cur:
            d = dict(row)
            status = d.get("status") or "unknown"
            d["event_type"] = f"memory.write_file.{status}"
            events.append(
                _row_to_event(
                    d,
                    layer="L2",
                    component="memory",
                    ts_field="created_at",
                    payload_field="payload",
                ),
            )
    return events


# ─── Factory used by the L4 lifespan ────────────────────────────────────────


def build_default_layer_readers(
    *,
    l4_conn: aiosqlite.Connection | None,
    l3_conn: aiosqlite.Connection | None,
    l2_conn: aiosqlite.Connection | None,
) -> dict[str, Any]:
    """Build the ``app.state.flow_layer_readers`` dict for the L4 lifespan.

    Each entry is a ``LayerReader`` — an async callable that takes a
    ``BusinessKey`` and returns a list of ``BusinessFlowEvent`` rows.
    Missing connections (``None``) produce a no-op reader so the
    timeline aggregation still works for partial wiring (e.g. L4-only
    dev mode where L2/L3 are not running).
    """

    async def _noop(key: BusinessKey) -> list[BusinessFlowEvent]:
        del key  # unused; intentional no-op reader
        return []

    readers: dict[str, Any] = {}

    # L4 readers — always wired (L4 owns this DB).
    if l4_conn is not None:
        async def _l4_sessions(key: BusinessKey) -> list[BusinessFlowEvent]:
            return await read_l4_sessions(l4_conn, key)

        async def _l4_room(key: BusinessKey) -> list[BusinessFlowEvent]:
            return await read_l4_event_room_events(l4_conn, key)

        async def _l4_session_events(key: BusinessKey) -> list[BusinessFlowEvent]:
            return await read_l4_session_events(l4_conn, key)

        readers["L4_sessions"] = _l4_sessions
        readers["L4_event_room_events"] = _l4_room
        readers["L4_session_events"] = _l4_session_events
    else:
        readers["L4_sessions"] = _noop
        readers["L4_event_room_events"] = _noop
        readers["L4_session_events"] = _noop

    # L3 readers — cross-DB; gracefully degrade if L3 conn is absent.
    if l3_conn is not None:
        async def _l3_decisions(key: BusinessKey) -> list[BusinessFlowEvent]:
            return await read_l3_governance_decisions(l3_conn, key)

        async def _l3_telemetry(key: BusinessKey) -> list[BusinessFlowEvent]:
            return await read_l3_telemetry_events(l3_conn, key)

        readers["L3_governance_decisions"] = _l3_decisions
        readers["L3_telemetry_events"] = _l3_telemetry
    else:
        readers["L3_governance_decisions"] = _noop
        readers["L3_telemetry_events"] = _noop

    # L2 readers — cross-DB; gracefully degrade if L2 conn is absent.
    if l2_conn is not None:
        async def _l2_memory(key: BusinessKey) -> list[BusinessFlowEvent]:
            return await read_l2_memory_files(l2_conn, key)

        readers["L2_memory_files"] = _l2_memory
    else:
        readers["L2_memory_files"] = _noop

    return readers


__all__ = [
    "build_default_layer_readers",
    "read_l2_memory_files",
    "read_l3_governance_decisions",
    "read_l3_telemetry_events",
    "read_l4_event_room_events",
    "read_l4_session_events",
    "read_l4_sessions",
]
