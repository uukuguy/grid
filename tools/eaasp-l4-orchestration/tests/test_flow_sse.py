"""Tests for flow_sse.py — v3.15.3 cross-layer event bus.

Covers:
- subscribe / unsubscribe lifecycle
- publish only delivers to matching key
- publish drops oldest when queue full (backpressure)
- async context manager subscription
- subscriber_count reflects state
- get_flow_event_bus singleton + reset
"""

from __future__ import annotations

import asyncio

from eaasp_common.business_flow import BusinessKey
from eaasp_l4_orchestration.flow_sse import (
    FlowEventBus,
    get_flow_event_bus,
    reset_flow_event_bus,
    subscribe_to_business_flow,
)
from eaasp_l4_orchestration.flow_timeline import BusinessFlowEvent


def _ev(ts: int = 1000, event_type: str = "test.event") -> BusinessFlowEvent:
    return BusinessFlowEvent(
        ts=ts, layer="L4", component="test", event_type=event_type, payload={}
    )


# ─── subscribe / unsubscribe ────────────────────────────────────────────────


async def test_subscribe_returns_queue() -> None:
    bus = FlowEventBus()
    sub = await bus.subscribe(BusinessKey(session_id="s1"))
    assert sub.queue is not None
    assert sub.key.session_id == "s1"
    await bus.unsubscribe(sub)
    assert bus.subscriber_count == 0


async def test_unsubscribe_idempotent() -> None:
    bus = FlowEventBus()
    sub = await bus.subscribe(BusinessKey(session_id="s1"))
    await bus.unsubscribe(sub)
    await bus.unsubscribe(sub)  # second call should not raise
    assert bus.subscriber_count == 0


# ─── publish matching ───────────────────────────────────────────────────────


async def test_publish_delivers_to_matching() -> None:
    bus = FlowEventBus()
    sub = await bus.subscribe(BusinessKey(session_id="s1", skill_id="k1"))
    n = await bus.publish(_ev(), BusinessKey(session_id="s1", skill_id="k1"))
    assert n == 1
    assert sub.queue.qsize() == 1
    await bus.unsubscribe(sub)


async def test_publish_skips_non_matching() -> None:
    bus = FlowEventBus()
    sub = await bus.subscribe(BusinessKey(session_id="s1"))
    n = await bus.publish(_ev(), BusinessKey(session_id="s2"))
    assert n == 0
    assert sub.queue.qsize() == 0
    await bus.unsubscribe(sub)


async def test_publish_prefix_match() -> None:
    """A subscriber with empty skill_id matches any skill in the published key."""
    bus = FlowEventBus()
    sub = await bus.subscribe(BusinessKey(session_id="s1"))
    n = await bus.publish(_ev(), BusinessKey(session_id="s1", skill_id="k1"))
    assert n == 1
    await bus.unsubscribe(sub)


# ─── backpressure ───────────────────────────────────────────────────────────


async def test_publish_drops_oldest_when_full() -> None:
    bus = FlowEventBus(queue_max=2)
    sub = await bus.subscribe(BusinessKey(session_id="s1"))
    # Fill the queue
    await bus.publish(_ev(ts=1), BusinessKey(session_id="s1"))
    await bus.publish(_ev(ts=2), BusinessKey(session_id="s1"))
    assert sub.queue.qsize() == 2
    # Publish one more — should drop ts=1 and queue ts=3
    await bus.publish(_ev(ts=3), BusinessKey(session_id="s1"))
    assert sub.queue.qsize() == 2
    first = sub.queue.get_nowait()
    second = sub.queue.get_nowait()
    assert first.ts == 2
    assert second.ts == 3
    await bus.unsubscribe(sub)


# ─── context manager ────────────────────────────────────────────────────────


async def test_subscribe_to_business_flow_context_manager() -> None:
    bus = FlowEventBus()
    async with subscribe_to_business_flow(bus, BusinessKey(session_id="s1")) as sub:
        assert bus.subscriber_count == 1
        await bus.publish(_ev(ts=42), BusinessKey(session_id="s1"))
        ev = await asyncio.wait_for(sub.queue.get(), timeout=1.0)
        assert ev.ts == 42
    # After exit, subscription is cleaned up.
    assert bus.subscriber_count == 0


# ─── singleton ──────────────────────────────────────────────────────────────


def test_get_flow_event_bus_singleton() -> None:
    reset_flow_event_bus()
    a = get_flow_event_bus()
    b = get_flow_event_bus()
    assert a is b


def test_reset_flow_event_bus_creates_new() -> None:
    reset_flow_event_bus()
    a = get_flow_event_bus()
    reset_flow_event_bus()
    b = get_flow_event_bus()
    assert a is not b
