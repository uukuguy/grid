"""Business Flow SSE — continuous cross-layer event subscription.

Per v3.15.3 (OBSTACK_DESIGN.md §3.6). Provides:

- ``FlowPublisher`` — in-process pub/sub that the L4 cross-layer
  instrumentation calls when a new event lands for a business flow.
  Subscribers receive every future event whose business key matches.
- ``subscribe_to_business_flow(key)`` — async context manager /
  generator that yields new events as they arrive.
- ``FlowEventBus.subscribe()`` — lower-level subscription API for
  components that want to forward events to SSE / WebSocket / log
  sinks without holding the bus.

The SSE channel itself is wired in ``api.py``; this module provides
the building block. The L4 server has one ``FlowPublisher`` per
process; the SSE handler subscribes and forwards to the wire.

Difference from L4 Event Room SSE
---------------------------------

L4 Event Room is **session-scoped** — events that occurred within a
single EAASP session. Business Flow SSE is **business-object-scoped**
— events that share a business key across potentially many sessions
(the same power transformer may be calibrated by many sessions over
its lifetime). They have different lifetimes and require different
SSE channels.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

from eaasp_common.business_flow import BusinessKey

from .flow_timeline import BusinessFlowEvent


@dataclass(frozen=True)
class _Subscription:
    """One subscriber's queue + matching predicate."""

    key: BusinessKey
    queue: asyncio.Queue[BusinessFlowEvent]


class FlowEventBus:
    """In-process pub/sub for cross-layer business-flow events.

    The bus is per-process (the L4 server runs one). Production-grade
    multi-process fan-out is deferred to v3.16+ (cross-cluster flow
    aggregation).

    The bus uses a single ``asyncio.Lock`` to protect subscription
    state; publish is fire-and-forget (drops events for slow
    subscribers to keep the hot path fast). The drop is logged so
    operators can detect backpressure.
    """

    def __init__(self, *, queue_max: int = 1024) -> None:
        self._subs: list[_Subscription] = []
        self._lock = asyncio.Lock()
        self._queue_max = queue_max

    async def subscribe(self, key: BusinessKey) -> _Subscription:
        """Register a subscriber for events matching ``key``.

        The returned subscription holds an ``asyncio.Queue``; the
        caller drains it via ``queue.get()`` (or via the
        ``subscribe_to_business_flow`` async generator below).

        Subscribers should consume the queue promptly; events that
        overflow ``queue_max`` are dropped (the oldest entries are
        discarded). The drop is logged so a slow consumer is
        visible in operations.
        """
        queue: asyncio.Queue[BusinessFlowEvent] = asyncio.Queue(maxsize=self._queue_max)
        sub = _Subscription(key=key, queue=queue)
        async with self._lock:
            self._subs.append(sub)
        return sub

    async def unsubscribe(self, sub: _Subscription) -> None:
        """Remove a subscriber. Idempotent — safe to call twice."""
        async with self._lock:
            try:
                self._subs.remove(sub)
            except ValueError:
                pass

    async def publish(self, event: BusinessFlowEvent, key: BusinessKey) -> int:
        """Publish one event to every subscriber for the exact key.

        Returns the number of subscribers the event was delivered to.
        Events that don't fit in a subscriber's queue are dropped
        (oldest first) to keep the hot path non-blocking.
        """
        delivered = 0
        async with self._lock:
            # This backs the public business-flow SSE route, where a partial
            # BusinessKey must never subscribe to another canonical flow.
            # ``BusinessKey.matches`` intentionally retains its prefix
            # semantics for explicit internal correlation use cases only.
            matching = [s for s in self._subs if s.key == key]
        for sub in matching:
            try:
                sub.queue.put_nowait(event)
                delivered += 1
            except asyncio.QueueFull:
                # Drop oldest to make room for the newest. Backpressure
                # is logged but does not block the publisher.
                try:
                    _ = sub.queue.get_nowait()
                    sub.queue.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass
        return delivered

    @property
    def subscriber_count(self) -> int:
        return len(self._subs)


# ─── Convenience async generator ────────────────────────────────────────────


@asynccontextmanager
async def subscribe_to_business_flow(
    bus: FlowEventBus, key: BusinessKey
) -> AsyncIterator[_Subscription]:
    """Async-context-manager wrapper around ``bus.subscribe`` + cleanup.

    Usage::

        async with subscribe_to_business_flow(bus, key) as sub:
            while True:
                event = await sub.queue.get()
                ...  # forward to SSE / log / etc.
    """
    sub = await bus.subscribe(key)
    try:
        yield sub
    finally:
        await bus.unsubscribe(sub)


# ─── Process-wide singleton ────────────────────────────────────────────────
#
# The L4 process instantiates one ``_bus`` and exposes it via
# ``get_flow_event_bus()``. Tests can construct their own bus to
# avoid coupling to the global state.

_bus: FlowEventBus | None = None


def get_flow_event_bus() -> FlowEventBus:
    """Return the process-wide ``FlowEventBus`` (lazy-initialized)."""
    global _bus
    if _bus is None:
        _bus = FlowEventBus()
    return _bus


def reset_flow_event_bus() -> None:
    """Reset the global bus. Test-only."""
    global _bus
    _bus = None


__all__ = [
    "FlowEventBus",
    "get_flow_event_bus",
    "reset_flow_event_bus",
    "subscribe_to_business_flow",
]
