"""FastAPI app exposing L4 orchestration REST surface.

Endpoints (MVP + Phase 1 Event Engine):

- ``GET  /health``                                    — liveness probe
- ``POST /v1/intents/dispatch``                       — Contract 2 intent dispatch
- ``POST /v1/sessions/create``                        — Contract 5 handshake (alias)
- ``POST /v1/sessions/{session_id}/message``          — append user message
- ``POST /v1/sessions/{session_id}/message/stream``   — SSE streaming message
- ``GET  /v1/sessions/{session_id}/events``           — list events (+ follow SSE)
- ``GET  /v1/sessions/{session_id}``                  — fetch session + payload
- ``GET  /v1/sessions``                               — list all sessions
- ``POST /v1/events/ingest``                          — Phase 1: L1 EmitEvent REST fallback
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field, ValidationError
from starlette.responses import JSONResponse

from .db import init_db
from . import flow_api as _flow_api
from .event_backend_sqlite import SqliteWalBackend
from .event_engine import EventEngine
from .event_models import Event, EventMetadata
from .event_stream import SessionEventStream
from .handshake import (
    L2_URL_DEFAULT,
    L3_URL_DEFAULT,
    SKILL_REGISTRY_URL_DEFAULT,
    L2Client,
    L3Client,
    SkillRegistryClient,
    UpstreamError,
)
from .l1_client import L1RuntimeError
from .mcp_resolver import McpResolver
from .session_orchestrator import (
    InvalidStateTransition,
    SessionNotFound,
    SessionOrchestrator,
)

# logger is now loguru — configured in lifespan

# L4-06 / D31 — valid loguru levels
_VALID_LOG_LEVELS: frozenset[str] = frozenset(
    {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}
)

# ─── Request models ─────────────────────────────────────────────────────────


class IntentDispatchRequest(BaseModel):
    intent_text: str = Field(..., min_length=1)
    skill_id: str = Field(..., min_length=0)
    runtime_pref: str = Field(..., min_length=1)
    user_id: str | None = None
    intent_id: str | None = None


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=0)


class EventIngestRequest(BaseModel):
    """Phase 1: L1 EmitEvent REST fallback (ADR-V2-001)."""

    session_id: str = Field(..., min_length=1)
    event_type: str = Field(..., min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    source: str = Field(default="")
    event_id: str | None = None


# ─── App factory ────────────────────────────────────────────────────────────


def create_app(
    db_path: str,
    *,
    l2_base_url: str | None = None,
    l3_base_url: str | None = None,
    skill_registry_base_url: str | None = None,
    http_client: httpx.AsyncClient | None = None,
    l1_factory: Any | None = None,
) -> FastAPI:
    """Build the FastAPI app.

    ``http_client`` is injectable for tests — when None the lifespan builds
    its own ``httpx.AsyncClient`` with a 5s timeout. Tests override this via
    the ``l4_http_client`` fixture so respx can intercept requests.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # L4-06 / D31 — loguru structured logging (copy L3 D23 pattern).
        logger.remove()  # clear default handler
        log_level = os.environ.get("L4_LOG_LEVEL", "INFO").upper()
        if log_level not in _VALID_LOG_LEVELS:
            raise ValueError(
                f"L4_LOG_LEVEL must be one of {sorted(_VALID_LOG_LEVELS)}, "
                f"got {log_level!r}"
            )
        logger.add(
            sys.stderr,
            format="{time:ISO} | {level: <8} | {name}:{function}:{line} | {message}",
            level=log_level,
        )
        await init_db(db_path)
        owned_client = False
        if http_client is None:
            # trust_env=False prevents L4 from picking up macOS system proxies
            # (Clash etc.) when calling L2/L3 over 127.0.0.1. Without this guard
            # the proxy turns localhost calls into 502 upstream_error reports —
            # see MEMORY.md "Ollama 本地模型已知问题" for the reqwest precedent.
            client = httpx.AsyncClient(timeout=5.0, trust_env=False)
            owned_client = True
        else:
            client = http_client
        app.state.http_client = client
        app.state.l2 = L2Client(client, base_url=l2_base_url or L2_URL_DEFAULT)
        app.state.l3 = L3Client(client, base_url=l3_base_url or L3_URL_DEFAULT)
        app.state.skill_registry = SkillRegistryClient(
            client, base_url=skill_registry_base_url or SKILL_REGISTRY_URL_DEFAULT
        )
        app.state.event_stream = SessionEventStream(db_path)
        app.state.mcp_resolver = McpResolver(client)
        # Phase 1: Event Engine with SqliteWalBackend.
        event_backend = SqliteWalBackend(db_path)
        event_engine = EventEngine(event_backend)
        await event_engine.start()
        app.state.event_engine = event_engine
        app.state.event_backend = event_backend
        app.state.orchestrator = SessionOrchestrator(
            db_path,
            l2=app.state.l2,
            l3=app.state.l3,
            skill_registry=app.state.skill_registry,
            event_stream=app.state.event_stream,
            l1_factory=l1_factory,
            mcp_resolver=app.state.mcp_resolver,
            event_engine=event_engine,
        )

        # v3.15.5 — OBSTACK §3.5 LayerReader wiring (V315-BUSINESS-FLOW-02).
        # Open connections to L4 / L3 / L2 databases and build the
        # ``app.state.flow_layer_readers`` dict that ``flow_api.py`` consumes.
        # Each reader is a small async wrapper that injects the connection
        # into the standalone functions in ``flow_readers.py``.
        from .flow_readers import build_default_layer_readers
        from .db import connect as l4_connect

        app.state.l4_db_conn = await l4_connect(db_path)

        # L3 cross-DB connect: graceful degrade when the L3 file is
        # not present (e.g. dev mode with only L4 running). The reader
        # returns an empty list in that case so the timeline aggregator
        # never raises.
        l3_db_path = os.environ.get("EAASP_L3_DB_PATH", "./data/governance.db")
        if os.path.exists(l3_db_path):
            app.state.l3_db_conn = await l4_connect(l3_db_path)
        else:
            app.state.l3_db_conn = None

        # L2 cross-DB connect: same graceful degrade. Default path
        # matches L2's own main.py default.
        l2_db_path = (
            os.environ.get("EAASP_L2_DB_PATH")
            or os.environ.get("L2_DB_PATH")
            or "./data/dev-l2.db"
        )
        if os.path.exists(l2_db_path):
            app.state.l2_db_conn = await l4_connect(l2_db_path)
        else:
            app.state.l2_db_conn = None

        app.state.flow_layer_readers = build_default_layer_readers(
            l4_conn=app.state.l4_db_conn,
            l3_conn=app.state.l3_db_conn,
            l2_conn=app.state.l2_db_conn,
        )

        try:
            yield
        finally:
            await event_engine.stop()
            if owned_client:
                await client.aclose()
            # Close the cross-layer DB connections that the L4 lifespan
            # opened. The SessionEventStream / EventEngine own their own
            # DB handles so they close via their own lifecycle.
            for attr in ("l4_db_conn", "l3_db_conn", "l2_db_conn"):
                conn = getattr(app.state, attr, None)
                if conn is not None:
                    try:
                        await conn.close()
                    except Exception:
                        pass

    app = FastAPI(
        title="EAASP L4 Orchestration",
        version="0.1.0",
        description=(
            "Thin L4 orchestration plane — Intent dispatch + Session handshake "
            "+ Event stream (MVP)"
        ),
        lifespan=lifespan,
    )

    # OBSTACK §3.5 — business-flow REST + SSE endpoints
    # (`/v1/business-flows/{key}/{timeline,summary,events-stream,evaluation}`).
    # Mount the flow_api router on the live app so the v3.15.5 walkthrough
    # can hit these via curl / `eaasp flow` CLI.
    app.include_router(_flow_api.router)

    def get_orchestrator() -> SessionOrchestrator:
        return app.state.orchestrator  # type: ignore[no-any-return]

    # ─── Health ──────────────────────────────────────────────────────────
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # ─── Contract 2: Intent dispatch ─────────────────────────────────────
    @app.post("/v1/intents/dispatch")
    async def dispatch_intent(
        body: IntentDispatchRequest,
        orchestrator: SessionOrchestrator = Depends(get_orchestrator),
        x_session_scope: str | None = Header(
            default=None, alias="X-Session-Scope"
        ),
        x_business_key: str | None = Header(
            default=None, alias="X-Business-Key"
        ),
    ) -> dict[str, Any]:
        # D8 / L3-04 RBAC (fail-CLOSED per ADR-V2-028): same binding logic
        # as /v1/sessions/create. See _resolve_skill_bound_scope below.
        if not x_session_scope:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "missing_scope",
                    "message": "X-Session-Scope header required (D8/L3-04 RBAC).",
                },
            )
        # D34 / L4-01: NLU intent→skill resolution when skill_id is empty.
        # Per CONTEXT.md D-03: NLU module queries skill list → builds index →
        # matches intent → dispatches to best skill. Per-skill scope
        # binding happens AFTER resolution (see end of this handler).
        if not body.skill_id:
            try:
                from .nlu_resolver import IntentResolver, NoSkillMatchError

                resolver = IntentResolver()
                # Fetch skill list from registry for index building.
                # For MVP, we use a known skill list; full registry integration
                # deferred to Phase 8.3 (D61).
                if orchestrator.skill_registry is not None:
                    skills = await _fetch_skill_list(orchestrator)
                    resolver.build_index_from_list(skills)
                    resolved_skill_id, candidates = resolver.resolve_intent(
                        body.intent_text
                    )
                    if resolved_skill_id is not None:
                        body.skill_id = resolved_skill_id
                    else:
                        # Per D-04: below threshold → return ranked list
                        # for user disambiguation, HTTP 300 Multiple Choices.
                        raise HTTPException(
                            status_code=300,
                            detail={
                                "code": "ambiguous_intent",
                                "intent_text": body.intent_text,
                                "candidates": candidates,
                                "message": (
                                    "Multiple skills match your intent. "
                                    "Please select one by skill_id."
                                ),
                            },
                        )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "code": "skill_id_required",
                            "message": (
                                "skill_id is required when skill registry is "
                                "not available. Provide a skill_id or ensure "
                                "the skill registry is running."
                            ),
                        },
                    )
            except HTTPException:
                raise
            except NoSkillMatchError as exc:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "no_skills_available",
                        "message": f"No skills in registry to match against: {exc}",
                    },
                ) from exc
            except Exception as exc:
                # Per D-34 success criteria: unknown intents return graceful
                # error, not 500 crash.
                raise HTTPException(
                    status_code=500,
                    detail={
                        "code": "nlu_error",
                        "message": f"Intent resolution failed: {exc}",
                    },
                ) from exc

        # Per-skill scope binding AFTER NLU resolution (skill_id is now
        # known). Same fail-closed logic as /v1/sessions/create.
        resolved_scope = await _resolve_skill_bound_scope(
            orchestrator, skill_id=body.skill_id, caller_scope=x_session_scope,
        )
        if resolved_scope is None:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "scope_mismatch",
                    "message": f"X-Session-Scope '{x_session_scope}' does not "
                    f"match skill '{body.skill_id}' registered access_scope.",
                },
            )
        return await _run_create_session(
            orchestrator, body, session_scope=resolved_scope,
            business_key=x_business_key,
        )

    # ─── Contract 5: Session create (alias — same body shape) ────────────
    @app.post("/v1/sessions/create")
    async def create_session(
        body: IntentDispatchRequest,
        orchestrator: SessionOrchestrator = Depends(get_orchestrator),
        x_session_scope: str | None = Header(
            default=None, alias="X-Session-Scope"
        ),
        x_business_key: str | None = Header(
            default=None, alias="X-Business-Key"
        ),
    ) -> dict[str, Any]:
        # D8 / L3-04 RBAC (fail-CLOSED per ADR-V2-028):
        #   - If X-Session-Scope is missing → 403 immediately. No wildcard
        #     fallback; no implicit scope. L3 hard-requires this header
        #     and an un-scoped L4 call would force L3 into "deny" mode
        #     anyway. Failing at L4 produces a clearer error and prevents
        #     accidental privilege escalation via header omission.
        #   - If X-Session-Scope is present, it must EQUAL the skill's
        #     registered access_scope (from skill-registry frontmatter).
        #     This binds the header value to ground truth rather than
        #     trusting whatever string the client sent. Free-form scope
        #     strings like "admin" or "org:victim" are rejected because
        #     they don't match the skill's declared scope.
        if not x_session_scope:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "missing_scope",
                    "message": "X-Session-Scope header required (D8/L3-04 RBAC). "
                    "Set the header on the call site or pass "
                    "EAASP_SESSION_SCOPE for the CLI.",
                },
            )
        # Bind scope to the skill's registered access_scope.
        # Read the skill from skill-registry (in-process, no network hop).
        resolved_scope = await _resolve_skill_bound_scope(
            orchestrator, skill_id=body.skill_id, caller_scope=x_session_scope,
        )
        if resolved_scope is None:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "scope_mismatch",
                    "message": f"X-Session-Scope '{x_session_scope}' does not "
                    f"match skill '{body.skill_id}' registered access_scope.",
                },
            )
        return await _run_create_session(
            orchestrator, body, session_scope=resolved_scope,
            business_key=x_business_key,
        )

    # ─── Contract 5: send message ────────────────────────────────────────
    @app.post("/v1/sessions/{session_id}/message")
    async def send_message(
        session_id: Annotated[
            str, Path(..., min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
        ],
        body: SendMessageRequest,
        orchestrator: SessionOrchestrator = Depends(get_orchestrator),
    ) -> dict[str, Any]:
        try:
            return await orchestrator.send_message(session_id, body.content)
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "session_not_found", "session_id": exc.session_id},
            ) from exc
        except L1RuntimeError as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "l1_runtime_error",
                    "runtime_id": exc.runtime_id,
                    "method": exc.method,
                    "detail": exc.detail,
                },
            ) from exc

    # ─── Contract 5: send message (SSE streaming) ─────────────────────────
    @app.post("/v1/sessions/{session_id}/message/stream")
    async def send_message_stream(
        session_id: Annotated[
            str, Path(..., min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
        ],
        body: SendMessageRequest,
        orchestrator: SessionOrchestrator = Depends(get_orchestrator),
    ) -> StreamingResponse:
        """SSE endpoint — streams response chunks as ``text/event-stream``."""
        # Validate session existence up front (fail fast with 404).
        try:
            await orchestrator._require_session(session_id)
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "session_not_found", "session_id": exc.session_id},
            ) from exc

        async def _sse_generator() -> AsyncIterator[str]:
            async for msg in orchestrator.stream_message(session_id, body.content):
                event = msg.get("event", "chunk")
                data = json.dumps(msg.get("data", {}), ensure_ascii=False, default=str)
                yield f"event: {event}\ndata: {data}\n\n"

        return StreamingResponse(
            _sse_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ─── Contract 5: close session ───────────────────────────────────────
    @app.post("/v1/sessions/{session_id}/close")
    async def close_session(
        session_id: Annotated[
            str, Path(..., min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
        ],
        orchestrator: SessionOrchestrator = Depends(get_orchestrator),
    ) -> dict[str, Any]:
        try:
            return await orchestrator.close_session(session_id)
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "session_not_found", "session_id": exc.session_id},
            ) from exc
        except InvalidStateTransition as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "invalid_state_transition",
                    "session_id": exc.session_id,
                    "current": exc.current,
                    "target": exc.target,
                },
            ) from exc

    # ─── Contract 5: list events ─────────────────────────────────────────
    @app.get("/v1/sessions/{session_id}/events")
    async def list_events(
        session_id: Annotated[
            str, Path(..., min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
        ],
        from_: int = Query(default=1, ge=1, alias="from"),
        to: int = Query(default=2**31 - 1, ge=1),
        limit: int = Query(default=500, ge=1, le=500),
        orchestrator: SessionOrchestrator = Depends(get_orchestrator),
    ) -> dict[str, Any]:
        try:
            events = await orchestrator.list_events(
                session_id, from_seq=from_, to_seq=to, limit=limit
            )
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "session_not_found", "session_id": exc.session_id},
            ) from exc
        return {"session_id": session_id, "events": events}

    # ─── S4.T2 (D84): list events as SSE stream (follow mode) ────────────
    @app.get("/v1/sessions/{session_id}/events/stream")
    async def stream_events(
        session_id: Annotated[
            str, Path(..., min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
        ],
        from_: int = Query(default=1, ge=1, alias="from"),
        poll_interval_ms: int = Query(default=500, ge=50, le=5000),
        heartbeat_secs: int = Query(default=15, ge=1, le=120),
        max_idle_polls: int = Query(default=0, ge=0, le=10000),
        orchestrator: SessionOrchestrator = Depends(get_orchestrator),
    ) -> StreamingResponse:
        """SSE tail-follow for session events.

        Emits each event as ``event: event\\ndata: <json>\\n\\n``. Replays all
        events with ``seq >= from`` then polls at ``poll_interval_ms``.
        Heartbeat comments (``: hb``) are emitted every ``heartbeat_secs`` to
        keep the connection alive and surface client disconnects quickly.

        ``max_idle_polls=0`` (default) polls forever. Set a positive value to
        terminate the stream after that many consecutive empty polls — useful
        for "catch up then exit" workflows and for tests running under an
        ASGI transport that buffers the full response body.
        """
        # Validate session up front (fail fast with 404 instead of in-stream).
        try:
            await orchestrator._require_session(session_id)
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "session_not_found", "session_id": exc.session_id},
            ) from exc

        async def _sse_generator() -> AsyncIterator[str]:
            # D124 (S4.T2 reviewer note): log follow-stream lifecycle for ops
            # visibility. Starlette detects client disconnect via is_disconnected()
            # polling in the response-sender task and raises CancelledError inside
            # our await points — we catch it here, log, and re-raise so Starlette
            # can complete its cleanup.
            logger.info("sse_follow_start session_id={} from={}", session_id, from_)
            last_seen = from_ - 1
            last_heartbeat = asyncio.get_event_loop().time()
            poll_s = poll_interval_ms / 1000.0
            idle_polls = 0
            try:
                while True:
                    try:
                        events = await orchestrator.list_events(
                            session_id,
                            from_seq=last_seen + 1,
                            limit=500,
                        )
                    except SessionNotFound:
                        # Session deleted mid-stream — emit a terminal error frame
                        # and break rather than raising (can't raise inside a
                        # started StreamingResponse body).
                        logger.info(
                            "sse_follow_session_gone session_id={} last_seen={}",
                            session_id,
                            last_seen,
                        )
                        yield (
                            "event: error\n"
                            "data: "
                            + json.dumps(
                                {
                                    "code": "session_not_found",
                                    "session_id": session_id,
                                }
                            )
                            + "\n\n"
                        )
                        return
                    if events:
                        idle_polls = 0
                        for ev in events:
                            payload = json.dumps(ev, ensure_ascii=False, default=str)
                            yield f"event: event\ndata: {payload}\n\n"
                            last_seen = int(ev["seq"])
                    else:
                        idle_polls += 1
                        if max_idle_polls and idle_polls >= max_idle_polls:
                            logger.debug(
                                "sse_follow_idle_exit session_id={} last_seen={}",
                                session_id,
                                last_seen,
                            )
                            return
                    now = asyncio.get_event_loop().time()
                    if now - last_heartbeat >= heartbeat_secs:
                        yield ": hb\n\n"
                        last_heartbeat = now
                    await asyncio.sleep(poll_s)
            except asyncio.CancelledError:
                logger.info(
                    "sse_follow_disconnect session_id={} last_seen={}",
                    session_id,
                    last_seen,
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

    # ─── Contract 5: get session ─────────────────────────────────────────
    @app.get("/v1/sessions/{session_id}")
    async def get_session(
        session_id: Annotated[
            str, Path(..., min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
        ],
        orchestrator: SessionOrchestrator = Depends(get_orchestrator),
    ) -> dict[str, Any]:
        try:
            return await orchestrator.get_session(session_id)
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "session_not_found", "session_id": exc.session_id},
            ) from exc

    # ─── List sessions (closes D41) ─────────────────────────────────────
    @app.get("/v1/sessions")
    async def list_sessions(
        limit: int = Query(default=50, ge=1, le=500),
        status: str | None = Query(default=None),
        orchestrator: SessionOrchestrator = Depends(get_orchestrator),
    ) -> dict[str, Any]:
        """List all sessions, newest first."""
        rows = await orchestrator.list_sessions(limit=limit, status=status)
        return {"sessions": rows}

    # ─── Phase 1: Event ingest (ADR-V2-001 REST fallback) ──────────────
    @app.post("/v1/events/ingest")
    async def ingest_event(
        body: EventIngestRequest,
        orchestrator: SessionOrchestrator = Depends(get_orchestrator),
    ) -> dict[str, Any]:
        """Accept an event from L1 EmitEvent REST fallback.

        Validates that the session exists before accepting the event
        to prevent dangling FK rows in session_events.
        """
        # Validate session existence — prevents FK violation + silent failures.
        try:
            await orchestrator.get_session(body.session_id)
        except SessionNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "session_not_found",
                    "session_id": exc.session_id,
                },
            ) from exc

        engine: EventEngine = app.state.event_engine
        event = Event(
            session_id=body.session_id,
            event_type=body.event_type,
            payload=body.payload,
            event_id=body.event_id or "",
            metadata=EventMetadata(source=body.source),
        )
        try:
            seq, event_id = await engine.ingest(event)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "ingest_failed", "error": str(exc)},
            ) from exc
        return {"seq": seq, "event_id": event_id}

    # ─── D28 / L4-04 — global exception handlers (defense-in-depth, copy L3 D22) ──

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(
        request, exc: ValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "detail": _sanitize_errors(exc.errors()),
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception")
        # Sanitize: max 500 chars, no traceback leakage (D28 success criteria).
        detail = str(exc)[:500]
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "detail": detail},
        )

    return app


