"""v3.16 browser credential-transport checks for direct-L4 development."""

from __future__ import annotations

import asyncio

import httpx

from eaasp_common.business_flow import BusinessKey
from eaasp_l4_orchestration.api import create_app
from eaasp_l4_orchestration.flow_sse import get_flow_event_bus, reset_flow_event_bus


async def test_dev_cors_preflight_allows_authorization_for_flow_sse(
    monkeypatch,
    tmp_db_path: str,
) -> None:
    """The direct-L4 dev topology permits the forwarded Bearer header."""
    monkeypatch.setenv("L4_ENV", "dev")
    app = create_app(tmp_db_path)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.options(
            "/v1/business-flows/session%7Cskill%7Cobject/events/stream",
            headers={
                "Origin": "http://127.0.0.1:5180",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )

    assert response.status_code == 200, response.text
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


async def test_direct_l4_dev_sse_accepts_missing_bearer_header(
    monkeypatch,
    tmp_db_path: str,
) -> None:
    """Bearer tolerance is a dev-only L4 transport contract, not auth."""
    monkeypatch.setenv("L4_ENV", "dev")
    reset_flow_event_bus()
    bus = get_flow_event_bus()
    app = create_app(tmp_db_path)
    key = BusinessKey("session-dev", "skill-dev", "object-dev")
    disconnected = asyncio.Event()
    request_seen = False
    sent: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        nonlocal request_seen
        if not request_seen:
            request_seen = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, object]) -> None:
        sent.append(message)

    scope: dict[str, object] = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": f"/v1/business-flows/{key.to_header()}/events/stream",
        "raw_path": f"/v1/business-flows/{key.to_header()}/events/stream".encode(),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 5180),
        "server": ("127.0.0.1", 18084),
    }

    async with app.router.lifespan_context(app):
        request = asyncio.create_task(app(scope, receive, send))
        try:
            for _ in range(50):
                if bus.subscriber_count == 1:
                    break
                await asyncio.sleep(0.01)
            assert bus.subscriber_count == 1
            assert sent[0]["type"] == "http.response.start"
            assert sent[0]["status"] == 200
        finally:
            disconnected.set()
            await asyncio.wait_for(request, timeout=1.0)
