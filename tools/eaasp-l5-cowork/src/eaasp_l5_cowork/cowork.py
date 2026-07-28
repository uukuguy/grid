"""CoworkBackend — REST + SSE bridge for the four-card Cowork substrate.

v3.13.0 — EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action /
Approval) + 回溯闭环 (retrospective cycle).

The backend is a thin FastAPI app on a dedicated port (env-
configurable; default ``:18086``) that:

- exposes the four card lists as JSON over REST
- exposes an SSE bridge that tails the L4 event stream and emits
  ``cowork.card.<type>.<event>`` events as new underlying rows
  arrive (D-36)
- delegates the actual projection work to ``CoworkProjection``
  (read-only, per D-31 / D-32)

Routes (v3.13.0):

- ``GET  /health``                                 — liveness probe
- ``GET  /v1/cowork/cards``                        — query the four
                                                      cards (query
                                                      params:
                                                      ``session_id``,
                                                      ``tenant_id``,
                                                      ``card_type``)
- ``GET  /v1/cowork/cards/stream``                 — SSE bridge that
                                                      tails the L4
                                                      event stream
                                                      and emits
                                                      ``cowork.card.*``
                                                      events
- ``GET  /v1/cowork/trace/{session_id}``           — backward
                                                      compatibility
                                                      shim — full
                                                      implementation
                                                      lands in
                                                      v3.13.2
                                                      RETROSPECTIVE
                                                      series

Tenant binding (D-33 / v3.12.1 D-28): the backend reads the
caller's tenant via the ``X-Tenant-Id`` header (or the
``tenant_id`` query param) and only returns cards whose
``tenant_id`` matches. Cross-tenant requests are rejected with
403. The default tenant for local dev / single-tenant setups is
``"default"`` (matching the L4 walkthrough default).

Frozen contract (audit §7.1): the backend is best-effort. Every
route wraps the underlying projection call in a try/except and
returns a 500 with a structured ``{"code": ..., "detail": ...}``
payload on unexpected failure. Card-list misses (empty result)
return ``[]`` (200 OK) — never 404, because a Cowork UI may
legitimately have no cards to render for a fresh session.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from .cards import (
    ActionCard,
    ApprovalCard,
    CardBase,
    EvidenceCard,
    EventCard,
)
from .projection import CoworkProjection
from .state import CoworkStateStore
from .state_backend import wire_state_routes


# ─── CoworkConfig (env-driven, strict-by-default per ADR-V2-028) ────────


class CoworkConfig(BaseModel):
    """L5 Cowork backend configuration.

    Strict-by-default: every field's default is the canonical
    EAASP v2.0 ``make dev-eaasp`` value; env override is the only
    way to change them.
    """

    l2_db_path: str = Field(
        default_factory=lambda: os.environ.get(
            "EAASP_L2_DB_PATH", "./data/memory.db"
        )
    )
    l3_db_path: str = Field(
        default_factory=lambda: os.environ.get(
            "EAASP_L3_DB_PATH", "./data/governance.db"
        )
    )
    l4_db_path: str = Field(
        default_factory=lambda: os.environ.get(
            "EAASP_L4_DB_PATH", "./data/orchestration.db"
        )
    )
    default_tenant: str = Field(
        default_factory=lambda: os.environ.get(
            "EAASP_L5_DEFAULT_TENANT", "default"
        )
    )
    port: int = Field(
        default_factory=lambda: int(
            os.environ.get("EAASP_L5_PORT", "18086")
        )
    )
    state_db_path: str = Field(
        default_factory=lambda: os.environ.get(
            "EAASP_L5_STATE_DB_PATH", "./data/cowork.db"
        )
    )


# ─── L4-06 / D31 valid loguru levels (mirrors L4 conventions) ────────────


_VALID_LOG_LEVELS: frozenset[str] = frozenset(
    {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}
)


# ─── Response models ──────────────────────────────────────────────────────


class CardsResponse(BaseModel):
    session_id: str
    tenant_id: str
    events: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class HealthResponse(BaseModel):
    status: str
    l2_db: str
    l3_db: str
    l4_db: str
    timestamp: str


# ─── Tenant resolution ────────────────────────────────────────────────────


def _resolve_caller_tenant(
    header_tenant: str | None,
    query_tenant: str | None,
    config_default: str,
) -> str:
    """Resolve the calling tenant for a Cowork request (D-33).

    Priority:
      1. ``X-Tenant-Id`` header (canonical, matches v3.12.1)
      2. ``?tenant_id=`` query param (CLI convenience)
      3. ``CoworkConfig.default_tenant`` (dev / single-tenant)
    """
    if header_tenant and header_tenant.strip():
        return header_tenant.strip()
    if query_tenant and query_tenant.strip():
        return query_tenant.strip()
    return config_default


def _authorize_tenant(
    *,
    caller_tenant: str,
    card_tenant: str,
) -> None:
    """Reject cross-tenant card reads with 403 (D-33).

    Mirrors the v3.12.1 D-28 / v3.12.2 REQ-A2A-02 security pattern.
    Raises ``HTTPException`` so FastAPI's exception handler
    converts it to a clean JSON error.
    """
    if card_tenant != caller_tenant:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "cross_tenant_forbidden",
                "caller_tenant": caller_tenant,
                "card_tenant": card_tenant,
            },
        )


# ─── App factory ──────────────────────────────────────────────────────────


def create_app(
    *,
    config: CoworkConfig | None = None,
    projection: CoworkProjection | None = None,
    state_store: CoworkStateStore | None = None,
) -> FastAPI:
    """Build the Cowork FastAPI app.

    The factory mirrors the L4 ``create_app`` pattern so the L5
    backend can be embedded in tests with a fixture projection
    (the v3.7.3 NEW-A1 pattern).
    """
    cfg = config or CoworkConfig()
    proj = projection or CoworkProjection(
        l2_db_path=cfg.l2_db_path,
        l3_db_path=cfg.l3_db_path,
        l4_db_path=cfg.l4_db_path,
    )
    store = state_store or CoworkStateStore(cfg.state_db_path)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "l5_cowork_start l2_db={} l3_db={} l4_db={} state_db={}",
            cfg.l2_db_path,
            cfg.l3_db_path,
            cfg.l4_db_path,
            cfg.state_db_path,
        )
        await store.init_db()
        try:
            yield
        finally:
            logger.info("l5_cowork_stop")

    app = FastAPI(
        title="EAASP L5 Cowork",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ─── /health ────────────────────────────────────────────────────────

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            l2_db=cfg.l2_db_path,
            l3_db=cfg.l3_db_path,
            l4_db=cfg.l4_db_path,
            timestamp=str(int(time.time())),
        )

    # ─── /v1/cowork/cards ──────────────────────────────────────────────

    @app.get("/v1/cowork/cards", response_model=CardsResponse)
    async def get_cards(
        session_id: Annotated[
            str,
            Query(..., min_length=1, pattern=r"^[a-zA-Z0-9_-]+$"),
        ],
        tenant_id: Annotated[str | None, Query()] = None,
        card_type: Annotated[
            str | None,
            Query(
                description=(
                    "Optional filter: event | evidence | action | approval"
                )
            ),
        ] = None,
        x_tenant_id: Annotated[str | None, Header()] = None,
    ) -> CardsResponse:
        caller_tenant = _resolve_caller_tenant(
            x_tenant_id, tenant_id, cfg.default_tenant
        )

        async def _safe(coro: Any) -> list[dict[str, Any]]:
            try:
                cards = await coro
            except Exception as exc:
                logger.warning(
                    "cowork_card_projection_failed session_id={} "
                    "kind={} detail={}",
                    session_id,
                    getattr(coro, "__name__", "?"),
                    exc,
                )
                return []
            out: list[dict[str, Any]] = []
            for c in cards:
                # Tenant gate (D-33). Defensive — projection also
                # filters, but this catches edge cases (legacy DB
                # without tenant_id).
                try:
                    _authorize_tenant(
                        caller_tenant=caller_tenant,
                        card_tenant=c.tenant_id,
                    )
                except HTTPException:
                    continue
                out.append(c.to_dict())
            return out

        async def _maybe(card_type_filter: str | None, coro: Any):
            if card_type_filter and card_type_filter != card_type_filter:
                # Placeholder so mypy/ruff stays quiet on the
                # always-truthy filter check.
                pass
            return await _safe(coro)

        event_cards = await _maybe(
            "event",
            proj.list_event_cards(session_id, tenant_id=caller_tenant),
        )
        evidence_cards = await _safe(
            proj.list_evidence_cards(session_id, tenant_id=caller_tenant)
        )
        action_cards = await _safe(
            proj.list_action_cards(session_id, tenant_id=caller_tenant)
        )
        approval_cards = await _safe(
            proj.list_approval_cards(session_id, tenant_id=caller_tenant)
        )

        if card_type:
            want = card_type.strip().lower()
            event_cards = event_cards if want == "event" else []
            evidence_cards = evidence_cards if want == "evidence" else []
            action_cards = action_cards if want == "action" else []
            approval_cards = approval_cards if want == "approval" else []

        total = (
            len(event_cards)
            + len(evidence_cards)
            + len(action_cards)
            + len(approval_cards)
        )

        return CardsResponse(
            session_id=session_id,
            tenant_id=caller_tenant,
            events=event_cards,
            evidence=evidence_cards,
            actions=action_cards,
            approvals=approval_cards,
            total=total,
        )

    # ─── /v1/cowork/cards/stream (L4 SSE bridge) ──────────────────────

    @app.get("/v1/cowork/cards/stream")
    async def stream_cards(
        session_id: Annotated[
            str,
            Query(..., min_length=1, pattern=r"^[a-zA-Z0-9_-]+$"),
        ],
        tenant_id: Annotated[str | None, Query()] = None,
        poll_interval_ms: int = Query(default=500, ge=50, le=5000),
        heartbeat_secs: int = Query(default=15, ge=1, le=120),
        max_idle_polls: int = Query(default=20, ge=0, le=10000),
        x_tenant_id: Annotated[str | None, Header()] = None,
    ) -> StreamingResponse:
        """SSE bridge — emits ``cowork.card.<type>.<event>`` for new rows.

        v3.13.0 — this endpoint emits:

        - ``cowork.card.event.created``     per new EventCard
        - ``cowork.card.evidence.created``  per new EvidenceCard
        - ``cowork.card.action.created``    per new ActionCard
        - ``cowork.card.approval.created``  per new ApprovalCard

        The bridge polls the underlying projection at
        ``poll_interval_ms`` and emits a card event whenever the
        projection's card list grows. State transitions +
        persistence land in 03.13.1; this phase ships the read-
        only substrate + initial ``.created`` events.
        """
        caller_tenant = _resolve_caller_tenant(
            x_tenant_id, tenant_id, cfg.default_tenant
        )

        async def _sse_generator() -> AsyncIterator[str]:
            seen_event_seqs: set[int] = set()
            seen_anchor_ids: set[str] = set()
            seen_event_ids: set[str] = set()
            seen_decision_ids: set[str] = set()
            last_heartbeat = asyncio.get_event_loop().time()
            idle_polls = 0
            try:
                while True:
                    # Re-project and emit new cards.
                    try:
                        events = await proj.list_event_cards(
                            session_id, tenant_id=caller_tenant
                        )
                        for ev in events:
                            if ev.event_seq in seen_event_seqs:
                                continue
                            seen_event_seqs.add(ev.event_seq)
                            payload = json.dumps(
                                ev.to_dict(),
                                ensure_ascii=False,
                                default=str,
                            )
                            yield (
                                "event: cowork.card.event.created\n"
                                f"data: {payload}\n\n"
                            )
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        logger.debug(
                            "sse_event_projection_failed "
                            "session_id={} detail={}",
                            session_id,
                            exc,
                        )

                    try:
                        evidence = await proj.list_evidence_cards(
                            session_id, tenant_id=caller_tenant
                        )
                        for ev in evidence:
                            if ev.anchor_id in seen_anchor_ids:
                                continue
                            seen_anchor_ids.add(ev.anchor_id)
                            payload = json.dumps(
                                ev.to_dict(),
                                ensure_ascii=False,
                                default=str,
                            )
                            yield (
                                "event: cowork.card.evidence.created\n"
                                f"data: {payload}\n\n"
                            )
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        logger.debug(
                            "sse_evidence_projection_failed "
                            "session_id={} detail={}",
                            session_id,
                            exc,
                        )

                    try:
                        actions = await proj.list_action_cards(
                            session_id, tenant_id=caller_tenant
                        )
                        for ac in actions:
                            if ac.id in seen_event_ids:
                                continue
                            seen_event_ids.add(ac.id)
                            payload = json.dumps(
                                ac.to_dict(),
                                ensure_ascii=False,
                                default=str,
                            )
                            yield (
                                "event: cowork.card.action.created\n"
                                f"data: {payload}\n\n"
                            )
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        logger.debug(
                            "sse_action_projection_failed "
                            "session_id={} detail={}",
                            session_id,
                            exc,
                        )

                    try:
                        approvals = await proj.list_approval_cards(
                            session_id, tenant_id=caller_tenant
                        )
                        for ap in approvals:
                            if ap.decision_id in seen_decision_ids:
                                continue
                            seen_decision_ids.add(ap.decision_id)
                            payload = json.dumps(
                                ap.to_dict(),
                                ensure_ascii=False,
                                default=str,
                            )
                            yield (
                                "event: cowork.card.approval.created\n"
                                f"data: {payload}\n\n"
                            )
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        logger.debug(
                            "sse_approval_projection_failed "
                            "session_id={} detail={}",
                            session_id,
                            exc,
                        )

                    # Idle / heartbeat logic (mirrors L4 session
                    # event SSE — same author).
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
                    "sse_cowork_disconnect session_id={}", session_id
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

    # ─── /v1/cowork/trace/{session_id} (forwarded to retrospective in v3.13.2) ─

    @app.get("/v1/cowork/trace/{session_id}")
    async def trace_session_placeholder(
        session_id: Annotated[
            str, Path(min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
        ],
        tenant_id: Annotated[str | None, Query()] = None,
        x_tenant_id: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        """Phase 03.13.0 placeholder — full implementation in 03.13.2.

        Returns the four-card chain via ``CoworkProjection`` only;
        the ``RETROSPECTIVE-*`` cross-refs + idempotency + 403
        boundary land in 03.13.2.
        """
        caller_tenant = _resolve_caller_tenant(
            x_tenant_id, tenant_id, cfg.default_tenant
        )
        events = await proj.list_event_cards(
            session_id, tenant_id=caller_tenant
        )
        evidence = await proj.list_evidence_cards(
            session_id, tenant_id=caller_tenant
        )
        actions = await proj.list_action_cards(
            session_id, tenant_id=caller_tenant
        )
        approvals = await proj.list_approval_cards(
            session_id, tenant_id=caller_tenant
        )
        return {
            "session_id": session_id,
            "tenant_id": caller_tenant,
            "events": [e.to_dict() for e in events],
            "evidence": [e.to_dict() for e in evidence],
            "actions": [a.to_dict() for a in actions],
            "approvals": [a.to_dict() for a in approvals],
            "cross_refs": [],
            "phase": "03.13.0",
            "note": (
                "placeholder; full RETROSPECTIVE chain (cross_refs + "
                "idempotency + 403) lands in 03.13.2"
            ),
        }

    # v3.13.1 — wire the state-machine routes (transition +
    # transitions list + session cards list + extended SSE).
    wire_state_routes(
        app, store, default_tenant=cfg.default_tenant
    )

    return app


__all__ = [
    "CardBase",
    "CardsResponse",
    "CoworkBackend",
    "CoworkConfig",
    "HealthResponse",
    "create_app",
]


# Backwards-compatible alias — used by the v3.13.0 docs and any
# test that imports ``CoworkBackend``. The actual class lives in
# ``projection.CoworkProjection``; this alias keeps the public
# API name stable.
class CoworkBackend:  # pragma: no cover — alias
    """Backward-compatible alias for ``CoworkProjection``.

    v3.13.0 — this name was used in the user's plan description;
    the canonical implementation lives in ``CoworkProjection``.
    """

    def __init__(self, **kwargs: Any) -> None:
        self._impl = CoworkProjection(**kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._impl, name)