# ─── NLU helper ─────────────────────────────────────────────────────────────


async def _fetch_skill_list(orchestrator: SessionOrchestrator) -> list[dict[str, Any]]:
    """Fetch skill list from registry for NLU index building.

    Bootstrap list of known EAASP verification skills. In Phase 8.3 (D61),
    this will be replaced with a real registry list endpoint.
    """
    # Known verification skill IDs from the EAASP skill registry.
    # These are the skills that exist in the test fixtures.
    KNOWN_SKILLS = [
        {
            "skill_id": "skill.verification.threshold-calibration",
            "name": "Threshold Calibration",
            "description": "SCADA threshold calibration verification skill",
        },
        {
            "skill_id": "skill.verification.modbus-coil-check",
            "name": "Modbus Coil Check",
            "description": "Modbus coil state verification",
        },
        {
            "skill_id": "skill.verification.iec-104-point-check",
            "name": "IEC-104 Point Check",
            "description": "IEC-104 telemetry point verification",
        },
        {
            "skill_id": "skill.verification.dnp3-point-check",
            "name": "DNP3 Point Check",
            "description": "DNP3 outstation point verification",
        },
        {
            "skill_id": "skill.verification.analog-alarm-check",
            "name": "Analog Alarm Check",
            "description": "Analog alarm threshold verification",
        },
    ]
    return KNOWN_SKILLS


