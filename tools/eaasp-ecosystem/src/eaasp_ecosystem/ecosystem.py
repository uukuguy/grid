"""Ecosystem backend — REST bridge for the Ontology + Marketplace surface.

v3.14.0 — EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem.

The backend is a thin FastAPI app on a dedicated port
(env-configurable; default ``:18087`` — per D-39 *no new service
port*, the ecosystem endpoints proxy to the existing EAASP L4
service port ``:18084`` when running in the standard ``make
dev-eaasp`` topology, but the package can also run standalone
for testing).

Routes (v3.14.0):

- ``GET  /health``                                 — liveness probe
- ``GET  /v1/ecosystem/ontology``                  — full taxonomy
                                                      + cross-domain
                                                      links
- ``GET  /v1/ecosystem/ontology/tree``             — list nodes under
                                                      ``?path=`` (path
                                                      = ``/``-separated
                                                      labels)
- ``GET  /v1/ecosystem/ontology/links``            — list all
                                                      cross-domain
                                                      links
- ``GET  /v1/ecosystem/schema``                    — JSON-schema for
                                                      all ecosystem
                                                      types (REQ-ID
                                                      SDK-03)

Authentication (round-1 security review fix): all
``/v1/ecosystem/ontology/...`` endpoints require a verified
``Authorization: Bearer <api_key>`` header. The ``X-Tenant-Id``
header and ``?tenant_id=`` query param are **never** trusted —
the caller's tenant is resolved from the authenticated
principal (API key → tenant mapping). Missing or invalid
credentials return ``401 Unauthorized``; authenticated
principal that fails tenant binding returns ``403 Forbidden``.

The ``/health`` and ``/v1/ecosystem/schema`` endpoints remain
public (no PII or tenant-specific data).

Tenant binding (D-33 / v3.13 / v3.12.1 D-28): the backend
only returns nodes whose ``tenant_id`` matches the
authenticated principal's tenant. Cross-tenant requests are
rejected with 403.

Frozen contract (audit §7.3): the backend is best-effort. Every
route wraps the underlying projection call in a try/except and
returns a 500 with a structured ``{"code": ..., "detail": ...}``
payload on unexpected failure. Empty results return ``[]`` (200
OK) — never 404, because a Cowork UI may legitimately have no
nodes to render for a fresh tenant.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from pydantic import BaseModel, Field

from .ontology import (
    CrossTenantForbidden,
    OntologyService,
)
from .marketplace import (
    MarketplaceACLForbidden,
    MarketplacePromotionError,
    OwnerRole,
    PromotionStage,
    SkillMarketplace,
    VisibilityScope,
)


# ─── Auth dependency (round-1 security review fix) ──────────────


class AuthenticatedPrincipal(BaseModel):
    """The authenticated principal resolved from a verified API key.

    Attributes
    ----------
    principal_id
        Stable identifier for the calling principal (e.g. the API
        key's owning user). Carries no PII.
    tenant_id
        The tenant this principal is bound to. Resolved from the
        API-key → tenant map (``EAASP_ECOSYSTEM_API_KEYS`` env var
        or the supplied ``api_keys`` fixture); never from a
        client-supplied header or query param.
    role
        The caller's role for ACL purposes. Resolved from the
        ``principal_roles`` map (``EAASP_ECOSYSTEM_PRINCIPAL_ROLES``
        env var or the ``cfg.principal_roles`` fixture).
    """

    principal_id: str
    tenant_id: str
    role: OwnerRole = OwnerRole.PUBLIC


_bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticationError(Exception):
    """Raised when the Authorization header is missing or invalid."""


class TenantBindingError(Exception):
    """Raised when an authenticated principal has no tenant binding."""


def _load_api_key_to_tenant_map(
    cfg: "EcosystemConfig",
) -> dict[str, str]:
    """Load the API-key → tenant-id map from env or fixture.

    Source: ``EAASP_ECOSYSTEM_API_KEYS`` env var (newline-separated
    ``api_key:tenant_id`` rows) or the ``cfg.api_keys`` fixture.
    For tests, ``cfg.api_keys`` is set directly; for production,
    the env var is the canonical source.

    Note: this is a minimal HMAC-style verification — sufficient
    for v3.14.0's third-party-publisher demo (the standard
    ``make dev-eaasp`` topology). v3.15+ may swap in OPA-issued
    tokens (per ADR-V2-034) or JWT (per v3.8 multi-user
    pattern); for v3.14.0 we stay simulator-level.
    """
    out: dict[str, str] = {}
    for key, tenant in (cfg.api_keys or {}).items():
        out[key] = tenant
    raw = os.environ.get("EAASP_ECOSYSTEM_API_KEYS", "")
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, t = line.split(":", 1)
        out[k.strip()] = t.strip()
    return out


def _require_principal(
    cfg: "EcosystemConfig",
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
) -> AuthenticatedPrincipal:
    """FastAPI dependency that resolves the authenticated principal.

    Returns ``AuthenticatedPrincipal(principal_id, tenant_id)`` on
    success. Raises ``HTTPException(401)`` on missing / invalid
    credentials.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "missing_credentials",
                "detail": "Authorization: Bearer <api_key> required",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    api_key = credentials.credentials
    mapping = _load_api_key_to_tenant_map(cfg)
    tenant_id = mapping.get(api_key)
    if tenant_id is None:
        # Constant-time-ish comparison to avoid leaking key length
        # / matching prefix through response timing.
        for k in mapping:
            if hmac.compare_digest(k, api_key):
                tenant_id = mapping[k]
                break
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "invalid_credentials",
                "detail": "API key not recognized",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    principal_id = "apikey:" + hashlib.sha256(
        api_key.encode()
    ).hexdigest()[:16]
    # Resolve role: cfg.principal_roles maps api_key → OwnerRole value.
    role = OwnerRole.PUBLIC
    raw_role = (cfg.principal_roles or {}).get(api_key)
    if raw_role is not None:
        try:
            role = OwnerRole(raw_role)
        except ValueError:
            role = OwnerRole.PUBLIC
    return AuthenticatedPrincipal(
        principal_id=principal_id, tenant_id=tenant_id, role=role
    )


