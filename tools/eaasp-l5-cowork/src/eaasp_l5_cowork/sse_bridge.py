"""L4 SSE bridge — tails the L4 event stream and emits Cowork card events.

v3.13.0 — EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action /
Approval) + 回溯闭环 (retrospective cycle).

This module hosts the **standalone** SSE bridge — useful for
tests that want to drive the projection independently of the L5
FastAPI app, and for any future deployment that wants to push
``cowork.card.<type>.<event>`` events onto a separate SSE
broker / Kafka topic.

The bridge polls the underlying L4 ``event_room_events`` table
at a fixed interval (``poll_interval_ms``) and emits one SSE
event per NEW row (seq > last_seen_seq). State transitions +
persistence land in 03.13.1; this phase ships the read-only
``*.created`` emission primitive.

Event family (D-36):

- ``cowork.card.event.created``
- ``cowork.card.evidence.created``
- ``cowork.card.action.created``
- ``cowork.card.approval.created``

These match the v3.11.2 ``governance.approval.<stage>`` and
v3.12.2 ``a2a.<event>`` families, so the Cowork SSE stream
slots into the existing event-family grammar with no surprise
naming.

Frozen contract (audit §7.1): the bridge is best-effort. Every
poll wraps the underlying DB read in a try/except and logs
failures. Per the v3.12.1 fan-out contract, failures NEVER
invert an authoritative audit decision; they surface as a
missing event in the Cowork stream.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from loguru import logger

from .projection import CoworkProjection


# SSE event-family constants (D-36). Keep in sync with the
# backend route in ``cowork.py`` so the standalone bridge emits
# the same names.
EVENT_CREATED = "cowork.card.event.created"
EVIDENCE_CREATED = "cowork.card.evidence.created"
ACTION_CREATED = "cowork.card.action.created"
APPROVAL_CREATED = "cowork.card.approval.created"

DEFAULT_POLL_MS = 500
DEFAULT_HEARTBEAT_S = 15
DEFAULT_MAX_IDLE_POLLS = 0  # 0 = poll forever


def _iso(ts: Any) -> str:
    if ts is None:
        return ""
    if isinstance(ts, (int, float)):
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(ts)))
    return str(ts)


async def bridge_session_events(
    projection: CoworkProjection,
    session_id: str,
    *,
    tenant_id: str,
    poll_interval_ms: int = DEFAULT_POLL_MS,
    heartbeat_secs: int = DEFAULT_HEARTBEAT_S,
    max_idle_polls: int = DEFAULT_MAX_IDLE_POLLS,
) -> AsyncIterator[str]:
    """Yield SSE events for new cards arriving on ``session_id``.

    The bridge re-projects on every tick; new cards (those not
    seen in a previous tick) become ``*.created`` SSE events.
    This is O(N) per tick, where N is the per-session card
    count; for the EAASP v2.0 MVP scale this is bounded by the
    per-session telemetry ingest rate (single-digit per second).
    """
    seen_event_seqs: set[int] = set()
    seen_anchor_ids: set[str] = set()
    seen_action_ids: set[str] = set()
    seen_decision_ids: set[str] = set()
    last_heartbeat = asyncio.get_event_loop().time()
    idle_polls = 0

    while True:
        try:
            events = await projection.list_event_cards(
                session_id, tenant_id=tenant_id
            )
            for ev in events:
                if ev.event_seq in seen_event_seqs:
                    continue
                seen_event_seqs.add(ev.event_seq)
                payload = json.dumps(
                    ev.to_dict(), ensure_ascii=False, default=str
                )
                yield f"event: {EVENT_CREATED}\ndata: {payload}\n\n"

            evidence = await projection.list_evidence_cards(
                session_id, tenant_id=tenant_id
            )
            for ev in evidence:
                if ev.anchor_id in seen_anchor_ids:
                    continue
                seen_anchor_ids.add(ev.anchor_id)
                payload = json.dumps(
                    ev.to_dict(), ensure_ascii=False, default=str
                )
                yield f"event: {EVIDENCE_CREATED}\ndata: {payload}\n\n"

            actions = await projection.list_action_cards(
                session_id, tenant_id=tenant_id
            )
            for ac in actions:
                if ac.id in seen_action_ids:
                    continue
                seen_action_ids.add(ac.id)
                payload = json.dumps(
                    ac.to_dict(), ensure_ascii=False, default=str
                )
                yield f"event: {ACTION_CREATED}\ndata: {payload}\n\n"

            approvals = await projection.list_approval_cards(
                session_id, tenant_id=tenant_id
            )
            for ap in approvals:
                if ap.decision_id in seen_decision_ids:
                    continue
                seen_decision_ids.add(ap.decision_id)
                payload = json.dumps(
                    ap.to_dict(), ensure_ascii=False, default=str
                )
                yield f"event: {APPROVAL_CREATED}\ndata: {payload}\n\n"
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — best-effort bridge
            logger.debug(
                "sse_bridge_projection_failed session_id={} detail={}",
                session_id,
                exc,
            )

        idle_polls += 1
        if max_idle_polls and idle_polls >= max_idle_polls:
            return
        now = asyncio.get_event_loop().time()
        if now - last_heartbeat >= heartbeat_secs:
            yield ": hb\n\n"
            last_heartbeat = now
        await asyncio.sleep(poll_interval_ms / 1000.0)


__all__ = [
    "ACTION_CREATED",
    "APPROVAL_CREATED",
    "EVIDENCE_CREATED",
    "EVENT_CREATED",
    "bridge_session_events",
]
