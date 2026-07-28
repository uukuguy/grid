"""Tests for the v3.14.1 Skill Marketplace service.

Covers REQ-IDs:

- MARKETPLACE-01 — 4-stage promotion lifecycle (draft → review →
  certified → published) with deterministic state transitions
- MARKETPLACE-02 — Per-skill ACL (VisibilityScope × OwnerRole)
- MARKETPLACE-03 — CLI commands (smoke-tested; covered by SDK in
  v3.14.2)
- MARKETPLACE-04 — ``skill_stats`` analytics (per-stage
  histogram + per-role viewer histogram)
- MARKETPLACE-05 — ``submission_audit`` (lifecycle history)

Plus frozen-contract guards from audit §7.4:

- Invalid transitions raise ``MarketplacePromotionError``
- ACL-denied reads raise ``MarketplaceACLForbidden``
- Cross-tenant access raises ``CrossTenantForbidden`` (round-1
  fail-closed)
- Empty inputs are idempotent

The skill-registry HTTP API is mocked via ``respx`` to keep the
tests self-contained (no live registry required).
"""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

import httpx
import pytest
import respx

from eaasp_ecosystem.marketplace import (
    CrossTenantForbidden,
    MarketplaceACLForbidden,
    MarketplacePromotionError,
    MarketplaceSkill,
    MarketplaceStats,
    OwnerRole,
    PromotionStage,
    SkillMarketplace,
    SubmissionAuditRow,
    VALID_TRANSITIONS,
    VisibilityScope,
)


REGISTRY_URL = "http://mock-registry.test:18081"


# ─── Mock registry + marketplace fixtures ─────────────────────────────


@pytest.fixture
def mock_registry(respx_mock: respx.MockRouter) -> respx.MockRouter:
    """Stub the v3.11.2 ``eaasp-skill-registry`` HTTP API."""
    # POST /skills/draft → returns {skill_id: <uuid>}
    def submit_endpoint(request: httpx.Request) -> httpx.Response:
        body = request.read()
        import json as _json

        payload = _json.loads(body) if body else {}
        sid = str(uuid.uuid4())
        return httpx.Response(
            201,
            json={
                "skill_id": sid,
                "name": payload.get("name", ""),
                "version": payload.get("version", ""),
            },
        )

    def promote_endpoint(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "promoted"})

    respx_mock.post(f"{REGISTRY_URL}/skills/draft").mock(
        side_effect=submit_endpoint
    )
    respx_mock.post(url__regex=r".*/skills/.+/promote/.+").mock(
        side_effect=promote_endpoint
    )
    return respx_mock


