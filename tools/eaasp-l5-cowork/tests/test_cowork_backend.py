"""v3.13.0 — Cowork backend (FastAPI) tests.

REQ-IDs: CARD-* (REST surface) + D-33 (tenant binding).

Exercises the FastAPI app via ASGI transport so the JSON
contracts + tenant boundary are pinned without booting uvicorn.
"""

from __future__ import annotations

import httpx

from conftest import (
    seed_event_room,
    seed_l2_anchor,
    seed_l3_decision,
    seed_l4_telemetry,
    seed_room_event,
)

from eaasp_l5_cowork.cowork import CoworkConfig, create_app
from eaasp_l5_cowork.projection import CoworkProjection


def _make_client(
    init_l2: str, init_l3: str, init_l4: str
) -> tuple[httpx.AsyncClient, CoworkProjection]:
    proj = CoworkProjection(
        l2_db_path=str(init_l2),
        l3_db_path=str(init_l3),
        l4_db_path=str(init_l4),
    )
    cfg = CoworkConfig(
        l2_db_path=str(init_l2),
        l3_db_path=str(init_l3),
        l4_db_path=str(init_l4),
        default_tenant="acme",
    )
    app = create_app(config=cfg, projection=proj)
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    return client, proj


async def test_health(init_l2: str, init_l3: str, init_l4: str) -> None:
    """Health probe returns OK + DB paths."""
    client, _ = _make_client(init_l2, init_l3, init_l4)
    async with client as c:
        r = await c.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["l2_db"] == str(init_l2)
        assert body["l3_db"] == str(init_l3)
        assert body["l4_db"] == str(init_l4)


async def test_cards_endpoint_returns_all_four_types(
    init_l2: str, init_l3: str, init_l4: str
) -> None:
    """GET /v1/cowork/cards?session_id=... returns 4 lists + total."""
    await seed_event_room(
        init_l4,
        room_id="er_api01",
        tenant_id="acme",
        session_ids=["sess_a"],
    )
    await seed_room_event(
        init_l4,
        room_id="er_api01",
        session_id="sess_a",
        event_type="a2a.request.sent",
        payload={"k": "v"},
    )
    await seed_l2_anchor(
        init_l2,
        anchor_id="anc_1",
        event_id="evt_1",
        session_id="sess_a",
    )
    await seed_l4_telemetry(
        init_l4,
        event_id="tev_1",
        session_id="sess_a",
        hook_id="PreToolUse",
        payload={"tool_name": "scada_read_snapshot"},
        tiebreaker=1,
    )
    await seed_l3_decision(
        init_l3,
        decision_id="gd_plan",
        session_id="sess_a",
        hook_id="PreToolUse",
        tool_name="scada_read_snapshot",
        risk_level="read",
        decision="allow",
        rationale="plan:ok",
        stage="plan",
    )

    client, _ = _make_client(init_l2, init_l3, init_l4)
    async with client as c:
        r = await c.get(
            "/v1/cowork/cards",
            params={"session_id": "sess_a", "tenant_id": "acme"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["session_id"] == "sess_a"
        assert body["tenant_id"] == "acme"
        assert len(body["events"]) == 1
        assert len(body["evidence"]) == 1
        assert len(body["actions"]) == 1
        assert len(body["approvals"]) == 1
        assert body["total"] == 4


async def test_cards_endpoint_card_type_filter(
    init_l2: str, init_l3: str, init_l4: str
) -> None:
    """``card_type=`` query param filters to a single list."""
    await seed_event_room(
        init_l4,
        room_id="er_api02",
        tenant_id="acme",
        session_ids=["sess_a"],
    )
    await seed_l2_anchor(
        init_l2,
        anchor_id="anc_f1",
        event_id="evt_f1",
        session_id="sess_a",
    )
    await seed_l3_decision(
        init_l3,
        decision_id="gd_f1",
        session_id="sess_a",
        hook_id="PreToolUse",
        tool_name="t",
        risk_level="read",
        decision="allow",
        rationale="ok",
        stage="plan",
    )

    client, _ = _make_client(init_l2, init_l3, init_l4)
    async with client as c:
        r = await c.get(
            "/v1/cowork/cards",
            params={
                "session_id": "sess_a",
                "tenant_id": "acme",
                "card_type": "evidence",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["evidence"]) == 1
        assert body["events"] == []
        assert body["actions"] == []
        assert body["approvals"] == []
        assert body["total"] == 1


async def test_cards_endpoint_tenant_via_header(
    init_l2: str, init_l3: str, init_l4: str
) -> None:
    """``X-Tenant-Id`` header binds the caller tenant (D-33)."""
    await seed_event_room(
        init_l4,
        room_id="er_h01",
        tenant_id="acme",
        session_ids=["sess_a"],
    )
    await seed_l2_anchor(
        init_l2,
        anchor_id="anc_h1",
        event_id="evt_h1",
        session_id="sess_a",
    )
    client, _ = _make_client(init_l2, init_l3, init_l4)
    async with client as c:
        # Header takes priority over query param (matches v3.12.1 D-28 pattern).
        r = await c.get(
            "/v1/cowork/cards",
            params={"session_id": "sess_a", "tenant_id": "globex"},
            headers={"X-Tenant-Id": "acme"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["tenant_id"] == "acme"
        assert len(body["evidence"]) == 1


async def test_cards_endpoint_default_tenant_when_no_header(
    init_l2: str, init_l3: str, init_l4: str
) -> None:
    """No header / no query param → ``CoworkConfig.default_tenant``."""
    await seed_event_room(
        init_l4,
        room_id="er_def01",
        tenant_id="acme",
        session_ids=["sess_a"],
    )
    await seed_l2_anchor(
        init_l2,
        anchor_id="anc_def1",
        event_id="evt_def1",
        session_id="sess_a",
    )
    client, _ = _make_client(init_l2, init_l3, init_l4)
    async with client as c:
        r = await c.get(
            "/v1/cowork/cards",
            params={"session_id": "sess_a"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["tenant_id"] == "acme"  # default


async def test_cards_endpoint_invalid_session_id_rejected(
    init_l2: str, init_l3: str, init_l4: str
) -> None:
    """Session_id pattern guard rejects unsafe characters."""
    client, _ = _make_client(init_l2, init_l3, init_l4)
    async with client as c:
        r = await c.get(
            "/v1/cowork/cards",
            params={"session_id": "../etc/passwd"},
        )
        assert r.status_code == 422


async def test_trace_endpoint_placeholder_returns_four_lists(
    init_l2: str, init_l3: str, init_l4: str
) -> None:
    """GET /v1/cowork/trace/{session_id} returns 4 lists (03.13.0 placeholder).

    Full RETROSPECTIVE-* (cross_refs + idempotency + 403) lands
    in 03.13.2.
    """
    await seed_event_room(
        init_l4,
        room_id="er_trace01",
        tenant_id="acme",
        session_ids=["sess_a"],
    )
    await seed_l2_anchor(
        init_l2,
        anchor_id="anc_t1",
        event_id="evt_t1",
        session_id="sess_a",
    )
    client, _ = _make_client(init_l2, init_l3, init_l4)
    async with client as c:
        # Note: 03.13.0 trace endpoint takes session_id via query (the
        # path-param URL lands in 03.13.2 when the route moves under
        # the RETROSPECTIVE envelope).
        r = await c.get(
            "/v1/cowork/trace/sess_a",
            params={"tenant_id": "acme"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["session_id"] == "sess_a"
        assert body["tenant_id"] == "acme"
        assert len(body["evidence"]) == 1
        assert body["cross_refs"] == []
        assert body["phase"] == "03.13.0"
