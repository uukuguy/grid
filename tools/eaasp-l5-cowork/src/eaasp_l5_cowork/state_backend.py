"""v3.13.1 backend extension — card state machine + SSE fan-out + persistence.

This module extends the v3.13.0 Cowork backend with:

- ``POST /v1/cowork/cards/{card_id}/transition`` — operator-driven
  state transitions (open → in_progress → closed / escalated).
- ``GET  /v1/cowork/cards/{card_id}/transitions`` — full
  append-only transition log (RETROSPECTIVE cross-ref source).
- ``GET  /v1/cowork/sessions/{session_id}/cards`` — list every
  Cowork card for a session (state-filtered, tenant-bound).
- ``GET  /v1/cowork/sessions/{session_id}/stream`` — extended SSE
  bridge that emits the full ``cowork.card.<type>.<event>`` family
  (created / updated / closed) + ``cowork.workflow.<event>``
  (advanced / escalated).

Routes are wired into the L5 FastAPI app via
``wire_state_routes(app, store, ...)``. The state store lives in
``CoworkStateStore`` (see ``state.py``).
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Annotated, Any

from fastapi import FastAPI, Header, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from .state import (
    ALL_STATES,
    CARD_ACTION,
    CARD_APPROVAL,
    CARD_EVIDENCE,
    CARD_EVENT,
    STATE_CLOSED,
    STATE_ESCALATED,
    STATE_IN_PROGRESS,
    CoworkCardNotFound,
    CoworkInvalidTransition,
    CoworkStateStore,
    CoworkTransition,
    EVENT_CLOSED,
    EVENT_CREATED,
    EVENT_UPDATED,
    EVENT_WORKFLOW_ADVANCED,
    EVENT_WORKFLOW_ESCALATED,
    make_event_name,
)


# ─── Request / response models ──────────────────────────────────────────


class TransitionRequest(BaseModel):
    to_state: str = Field(..., min_length=1)
    actor: str | None = None
    rationale: str = ""


class TransitionResponse(BaseModel):
    card_id: str
    from_state: str | None
    to_state: str
    transition_id: int
    rationale: str = ""
    actor: str | None = None
    created_at: int


class CardsListResponse(BaseModel):
    session_id: str
    tenant_id: str
    state: str | None
    cards: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


# ─── Tenant resolution (mirrors cowork.py) ──────────────────────────────


def _resolve_caller_tenant(
    header_tenant: str | None,
    query_tenant: str | None,
    config_default: str,
) -> str:
    if header_tenant and header_tenant.strip():
        return header_tenant.strip()
    if query_tenant and query_tenant.strip():
        return query_tenant.strip()
    return config_default


# ─── Route wiring ────────────────────────────────────────────────────────


def wire_state_routes(
    app: FastAPI,
    store: CoworkStateStore,
    *,
    default_tenant: str = "default",
) -> None:
    """Mount the v3.13.1 state machine + SSE fan-out routes."""

    @app.post("/v1/cowork/cards/{card_id}/transition")
    async def transition_card(
        card_id: Annotated[
            str, Path(min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
        ],
        body: TransitionRequest,
        x_tenant_id: Annotated[str | None, Header()] = None,
        tenant_id: Annotated[str | None, Query()] = None,
    ) -> TransitionResponse:
        """Drive a card through the state machine (operator action)."""
        caller_tenant = _resolve_caller_tenant(
            x_tenant_id, tenant_id, default_tenant
        )
        if body.to_state not in ALL_STATES:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_state",
                    "to_state": body.to_state,
                    "valid_states": sorted(ALL_STATES),
                },
            )
        try:
            updated, transition = await store.transition(
                card_id=card_id,
                to_state=body.to_state,
                actor=body.actor,
                rationale=body.rationale,
            )
        except CoworkCardNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "card_not_found", "card_id": exc.card_id},
            ) from exc
        except CoworkInvalidTransition as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "invalid_transition",
                    "card_id": exc.card_id,
                    "from_state": exc.from_state,
                    "to_state": exc.to_state,
                },
            ) from exc

        # Tenant gate (D-33) — defensive.
        if updated.tenant_id != caller_tenant:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "cross_tenant_forbidden",
                    "caller_tenant": caller_tenant,
                    "card_tenant": updated.tenant_id,
                },
            )

        logger.info(
            "cowork_transition card_id={} from={} to={} actor={}",
            card_id,
            transition.from_state,
            transition.to_state,
            body.actor,
        )
        return TransitionResponse(
            card_id=card_id,
            from_state=transition.from_state,
            to_state=transition.to_state,
            transition_id=transition.transition_id,
            rationale=transition.rationale,
            actor=transition.actor,
            created_at=transition.created_at,
        )

    @app.get("/v1/cowork/cards/{card_id}/transitions")
    async def list_transitions(
        card_id: Annotated[
            str, Path(min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
        ],
        x_tenant_id: Annotated[str | None, Header()] = None,
        tenant_id: Annotated[str | None, Query()] = None,
    ) -> dict[str, Any]:
        """Return the full append-only transition log for a card."""
        caller_tenant = _resolve_caller_tenant(
            x_tenant_id, tenant_id, default_tenant
        )
        cards = await store.list_cards_by_id(card_id)
        if not cards:
            raise HTTPException(
                status_code=404,
                detail={"code": "card_not_found", "card_id": card_id},
            )
        # Tenant gate.
        if cards[0].tenant_id != caller_tenant:
            raise HTTPException(
                status_code=403,
                detail={"code": "cross_tenant_forbidden"},
            )
        transitions = await store.list_transitions(card_id)
        return {
            "card_id": card_id,
            "tenant_id": caller_tenant,
            "transitions": [t.to_dict() for t in transitions],
            "total": len(transitions),
        }

    @app.get("/v1/cowork/sessions/{session_id}/cards")
    async def list_session_cards(
        session_id: Annotated[
            str, Path(min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
        ],
        x_tenant_id: Annotated[str | None, Header()] = None,
        tenant_id: Annotated[str | None, Query()] = None,
        state: Annotated[
            str | None,
            Query(description=f"Optional filter: one of {sorted(ALL_STATES)}"),
        ] = None,
    ) -> CardsListResponse:
        """List every Cowork card for a session, optionally state-filtered."""
        caller_tenant = _resolve_caller_tenant(
            x_tenant_id, tenant_id, default_tenant
        )
        if state and state not in ALL_STATES:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_state",
                    "state": state,
                    "valid_states": sorted(ALL_STATES),
                },
            )
        cards = await store.list_cards(
            session_id, tenant_id=caller_tenant
        )
        if state:
            cards = [c for c in cards if c.state == state]
        return CardsListResponse(
            session_id=session_id,
            tenant_id=caller_tenant,
            state=state,
            cards=[c.to_dict() for c in cards],
            total=len(cards),
        )

    @app.get("/v1/cowork/sessions/{session_id}/stream")
    async def stream_session(
        session_id: Annotated[
            str, Path(min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
        ],
        x_tenant_id: Annotated[str | None, Header()] = None,
        tenant_id: Annotated[str | None, Query()] = None,
        poll_interval_ms: int = Query(default=500, ge=50, le=5000),
        heartbeat_secs: int = Query(default=15, ge=1, le=120),
        max_idle_polls: int = Query(default=20, ge=0, le=10000),
    ) -> StreamingResponse:
        """SSE stream — emits ``cowork.card.<type>.<event>`` family.

        v3.13.1 — extended beyond 03.13.0's ``*.created`` only.
        The bridge now also emits ``cowork.card.<type>.updated``
        (when a card's state changes via the transition endpoint)
        and ``cowork.card.<type>.closed`` (when a card reaches
        STATE_CLOSED).

        The bridge also emits ``cowork.workflow.advanced`` and
        ``cowork.workflow.escalated`` so a Cowork UI can render
        workflow-level events distinct from card-level events.
        """
        caller_tenant = _resolve_caller_tenant(
            x_tenant_id, tenant_id, default_tenant
        )

        async def _sse_generator():
            seen_card_ids: set[str] = set()
            seen_transition_ids: set[int] = set()
            last_heartbeat = asyncio.get_event_loop().time()
            idle_polls = 0
            try:
                while True:
                    try:
                        cards = await store.list_cards(
                            session_id, tenant_id=caller_tenant
                        )
                        for c in cards:
                            if c.card_id in seen_card_ids:
                                continue
                            seen_card_ids.add(c.card_id)
                            payload = json.dumps(
                                c.to_dict(),
                                ensure_ascii=False,
                                default=str,
                            )
                            yield (
                                f"event: {make_event_name(EVENT_CREATED, c.card_type)}\n"
                                f"data: {payload}\n\n"
                            )
                        # Emit per-card transitions since last tick.
                        for c in cards:
                            try:
                                transitions = await store.list_transitions(
                                    c.card_id
                                )
                            except Exception:
                                continue
                            for t in transitions:
                                if t.transition_id in seen_transition_ids:
                                    continue
                                seen_transition_ids.add(t.transition_id)
                                payload = json.dumps(
                                    {
                                        "card_id": c.card_id,
                                        "card_type": c.card_type,
                                        "transition": t.to_dict(),
                                    },
                                    ensure_ascii=False,
                                    default=str,
                                )
                                if t.to_state == STATE_CLOSED:
                                    evt_name = make_event_name(
                                        EVENT_CLOSED, c.card_type
                                    )
                                elif t.to_state == STATE_ESCALATED:
                                    evt_name = EVENT_WORKFLOW_ESCALATED
                                else:
                                    evt_name = make_event_name(
                                        EVENT_UPDATED, c.card_type
                                    )
                                    # Workflow advanced notification
                                    # rides alongside the updated card.
                                    yield (
                                        f"event: {EVENT_WORKFLOW_ADVANCED}\n"
                                        f"data: {payload}\n\n"
                                    )
                                yield f"event: {evt_name}\ndata: {payload}\n\n"
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        logger.debug(
                            "sse_session_bridge_projection_failed "
                            "session_id={} detail={}",
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
            except asyncio.CancelledError:
                logger.info(
                    "sse_session_bridge_disconnect session_id={}",
                    session_id,
                )
                raise

        return StreamingResponse(
            _sse_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )


# CoworkStateStore.list_cards_by_id helper — small enough to add
# here rather than refactor state.py.
async def _list_cards_by_id(self: CoworkStateStore, card_id: str):
    """Return every Cowork card row for ``card_id`` (usually 0 or 1)."""
    from .state import _row_to_state  # type: ignore

    db = await self._open()  # type: ignore[attr-defined]
    try:
        cur = await db.execute(
            "SELECT * FROM cowork_cards WHERE card_id = ?",
            (card_id,),
        )
        row = await cur.fetchone()
    finally:
        await db.close()
    if row is None:
        return []
    return [_row_to_state(row)]


CoworkStateStore.list_cards_by_id = _list_cards_by_id  # type: ignore[attr-defined]


__all__ = ["wire_state_routes"]