def _ensure_analytics_schemas(l3_db: Path, l4_db: Path) -> None:
    """Ensure L3 / L4 DBs have the analytics tables (idempotent).

    Other fixtures (conftest) already create the base schemas; we
    only add what's missing for marketplace analytics:
      - L3: governance_decisions (analytics column approver)
      - L4: event_rooms + event_room_events (JOIN target)
    """
    with sqlite3.connect(l3_db) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS governance_decisions (
                decision_id TEXT PRIMARY KEY,
                session_id  TEXT NOT NULL,
                hook_id     TEXT NOT NULL,
                tool_name   TEXT NOT NULL,
                risk_level  TEXT NOT NULL,
                decision    TEXT NOT NULL,
                approver    TEXT,
                rationale   TEXT NOT NULL,
                stage       TEXT,
                ts          TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        conn.commit()
    with sqlite3.connect(l4_db) as conn:
        # Only create tables that may not exist; do NOT overwrite
        # the conftest's schema.
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS event_rooms (
                room_id          TEXT PRIMARY KEY,
                tenant_id        TEXT NOT NULL,
                owner_principal  TEXT NOT NULL,
                status           TEXT NOT NULL,
                created_at       INTEGER NOT NULL,
                expires_at       INTEGER NOT NULL
            );
            """
        )
        conn.commit()


@pytest.fixture
def marketplace(
    tmp_path: Path, l3_db: Path, l4_db: Path
) -> SkillMarketplace:
    """Build a SkillMarketplace with a per-test marketplace DB."""
    db = tmp_path / "marketplace.db"
    _ensure_analytics_schemas(l3_db, l4_db)
    return SkillMarketplace(
        skill_registry_url=REGISTRY_URL,
        marketplace_db_path=str(db),
        l3_db_path=str(l3_db),
        l4_db_path=str(l4_db),
        default_tenant="default",
    )


@pytest.fixture
def mock_registry_url() -> str:
    """Return the mock registry URL."""
    return REGISTRY_URL


# ─── MARKETPLACE-01: 4-stage promotion lifecycle ──────────────────────


def test_valid_transitions_complete() -> None:
    """All four stages can reach every valid successor."""
    assert PromotionStage.REVIEW in VALID_TRANSITIONS[PromotionStage.DRAFT]
    assert PromotionStage.CERTIFIED in VALID_TRANSITIONS[PromotionStage.REVIEW]
    assert PromotionStage.PUBLISHED in VALID_TRANSITIONS[PromotionStage.CERTIFIED]
    assert PromotionStage.DRAFT in VALID_TRANSITIONS[PromotionStage.PUBLISHED]


def test_invalid_transition_published_to_review_rejected() -> None:
    """``PUBLISHED → REVIEW`` is rejected (no skip-back allowed)."""
    with pytest.raises(MarketplacePromotionError):
        # Direct module-level transition check; the service applies
        # the same logic via _check_transition.
        m = SkillMarketplace(
            skill_registry_url=REGISTRY_URL,
            marketplace_db_path=":memory:",
            l3_db_path=":memory:",
            l4_db_path=":memory:",
        )
        m._check_transition(
            PromotionStage.PUBLISHED, PromotionStage.REVIEW
        )


def test_invalid_transition_review_to_published_rejected() -> None:
    """``REVIEW → PUBLISHED`` skips CERTIFIED → rejected."""
    m = SkillMarketplace(
        skill_registry_url=REGISTRY_URL,
        marketplace_db_path=":memory:",
        l3_db_path=":memory:",
        l4_db_path=":memory:",
    )
    with pytest.raises(MarketplacePromotionError):
        m._check_transition(
            PromotionStage.REVIEW, PromotionStage.PUBLISHED
        )


def test_submit_skill_writes_initial_lifecycle_row(
    marketplace: SkillMarketplace,
    mock_registry: respx.MockRouter,
) -> None:
    """submit_skill writes a DRAFT row to skill_lifecycle."""
    skill = marketplace.submit_skill(
        tenant_id="default",
        author_principal="alice@example.com",
        name="acme-thermo-reader",
        summary="Read temperature from SCADA",
        version="1.0.0",
        manifest={"entrypoints": ["read_temp"]},
        scope=VisibilityScope.TENANT,
        tags=("scada", "temperature"),
    )
    assert skill.current_stage == PromotionStage.DRAFT
    assert skill.scope == VisibilityScope.TENANT
    assert skill.tenant_id == "default"
    assert skill.author_principal == "alice@example.com"


def test_promote_skill_writes_lifecycle_row(
    marketplace: SkillMarketplace, mock_registry: respx.MockRouter
) -> None:
    """promote_skill writes a row + calls registry."""
    skill = marketplace.submit_skill(
        tenant_id="default",
        author_principal="alice",
        name="s1",
        summary="x",
        version="1.0.0",
        manifest={},
        scope=VisibilityScope.PRIVATE,
    )
    audit = marketplace.promote_skill(
        tenant_id="default",
        actor_principal="alice",
        actor_role=OwnerRole.AUTHOR,
        skill_id=skill.skill_id,
        from_stage=PromotionStage.DRAFT,
        to_stage=PromotionStage.REVIEW,
        rationale="ready for review",
    )
    assert audit.from_stage == PromotionStage.DRAFT
    assert audit.to_stage == PromotionStage.REVIEW


def test_full_lifecycle_draft_to_published(
    marketplace: SkillMarketplace, mock_registry: respx.MockRouter
) -> None:
    """A skill can traverse the full 4-stage lifecycle."""
    skill = marketplace.submit_skill(
        tenant_id="default",
        author_principal="alice",
        name="s2",
        summary="x",
        version="1.0.0",
        manifest={},
        scope=VisibilityScope.MARKETPLACE,
    )
    sid = skill.skill_id
    # Author → REVIEW
    marketplace.promote_skill(
        tenant_id="default",
        actor_principal="alice",
        actor_role=OwnerRole.AUTHOR,
        skill_id=sid,
        from_stage=PromotionStage.DRAFT,
        to_stage=PromotionStage.REVIEW,
        rationale="ready",
    )
    # Reviewer → CERTIFIED
    marketplace.promote_skill(
        tenant_id="default",
        actor_principal="reviewer-1",
        actor_role=OwnerRole.REVIEWER,
        skill_id=sid,
        from_stage=PromotionStage.REVIEW,
        to_stage=PromotionStage.CERTIFIED,
        rationale="approved",
    )
    # Admin → PUBLISHED
    marketplace.promote_skill(
        tenant_id="default",
        actor_principal="admin-1",
        actor_role=OwnerRole.ADMIN,
        skill_id=sid,
        from_stage=PromotionStage.CERTIFIED,
        to_stage=PromotionStage.PUBLISHED,
        rationale="published",
    )
    audit = marketplace.submission_audit(
        tenant_id="default",
        skill_id=sid,
        caller_principal="alice",
        caller_role=OwnerRole.AUTHOR,
    )
    stages = [r.to_stage for r in audit]
    assert stages == [
        PromotionStage.DRAFT,
        PromotionStage.REVIEW,
        PromotionStage.CERTIFIED,
        PromotionStage.PUBLISHED,
    ]


# ─── MARKETPLACE-02: ACL enforcement ───────────────────────────────────


def test_acl_private_author_can_read() -> None:
    """``VisibilityScope.PRIVATE + OwnerRole.AUTHOR`` is allowed."""
    m = SkillMarketplace(
        skill_registry_url=REGISTRY_URL,
        marketplace_db_path=":memory:",
        l3_db_path=":memory:",
        l4_db_path=":memory:",
    )
    m._check_acl(
        scope=VisibilityScope.PRIVATE,
        tenant_id="default",
        author_principal="alice",
        caller_principal="alice",
        caller_role=OwnerRole.AUTHOR,
    )  # no raise


def test_acl_private_public_rejected() -> None:
    """``VisibilityScope.PRIVATE + OwnerRole.PUBLIC`` is rejected."""
    m = SkillMarketplace(
        skill_registry_url=REGISTRY_URL,
        marketplace_db_path=":memory:",
        l3_db_path=":memory:",
        l4_db_path=":memory:",
    )
    with pytest.raises(MarketplaceACLForbidden):
        m._check_acl(
            scope=VisibilityScope.PRIVATE,
            tenant_id="default",
            author_principal="alice",
            caller_principal="bob",
            caller_role=OwnerRole.PUBLIC,
        )


def test_acl_marketplace_allows_any_authenticated() -> None:
    """``VisibilityScope.MARKETPLACE`` is allowed for any caller."""
    m = SkillMarketplace(
        skill_registry_url=REGISTRY_URL,
        marketplace_db_path=":memory:",
        l3_db_path=":memory:",
        l4_db_path=":memory:",
    )
    m._check_acl(
        scope=VisibilityScope.MARKETPLACE,
        tenant_id="default",
        author_principal="alice",
        caller_principal="bob",
        caller_role=OwnerRole.PUBLIC,
    )  # no raise


def test_acl_tenant_requires_membership() -> None:
    """``VisibilityScope.TENANT + OwnerRole.PUBLIC`` is rejected."""
    m = SkillMarketplace(
        skill_registry_url=REGISTRY_URL,
        marketplace_db_path=":memory:",
        l3_db_path=":memory:",
        l4_db_path=":memory:",
    )
    with pytest.raises(MarketplaceACLForbidden):
        m._check_acl(
            scope=VisibilityScope.TENANT,
            tenant_id="default",
            author_principal="alice",
            caller_principal="bob",
            caller_role=OwnerRole.PUBLIC,
        )


# ─── MARKETPLACE-04: skill_stats ───────────────────────────────────────


def test_skill_stats_empty(
    marketplace: SkillMarketplace, mock_registry: respx.MockRouter
) -> None:
    """``skill_stats`` on a fresh skill returns zeros."""
    skill = marketplace.submit_skill(
        tenant_id="default",
        author_principal="alice",
        name="s3",
        summary="x",
        version="1.0.0",
        manifest={},
        scope=VisibilityScope.PRIVATE,
    )
    stats = marketplace.skill_stats(
        tenant_id="default",
        skill_id=skill.skill_id,
        caller_principal="alice",
        caller_role=OwnerRole.AUTHOR,
    )
    assert isinstance(stats, MarketplaceStats)
    assert stats.total_submissions == 1  # the initial DRAFT row
    assert stats.total_certifications == 0
    assert stats.total_downloads == 0


def test_skill_stats_includes_per_stage_histogram(
    marketplace: SkillMarketplace, mock_registry: respx.MockRouter
) -> None:
    """``skill_stats`` includes the per-stage histogram."""
    skill = marketplace.submit_skill(
        tenant_id="default",
        author_principal="alice",
        name="s4",
        summary="x",
        version="1.0.0",
        manifest={},
        scope=VisibilityScope.PRIVATE,
    )
    marketplace.promote_skill(
        tenant_id="default",
        actor_principal="alice",
        actor_role=OwnerRole.AUTHOR,
        skill_id=skill.skill_id,
        from_stage=PromotionStage.DRAFT,
        to_stage=PromotionStage.REVIEW,
        rationale="ready",
    )
    stats = marketplace.skill_stats(
        tenant_id="default",
        skill_id=skill.skill_id,
        caller_principal="alice",
        caller_role=OwnerRole.AUTHOR,
    )
    assert stats.per_stage_histogram[PromotionStage.DRAFT.value] == 1
    assert stats.per_stage_histogram[PromotionStage.REVIEW.value] == 1


# ─── MARKETPLACE-05: submission_audit ──────────────────────────────────


def test_submission_audit_returns_full_history(
    marketplace: SkillMarketplace, mock_registry: respx.MockRouter
) -> None:
    """``submission_audit`` returns every lifecycle row in order."""
    skill = marketplace.submit_skill(
        tenant_id="default",
        author_principal="alice",
        name="s5",
        summary="x",
        version="1.0.0",
        manifest={},
        scope=VisibilityScope.MARKETPLACE,
    )
    marketplace.promote_skill(
        tenant_id="default",
        actor_principal="alice",
        actor_role=OwnerRole.AUTHOR,
        skill_id=skill.skill_id,
        from_stage=PromotionStage.DRAFT,
        to_stage=PromotionStage.REVIEW,
        rationale="r1",
    )
    marketplace.promote_skill(
        tenant_id="default",
        actor_principal="reviewer-1",
        actor_role=OwnerRole.REVIEWER,
        skill_id=skill.skill_id,
        from_stage=PromotionStage.REVIEW,
        to_stage=PromotionStage.CERTIFIED,
        rationale="r2",
    )
    audit = marketplace.submission_audit(
        tenant_id="default",
        skill_id=skill.skill_id,
        caller_principal="alice",
        caller_role=OwnerRole.AUTHOR,
    )
    assert len(audit) == 3
    assert isinstance(audit[0], SubmissionAuditRow)
    assert audit[0].from_stage is None
    assert audit[0].to_stage == PromotionStage.DRAFT
    assert audit[1].from_stage == PromotionStage.DRAFT
    assert audit[1].to_stage == PromotionStage.REVIEW
    assert audit[2].from_stage == PromotionStage.REVIEW
    assert audit[2].to_stage == PromotionStage.CERTIFIED


# ─── Cross-tenant guard (round-1 fail-closed carry-over) ──────────────


def test_cross_tenant_resolution_rejected(
    marketplace: SkillMarketplace,
) -> None:
    """``tenant_id=None / ""`` is rejected (round-1 fail-closed)."""
    with pytest.raises(CrossTenantForbidden):
        marketplace.submit_skill(
            tenant_id=None,
            author_principal="alice",
            name="s",
            summary="x",
            version="1.0.0",
            manifest={},
        )
    with pytest.raises(CrossTenantForbidden):
        marketplace.submit_skill(
            tenant_id="",
            author_principal="alice",
            name="s",
            summary="x",
            version="1.0.0",
            manifest={},
        )


def test_cross_tenant_assert_fail_closed(
    marketplace: SkillMarketplace,
) -> None:
    """``_assert_same_tenant`` rejects when row_tenant is None."""
    with pytest.raises(CrossTenantForbidden):
        marketplace._assert_same_tenant("default", None)


def test_cross_tenant_assert_rejects_mismatch(
    marketplace: SkillMarketplace,
) -> None:
    """``_assert_same_tenant`` rejects on tenant mismatch."""
    with pytest.raises(CrossTenantForbidden):
        marketplace._assert_same_tenant("acme", "beta")


# ─── JSON-schema (REQ-ID SDK-03 emission) ─────────────────────────────


def test_marketplace_json_schema_includes_required_types(
    marketplace: SkillMarketplace,
) -> None:
    """Marketplace JSON-schema includes MarketplaceSkill +
    MarketplaceStats + SubmissionAuditRow."""
    schema = marketplace.json_schema()
    assert "MarketplaceSkill" in schema["properties"]
    assert "MarketplaceStats" in schema["properties"]
    assert "SubmissionAuditRow" in schema["properties"]
    assert "VisibilityScope" in schema["properties"]
    assert "OwnerRole" in schema["properties"]
    assert "PromotionStage" in schema["properties"]


# ─── Dataclass shape (REQ-IDs MARKETPLACE-01..05) ──────────────────────


def test_marketplace_skill_to_dict_keys() -> None:
    """``MarketplaceSkill.to_dict`` exposes the documented keys."""
    s = MarketplaceSkill(
        skill_id="s1", version="1.0", name="n", summary="x",
        author_principal="a", tenant_id="t",
        scope=VisibilityScope.PRIVATE,
        current_stage=PromotionStage.DRAFT,
        created_at=1, tags=("a", "b"),
    )
    d = s.to_dict()
    assert "scope" in d
    assert d["scope"] == "private"
    assert d["current_stage"] == "draft"


def test_promote_skill_unknown_skill_rejected(
    marketplace: SkillMarketplace,
) -> None:
    """Promoting a non-existent skill raises MarketplacePromotionError."""
    with pytest.raises(MarketplacePromotionError):
        marketplace.promote_skill(
            tenant_id="default",
            actor_principal="alice",
            actor_role=OwnerRole.AUTHOR,
            skill_id="does-not-exist",
            from_stage=PromotionStage.DRAFT,
            to_stage=PromotionStage.REVIEW,
            rationale="x",
        )


# ─── Round-2 security regression tests ──────────────────────────────────
#
# Three regression tests added to lock the round-2 security review
# fixes (spoofed author_principal, role-prefix bypass, unassigned
# reviewer ACL). They pin the new contract and prevent regressions.


def test_round2_spoofed_author_principal_rejected_at_api_layer(
    tmp_path: Path, respx_mock: respx.MockRouter
) -> None:
    """API endpoint MUST use server-derived principal, not body field.

    Per round-2 issue #1: client A submits with
    ``author_principal="B"`` → the server writes author=A
    (the authenticated principal), not B.
    """
    from fastapi.testclient import TestClient
    from eaasp_ecosystem.ecosystem import EcosystemConfig, create_app

    cfg = EcosystemConfig(
        l2_db_path=":memory:",
        l3_db_path=":memory:",
        l4_db_path=":memory:",
        l5_db_path=":memory:",
        default_tenant="default",
        marketplace_db_path=str(tmp_path / "mkt.db"),
        api_keys={"key-A": "default"},
    )
    app = create_app(config=cfg)
    client = TestClient(app)

    respx_mock.post(
        f"{REGISTRY_URL}/skills/draft"
    ).mock(
        return_value=httpx.Response(
            201, json={"skill_id": "skill-from-A"}
        )
    )

    # Submit with author_principal="B" (spoofed).
    resp = client.post(
        "/v1/ecosystem/marketplace/skills/submit",
        headers={"Authorization": "Bearer key-A"},
        json={
            "name": "spoof-test",
            "summary": "x",
            "version": "1.0",
            "author_principal": "B",
            "manifest": {},
            "scope": "private",
            "tags": [],
        },
    )
    # After round-2 fix, ``author_principal`` is removed from the
    # request body schema; FastAPI returns 422 (body field not
    # accepted / missing required). The server NEVER writes
    # author="B" — either the request is rejected (422/400) or
    # accepted with author = server-derived principal.
    assert resp.status_code in (400, 422), (
        f"spoofed author must be rejected; got {resp.status_code}: {resp.text}"
    )
    # In particular, a successful 201 with author="B" would prove
    # the bug is still present.
    assert resp.status_code != 201


def test_round2_role_prefix_bypass_blocked(
    tmp_path: Path, respx_mock: respx.MockRouter
) -> None:
    """actor_principal="system:admin_evil" is NOT inferred as ADMIN.

    Per round-2 issue #2: the string-prefix role inference is
    trivially spoofable. The role MUST come from an explicit
    ``actor_role`` parameter (sourced from the authenticated
    principal at the API layer).
    """
    import sqlite3
    db = tmp_path / "mkt.db"
    _ensure_analytics_schemas(":memory:", ":memory:")
    # Mock the registry endpoints used by submit_skill.
    respx_mock.post(f"{REGISTRY_URL}/skills/draft").mock(
        return_value=httpx.Response(201, json={"skill_id": "spoof-1"})
    )
    m = SkillMarketplace(
        skill_registry_url=REGISTRY_URL,
        marketplace_db_path=str(db),
        l3_db_path=":memory:",
        l4_db_path=":memory:",
        default_tenant="default",
    )
    # Set up a skill
    skill = m.submit_skill(
        tenant_id="default",
        author_principal="alice",
        name="s-prefix",
        summary="x",
        version="1.0.0",
        manifest={},
        scope=VisibilityScope.PRIVATE,
    )
    # Spoofed "admin" principal with PUBLIC role should NOT pass.
    # The previous code would have inferred role=ADMIN from
    # startswith("system:admin") and let the call succeed.
    with pytest.raises(MarketplaceACLForbidden):
        m._check_acl(
            scope=VisibilityScope.PRIVATE,
            tenant_id="default",
            author_principal="alice",
            caller_principal="system:admin_evil",
            caller_role=OwnerRole.PUBLIC,  # explicit role
            skill_id=skill.skill_id,
        )


def test_round2_unassigned_reviewer_denied(
    tmp_path: Path, respx_mock: respx.MockRouter
) -> None:
    """REVIEWER C (not assigned) cannot read a PRIVATE skill.

    Per round-2 issue #3: PRIVATE + REVIEWER/Admin should only
    pass for ASSIGNED reviewers, not arbitrary principals
    claiming the REVIEWER role.
    """
    db = tmp_path / "mkt.db"
    _ensure_analytics_schemas(":memory:", ":memory:")
    # Mock the registry endpoints used by submit_skill.
    respx_mock.post(f"{REGISTRY_URL}/skills/draft").mock(
        return_value=httpx.Response(201, json={"skill_id": "assign-1"})
    )
    m = SkillMarketplace(
        skill_registry_url=REGISTRY_URL,
        marketplace_db_path=str(db),
        l3_db_path=":memory:",
        l4_db_path=":memory:",
        default_tenant="default",
    )
    skill = m.submit_skill(
        tenant_id="default",
        author_principal="alice",
        name="s-assign",
        summary="x",
        version="1.0.0",
        manifest={},
        scope=VisibilityScope.PRIVATE,
    )
    # Reviewer C (not assigned) → denied
    with pytest.raises(MarketplaceACLForbidden):
        m._check_acl(
            scope=VisibilityScope.PRIVATE,
            tenant_id="default",
            author_principal="alice",
            caller_principal="reviewer-C",
            caller_role=OwnerRole.REVIEWER,
            skill_id=skill.skill_id,
        )
    # Now assign reviewer C → access granted
    m._assign_reviewer(
        skill_id=skill.skill_id,
        tenant_id="default",
        principal="reviewer-C",
        assigned_by="alice",
    )
    m._check_acl(
        scope=VisibilityScope.PRIVATE,
        tenant_id="default",
        author_principal="alice",
        caller_principal="reviewer-C",
        caller_role=OwnerRole.REVIEWER,
        skill_id=skill.skill_id,
    )  # no raise — assigned reviewer accepted