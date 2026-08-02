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
from .managed_settings import ManagedSettings, ensure_mode, ensure_risk_level, hook_matches
from .opa_backend import OPABackend
from .policy_engine import GateDecision, HookNotFoundError, PolicyEngine
from eaasp_common.errors import sanitize_errors
from .mcp_server import build_server as build_mcp_server


class ModeSwitchRequest(BaseModel):
    mode: str = Field(..., description="enforce | shadow")


class SessionValidateRequest(BaseModel):
    agent_id: str | None = None
    skill_id: str | None = None
    runtime_tier: str | None = None


# v3.11.1 — Risk-aware gate evaluation request (OPA-backed in production,
# in-process in dev/test per ADR-V2-034). The API is the SWITCH: it reads
# ``opa_enabled`` on the engine and routes to evaluate_with_opa() or
# evaluate_gate() accordingly.
class EvaluateRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    hook_id: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)
    risk_level: str = Field(..., min_length=1)  # validated by ensure_risk_level
    action_preview: str = Field(..., min_length=1)
    agent_id: str | None = None
    skill_id: str | None = None
    # V315-BUSINESS-FLOW-02 commit 3/6 — cross-layer business-flow binding.
    # Wire-format ``"session|skill|object"`` (same as the L4 X-Business-Key
    # header). When set, the decision is tagged into the L3 ledger so
    # the cross-layer timeline aggregator can JOIN it with L2/L4 rows.
    # Optional — pre-v3.15.5 callers may not supply this.
    business_key: str | None = None


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

# v3.11.1 security review [Issue 1 / HIGH]: in-process principal store
# that binds ``session_id`` -> ``{access_scope, tenant_id, principal}``
# at /v1/sessions/{id}/validate time, and that ``/v1/evaluate`` uses
# to verify (a) the session exists, (b) the caller's scope matches
# the session's scope, and (c) the resolved hook's ``access_scope``
# matches the caller's scope (with wildcard + admin carve-outs).
#
# Production replaces this with the EAASP L2 session DB; the contract
# shape is the same — this is the v3.11.1 anchor.
_SESSION_PRINCIPALS: dict[str, dict[str, str]] = {}


async def register_session_principal(
    session_id: str,
    *,
    access_scope: str,
    tenant_id: str,
    principal: str,
) -> dict[str, str]:
    """Bind a session_id to a verified principal + scope at validate time.

    Returns the stored principal dict. Idempotent: re-registering the
    same session_id overwrites the prior binding (the validate endpoint
    is the only path that produces valid bindings).
    """
    bound = {
        "session_id": session_id,
        "access_scope": access_scope,
        "tenant_id": tenant_id,
        "principal": principal,
    }
    _SESSION_PRINCIPALS[session_id] = bound
    return bound


