"""Tests for the v3.14.0 ecosystem FastAPI backend.

Covers:

- ``GET /health`` — liveness probe (public)
- ``GET /v1/ecosystem/schema`` — JSON-schema (public)
- ``GET /v1/ecosystem/ontology`` — full taxonomy + cross-domain
  links (authenticated)
- ``GET /v1/ecosystem/ontology/tree?path=`` — list nodes under
  path (authenticated)
- ``GET /v1/ecosystem/ontology/links`` — list cross-domain links
  (authenticated)

Plus regression tests added in round-1 security review:

- 401 on missing / invalid credentials
- X-Tenant-Id header is NOT trusted (returns 401, not 200)
- ?tenant_id= query param is NOT trusted (returns 401, not 200)

Plus frozen-contract guards (audit §7.3): empty results return
200 with ``[]``, never 404.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eaasp_ecosystem.ecosystem import EcosystemConfig, create_app

from .conftest import (
    seed_l2_anchor,
    seed_l3_decision,
    seed_l4_event,
    seed_l5_card,
)


# ─── Fixtures ────────────────────────────────────────────────────────────


AUTH_HEADERS = {"Authorization": "Bearer dev-test-key-acme"}
AUTH_HEADERS_B = {"Authorization": "Bearer dev-test-key-beta"}


@pytest.fixture
def client(
    l2_db: Path, l3_db: Path, l4_db: Path, l5_db: Path, tmp_path: Path
) -> TestClient:
    """Build a TestClient backed by the per-test SQLite stores.

    Two API keys are registered for tenant-isolation regression
    tests: ``dev-test-key-acme`` → ``acme``, ``dev-test-key-beta``
    → ``beta``. The L2/L3 stores are bound to ``acme`` (the
    standard ``make dev-eaasp`` topology is single-tenant per
    store). Cross-tenant access (beta → acme stores) is rejected
    by the service's ``_assert_same_tenant`` guard.
    """
    cfg = EcosystemConfig(
        l2_db_path=str(l2_db),
        l3_db_path=str(l3_db),
        l4_db_path=str(l4_db),
        l5_db_path=str(l5_db),
        default_tenant="acme",
        root_layer="l2_type",
        marketplace_db_path=str(tmp_path / "mkt-acme.db"),
        api_keys={
            "dev-test-key-acme": "acme",
            "dev-test-key-beta": "beta",
        },
    )
    app = create_app(config=cfg)
    return TestClient(app)


@pytest.fixture
def client_for_tenant_beta(
    l2_db: Path, l3_db: Path, l4_db: Path, l5_db: Path, tmp_path: Path
) -> TestClient:
    """Build a TestClient whose L2/L3 stores are bound to ``beta``.

    Used by tests that exercise the ``beta`` authenticated tenant
    end-to-end (so the L2/L3 single-tenant guard accepts ``beta``).
    """
    cfg = EcosystemConfig(
        l2_db_path=str(l2_db),
        l3_db_path=str(l3_db),
        l4_db_path=str(l4_db),
        l5_db_path=str(l5_db),
        default_tenant="beta",
        root_layer="l2_type",
        marketplace_db_path=str(tmp_path / "mkt-beta.db"),
        api_keys={
            "dev-test-key-acme": "acme",
            "dev-test-key-beta": "beta",
        },
    )
    app = create_app(config=cfg)
    return TestClient(app)


# ─── /health (public) ────────────────────────────────────────────────────


def test_health_returns_ok(client: TestClient) -> None:
    """``GET /health`` returns 200 with ``status: ok`` (public)."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_health_no_auth_required(client: TestClient) -> None:
    """``GET /health`` works without any auth header."""
    resp = client.get("/health")
    assert resp.status_code == 200


# ─── /v1/ecosystem/schema (public) ───────────────────────────────────────


def test_get_schema_returns_ontology_schema(client: TestClient) -> None:
    """``GET /v1/ecosystem/schema`` returns the JSON-schema (public)."""
    resp = client.get("/v1/ecosystem/schema")
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "EAASP Ecosystem Surface"
    assert "TaxonomyNode" in body["properties"]
    assert "CrossDomainLink" in body["properties"]
    assert "MarketplaceSkill" in body["properties"]
    assert "PromotionStage" in body["properties"]


def test_get_schema_no_auth_required(client: TestClient) -> None:
    """Schema endpoint is public (no PII, no tenant data)."""
    resp = client.get("/v1/ecosystem/schema")
    assert resp.status_code == 200


# ─── Auth: missing / invalid credentials ────────────────────────────────


def test_ontology_requires_auth(client: TestClient) -> None:
    """``GET /v1/ecosystem/ontology`` without auth → 401."""
    resp = client.get("/v1/ecosystem/ontology")
    assert resp.status_code == 401
    body = resp.json()
    assert body["detail"]["code"] == "missing_credentials"


