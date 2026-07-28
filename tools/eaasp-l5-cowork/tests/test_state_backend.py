"""v3.13.1 — Cowork state-machine backend (FastAPI) tests.

Covers:

- ``POST /v1/cowork/cards/{card_id}/transition`` — operator-driven
  state transitions (404, 409 invalid, 200 happy path).
- ``GET  /v1/cowork/cards/{card_id}/transitions`` — append-only log.
- ``GET  /v1/cowork/sessions/{session_id}/cards`` — list by state.
- Cross-tenant rejection (D-33).
"""

from __future__ import annotations

from pathlib import Path

import httpx

from eaasp_l5_cowork.cowork import CoworkConfig, create_app
from eaasp_l5_cowork.projection import CoworkProjection
from eaasp_l5_cowork.state import (
    CARD_APPROVAL,
    STATE_CLOSED,
    STATE_ESCALATED,
    STATE_IN_PROGRESS,
    STATE_OPEN,
    CoworkStateStore,
)


async def _make_app_and_client(
    init_l2: Path, init_l3: Path, init_l4: Path, tmp_path: Path
) -> tuple[httpx.AsyncClient, CoworkStateStore]:
    proj = CoworkProjection(
        l2_db_path=str(init_l2),
        l3_db_path=str(init_l3),
        l4_db_path=str(init_l4),
    )
    state_store = CoworkStateStore(str(tmp_path / "cowork.db"))
    cfg = CoworkConfig(
        l2_db_path=str(init_l2),
        l3_db_path=str(init_l3),
        l4_db_path=str(init_l4),
        state_db_path=str(tmp_path / "cowork.db"),
        default_tenant="acme",
    )
    # Initialise the state schema up front so tests can seed
    # cards before any HTTP round-trip.
    await state_store.init_db()
    app = create_app(config=cfg, projection=proj, state_store=state_store)
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    return client, state_store


async def _seed_card(
    store: CoworkStateStore,
    *,
    card_id: str,
    tenant_id: str = "acme",
    session_id: str = "sess_a",
) -> None:
    await store.upsert_card(
        card_id=card_id,
        session_id=session_id,
        tenant_id=tenant_id,
        card_type=CARD_APPROVAL,
        source_id="gd_1",
        summary="plan:ok",
    )


# ─── /transition ────────────────────────────────────────────────────────