# ─── Shared handler ─────────────────────────────────────────────────────────


async def _resolve_skill_bound_scope(
    orchestrator: SessionOrchestrator,
    *,
    skill_id: str | None,
    caller_scope: str,
) -> str | None:
    """Resolve the scope that the orchestrator should use for this session.

    D8 / L3-04 RBAC enforcement (truly fail-CLOSED per ADR-V2-028 +
    commit security review round-2):
    - Reads the skill's registered ``access_scope`` from skill-registry
      frontmatter (via ``orchestrator.skill_registry.read_skill``).
    - Returns the registered scope ONLY IF ``caller_scope`` matches it
      exactly. Otherwise returns None (the caller handler must raise 403).
    - The reserved wildcard ``"*"`` is rejected unless the skill's
      registered scope is also ``"*"`` (the conservative case where a
      skill declares itself as public).
    - Empty skill_id (e.g. mid-NLU failure) returns None.
    - Skill-registry unavailable (None OR read_skill raises) returns
      None — fail-CLOSED. Previously this had a "callers can pass
      through" fallback which the security review flagged as a backdoor.
    - Skill with no ``access_scope`` declared in frontmatter returns
      None — fail-CLOSED. Previously this defaulted to "*"; the review
      correctly identified that as a wildcard backdoor for any
      undeclared skill (which is the default state of legacy skills
      pre-D11).
    - Explicit dev passthrough ONLY when ``EAASP_DEV_DISABLE_SCOPE_BINDING=1``
      is set. This makes dev-mode behavior intentional + auditable
      rather than structural.

    This binding replaces the prior free-form "trust whatever the client
    sent" pattern (which let any client impersonate any scope). The scope
    is now bound to ground truth — the skill's declared access_scope.

    Long-term: replace this with a JWT-bearing claim signed by an
    issuer the orchestrator trusts (e.g. per-tenant HMAC). For now,
    skill-registry is the source of truth and the binding is sufficient
    to defeat impersonation within a tenant.
    """
    if not skill_id:
        return None
    # EAASP_DEV_DISABLE_SCOPE_BINDING=1 explicitly disables the
    # per-skill scope binding. This is for dev/test environments where
    # the skill-registry may not be reachable OR skills may not have
    # declared access_scope yet. Production must NEVER set this flag.
    if os.environ.get("EAASP_DEV_DISABLE_SCOPE_BINDING") == "1":
        logger.warning(
            "EAASP_DEV_DISABLE_SCOPE_BINDING=1 set — skipping per-skill "
            "scope binding for skill={}. DO NOT USE IN PRODUCTION.",
            skill_id,
        )
        return caller_scope or "*"
    if orchestrator.skill_registry is None:
        # Truly fail-closed: no skill-registry wired means we cannot
        # bind the scope to ground truth. Refuse rather than trust
        # the caller's claim.
        logger.warning(
            "resolve_skill_bound_scope: skill_registry not configured; "
            "cannot bind scope for skill={}. Rejecting call (fail-closed).",
            skill_id,
        )
        return None
    try:
        skill_data = await orchestrator.skill_registry.read_skill(skill_id)
    except Exception as exc:
        # Truly fail-closed: registry errors must NOT silently downgrade
        # to caller-trust mode. The security review caught this as
        # fail-open-state-drift. Surface as None so handler returns 403.
        logger.warning(
            "resolve_skill_bound_scope: failed to read skill={}: {}. "
            "Rejecting call (fail-closed).",
            skill_id, exc,
        )
        return None
    parsed_v2 = skill_data.get("parsed_v2") or {}
    registered_scope = parsed_v2.get("access_scope")
    if not registered_scope:
        # Truly fail-closed: an undeclared access_scope is NOT a default
        # to "*" — it's a configuration gap. The security review
        # flagged the prior default-to-"*" as fail-open-default. Skill
        # owners MUST declare access_scope explicitly. Operators can
        # audit undeclared skills via skill-registry /admin.
        logger.warning(
            "resolve_skill_bound_scope: skill={} has no access_scope "
            "declared in frontmatter. Rejecting call (fail-closed). "
            "Skill owners must declare access_scope explicitly.",
            skill_id,
        )
        return None
    # Reject the wildcard when the skill is NOT public.
    if registered_scope != "*" and caller_scope == "*":
        logger.warning(
            "resolve_skill_bound_scope: caller sent wildcard '*' for "
            "skill={} which declares scope={}. Rejecting.",
            skill_id, registered_scope,
        )
        return None
    if caller_scope != registered_scope:
        logger.warning(
            "resolve_skill_bound_scope: scope mismatch for skill={}: "
            "caller sent '{}', registered is '{}'. Rejecting.",
            skill_id, caller_scope, registered_scope,
        )
        return None
    return registered_scope


