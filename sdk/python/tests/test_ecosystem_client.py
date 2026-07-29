"""Tests for the v3.14.2 Ecosystem thin client (EaaspEcosystemClient + Async).

REQ-IDs covered: SDK-01 (typed sync + async clients over the 10 L4
``/v1/ecosystem/*`` endpoints), SDK-03 (JSON-schema pass-through via
``get_schema()``).

All tests use ``respx`` to mock the HTTP transport — no real FastAPI
TestClient, no network. The backend surface is exhaustively covered by
``tools/eaasp-ecosystem/tests/test_ecosystem_backend.py`` (20 tests,
``TestClient``); the SDK layer only needs to lock its own error mapping
and parameter-forwarding behavior.
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from eaasp.client.ecosystem_client import (
    AsyncEaaspEcosystemClient,
    EaaspEcosystemACLDenied,
    EaaspEcosystemAuthError,
    EaaspEcosystemClient,
    EaaspEcosystemPromotionError,
    EaaspEcosystemTenantForbidden,
)


API_KEY = "dev-test-key-acme"
BASE_URL = "http://127.0.0.1:18087"


# ─── Health + schema (public) ──────────────────────────────────────────


def test_get_health_returns_status() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/health").mock(
            return_value=Response(200, json={"status": "ok", "version": "0.1.0"})
        )
        with EaaspEcosystemClient(base_url=BASE_URL, api_key=API_KEY) as client:
            result = client.get_health()
    assert result == {"status": "ok", "version": "0.1.0"}


def test_get_schema_returns_full_ecosystem_types() -> None:
    """SDK-03 — JSON-schema endpoint emits all 9 types.

    Locks the SDK-03 contract: the ``properties`` block must include
    ``TaxonomyNode`` / ``CrossDomainLink`` / ``TaxonomyGraph`` (Ontology)
    plus ``MarketplaceSkill`` / ``MarketplaceStats`` / ``SubmissionAuditRow``
    (Marketplace) plus the 3 enums ``VisibilityScope`` / ``OwnerRole`` /
    ``PromotionStage``.
    """
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "EAASP Ecosystem Surface",
        "version": "1.0.0",
        "type": "object",
        "properties": {
            "TaxonomyNode": {"type": "object"},
            "CrossDomainLink": {"type": "object"},
            "TaxonomyGraph": {"type": "object"},
            "MarketplaceSkill": {"type": "object"},
            "MarketplaceStats": {"type": "object"},
            "SubmissionAuditRow": {"type": "object"},
            "VisibilityScope": {"type": "string"},
            "OwnerRole": {"type": "string"},
            "PromotionStage": {"type": "string"},
        },
    }
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/v1/ecosystem/schema").mock(return_value=Response(200, json=schema))
        with EaaspEcosystemClient(base_url=BASE_URL, api_key=API_KEY) as client:
            result = client.get_schema()
    assert set(result["properties"].keys()) == {
        "TaxonomyNode",
        "CrossDomainLink",
        "TaxonomyGraph",
        "MarketplaceSkill",
        "MarketplaceStats",
        "SubmissionAuditRow",
        "VisibilityScope",
        "OwnerRole",
        "PromotionStage",
    }


# ─── Ontology ──────────────────────────────────────────────────────────


def test_derive_taxonomy_returns_graph() -> None:
    graph = {"tenant_id": "acme", "root_id": "root", "nodes": [], "links": []}
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/v1/ecosystem/ontology").mock(
            return_value=Response(200, json=graph)
        )
        with EaaspEcosystemClient(base_url=BASE_URL, api_key=API_KEY) as client:
            result = client.derive_taxonomy()
    assert result["tenant_id"] == "acme"


def test_list_taxonomy_with_path() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/v1/ecosystem/ontology/tree").mock(
            return_value=Response(
                200, json={"tenant_id": "acme", "path": "plant", "nodes": []}
            )
        )
        with EaaspEcosystemClient(base_url=BASE_URL, api_key=API_KEY) as client:
            result = client.list_taxonomy(path="plant")
    assert result["path"] == "plant"
    assert route.calls.last.request.url.params["path"] == "plant"


def test_list_ontology_links() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/v1/ecosystem/ontology/links").mock(
            return_value=Response(200, json={"tenant_id": "acme", "links": []})
        )
        with EaaspEcosystemClient(base_url=BASE_URL, api_key=API_KEY) as client:
            result = client.list_ontology_links()
    assert result["links"] == []


# ─── Marketplace ───────────────────────────────────────────────────────


def test_submit_skill_returns_201_skill_dict() -> None:
    skill = {
        "skill_id": "skill-001",
        "name": "threshold-calibration",
        "version": "0.1.0",
        "current_stage": "draft",
    }
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/v1/ecosystem/marketplace/skills/submit").mock(
            return_value=Response(201, json=skill)
        )
        with EaaspEcosystemClient(base_url=BASE_URL, api_key=API_KEY) as client:
            result = client.submit_skill(
                name="threshold-calibration",
                summary="Auto-tune LLM confidence",
                version="0.1.0",
                manifest={"entrypoints": ["calibrate"]},
                scope="tenant",
                tags=("eaasp", "llm"),
                author_principal="apikey:abc",
            )
    assert result["skill_id"] == "skill-001"


def test_promote_skill_returns_audit_row() -> None:
    audit = {
        "skill_id": "skill-001",
        "lifecycle_id": "lc-1",
        "from_stage": "draft",
        "to_stage": "review",
        "actor_principal": "apikey:abc",
    }
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/v1/ecosystem/marketplace/skills/promote").mock(
            return_value=Response(200, json=audit)
        )
        with EaaspEcosystemClient(base_url=BASE_URL, api_key=API_KEY) as client:
            result = client.promote_skill(
                skill_id="skill-001",
                from_stage="draft",
                to_stage="review",
                rationale="ready for review",
                actor_principal="apikey:abc",
                actor_role="reviewer",
            )
    assert result["to_stage"] == "review"


def test_list_skills_with_tag_filter() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/v1/ecosystem/marketplace/skills/list").mock(
            return_value=Response(200, json={"tenant_id": "acme", "skills": []})
        )
        with EaaspEcosystemClient(base_url=BASE_URL, api_key=API_KEY) as client:
            client.list_skills(tag="eaasp")
    assert route.calls.last.request.url.params["tag"] == "eaasp"


def test_skill_stats_unknown_skill_raises_promotion_error() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/v1/ecosystem/marketplace/skills/stats").mock(
            return_value=Response(404, json={"code": "skill_not_found"})
        )
        with EaaspEcosystemClient(base_url=BASE_URL, api_key=API_KEY) as client:
            with pytest.raises(EaaspEcosystemPromotionError):
                client.skill_stats(skill_id="ghost")


def test_submission_audit_returns_history() -> None:
    payload = {
        "tenant_id": "acme",
        "skill_id": "skill-001",
        "audit": [{"to_stage": "draft"}, {"to_stage": "review"}],
    }
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/v1/ecosystem/marketplace/skills/audit").mock(
            return_value=Response(200, json=payload)
        )
        with EaaspEcosystemClient(base_url=BASE_URL, api_key=API_KEY) as client:
            result = client.submission_audit(skill_id="skill-001")
    assert len(result["audit"]) == 2


# ─── Error mapping ─────────────────────────────────────────────────────


def test_missing_credentials_401_raises_auth_error() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/v1/ecosystem/ontology").mock(
            return_value=Response(401, json={"code": "missing_credentials"})
        )
        with EaaspEcosystemClient(base_url=BASE_URL, api_key=API_KEY) as client:
            with pytest.raises(EaaspEcosystemAuthError):
                client.derive_taxonomy()


def test_acl_denied_403_raises_acl_error() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/v1/ecosystem/marketplace/skills/list").mock(
            return_value=Response(403, json={"code": "acl_forbidden"})
        )
        with EaaspEcosystemClient(base_url=BASE_URL, api_key=API_KEY) as client:
            with pytest.raises(EaaspEcosystemACLDenied):
                client.list_skills()


def test_cross_tenant_403_raises_tenant_forbidden() -> None:
    """The server's ``_require_principal`` emits ``code: cross_tenant_forbidden``
    when the caller's tenant does not match the resource's tenant. The SDK
    surfaces this as :class:`EaaspEcosystemTenantForbidden`, not as a generic
    ACL error, so callers can branch on cross-tenant vs ACL correctly.
    """
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/v1/ecosystem/ontology").mock(
            return_value=Response(403, json={"code": "cross_tenant_forbidden"})
        )
        with EaaspEcosystemClient(base_url=BASE_URL, api_key=API_KEY) as client:
            with pytest.raises(EaaspEcosystemTenantForbidden):
                client.derive_taxonomy()


def test_registry_unreachable_502_raises_promotion_error() -> None:
    """502 from the marketplace endpoint indicates the upstream
    ``eaasp-skill-registry`` is unreachable. Per the v3.14.1 backend
    contract, this surfaces as a promotion error (not a generic 5xx).
    """
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/v1/ecosystem/marketplace/skills/submit").mock(
            return_value=Response(502, json={"code": "registry_unreachable"})
        )
        with EaaspEcosystemClient(base_url=BASE_URL, api_key=API_KEY) as client:
            with pytest.raises(EaaspEcosystemPromotionError):
                client.submit_skill(
                    name="x",
                    summary="x",
                    version="0.1.0",
                    manifest={},
                    author_principal="apikey:abc",
                )


def test_empty_api_key_raises_at_construction() -> None:
    with pytest.raises(EaaspEcosystemAuthError):
        EaaspEcosystemClient(base_url=BASE_URL, api_key="")


# ─── Async mirror ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_derive_taxonomy_returns_graph() -> None:
    graph = {"tenant_id": "acme", "root_id": "root", "nodes": [], "links": []}
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/v1/ecosystem/ontology").mock(
            return_value=Response(200, json=graph)
        )
        async with AsyncEaaspEcosystemClient(
            base_url=BASE_URL, api_key=API_KEY
        ) as client:
            result = await client.derive_taxonomy()
    assert result["tenant_id"] == "acme"


@pytest.mark.asyncio
async def test_async_submit_skill_returns_skill_dict() -> None:
    skill = {"skill_id": "skill-async", "current_stage": "draft"}
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/v1/ecosystem/marketplace/skills/submit").mock(
            return_value=Response(201, json=skill)
        )
        async with AsyncEaaspEcosystemClient(
            base_url=BASE_URL, api_key=API_KEY
        ) as client:
            result = await client.submit_skill(
                name="async-skill",
                summary="async test",
                version="0.1.0",
                manifest={},
                author_principal="apikey:abc",
            )
    assert result["skill_id"] == "skill-async"