async def test_transition_happy_path(
    init_l2: Path, init_l3: Path, init_l4: Path, tmp_path: Path
) -> None:
    """POST /transition open → in_progress returns 200."""
    client, store = await _make_app_and_client(init_l2, init_l3, init_l4, tmp_path)
    await _seed_card(store, card_id="card_h1")
    async with client as c:
        r = await c.post(
            "/v1/cowork/cards/card_h1/transition",
            json={
                "to_state": STATE_IN_PROGRESS,
                "actor": "alice",
                "rationale": "picking up",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["card_id"] == "card_h1"
        assert body["from_state"] == STATE_OPEN
        assert body["to_state"] == STATE_IN_PROGRESS


async def test_transition_invalid_state_machine_rejects_409(
    init_l2: Path, init_l3: Path, init_l4: Path, tmp_path: Path
) -> None:
    """Invalid transition (in_progress → open) returns 409."""
    client, store = await _make_app_and_client(init_l2, init_l3, init_l4, tmp_path)
    await _seed_card(store, card_id="card_h2")
    # First move it to in_progress (legal).
    await store.transition(card_id="card_h2", to_state=STATE_IN_PROGRESS)
    async with client as c:
        r = await c.post(
            "/v1/cowork/cards/card_h2/transition",
            json={"to_state": STATE_OPEN},
        )
        assert r.status_code == 409, r.text
        body = r.json()
        assert body["detail"]["code"] == "invalid_transition"


async def test_transition_unknown_card_returns_404(
    init_l2: Path, init_l3: Path, init_l4: Path, tmp_path: Path
) -> None:
    client, _ = await _make_app_and_client(init_l2, init_l3, init_l4, tmp_path)
    async with client as c:
        r = await c.post(
            "/v1/cowork/cards/nonexistent/transition",
            json={"to_state": STATE_IN_PROGRESS},
        )
        assert r.status_code == 404


async def test_transition_invalid_state_string_returns_422(
    init_l2: Path, init_l3: Path, init_l4: Path, tmp_path: Path
) -> None:
    client, store = await _make_app_and_client(init_l2, init_l3, init_l4, tmp_path)
    await _seed_card(store, card_id="card_h3")
    async with client as c:
        r = await c.post(
            "/v1/cowork/cards/card_h3/transition",
            json={"to_state": "bogus"},
        )
        assert r.status_code == 422


async def test_transition_cross_tenant_returns_403(
    init_l2: Path, init_l3: Path, init_l4: Path, tmp_path: Path
) -> None:
    """Cross-tenant transition is rejected with 403 (D-33)."""
    client, store = await _make_app_and_client(init_l2, init_l3, init_l4, tmp_path)
    # Card belongs to globex; caller is acme (default).
    await _seed_card(store, card_id="card_x1", tenant_id="globex")
    async with client as c:
        r = await c.post(
            "/v1/cowork/cards/card_x1/transition",
            json={"to_state": STATE_IN_PROGRESS},
            headers={"X-Tenant-Id": "acme"},
        )
        assert r.status_code == 403, r.text


# ─── /transitions ───────────────────────────────────────────────────────


async def test_list_transitions_returns_full_log(
    init_l2: Path, init_l3: Path, init_l4: Path, tmp_path: Path
) -> None:
    """GET /transitions returns the append-only log in canonical order."""
    client, store = await _make_app_and_client(init_l2, init_l3, init_l4, tmp_path)
    await _seed_card(store, card_id="card_l1")
    await store.transition(card_id="card_l1", to_state=STATE_IN_PROGRESS)
    await store.transition(card_id="card_l1", to_state=STATE_ESCALATED)
    await store.transition(card_id="card_l1", to_state=STATE_IN_PROGRESS)
    await store.transition(card_id="card_l1", to_state=STATE_CLOSED)

    async with client as c:
        r = await c.get("/v1/cowork/cards/card_l1/transitions")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 5  # initial + 4
        states = [t["to_state"] for t in body["transitions"]]
        assert states == [
            STATE_OPEN,
            STATE_IN_PROGRESS,
            STATE_ESCALATED,
            STATE_IN_PROGRESS,
            STATE_CLOSED,
        ]


# ─── /sessions/{session_id}/cards ───────────────────────────────────────


async def test_session_cards_endpoint(
    init_l2: Path, init_l3: Path, init_l4: Path, tmp_path: Path
) -> None:
    """GET /sessions/{id}/cards returns every card (state-filter optional)."""
    client, store = await _make_app_and_client(init_l2, init_l3, init_l4, tmp_path)
    await _seed_card(store, card_id="c_s1")
    await _seed_card(store, card_id="c_s2")
    await store.transition(card_id="c_s2", to_state=STATE_CLOSED)
    async with client as c:
        r = await c.get("/v1/cowork/sessions/sess_a/cards")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 2
        assert body["state"] is None

        r = await c.get(
            "/v1/cowork/sessions/sess_a/cards", params={"state": STATE_CLOSED}
        )
        body = r.json()
        assert body["total"] == 1
        assert body["cards"][0]["card_id"] == "c_s2"


async def test_session_cards_state_filter_invalid_422(
    init_l2: Path, init_l3: Path, init_l4: Path, tmp_path: Path
) -> None:
    client, _ = await _make_app_and_client(init_l2, init_l3, init_l4, tmp_path)
    async with client as c:
        r = await c.get(
            "/v1/cowork/sessions/sess_a/cards",
            params={"state": "bogus"},
        )
        assert r.status_code == 422


# ─── Cross-tenant on /transitions ──────────────────────────────────────


async def test_transitions_cross_tenant_returns_403(
    init_l2: Path, init_l3: Path, init_l4: Path, tmp_path: Path
) -> None:
    client, store = await _make_app_and_client(init_l2, init_l3, init_l4, tmp_path)
    await _seed_card(store, card_id="c_x2", tenant_id="globex")
    async with client as c:
        r = await c.get(
            "/v1/cowork/cards/c_x2/transitions",
            headers={"X-Tenant-Id": "acme"},
        )
        assert r.status_code == 403


# ─── SSE event family (D-36 extension) ─────────────────────────────────


async def test_session_stream_emits_card_events(
    init_l2: Path, init_l3: Path, init_l4: Path, tmp_path: Path
) -> None:
    """SSE bridge emits ``cowork.card.<type>.created`` + transitions.

    Validates that the full D-36 event family members
    (created / updated / closed / workflow.advanced /
    workflow.escalated) are emitted by the v3.13.1 backend.
    """
    client, store = await _make_app_and_client(init_l2, init_l3, init_l4, tmp_path)
    await _seed_card(store, card_id="c_stream_1")
    await store.transition(card_id="c_stream_1", to_state=STATE_IN_PROGRESS)
    await store.transition(card_id="c_stream_1", to_state=STATE_ESCALATED)
    await store.transition(card_id="c_stream_1", to_state=STATE_CLOSED)

    async with client as c:
        r = await c.get(
            "/v1/cowork/sessions/sess_a/stream",
            params={"max_idle_polls": 1, "poll_interval_ms": 50},
        )
        assert r.status_code == 200, r.text
        body = r.text
        # The 5 SSE event family members should each appear at least once.
        assert "event: cowork.card.approval.created" in body
        assert "event: cowork.card.approval.updated" in body
        assert "event: cowork.card.approval.closed" in body
        assert "event: cowork.workflow.advanced" in body
        assert "event: cowork.workflow.escalated" in body
