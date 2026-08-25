"""v3.16 live business-flow SSE publishing from the EventEngine."""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from eaasp_common.business_flow import BusinessKey
from eaasp_l4_orchestration.db import connect
from eaasp_l4_orchestration.flow_sse import (
    get_flow_event_bus,
    reset_flow_event_bus,
)
from eaasp_l4_orchestration.flow_timeline import BusinessFlowEvent


async def _set_session_business_key(
    db_path: str, session_id: str, business_key: str | None
) -> None:
    db = await connect(db_path)
    try:
        await db.execute(
            "UPDATE sessions SET business_key = ? WHERE session_id = ?",
            (business_key, session_id),
        )
        await db.commit()
    finally:
        await db.close()


async def test_rest_ingest_publishes_persisted_session_key_to_live_bus(
    app_client: httpx.AsyncClient,
    tmp_db_path: str,
    seed_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REST fallback shares the post-persist observer path used by all ingress."""
    reset_flow_event_bus()
    session_id = await seed_session("sess_v316_live_valid")
    key = BusinessKey(
        session_id=session_id,
        skill_id="skill.live",
        business_object_id="transformer-001",
    )
    await _set_session_business_key(tmp_db_path, session_id, key.to_header())
    bus = get_flow_event_bus()
    real_publish = bus.publish
    published_keys: list[BusinessKey] = []

    async def capture_publish(
        event: BusinessFlowEvent, published_key: BusinessKey
    ) -> int:
        published_keys.append(published_key)
        return await real_publish(event, published_key)

    monkeypatch.setattr(bus, "publish", capture_publish)
    sub = await bus.subscribe(key)
    before_ms = int(time.time() * 1000)

    try:
        response = await app_client.post(
            "/v1/events/ingest",
            json={
                "session_id": session_id,
                "event_type": "PRE_TOOL_USE",
                "payload": {"tool_name": "scada_read"},
                "source": "runtime:grid-runtime",
            },
        )
        event = await asyncio.wait_for(sub.queue.get(), timeout=0.5)
    finally:
        await bus.unsubscribe(sub)

    assert response.status_code == 200
    assert published_keys == [key]
    # Event.created_at is stored as whole seconds; fan-out converts that
    # canonical source timestamp to milliseconds rather than using a new clock.
    assert event.ts >= before_ms - 1000
    assert event.ts % 1000 == 0
    assert event.layer == "L4"
    assert event.component == "runtime:grid-runtime"
    assert event.event_type == "PRE_TOOL_USE"
    assert event.payload == {"tool_name": "scada_read"}


async def test_rest_ingest_skips_live_publish_for_null_persisted_key(
    app_client: httpx.AsyncClient,
    tmp_db_path: str,
    seed_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy sessions with NULL keys are durable-only and never inferred."""
    reset_flow_event_bus()
    session_id = await seed_session("sess_v316_live_null")
    await _set_session_business_key(tmp_db_path, session_id, None)
    bus = get_flow_event_bus()
    published: list[object] = []

    async def capture_publish(*args: object) -> int:
        published.append(args)
        return 0

    monkeypatch.setattr(bus, "publish", capture_publish)

    response = await app_client.post(
        "/v1/events/ingest",
        json={"session_id": session_id, "event_type": "STOP", "payload": {}},
    )

    assert response.status_code == 200
    assert published == []


async def test_rest_ingest_skips_live_publish_for_malformed_persisted_key(
    app_client: httpx.AsyncClient,
    tmp_db_path: str,
    seed_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed historical keys are not repaired or used for fan-out."""
    reset_flow_event_bus()
    session_id = await seed_session("sess_v316_live_malformed")
    await _set_session_business_key(tmp_db_path, session_id, "not-a-canonical-key")
    bus = get_flow_event_bus()
    published: list[object] = []

    async def capture_publish(*args: object) -> int:
        published.append(args)
        return 0

    monkeypatch.setattr(bus, "publish", capture_publish)

    response = await app_client.post(
        "/v1/events/ingest",
        json={"session_id": session_id, "event_type": "STOP", "payload": {}},
    )

    assert response.status_code == 200
    assert published == []
