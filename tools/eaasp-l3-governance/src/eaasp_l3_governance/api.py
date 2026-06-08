"""FastAPI app exposing L3 governance REST surface.

Endpoints (MVP scope):

- ``GET  /health``                                     — liveness probe
- ``PUT  /v1/policies/managed-hooks``                  — deploy managed-settings
- ``GET  /v1/policies/versions``                       — newest-first version list
- ``PUT  /v1/policies/{hook_id}/mode``                 — enforce/shadow switch
- ``POST /v1/telemetry/events``                        — async telemetry ingest
- ``GET  /v1/telemetry/events``                        — telemetry query
- ``POST /v1/sessions/{session_id}/validate``          — three-way handshake stub
"""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query
from loguru import logger
from pydantic import BaseModel, Field, ValidationError
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from mcp.server import NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.sse import SseServerTransport

from .audit import AuditStore, TelemetryEventIn
from .db import init_db
from .managed_settings import ManagedSettings, ensure_mode, hook_matches
from .policy_engine import HookNotFoundError, PolicyEngine
from eaasp_common.errors import sanitize_errors
from .mcp_server import build_server as build_mcp_server


class ModeSwitchRequest(BaseModel):
    mode: str = Field(..., description="enforce | shadow")


class SessionValidateRequest(BaseModel):
    agent_id: str | None = None
    skill_id: str | None = None
    runtime_tier: str | None = None


# D23 / L3-01 — valid loguru levels
_VALID_LOG_LEVELS: frozenset[str] = frozenset(
    {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}
)


# D8 / L3-04 — RBAC dependency: extract X-Session-Scope header.
# Returns the scope or raises 403 if missing.
async def require_access_scope(
    x_session_scope: str | None = Header(default=None, alias="X-Session-Scope"),
) -> str:
    """Extract and return the caller's access_scope from X-Session-Scope header."""
    if x_session_scope is None:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden",
                "message": "missing X-Session-Scope header — RBAC required",
            },
        )
    return x_session_scope


