"""v3.16 browser authentication transport checks for direct-L4 development."""

from __future__ import annotations

import httpx

from eaasp_l4_orchestration.api import create_app


async def test_dev_cors_preflight_allows_authorization_for_flow_sse(
    monkeypatch,
    tmp_db_path: str,
) -> None:
    """The direct-L4 dev topology permits the Bearer header used by SSE."""
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