async def lookup_session_principal(session_id: str) -> dict[str, str] | None:
    """Return the principal bound at validate time, or None if missing."""
    return _SESSION_PRINCIPALS.get(session_id)


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
        # v3.11.1 — close the OPA client if we own one. Built AFTER
        # ``yield`` so it runs on FastAPI shutdown; the backend is
        # already constructed by the time we get here.
        if opa_backend is not None:
            await opa_backend.aclose()

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

    # v3.11.1 — OPA backend construction (ADR-V2-034 §Decision).
    # The backend is constructed ONLY when the operator opted in via
    # ``L3_OPA_ENABLED=1`` (truthy). Missing/invalid env vars in that
    # case surface as a startup RuntimeError (per ADR-V2-028); a
    # developer / CI environment without OPA simply leaves
    # L3_OPA_ENABLED unset and gets the in-process path.
    opa_backend: OPABackend | None = None
    if os.environ.get("L3_OPA_ENABLED", "").strip().lower() in {"1", "true", "yes"}:
        opa_backend = OPABackend.from_env()
        # Wire the backend into the existing PolicyEngine. We use
        # ``object.__setattr__`` on the private slot because
        # ``_opa_backend`` is intentionally a private impl detail; the
        # public surface is ``opa_enabled`` (read-only property).
        object.__setattr__(policy, "_opa_backend", opa_backend)
        logger.info(
            "L3 OPA backend enabled",
            base_url=opa_backend.config.base_url,
            bundle_dir=opa_backend.config.bundle_dir,
        )

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
        # Security review Issue 1: bind session_id to a verified principal
        # BEFORE any hook resolution so /v1/evaluate cannot accept a
        # free-form session_id from an unauthenticated caller. The
        # principal's scope = caller_scope; tenant_id derives from the
        # X-Session-Scope header (or '*' wildcard); principal defaults to
        # "caller". Production replaces this with an L2 join.
        await register_session_principal(
            session_id,
            access_scope=caller_scope,
            tenant_id=str(body.agent_id) if body.agent_id else "default",
            principal="caller",
        )
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

    # ─── v3.11.1 — Risk-aware gate evaluation (OPA switch per ADR-V2-034) ───
    @app.post("/v1/evaluate")
    async def evaluate(
        body: EvaluateRequest,
        caller_scope: str = Depends(require_access_scope),
        x_business_key: str | None = Header(
            default=None, alias="X-Business-Key"
        ),
    ) -> dict[str, Any]:
        """Evaluate a governance gate decision.

        Routing (per ADR-V2-034 §Decision):

        - ``policy.opa_enabled is True``  → ``PolicyEngine.evaluate_with_opa()``
          (production path; OPA produces the decision).
        - ``policy.opa_enabled is False`` → ``PolicyEngine.evaluate_gate()``
          (in-process path; dev / CI / unit-test path).

        Security [Issue 1 / HIGH]: the request MUST be backed by an
        authenticated session (registered via /v1/sessions/{id}/validate),
        the resolved hook's ``access_scope`` MUST equal ``caller_scope``
        (or the caller is wildcard / admin), and ``session_id`` is
        carried as an authenticated session_id rather than a free-form
        string. Cross-scope mismatches → 403.
        """
        # Defense-in-depth: validate risk_level at the API surface even
        # though evaluate_with_opa/evaluate_gate also validate it. This
        # gives a clean 422 instead of leaking ValueError as 500.
        try:
            ensure_risk_level(body.risk_level)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"error": "validation_error", "message": str(exc)},
            ) from exc

        # ── Step 1: bind session_id to an authenticated principal ────────
        principal = await lookup_session_principal(body.session_id)
        if principal is None:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "forbidden",
                    "message": "session_id is not authenticated; call "
                                "/v1/sessions/{id}/validate first",
                },
            )
        if principal["access_scope"] != caller_scope and caller_scope != "*":
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "forbidden",
                    "message": "caller scope does not match authenticated "
                                "session scope",
                },
            )

        # ── Step 2: resolve hook by (session_id, hook_id) and enforce scope
        latest = await policy.latest_version()
        if latest is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": "no managed-settings version has been "
                                "deployed yet",
                },
            )
        resolved_hook: dict[str, Any] | None = None
        for hook in latest.payload.get("hooks", []):
            if not hook_matches(hook, body.agent_id, body.skill_id):
                continue
            if hook.get("hook_id") != body.hook_id:
                continue
            resolved_hook = hook
            break
        if resolved_hook is None:
            # Either hook_id is unknown OR it doesn't match the agent/skill
            # binding — both surface as "not found" to avoid leaking which
            # hooks exist.
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"hook {body.hook_id!r} is not bound to this "
                                f"session (agent_id/skill_id/hook_id mismatch)",
                },
            )

        # ── Step 3: enforce hook.access_scope == caller_scope (with carve-outs)
        hook_scope = resolved_hook.get("access_scope")
        if (
            hook_scope is not None
            and caller_scope != "*"
            and caller_scope != "admin"
            and hook_scope != caller_scope
        ):
            logger.warning(
                "RBAC rejected on /v1/evaluate",
                hook_id=body.hook_id,
                session_id=body.session_id,
                caller_scope=caller_scope,
                required_scope=hook_scope,
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "forbidden",
                    "message": (
                        f"hook requires scope {hook_scope!r}; caller has "
                        f"{caller_scope!r}"
                    ),
                },
            )

        # ── Step 4: route to OPA or in-process, passing principal forward
        # V315-BUSINESS-FLOW-02 commit 3 — forward business_key (header
        # takes precedence over body field, mirroring the L4 pattern).
        # Body field is still accepted for callers that prefer JSON; if
        # both are set, header wins (consistent with REST conventions).
        effective_business_key = x_business_key or body.business_key
        if policy.opa_enabled:
            decision = await policy.evaluate_with_opa(
                session_id=body.session_id,
                hook_id=body.hook_id,
                tool_name=body.tool_name,
                risk_level=body.risk_level,
                action_preview=body.action_preview,
                agent_id=body.agent_id,
                skill_id=body.skill_id,
                principal_scope=caller_scope,
                principal_id=principal["principal"],
                tenant_id=principal["tenant_id"],
                business_key=effective_business_key,
            )
            backend_kind = "opa"
        else:
            decision = await policy.evaluate_gate(
                session_id=body.session_id,
                hook_id=body.hook_id,
                tool_name=body.tool_name,
                risk_level=body.risk_level,
                action_preview=body.action_preview,
                business_key=effective_business_key,
            )
            backend_kind = "in_process"

        logger.debug(
            "L3 gate evaluated",
            session_id=body.session_id,
            hook_id=body.hook_id,
            decision=decision.decision,
            backend=backend_kind,
        )
        return {
            "decision_id": decision.decision_id,
            "decision": decision.decision,
            "rationale": decision.rationale,
            "backend": backend_kind,
        }

    # ─── D22 / L3-02 — global exception handlers (defense-in-depth) ──────
    @app.exception_handler(HookNotFoundError)
    async def hook_not_found_handler(request, exc: HookNotFoundError) -> JSONResponse:
        """Map ``HookNotFoundError`` raised from evaluate paths to a 404.

        Without this, the generic Exception handler returns 500. The
        /v1/evaluate endpoint can hit this for any hook_id that the
        caller has not yet deployed (or has typos in).
        """
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "message": str(exc)},
        )

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