def test_ontology_rejects_invalid_auth(client: TestClient) -> None:
    """Invalid Bearer token → 401 (invalid_credentials)."""
    resp = client.get(
        "/v1/ecosystem/ontology",
        headers={"Authorization": "Bearer not-a-real-key"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["detail"]["code"] == "invalid_credentials"


def test_ontology_tree_requires_auth(client: TestClient) -> None:
    """``GET /v1/ecosystem/ontology/tree`` without auth → 401."""
    resp = client.get("/v1/ecosystem/ontology/tree")
    assert resp.status_code == 401


def test_ontology_links_requires_auth(client: TestClient) -> None:
    """``GET /v1/ecosystem/ontology/links`` without auth → 401."""
    resp = client.get("/v1/ecosystem/ontology/links")
    assert resp.status_code == 401


# ─── Auth: X-Tenant-Id header / ?tenant_id= are NOT trusted ─────────────


def test_x_tenant_id_header_is_not_trusted(
    client: TestClient, l2_db: Path
) -> None:
    """X-Tenant-Id header alone (no auth) is rejected with 401.

    Regression test for round-1 security review issue #3.
    """
    seed_l2_anchor(l2_db, anchor_id="a1", event_id="e1", session_id="s1", type_value="plant")
    resp = client.get(
        "/v1/ecosystem/ontology",
        headers={"X-Tenant-Id": "acme"},
    )
    assert resp.status_code == 401


def test_tenant_id_query_param_is_not_trusted(
    client: TestClient, l2_db: Path
) -> None:
    """``?tenant_id=acme`` without auth is rejected with 401.

    Regression test for round-1 security review issue #3.
    """
    seed_l2_anchor(l2_db, anchor_id="a1", event_id="e1", session_id="s1", type_value="plant")
    resp = client.get("/v1/ecosystem/ontology?tenant_id=acme")
    assert resp.status_code == 401


def test_x_tenant_id_header_does_not_override_authenticated_tenant(
    client_for_tenant_beta: TestClient, l2_db: Path
) -> None:
    """Even with auth, X-Tenant-Id is ignored — the authenticated
    principal's tenant wins."""
    seed_l2_anchor(l2_db, anchor_id="a1", event_id="e1", session_id="s1", type_value="plant")
    resp = client_for_tenant_beta.get(
        "/v1/ecosystem/ontology",
        headers={
            **AUTH_HEADERS_B,  # authenticated as tenant 'beta'
            "X-Tenant-Id": "acme",  # attempted override
        },
    )
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == "beta"


# ─── Authenticated requests work end-to-end ─────────────────────────────


def test_get_ontology_empty(client: TestClient) -> None:
    """Authenticated + empty stores → only the synthetic ``root``."""
    resp = client.get(
        "/v1/ecosystem/ontology", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_id"] == "acme"
    assert body["root_id"] == "root"
    assert len(body["nodes"]) == 1
    assert body["nodes"][0]["node_id"] == "root"


def test_get_ontology_with_data(client: TestClient, l2_db: Path) -> None:
    """Authenticated + L2 anchors produce taxonomy nodes."""
    seed_l2_anchor(l2_db, anchor_id="a1", event_id="e1", session_id="s1", type_value="plant")
    seed_l2_anchor(l2_db, anchor_id="a2", event_id="e2", session_id="s1", type_value="grid")
    resp = client.get(
        "/v1/ecosystem/ontology", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    body = resp.json()
    labels = sorted(
        n["label"] for n in body["nodes"] if n["layer"] == "l2_type"
    )
    assert labels == ["grid", "plant"]


def test_get_ontology_returns_authenticated_tenant(
    client_for_tenant_beta: TestClient,
) -> None:
    """``tenant_id`` in the response matches the authenticated tenant."""
    resp = client_for_tenant_beta.get(
        "/v1/ecosystem/ontology", headers=AUTH_HEADERS_B
    )
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == "beta"


# ─── Tree + links endpoints (authenticated) ─────────────────────────────


def test_get_ontology_tree_root(client: TestClient, l2_db: Path) -> None:
    """``GET /v1/ecosystem/ontology/tree`` returns top-level nodes."""
    seed_l2_anchor(l2_db, anchor_id="a1", event_id="e1", session_id="s1", type_value="plant")
    resp = client.get(
        "/v1/ecosystem/ontology/tree", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["path"] == ""
    labels = sorted(n["label"] for n in body["nodes"])
    assert "plant" in labels


def test_get_ontology_tree_with_path(client: TestClient, l2_db: Path) -> None:
    """``GET /v1/ecosystem/ontology/tree?path=plant`` walks one level."""
    seed_l2_anchor(l2_db, anchor_id="a1", event_id="e1", session_id="s1", type_value="plant")
    resp = client.get(
        "/v1/ecosystem/ontology/tree?path=plant", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["path"] == "plant"


def test_get_ontology_tree_empty_returns_200(client: TestClient) -> None:
    """Empty stores + tree endpoint → 200 with ``nodes: []``."""
    resp = client.get(
        "/v1/ecosystem/ontology/tree", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    assert resp.json()["nodes"] == []


def test_get_ontology_links_empty(client: TestClient) -> None:
    """Empty stores → 200 with ``links: []``."""
    resp = client.get(
        "/v1/ecosystem/ontology/links", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    assert resp.json()["links"] == []


def test_get_ontology_links_with_cross_domain(
    client: TestClient, l2_db: Path, l3_db: Path
) -> None:
    """Cross-domain link between L2 + L3 nodes sharing evidence."""
    seed_l2_anchor(l2_db, anchor_id="shared", event_id="e1", session_id="s1", type_value="plant")
    seed_l3_decision(
        l3_db, decision_id="shared", session_id="s1", hook_id="h1",
        tool_name="read_doc", risk_level="read",
    )
    resp = client.get(
        "/v1/ecosystem/ontology/links", headers=AUTH_HEADERS
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["links"]) >= 1
    link = body["links"][0]
    assert "shared" in link["evidence_refs"]


# ─── Frozen contract: empty results never 404 ───────────────────────────


def test_ontology_unknown_tenant_returns_200(client: TestClient) -> None:
    """Unknown authenticated tenant → 200 with empty graph."""
    resp = client.get(
        "/v1/ecosystem/ontology",
        headers={"Authorization": "Bearer dev-test-key-acme"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_id"] == "acme"
    assert len(body["nodes"]) == 1  # root only
    assert body["nodes"][0]["node_id"] == "root"