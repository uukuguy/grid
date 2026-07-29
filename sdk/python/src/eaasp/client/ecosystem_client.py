"""Thin HTTP client for the EAASP v2.0 Ecosystem backend (v3.14.2).

Wraps the ``L4 /v1/ecosystem/*`` surface — Ontology + Marketplace + JSON-schema
emission — exposed by ``tools/eaasp-ecosystem`` (FastAPI on default
``127.0.0.1:18087``).

Per D-42, this is a **thin client**: every method is a single HTTP call to an
existing endpoint. No business logic is re-implemented. Authentication is
``Authorization: Bearer <api_key>`` resolved server-side by
``_require_principal`` (``tools/eaasp-ecosystem/src/eaasp_ecosystem/ecosystem.py:151``).

Two variants are exposed:

- ``EaaspEcosystemClient`` — sync, uses ``httpx.Client(trust_env=False)``.
  ``trust_env=False`` skips the macOS Clash proxy (per the project-wide
  ``feedback_env_var_conventions`` gotcha).
- ``AsyncEaaspEcosystemClient`` — async, uses ``httpx.AsyncClient``.

The sync variant is the default; the async variant is for embedding the SDK
inside an already-async code path (e.g. an L4 SSE consumer).

HTTP status code → typed exception mapping (audited in the v3.14.0 /
v3.14.1 round-1 + round-2 security review fixes):

- 401 → ``EaaspEcosystemAuthError`` (missing / invalid Bearer credential)
- 403 → ``EaaspEcosystemACLDenied`` (authenticated but caller lacks
  ``VisibilityScope`` / ``OwnerRole`` / tenant binding)
- 404 → ``EaaspEcosystemPromotionError`` (skill_id not found)
- 502 → ``EaaspEcosystemPromotionError`` (upstream skill-registry unreachable)
- any 4xx/5xx other → ``EaaspEcosystemError`` (parent)
"""

from __future__ import annotations

from typing import Any

import httpx


# ─── Typed exceptions ────────────────────────────────────────────────────


class EaaspEcosystemError(Exception):
    """Base class for all Ecosystem SDK errors."""


class EaaspEcosystemAuthError(EaaspEcosystemError):
    """401 — missing or invalid ``Authorization: Bearer`` credential.

    The server's ``_require_principal`` raises 401 when no Bearer header is
    present or the API key is unknown. Callers should verify the API key
    before retrying.
    """


class EaaspEcosystemACLDenied(EaaspEcosystemError):
    """403 — authenticated caller lacks the required scope/role/tenant.

    The marketplace ``VisibilityScope`` (private / tenant / marketplace) and
    ``OwnerRole`` (author / reviewer / admin / public) matrix produces 403
    when a caller attempts a read or promote that they are not entitled to.
    """


class EaaspEcosystemTenantForbidden(EaaspEcosystemError):
    """403 — cross-tenant access attempted.

    The server enforces a fail-closed tenant guard (per the v3.14.0
    round-1 security review). Attempting to read another tenant's ontology
    or marketplace state surfaces as 403; this is *not* an ACL scope/role
    issue but a tenant-membership violation.
    """


class EaaspEcosystemPromotionError(EaaspEcosystemError):
    """400 / 404 / 502 — promotion lifecycle, skill-not-found, or upstream error.

    The server emits 400 for invalid stage transitions
    (``MarketplacePromotionError``), 404 for unknown ``skill_id`` on
    ``/stats`` or ``/audit``, and 502 when the upstream
    ``eaasp-skill-registry`` (default ``127.0.0.1:18081``) is unreachable.
    """


# ─── Sync client ────────────────────────────────────────────────────────