def create_app(db_path: str) -> FastAPI:
    # Build MCP server for SSE transport (D-04/D-06 — dual-transport)
    mcp_server, _ = build_mcp_server(db_path)
    mcp_init_options = InitializationOptions(
        server_name=mcp_server.name,
        server_version="0.1.0",
        capabilities=mcp_server.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={},
        ),
    )
    sse = SseServerTransport("/mcp/messages/")

    async def handle_mcp_sse(request):  # type: ignore[no-untyped-def]
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp_server.run(streams[0], streams[1], mcp_init_options)
        return Response()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # D23 / L3-01 — loguru structured logging
        logger.remove()  # clear default handler
        log_level = os.environ.get("L3_LOG_LEVEL", "INFO").upper()
        if log_level not in _VALID_LOG_LEVELS:
            raise ValueError(
                f"L3_LOG_LEVEL must be one of {sorted(_VALID_LOG_LEVELS)}, "
                f"got {log_level!r}"
            )
        logger.add(
            sys.stderr,
            format="{time:ISO} | {level: <8} | {name}:{function}:{line} | {message}",
            level=log_level,
        )
        await init_db(db_path)
        yield

    app = FastAPI(
        title="EAASP L3 Governance",
        version="0.1.0",
        description="Thin L3 governance plane — Policy deployment + Telemetry ingest + Session validate (MVP)",
        lifespan=lifespan,
    )

    # Mount MCP SSE transport alongside REST routes (D-04 — dual-transport)
    app.router.routes.insert(
        0, Route("/mcp/sse", endpoint=handle_mcp_sse, methods=["GET"])
    )
    app.router.routes.insert(1, Mount("/mcp/messages/", app=sse.handle_post_message))

    policy = PolicyEngine(db_path)
    audit = AuditStore(db_path)

    # ─── Health ───────────────────────────────────────────────────────────
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # ─── Contract 1: Policy Deployment ────────────────────────────────────
    @app.put("/v1/policies/managed-hooks")
    async def deploy_managed_hooks(payload: dict[str, Any]) -> dict[str, Any]:
        """Accept a pre-compiled managed-settings.json body and persist it."""
        try:
            settings = ManagedSettings.model_validate(payload)
        except ValidationError as exc:
            # Sanitize errors: Pydantic v2 can embed raw Python exceptions in
            # ``ctx`` (e.g. the ValueError raised by our unique-hook-id
            # validator), which JSONResponse cannot serialize. Convert each
            # error dict to a JSON-safe projection.
            raise HTTPException(
                status_code=422, detail=sanitize_errors(exc.errors())
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        result = await policy.deploy(settings)
        logger.info(
            "Policy deployed", version=result.version, hook_count=result.hook_count
        )
        return result.model_dump()

    @app.get("/v1/policies/versions")
    async def list_policy_versions(
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, Any]:
        versions = await policy.list_versions(limit=limit)
        return {"versions": [v.model_dump() for v in versions]}

    @app.put("/v1/policies/{hook_id}/mode")
    async def switch_hook_mode(hook_id: str, body: ModeSwitchRequest) -> dict[str, Any]:
        try:
            ensure_mode(body.mode)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            override = await policy.switch_mode(hook_id, body.mode)
        except HookNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": str(exc)},
            ) from exc
        return override.model_dump()

    # ─── Contract 4: Telemetry Ingest ─────────────────────────────────────
    @app.post("/v1/telemetry/events")
    async def ingest_telemetry(event: TelemetryEventIn) -> dict[str, Any]:
        result = await audit.ingest(event)
        logger.debug("Telemetry ingested", event_id=result.event_id)
        return {
            "event_id": result.event_id,
            "received_at": result.received_at,
        }

    @app.get("/v1/telemetry/events")
    async def query_telemetry(
        session_id: str | None = Query(default=None),
        since: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, Any]:
        events = await audit.query(session_id=session_id, since=since, limit=limit)
        return {"events": [e.model_dump() for e in events]}

    # ─── D9 / L3-02 — skill usage telemetry (L2-primary + L3-fallback) ────
    l2_url = os.environ.get("L2_MEMORY_ENGINE_URL", "http://localhost:18082")

    @app.get("/v1/telemetry/skill-usage")
    async def get_skill_usage(
        skill_id: str = Query(..., min_length=1),
        since: str | None = Query(default=None),
        caller_scope: str = Depends(require_access_scope),
    ) -> dict[str, Any]:
        result = await audit.skill_usage(
            skill_id=skill_id,
            since=since,
            l2_base_url=l2_url,
        )
        return result

    # ─── Contract 5 (partial): Session validate ───────────────────────────
    @app.post("/v1/sessions/{session_id}/validate")
    async def validate_session(
        session_id: Annotated[
            str, Path(..., min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
        ],
        body: SessionValidateRequest,
        caller_scope: str = Depends(require_access_scope),
    ) -> dict[str, Any]:
        latest = await policy.latest_version()
        if latest is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "no_policy",
                    "message": "no managed-settings version has been deployed yet",
                },
            )

        hooks_to_attach: list[dict[str, Any]] = []
        for hook in latest.payload.get("hooks", []):
            if not hook_matches(hook, body.agent_id, body.skill_id):
                continue
            # D8 / L3-04 — RBAC scope check: skip hooks whose access_scope
            # doesn't match the caller's scope (unless caller is wildcard *).
            hook_scope = hook.get("access_scope")
            if (
                hook_scope is not None
                and caller_scope != "*"
                and hook_scope != caller_scope
            ):
                logger.warning(
                    "RBAC rejected",
                    hook_id=hook.get("hook_id"),
                    caller_scope=caller_scope,
                    required_scope=hook_scope,
                )
                continue  # skip this hook — caller's scope doesn't match
            # D17 / L3-05 — hook_id guard: use .get() not [] to avoid KeyError.
            hook_id = hook.get("hook_id")
            if hook_id is None:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "invalid_hook",
                        "message": f"hook missing required field: hook_id (hook data: {hook})",
                    },
                )
            # Apply per-hook mode override if one has been set via
            # PUT /v1/policies/{hook_id}/mode (floats above version rows).
            override = await policy.get_mode_override(hook_id)
            merged = dict(hook)
            if override is not None:
                merged["mode"] = override.mode
            hooks_to_attach.append(merged)

        logger.debug(
            "Session validated",
            session_id=session_id,
            hook_count=len(hooks_to_attach),
        )
        return {
            "session_id": session_id,
            "hooks_to_attach": hooks_to_attach,
            "managed_settings_version": latest.version,
            "validated_at": latest.created_at,
            "runtime_tier": body.runtime_tier,
        }

    # ─── D22 / L3-02 — global exception handlers (defense-in-depth) ──────
    @app.exception_handler(ValidationError)
    async def validation_exception_handler(
        request, exc: ValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "detail": sanitize_errors(exc.errors()),
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception")
        # Sanitize: max 500 chars, no traceback
        detail = str(exc)[:500]
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "detail": detail},
        )

    return app