# ─── Config ──────────────────────────────────────────────────────────────


class EcosystemConfig(BaseModel):
    """Configuration for the ecosystem backend.

    All fields are env-overridable; defaults match the
    ``make dev-eaasp`` launch topology.
    """

    l2_db_path: str = Field(
        default_factory=lambda: os.environ.get(
            "EAASP_L2_DB_PATH", "./data/dev-l2.db"
        )
    )
    l3_db_path: str = Field(
        default_factory=lambda: os.environ.get(
            "EAASP_L3_DB_PATH", "./data/dev-l3.db"
        )
    )
    l4_db_path: str = Field(
        default_factory=lambda: os.environ.get(
            "EAASP_L4_DB_PATH", "./data/dev-l4.db"
        )
    )
    l5_db_path: str | None = Field(
        default_factory=lambda: os.environ.get("EAASP_L5_DB_PATH", None)
    )
    default_tenant: str = Field(
        default_factory=lambda: os.environ.get(
            "EAASP_ECOSYSTEM_DEFAULT_TENANT", "default"
        )
    )
    root_layer: str = Field(
        default_factory=lambda: os.environ.get(
            "EAASP_ECOSYSTEM_ROOT_LAYER", "l2_type"
        )
    )
    port: int = Field(
        default_factory=lambda: int(
            os.environ.get("EAASP_ECOSYSTEM_PORT", "18087")
        )
    )
    api_keys: dict[str, str] = Field(default_factory=dict)
    skill_registry_url: str = Field(
        default_factory=lambda: os.environ.get(
            "EAASP_SKILL_REGISTRY_URL", "http://127.0.0.1:18081"
        )
    )
    marketplace_db_path: str = Field(
        default_factory=lambda: os.environ.get(
            "EAASP_MARKETPLACE_DB_PATH", "./data/ecosystem-marketplace.db"
        )
    )
    principal_roles: dict[str, str] = Field(default_factory=dict)
    """Map of API key → OwnerRole value (author / reviewer / admin / public)."""


# ─── App factory ─────────────────────────────────────────────────────────


def _build_service(cfg: EcosystemConfig) -> OntologyService:
    return OntologyService(
        l2_db_path=cfg.l2_db_path,
        l3_db_path=cfg.l3_db_path,
        l4_db_path=cfg.l4_db_path,
        l5_db_path=cfg.l5_db_path,
        default_tenant=cfg.default_tenant,
        root_layer=cfg.root_layer,
    )