class EaaspEcosystemClient:
    """Sync thin client for the EAASP v2.0 Ecosystem backend.

    Parameters
    ----------
    base_url
        Root URL of the ecosystem FastAPI service. Default
        ``http://127.0.0.1:18087`` (matches ``EAASP_ECOSYSTEM_PORT``).
    api_key
        Bearer credential registered server-side via
        ``EAASP_ECOSYSTEM_API_KEYS`` or ``EcosystemConfig.api_keys``.
    timeout
        Per-request timeout in seconds. Default 10.0.
    """

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:18087",
        api_key: str,
        timeout: float = 10.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise EaaspEcosystemAuthError(
                "api_key required: ecosystem backend requires a Bearer "
                "credential (see EAASP_ECOSYSTEM_API_KEYS env var)"
            )
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key.strip()
        self._timeout = timeout
        # trust_env=False avoids the macOS Clash proxy (per project-wide
        # feedback_env_var_conventions gotcha). 127.0.0.1 + Clash = 502.
        self._client = httpx.Client(
            trust_env=False,
            timeout=timeout,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )

    def close(self) -> None:
        """Close the underlying ``httpx.Client`` connection pool."""
        self._client.close()

    def __enter__(self) -> "EaaspEcosystemClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ARG002
        self.close()

    # ─── Health + schema (public) ──────────────────────────────

    def get_health(self) -> dict[str, str]:
        """GET ``/health`` (no auth required)."""
        resp = self._client.get(f"{self.base_url}/health")
        return self._check(resp)

    def get_schema(self) -> dict[str, Any]:
        """GET ``/v1/ecosystem/schema`` — full JSON-schema of the ecosystem surface.

        Returns the merged Ontology + Marketplace JSON-schema. Used by SDK
        code-gen (v3.14.2 SDK-03 pass-through).
        """
        resp = self._client.get(f"{self.base_url}/v1/ecosystem/schema")
        return self._check(resp)

    # ─── Ontology (Bearer) ─────────────────────────────────────

    def derive_taxonomy(self) -> dict[str, Any]:
        """GET ``/v1/ecosystem/ontology`` — full taxonomy graph for the caller's tenant."""
        resp = self._client.get(f"{self.base_url}/v1/ecosystem/ontology")
        return self._check(resp)

    def list_taxonomy(self, path: str | None = None) -> dict[str, Any]:
        """GET ``/v1/ecosystem/ontology/tree?path=<path>`` — nodes under ``path``."""
        params: dict[str, str] = {}
        if path:
            params["path"] = path
        resp = self._client.get(
            f"{self.base_url}/v1/ecosystem/ontology/tree", params=params
        )
        return self._check(resp)

    def list_ontology_links(self) -> dict[str, Any]:
        """GET ``/v1/ecosystem/ontology/links`` — cross-domain links."""
        resp = self._client.get(f"{self.base_url}/v1/ecosystem/ontology/links")
        return self._check(resp)

    # ─── Marketplace (Bearer) ──────────────────────────────────

    def submit_skill(
        self,
        *,
        name: str,
        summary: str,
        version: str,
        manifest: dict[str, Any],
        scope: str = "private",
        tags: tuple[str, ...] = (),
        author_principal: str,
    ) -> dict[str, Any]:
        """POST ``/v1/ecosystem/marketplace/skills/submit`` — third-party submission.

        ``scope`` must be one of ``private`` / ``tenant`` / ``marketplace``
        (the ``VisibilityScope`` enum, lowercased). ``tags`` is a tuple of
        tag strings used to index the skill under the Ontology taxonomy.
        """
        body = {
            "name": name,
            "summary": summary,
            "version": version,
            "manifest": manifest,
            "scope": scope,
            "tags": list(tags),
            "author_principal": author_principal,
        }
        resp = self._client.post(
            f"{self.base_url}/v1/ecosystem/marketplace/skills/submit", json=body
        )
        return self._check(resp)

    def promote_skill(
        self,
        *,
        skill_id: str,
        from_stage: str,
        to_stage: str,
        rationale: str,
        actor_principal: str,
        actor_role: str,
    ) -> dict[str, Any]:
        """POST ``/v1/ecosystem/marketplace/skills/promote`` — 4-stage transition.

        ``actor_role`` is required (v3.14.1 round-2 security review) and must
        be one of ``author`` / ``reviewer`` / ``admin`` / ``public``. The
        server enforces the ACL: ``public`` cannot promote; ``reviewer``
        can only advance DRAFT → REVIEW.
        """
        body = {
            "skill_id": skill_id,
            "from_stage": from_stage,
            "to_stage": to_stage,
            "rationale": rationale,
            "actor_principal": actor_principal,
            "actor_role": actor_role,
        }
        resp = self._client.post(
            f"{self.base_url}/v1/ecosystem/marketplace/skills/promote", json=body
        )
        return self._check(resp)

    def list_skills(self, *, tag: str | None = None) -> dict[str, Any]:
        """GET ``/v1/ecosystem/marketplace/skills/list`` — ACL-filtered list."""
        params: dict[str, str] = {}
        if tag:
            params["tag"] = tag
        resp = self._client.get(
            f"{self.base_url}/v1/ecosystem/marketplace/skills/list", params=params
        )
        return self._check(resp)

    def skill_stats(self, *, skill_id: str) -> dict[str, Any]:
        """GET ``/v1/ecosystem/marketplace/skills/stats?skill_id=<id>``.

        Raises ``EaaspEcosystemPromotionError`` if the ``skill_id`` is
        unknown (404) or ACL-denied (403).
        """
        resp = self._client.get(
            f"{self.base_url}/v1/ecosystem/marketplace/skills/stats",
            params={"skill_id": skill_id},
        )
        return self._check(resp)

    def submission_audit(self, *, skill_id: str) -> dict[str, Any]:
        """GET ``/v1/ecosystem/marketplace/skills/audit?skill_id=<id>`` — full audit."""
        resp = self._client.get(
            f"{self.base_url}/v1/ecosystem/marketplace/skills/audit",
            params={"skill_id": skill_id},
        )
        return self._check(resp)

    # ─── Error mapping ──────────────────────────────────────────

    @staticmethod
    def _check(resp: httpx.Response) -> dict[str, Any]:
        """Translate ``httpx.Response`` status code → typed exception or JSON body."""
        if resp.status_code == 200 or resp.status_code == 201:
            return resp.json()
        # Try to extract a structured error code from the body.
        try:
            body = resp.json()
        except ValueError:
            body = {"detail": resp.text}
        code = body.get("code") if isinstance(body, dict) else None
        detail = body.get("detail") if isinstance(body, dict) else resp.text

        if resp.status_code == 401:
            raise EaaspEcosystemAuthError(
                f"401 Unauthorized (code={code}): {detail}"
            )
        if resp.status_code == 403:
            # Distinguish ACL denied vs cross-tenant by the server's code
            # string. The server emits `code: cross_tenant_forbidden` for
            # cross-tenant access; other 403s are ACL denials.
            if code == "cross_tenant_forbidden":
                raise EaaspEcosystemTenantForbidden(
                    f"403 cross-tenant forbidden: {detail}"
                )
            raise EaaspEcosystemACLDenied(
                f"403 ACL denied (code={code}): {detail}"
            )
        if resp.status_code in (400, 404, 502):
            raise EaaspEcosystemPromotionError(
                f"{resp.status_code} (code={code}): {detail}"
            )
        raise EaaspEcosystemError(
            f"{resp.status_code} unexpected (code={code}): {detail}"
        )


