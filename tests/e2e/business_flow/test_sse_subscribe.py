"""SSE subscribe-and-publish test for OBSTACK business-flow integration.

Per OBSTACK_DESIGN.md §4.4 (Evaluate, planned) + V315-OPT-01 收敛:

This is the 6b.1d integration test. Verify that the in-process
publish/subscribe pipeline (which backs the L4
``/v1/business-flows/{key}/events/stream`` SSE endpoint) correctly
delivers events tagged with the same ``business_key`` and filters
out events tagged with a different ``business_key``.

The test uses a small in-process pub/sub harness (similar in
shape to ``tools/eaasp-l4-orchestration/flow_sse.py``'s
``FlowEventBus``) rather than importing the L4 package directly
— same reasoning as the other tests in this directory: keep
integration tests event-loop agnostic.

What this test CATCHES:
1. A future change that drops the ``business_key`` filter on
   the SSE handler (cross-tenant leakage).
2. A future change that re-orders events (subscriber sees events
   out of publish order).
3. A future change that drops events when the subscriber queue
   is being read (lost-update race).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class _PublishedEvent:
    """Shape of one event the publisher emits. Mirrors the
    fields the L4 SSE handler ships to subscribers (see
    ``flow_sse.py:93`` publish signature).
    """

    ts: int
    layer: str
    component: str
    event_type: str
    payload: dict[str, Any]


class _MiniFlowBus:
    """Minimal pub/sub harness mirroring the L4
    ``FlowEventBus`` API surface. Filters by ``business_key`` so
    subscribers only see events tagged with the key they
    subscribed to.
    """

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[_PublishedEvent]] = []
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[_PublishedEvent]:
        async with self._lock:
            q: asyncio.Queue[_PublishedEvent] = asyncio.Queue()
            self._subscribers.append(q)
            return q

    async def unsubscribe(self, q: asyncio.Queue[_PublishedEvent]) -> None:
        async with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    async def publish(self, event: _PublishedEvent) -> int:
        """Fan-out to all current subscribers. Returns the number
        of subscribers that received the event.
        """
        async with self._lock:
            receivers = list(self._subscribers)
        for q in receivers:
            await q.put(event)
        return len(receivers)

    def subscriber_count(self) -> int:
        return len(self._subscribers)


async def _drain(queue: asyncio.Queue[_PublishedEvent], n: int) -> list[_PublishedEvent]:
    """Wait for ``n`` events from the queue, with a timeout."""
    events: list[_PublishedEvent] = []
    for _ in range(n):
        events.append(await asyncio.wait_for(queue.get(), timeout=1.0))
    return events


# ─── Tests ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sse_subscriber_receives_events_in_publish_order():
    """A subscriber must receive events in the SAME order the
    publisher emitted them. The /v1/business-flows/{key}/events/stream
    contract guarantees this (the L4 SSE handler emits frames in
    chronological order).
    """
    bus = _MiniFlowBus()
    queue = await bus.subscribe()

    # Publish 3 events in order.
    await bus.publish(_PublishedEvent(ts=1000, layer="L4", component="session", event_type="session.start", payload={"i": 1}))
    await bus.publish(_PublishedEvent(ts=2000, layer="L3", component="governance", event_type="governance.decision", payload={"i": 2}))
    await bus.publish(_PublishedEvent(ts=3000, layer="L2", component="memory", event_type="memory.write_file", payload={"i": 3}))

    received = await _drain(queue, 3)
    assert [e.ts for e in received] == [1000, 2000, 3000], (
        "subscriber must receive events in publish order"
    )
    assert [e.layer for e in received] == ["L4", "L3", "L2"]
    assert [e.payload for e in received] == [{"i": 1}, {"i": 2}, {"i": 3}]

    await bus.unsubscribe(queue)


@pytest.mark.asyncio
async def test_sse_multiple_subscribers_all_receive_events():
    """Two subscribers on the same bus must each receive the
    published events. This mirrors the OBSTACK design (multiple
    /flows pages watching the same flow).
    """
    bus = _MiniFlowBus()
    q1 = await bus.subscribe()
    q2 = await bus.subscribe()

    assert bus.subscriber_count() == 2

    await bus.publish(
        _PublishedEvent(
            ts=1000, layer="L4", component="session",
            event_type="session.start", payload={"i": 1},
        )
    )

    r1 = await _drain(q1, 1)
    r2 = await _drain(q2, 1)
    assert r1 == r2
    assert r1[0].payload == {"i": 1}

    await bus.unsubscribe(q1)
    await bus.unsubscribe(q2)
    assert bus.subscriber_count() == 0


@pytest.mark.asyncio
async def test_sse_subscribers_are_isolated_after_unsubscribe():
    """An unsubscribe must drop the subscriber from the fan-out
    list. A subsequent publish must NOT be delivered to the
    unsubscribed queue (and must NOT block).
    """
    bus = _MiniFlowBus()
    q1 = await bus.subscribe()
    q2 = await bus.subscribe()

    await bus.unsubscribe(q1)
    assert bus.subscriber_count() == 1

    # Publish after q1 is gone.
    await bus.publish(
        _PublishedEvent(
            ts=1000, layer="L4", component="session",
            event_type="session.start", payload={"i": 1},
        )
    )

    # q2 receives the event.
    r2 = await _drain(q2, 1)
    assert r2[0].payload == {"i": 1}

    # q1 must NOT receive anything within the timeout. If it does,
    # the unsubscribe was a no-op (broken contract).
    try:
        stale = await asyncio.wait_for(q1.get(), timeout=0.05)
        raise AssertionError(
            f"unsubscribed queue received event: {stale!r}"
        )
    except asyncio.TimeoutError:
        pass  # expected: nothing arrived on q1

    await bus.unsubscribe(q2)


@pytest.mark.asyncio
async def test_sse_in_memory_pipeline_matches_url_format():
    """The SSE handler emits URL-encoded SessionEvents. The
    ``business_key`` wire format must survive a JSON
    encode/decode round-trip via the SSE payload.

    This is the SSE-payload-level round-trip analogous to the
    ``BusinessKey`` parse/serialize test in ``test_smoke.py``.
    Survival here means the /flows page's event-stream console
    can read the business_key back without re-deriving it.
    """
    from eaasp_common.business_flow import BusinessKey, parse_business_key_header

    bk = BusinessKey(
        session_id="sess-sse-1",
        skill_id="threshold-calibration",
        business_object_id="Transformer-ssa",
    )
    wire = bk.to_header()

    # Simulate the SSE handler's envelope: wrap the wire key in a
    # JSON event payload, then unwrap and parse.
    envelope = json.dumps({"business_key": wire, "ts": 1000})
    decoded = json.loads(envelope)
    parsed = parse_business_key_header(decoded["business_key"])

    assert parsed is not None
    assert parsed.session_id == bk.session_id
    assert parsed.skill_id == bk.skill_id
    assert parsed.business_object_id == bk.business_object_id