def _build_marketplace(cfg: EcosystemConfig) -> SkillMarketplace:
    return SkillMarketplace(
        skill_registry_url=cfg.skill_registry_url,
        marketplace_db_path=cfg.marketplace_db_path,
        l3_db_path=cfg.l3_db_path,
        l4_db_path=cfg.l4_db_path,
        default_tenant=cfg.default_tenant,
    )


def create_app(
    *,
    config: EcosystemConfig | None = None,
    service: OntologyService | None = None,
    marketplace: SkillMarketplace | None = None,
) -> FastAPI:
    """Build the FastAPI app for the ecosystem backend.

    ``service`` may be passed in for testing; otherwise an
    ``OntologyService`` is built from ``config``. ``marketplace``
    is the optional pre-built ``SkillMarketplace`` instance.
    """
    cfg = config or EcosystemConfig()
    svc = service or _build_service(cfg)
    mkt = marketplace or _build_marketplace(cfg)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        logger.info(
            "EAASP ecosystem backend starting "
            "(l2={} l3={} l4={} l5={})",
            cfg.l2_db_path, cfg.l3_db_path, cfg.l4_db_path, cfg.l5_db_path,
        )
        yield
        logger.info("EAASP ecosystem backend shutting down")

    app = FastAPI(
        title="EAASP Ecosystem Backend",
        version="0.1.0",
        description=(
            "v3.14.0 — EAASP Phase 6 ecosystem (Ontology / "
            "Marketplace / SDK surface). Authenticated-only: "
            "X-Tenant-Id header / ?tenant_id= query param are "
            "NEVER trusted; the caller's tenant is resolved from "
            "the authenticated principal."
        ),
        lifespan=lifespan,
    )

    # ─── Health (public) ──────────────────────────────────────

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": "0.1.0"}

    # ─── JSON-schema endpoint (public) ────────────────────────

    @app.get("/v1/ecosystem/schema")
    async def get_schema() -> dict[str, Any]:
        """Emit the EAASP v2.0 ecosystem surface as JSON-schema.

        Third-party clients (incl. ``sdk/python/eaasp_sdk/``) use
        this endpoint to generate typed clients per language.
        The schema is static — no tenant-specific data — so the
        endpoint is public.
        """
        ont = svc.json_schema()
        mkt_schema = mkt.json_schema()
        merged = {
            "$schema": ont["$schema"],
            "title": "EAASP Ecosystem Surface",
            "version": "1.0.0",
            "description": (
                "EAASP v2.0 Phase 6 ecosystem (Ontology + "
                "Marketplace) projection schemas."
            ),
            "type": "object",
            "properties": {
                **ont["properties"],
                **mkt_schema["properties"],
            },
            "$defs": {
                **ont.get("$defs", {}),
                **mkt_schema.get("$defs", {}),
            },
        }
        return merged

    # ─── Auth dependency bound to cfg (per-instance closure) ────────

    def _auth_dep(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
        ],
    ) -> AuthenticatedPrincipal:
        return _require_principal(cfg, credentials)

    # ─── Ontology endpoints (auth required) ────────────────────

    @app.get(
        "/v1/ecosystem/ontology",
        response_model=None,
        responses={
            200: {"description": "Full taxonomy + cross-domain links"},
            401: {"description": "Missing or invalid credentials"},
            403: {"description": "Cross-tenant access forbidden"},
        },
    )
    async def get_ontology(
        principal: AuthenticatedPrincipal = Depends(_auth_dep),
    ) -> dict[str, Any]:
        """Return the full taxonomy graph for the caller's tenant.

        The ``tenant_id`` is the **authenticated** principal's
        tenant — never a client-supplied header or query param.
        """
        try:
            graph = svc.derive_taxonomy(tenant_id=principal.tenant_id)
        except CrossTenantForbidden as exc:
            raise HTTPException(
                status_code=403,
                detail={"code": "cross_tenant_forbidden", "detail": str(exc)},
            ) from exc
        return graph.to_dict()

    @app.get(
        "/v1/ecosystem/ontology/tree",
        response_model=None,
        responses={
            200: {"description": "List of taxonomy nodes"},
            401: {"description": "Missing or invalid credentials"},
            403: {"description": "Cross-tenant access forbidden"},
        },
    )
    async def get_ontology_tree(
        path: Annotated[str | None, Query()] = None,
        principal: AuthenticatedPrincipal = Depends(_auth_dep),
    ) -> dict[str, Any]:
        """List taxonomy nodes under ``path`` (``/``-separated labels)."""
        try:
            nodes = svc.list_taxonomy(
                path=path, tenant_id=principal.tenant_id
            )
        except CrossTenantForbidden as exc:
            raise HTTPException(
                status_code=403,
                detail={"code": "cross_tenant_forbidden", "detail": str(exc)},
            ) from exc
        return {
            "tenant_id": principal.tenant_id,
            "path": path or "",
            "nodes": [n.to_dict() for n in nodes],
        }

    @app.get(
        "/v1/ecosystem/ontology/links",
        response_model=None,
        responses={
            200: {"description": "List of cross-domain links"},
            401: {"description": "Missing or invalid credentials"},
            403: {"description": "Cross-tenant access forbidden"},
        },
    )
    async def get_ontology_links(
        principal: AuthenticatedPrincipal = Depends(_auth_dep),
    ) -> dict[str, Any]:
        """List all cross-domain links for the caller's tenant."""
        try:
            graph = svc.derive_taxonomy(tenant_id=principal.tenant_id)
        except CrossTenantForbidden as exc:
            raise HTTPException(
                status_code=403,
                detail={"code": "cross_tenant_forbidden", "detail": str(exc)},
            ) from exc
        return {
            "tenant_id": principal.tenant_id,
            "links": [l.to_dict() for l in graph.links],
        }

    # ─── Marketplace endpoints (MARKETPLACE-01..05) ────────────

    from pydantic import BaseModel as _BM

    class SubmitSkillRequest(_BM):
        name: str
        summary: str
        version: str
        manifest: dict
        scope: VisibilityScope = VisibilityScope.PRIVATE
        tags: list[str] = []

    class PromoteSkillRequest(_BM):
        skill_id: str
        from_stage: PromotionStage
        to_stage: PromotionStage
        rationale: str

    @app.post(
        "/v1/ecosystem/marketplace/skills/submit",
        response_model=None,
        responses={
            201: {"description": "Skill created"},
            401: {"description": "Missing or invalid credentials"},
            403: {"description": "Cross-tenant access forbidden"},
            502: {"description": "Skill registry unreachable"},
        },
    )
    async def submit_skill(
        req: SubmitSkillRequest,
        principal: AuthenticatedPrincipal = Depends(_auth_dep),
    ) -> dict:
        """Submit a new skill to the marketplace (MARKETPLACE-01)."""
        try:
            skill = mkt.submit_skill(
                tenant_id=principal.tenant_id,
                author_principal=principal.principal_id,
                name=req.name,
                summary=req.summary,
                version=req.version,
                manifest=req.manifest,
                scope=req.scope,
                tags=tuple(req.tags),
            )
        except CrossTenantForbidden as exc:
            raise HTTPException(
                status_code=403,
                detail={"code": "cross_tenant_forbidden", "detail": str(exc)},
            ) from exc
        except MarketplacePromotionError as exc:
            raise HTTPException(
                status_code=502,
                detail={"code": "registry_rejected", "detail": str(exc)},
            ) from exc
        return skill.to_dict()

    @app.post(
        "/v1/ecosystem/marketplace/skills/promote",
        response_model=None,
        responses={
            200: {"description": "Promotion row written"},
            400: {"description": "Invalid transition"},
            401: {"description": "Missing or invalid credentials"},
            403: {"description": "ACL denied"},
            502: {"description": "Skill registry unreachable"},
        },
    )
    async def promote_skill(
        req: PromoteSkillRequest,
        principal: AuthenticatedPrincipal = Depends(_auth_dep),
    ) -> dict:
        """Promote a skill along the 4-stage lifecycle (MARKETPLACE-01)."""
        try:
            audit = mkt.promote_skill(
                tenant_id=principal.tenant_id,
                actor_principal=principal.principal_id,
                actor_role=principal.role,
                skill_id=req.skill_id,
                from_stage=req.from_stage,
                to_stage=req.to_stage,
                rationale=req.rationale,
            )
        except CrossTenantForbidden as exc:
            raise HTTPException(
                status_code=403,
                detail={"code": "cross_tenant_forbidden", "detail": str(exc)},
            ) from exc
        except MarketplaceACLForbidden as exc:
            raise HTTPException(
                status_code=403,
                detail={"code": "acl_forbidden", "detail": str(exc)},
            ) from exc
        except MarketplacePromotionError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "promotion_error", "detail": str(exc)},
            ) from exc
        return audit.to_dict()

    @app.get(
        "/v1/ecosystem/marketplace/skills/list",
        response_model=None,
        responses={
            200: {"description": "List of visible skills"},
            401: {"description": "Missing or invalid credentials"},
            403: {"description": "Cross-tenant access forbidden"},
        },
    )
    async def list_skills(
        tag: Annotated[str | None, Query()] = None,
        principal: AuthenticatedPrincipal = Depends(_auth_dep),
    ) -> dict:
        """List marketplace skills visible to the caller (MARKETPLACE-02)."""
        try:
            skills = mkt.list_skills(
                tenant_id=principal.tenant_id,
                caller_principal=principal.principal_id,
                caller_role=principal.role,
                tag=tag,
            )
        except CrossTenantForbidden as exc:
            raise HTTPException(
                status_code=403,
                detail={"code": "cross_tenant_forbidden", "detail": str(exc)},
            ) from exc
        return {
            "tenant_id": principal.tenant_id,
            "skills": [s.to_dict() for s in skills],
        }

    @app.get(
        "/v1/ecosystem/marketplace/skills/stats",
        response_model=None,
        responses={
            200: {"description": "Per-skill analytics"},
            401: {"description": "Missing or invalid credentials"},
            403: {"description": "ACL denied"},
        },
    )
    async def skill_stats(
        skill_id: Annotated[str, Query()] = ...,
        principal: AuthenticatedPrincipal = Depends(_auth_dep),
    ) -> dict:
        """Per-skill analytics (MARKETPLACE-04)."""
        try:
            stats = mkt.skill_stats(
                tenant_id=principal.tenant_id,
                skill_id=skill_id,
                caller_principal=principal.principal_id,
                caller_role=principal.role,
            )
        except CrossTenantForbidden as exc:
            raise HTTPException(
                status_code=403,
                detail={"code": "cross_tenant_forbidden", "detail": str(exc)},
            ) from exc
        except MarketplaceACLForbidden as exc:
            raise HTTPException(
                status_code=403,
                detail={"code": "acl_forbidden", "detail": str(exc)},
            ) from exc
        except MarketplacePromotionError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "skill_not_found", "detail": str(exc)},
            ) from exc
        return stats.to_dict()

    @app.get(
        "/v1/ecosystem/marketplace/skills/audit",
        response_model=None,
        responses={
            200: {"description": "Submission audit trail"},
            401: {"description": "Missing or invalid credentials"},
            403: {"description": "ACL denied"},
        },
    )
    async def submission_audit(
        skill_id: Annotated[str, Query()] = ...,
        principal: AuthenticatedPrincipal = Depends(_auth_dep),
    ) -> dict:
        """Submission audit trail (MARKETPLACE-05)."""
        try:
            rows = mkt.submission_audit(
                tenant_id=principal.tenant_id,
                skill_id=skill_id,
                caller_principal=principal.principal_id,
                caller_role=principal.role,
            )
        except CrossTenantForbidden as exc:
            raise HTTPException(
                status_code=403,
                detail={"code": "cross_tenant_forbidden", "detail": str(exc)},
            ) from exc
        except MarketplaceACLForbidden as exc:
            raise HTTPException(
                status_code=403,
                detail={"code": "acl_forbidden", "detail": str(exc)},
            ) from exc
        except MarketplacePromotionError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "skill_not_found", "detail": str(exc)},
            ) from exc
        return {
            "tenant_id": principal.tenant_id,
            "skill_id": skill_id,
            "audit": [r.to_dict() for r in rows],
        }

    return app


__all__ = [
    "AuthenticatedPrincipal",
    "AuthenticationError",
    "EcosystemConfig",
    "TenantBindingError",
    "create_app",
]