# ─── Async client ──────────────────────────────────────────────────────


class AsyncEaaspEcosystemClient:
    """Async thin client for the EAASP v2.0 Ecosystem backend.

    Mirrors :class:`EaaspEcosystemClient` but uses ``httpx.AsyncClient`` and
    returns awaitables. Use when embedding the SDK inside an already-async
    code path (e.g. an L4 SSE consumer). All 10 method names + signatures
    are identical to the sync variant.
    """

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:18087",
        api_key: str,
        timeout: float = 10.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise EaaspEcosystemAuthError(
                "api_key required: ecosystem backend requires a Bearer "
                "credential (see EAASP_ECOSYSTEM_API_KEYS env var)"
            )
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key.strip()
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            trust_env=False,
            timeout=timeout,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )

    async def aclose(self) -> None:
        """Close the underlying ``httpx.AsyncClient`` connection pool."""
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncEaaspEcosystemClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ARG002
        await self.aclose()

    async def get_health(self) -> dict[str, str]:
        resp = await self._client.get(f"{self.base_url}/health")
        return EaaspEcosystemClient._check(resp)

    async def get_schema(self) -> dict[str, Any]:
        resp = await self._client.get(f"{self.base_url}/v1/ecosystem/schema")
        return EaaspEcosystemClient._check(resp)

    async def derive_taxonomy(self) -> dict[str, Any]:
        resp = await self._client.get(f"{self.base_url}/v1/ecosystem/ontology")
        return EaaspEcosystemClient._check(resp)

    async def list_taxonomy(self, path: str | None = None) -> dict[str, Any]:
        params: dict[str, str] = {}
        if path:
            params["path"] = path
        resp = await self._client.get(
            f"{self.base_url}/v1/ecosystem/ontology/tree", params=params
        )
        return EaaspEcosystemClient._check(resp)

    async def list_ontology_links(self) -> dict[str, Any]:
        resp = await self._client.get(
            f"{self.base_url}/v1/ecosystem/ontology/links"
        )
        return EaaspEcosystemClient._check(resp)

    async def submit_skill(
        self,
        *,
        name: str,
        summary: str,
        version: str,
        manifest: dict[str, Any],
        scope: str = "private",
        tags: tuple[str, ...] = (),
        author_principal: str,
    ) -> dict[str, Any]:
        body = {
            "name": name,
            "summary": summary,
            "version": version,
            "manifest": manifest,
            "scope": scope,
            "tags": list(tags),
            "author_principal": author_principal,
        }
        resp = await self._client.post(
            f"{self.base_url}/v1/ecosystem/marketplace/skills/submit", json=body
        )
        return EaaspEcosystemClient._check(resp)

    async def promote_skill(
        self,
        *,
        skill_id: str,
        from_stage: str,
        to_stage: str,
        rationale: str,
        actor_principal: str,
        actor_role: str,
    ) -> dict[str, Any]:
        body = {
            "skill_id": skill_id,
            "from_stage": from_stage,
            "to_stage": to_stage,
            "rationale": rationale,
            "actor_principal": actor_principal,
            "actor_role": actor_role,
        }
        resp = await self._client.post(
            f"{self.base_url}/v1/ecosystem/marketplace/skills/promote", json=body
        )
        return EaaspEcosystemClient._check(resp)

    async def list_skills(self, *, tag: str | None = None) -> dict[str, Any]:
        params: dict[str, str] = {}
        if tag:
            params["tag"] = tag
        resp = await self._client.get(
            f"{self.base_url}/v1/ecosystem/marketplace/skills/list", params=params
        )
        return EaaspEcosystemClient._check(resp)

    async def skill_stats(self, *, skill_id: str) -> dict[str, Any]:
        resp = await self._client.get(
            f"{self.base_url}/v1/ecosystem/marketplace/skills/stats",
            params={"skill_id": skill_id},
        )
        return EaaspEcosystemClient._check(resp)

    async def submission_audit(self, *, skill_id: str) -> dict[str, Any]:
        resp = await self._client.get(
            f"{self.base_url}/v1/ecosystem/marketplace/skills/audit",
            params={"skill_id": skill_id},
        )
        return EaaspEcosystemClient._check(resp)


__all__ = [
    "AsyncEaaspEcosystemClient",
    "EaaspEcosystemACLDenied",
    "EaaspEcosystemAuthError",
    "EaaspEcosystemClient",
    "EaaspEcosystemError",
    "EaaspEcosystemPromotionError",
    "EaaspEcosystemTenantForbidden",
]