async def _run_create_session(
    orchestrator: SessionOrchestrator,
    body: IntentDispatchRequest,
    *,
    session_scope: str = "*",
    business_key: str | None = None,
) -> dict[str, Any]:
    """Call orchestrator.create_session and map upstream errors to HTTP."""
    try:
        return await orchestrator.create_session(
            intent_text=body.intent_text,
            skill_id=body.skill_id,
            runtime_pref=body.runtime_pref,
            user_id=body.user_id,
            intent_id=body.intent_id,
            session_scope=session_scope,
            business_key=business_key,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=422, detail=_sanitize_errors(exc.errors())
        ) from exc
    except UpstreamError as exc:
        raise _upstream_to_http(exc) from exc
    except L1RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "l1_runtime_error",
                "runtime_id": exc.runtime_id,
                "method": exc.method,
                "detail": exc.detail,
            },
        ) from exc


def _upstream_to_http(exc: UpstreamError) -> HTTPException:
    """Map ``UpstreamError`` into an HTTP status code + payload."""
    if exc.kind == "unavailable":
        return HTTPException(
            status_code=503,
            detail={
                "code": "upstream_unavailable",
                "service": exc.service,
                "detail": exc.detail,
            },
        )
    if exc.kind == "no_policy":
        # 424 Failed Dependency — L3 has no managed-settings version yet.
        return HTTPException(
            status_code=424,
            detail={
                "code": "no_policy",
                "service": exc.service,
                "message": exc.detail
                or "no managed-settings version has been deployed yet",
            },
        )
    # Default: upstream 5xx / unexpected.
    return HTTPException(
        status_code=502,
        detail={
            "code": "upstream_error",
            "service": exc.service,
            "detail": exc.detail,
        },
    )


def _sanitize_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip non-JSON-serializable objects from Pydantic error dicts."""
    clean: list[dict[str, Any]] = []
    for err in errors:
        safe: dict[str, Any] = {}
        for key, value in err.items():
            if key == "ctx" and isinstance(value, dict):
                safe[key] = {
                    ctx_key: (
                        str(ctx_val) if isinstance(ctx_val, BaseException) else ctx_val
                    )
                    for ctx_key, ctx_val in value.items()
                }
            elif isinstance(value, BaseException):
                safe[key] = str(value)
            else:
                safe[key] = value
        clean.append(safe)
    return clean
