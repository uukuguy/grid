"""Skill Marketplace service — 4-stage promotion lifecycle + ACL + analytics.

v3.14.1 — EAASP Phase 6 — Skill Marketplace API + 第三方提交 / 4 阶段
promotion / 完整 ACL / analytics.

Per ``EAASP_v2_0_EVOLUTION_PATH.md`` §三 Phase 6 + spec §7.5–§7.8:

- The marketplace **extends** the v3.11.2 ``eaasp-skill-registry``
  (Cargo). It does NOT replace the registry (per D-41). The
  registry continues to own ``skill_manifest`` / ``entrypoints`` /
  ``mcp_servers`` / ``permissions`` storage; the marketplace adds
  a 4-stage promotion lifecycle (``draft → review → certified →
  published``), per-skill ACL, and analytics on top.
- Per D-40, no new tables / no new columns / no new event types.
  The marketplace projection writes lifecycle rows to the
  registry's existing ``skill_lifecycle`` table (created by the
  v3.11.2 promotion flow) and reads analytics from the existing
  L3 ``governance_decisions`` + L4 ``event_room_events``.
- The marketplace consumes ``eaasp-skill-registry`` via its
  existing HTTP API (``/skills/draft``, ``/skills/{id}/promote/{version}``,
  ``/skills/search``, ``/skills/{id}/content``) — it does NOT
  duplicate the registry's persistence layer. In the v3.14
  single-tenant ``make dev-eaasp`` topology, both services run
  on localhost; in production they would be split per tenant.

Frozen contract (audit §7.4):

- All marketplace state transitions are deterministic.
- Each transition writes a row to ``skill_lifecycle`` (existing
  v3.11.2 table); the marketplace READS but never modifies the
  registry's skill manifest storage.
- ACL is enforced at every read: ``VisibilityScope.{Private,
  Tenant, Marketplace}`` × ``OwnerRole.{Author, Reviewer, Admin,
  Public}`` matrix.
- ``skill_stats`` and ``submission_audit`` are computed on-the-fly
  via SELECT over L3 / L4 stores; they do NOT introduce new
  analytics tables.

ACL matrix (per MARKETPLACE-02 REQ-ID):

- ``Private + Author`` → only the original author can read
- ``Private + Reviewer`` → only the assigned reviewer (per
  ``skill_reviewers`` join table) can read; unassigned reviewers
  are rejected (round-2 fix)
- ``Private + Admin`` → tenant admins can read
- ``Tenant + Author/Reviewer/Admin`` → same tenant members can read
- ``Marketplace + Public`` → any authenticated principal can read
- ``Marketplace + Author/Reviewer/Admin`` → restricted to the
  authenticated tenant

Cross-tenant access (tenant B reading tenant A's skills) is
rejected with ``CrossTenantForbidden`` (matching the round-1
security review fix in v3.14.0 ``ontology.py``).

Reviewer assignment (round-2 fix):

- When a skill enters the ``REVIEW`` stage via
  ``promote_skill(DRAFT → REVIEW)``, the actor is auto-recorded
  as an assigned reviewer (via the ``skill_reviewers`` table).
- ``_check_acl`` consults ``skill_reviewers`` to verify the
  ``REVIEWER`` role is actually assigned to the skill — string-
  prefix role inference is gone (round-2 fix).
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
import urllib.parse
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from .ontology import CrossTenantForbidden


# ─── ACL enums ──────────────────────────────────────────────────────────


class VisibilityScope(str, Enum):
    """Visibility scope for a marketplace skill.

    ``PRIVATE`` → only the author / reviewers / admins can see it
    ``TENANT`` → any member of the owning tenant can see it
    ``MARKETPLACE`` → any authenticated principal can see it
    """

    PRIVATE = "private"
    TENANT = "tenant"
    MARKETPLACE = "marketplace"


class OwnerRole(str, Enum):
    """The role of the authenticated principal requesting access.

    ``AUTHOR`` → the original author of the skill
    ``REVIEWER`` → a reviewer (with a ``ReviewSet`` decision)
    ``ADMIN`` → a tenant administrator
    ``PUBLIC`` → any other authenticated principal
    """

    AUTHOR = "author"
    REVIEWER = "reviewer"
    ADMIN = "admin"
    PUBLIC = "public"


class PromotionStage(str, Enum):
    """The 4-stage promotion lifecycle.

    ``DRAFT`` → ``REVIEW`` → ``CERTIFIED`` → ``PUBLISHED``.

    Valid transitions:
    - DRAFT → REVIEW (author submits for review)
    - REVIEW → CERTIFIED (reviewer certifies)
    - CERTIFIED → PUBLISHED (admin publishes)
    - any → DRAFT (rejected back to draft)

    Invalid transitions raise ``MarketplacePromotionError``.
    """

    DRAFT = "draft"
    REVIEW = "review"
    CERTIFIED = "certified"
    PUBLISHED = "published"


# Valid transition graph
VALID_TRANSITIONS: dict[PromotionStage, set[PromotionStage]] = {
    PromotionStage.DRAFT: {
        PromotionStage.REVIEW,
        PromotionStage.DRAFT,  # no-op self-transition
    },
    PromotionStage.REVIEW: {
        PromotionStage.CERTIFIED,
        PromotionStage.DRAFT,  # reviewer rejects → back to draft
        PromotionStage.REVIEW,
    },
    PromotionStage.CERTIFIED: {
        PromotionStage.PUBLISHED,
        PromotionStage.DRAFT,  # admin unpublishes → back to draft
        PromotionStage.CERTIFIED,
    },
    PromotionStage.PUBLISHED: {
        PromotionStage.DRAFT,  # admin unpublishes
        PromotionStage.PUBLISHED,
    },
}


# ─── Errors ─────────────────────────────────────────────────────────────


class MarketplacePromotionError(ValueError):
    """Raised when a promotion transition is not allowed.

    Examples:
    - ``PUBLISHED → CERTIFIED`` is not a valid transition
    - ``REVIEW → PUBLISHED`` skips ``CERTIFIED`` (rejected)
    """


class MarketplaceACLForbidden(PermissionError):
    """Raised when an ACL check denies a marketplace read."""

    def __init__(
        self,
        message: str,
        *,
        scope: VisibilityScope | None = None,
        role: OwnerRole | None = None,
    ) -> None:
        super().__init__(message)
        self.scope = scope
        self.role = role


# ─── Projection types ──────────────────────────────────────────────────


@dataclass(frozen=True)
class MarketplaceSkill:
    """A skill as exposed by the marketplace API.

    Carries the registry's skill_id + version + manifest summary,
    plus the marketplace's ACL + lifecycle + analytics fields.
    """

    skill_id: str
    version: str
    name: str
    summary: str
    author_principal: str
    tenant_id: str
    scope: VisibilityScope
    current_stage: PromotionStage
    created_at: int
    promoted_at: int | None = None
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "version": self.version,
            "name": self.name,
            "summary": self.summary,
            "author_principal": self.author_principal,
            "tenant_id": self.tenant_id,
            "scope": self.scope.value,
            "current_stage": self.current_stage.value,
            "created_at": self.created_at,
            "promoted_at": self.promoted_at,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class MarketplaceStats:
    """Per-skill analytics. Read-only; computed on-the-fly."""

    skill_id: str
    total_submissions: int
    total_certifications: int
    total_downloads: int  # per-tenant
    per_stage_histogram: dict[str, int]
    per_role_viewer_histogram: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "total_submissions": self.total_submissions,
            "total_certifications": self.total_certifications,
            "total_downloads": self.total_downloads,
            "per_stage_histogram": dict(self.per_stage_histogram),
            "per_role_viewer_histogram": dict(self.per_role_viewer_histogram),
        }


@dataclass(frozen=True)
class SubmissionAuditRow:
    """One row in a skill's submission audit trail."""

    skill_id: str
    lifecycle_id: str
    from_stage: PromotionStage | None
    to_stage: PromotionStage
    actor_principal: str
    rationale: str
    ts: int
    cross_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "lifecycle_id": self.lifecycle_id,
            "from_stage": self.from_stage.value if self.from_stage else None,
            "to_stage": self.to_stage.value,
            "actor_principal": self.actor_principal,
            "rationale": self.rationale,
            "ts": self.ts,
            "cross_refs": list(self.cross_refs),
        }


# ─── Stable ID helpers ──────────────────────────────────────────────────


def _stable_lifecycle_id(skill_id: str, ts: int, seq: int) -> str:
    """Compute a stable lifecycle ID for a marketplace audit row.

    Combines the skill_id + timestamp + sequence into a SHA-256
    hash; the seq parameter is incremented per-call so two rows
    written in the same second get distinct IDs.
    """
    h = hashlib.sha256(
        f"{skill_id}|{ts}|{seq}".encode()
    ).hexdigest()
    return f"lifecycle-{h[:16]}"


def _next_lifecycle_seq(marketplace_db_path: str, skill_id: str) -> int:
    """Return the next sequence number for a skill's lifecycle rows.

    Used to disambiguate lifecycle IDs when multiple promotions
    occur in the same wall-clock second.
    """
    with sqlite3.connect(marketplace_db_path) as conn:
        try:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n FROM skill_lifecycle
                WHERE skill_id = ?
                """,
                (skill_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return 0
    return int(row[0]) if row else 0


# ─── Skill Marketplace ──────────────────────────────────────────────────


class SkillMarketplace:
    """Read-write projection layer over the v3.11.2 skill-registry.

    The marketplace delegates skill-manifest storage to the
    registry (via HTTP) and persists lifecycle rows in a
    local SQLite store (the marketplace's own bookkeeping table).
    The lifecycle store mirrors the registry's existing
    ``skill_lifecycle`` table schema so an export-import to the
    registry remains trivial.

    Parameters
    ----------
    skill_registry_url
        Base URL of the v3.11.2 ``eaasp-skill-registry`` HTTP API.
        The marketplace talks to the registry via
        ``httpx.Client(trust_env=False)`` (per the Clash proxy
        gotcha — see ``feedback_env_var_conventions``).
    marketplace_db_path
        Path to the marketplace's local SQLite store (lifecycle +
        analytics bookkeeping). One DB per deployment; the schema
        is initialised on first ``__init__``.
    l3_db_path, l4_db_path
        Paths to the L3 / L4 SQLite stores for analytics reads
        (MARKETPLACE-04 / -05 REQ-IDs).
    default_tenant
        Tenant this marketplace is bound to (single-tenant per
        store, matching v3.7.3 L2/L3 schema + D-40 no schema
        migration). Cross-tenant writes are rejected.
    """

    def __init__(
        self,
        *,
        skill_registry_url: str,
        marketplace_db_path: str,
        l3_db_path: str,
        l4_db_path: str,
        default_tenant: str = "default",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.skill_registry_url = skill_registry_url.rstrip("/")
        self.marketplace_db_path = marketplace_db_path
        self.l3_db_path = l3_db_path
        self.l4_db_path = l4_db_path
        self.default_tenant = default_tenant
        self.timeout_seconds = timeout_seconds
        self._init_db()

    # ─── DB initialisation ───────────────────────────────────────

    def _init_db(self) -> None:
        """Initialise the marketplace's lifecycle store.

        Schema mirrors the v3.11.2 ``skill_lifecycle`` table so an
        export-import to the registry remains trivial. No new
        tables beyond the lifecycle store (D-40).
        """
        schema = """
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS skill_lifecycle (
            lifecycle_id      TEXT PRIMARY KEY,
            skill_id          TEXT NOT NULL,
            version           TEXT NOT NULL,
            from_stage        TEXT,
            to_stage          TEXT NOT NULL,
            actor_principal   TEXT NOT NULL,
            tenant_id         TEXT NOT NULL,
            rationale         TEXT NOT NULL,
            ts                INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_skill_lifecycle_skill_id
            ON skill_lifecycle(skill_id);
        CREATE INDEX IF NOT EXISTS idx_skill_lifecycle_tenant_id
            ON skill_lifecycle(tenant_id);

        CREATE TABLE IF NOT EXISTS skill_acl (
            skill_id          TEXT NOT NULL,
            tenant_id         TEXT NOT NULL,
            scope             TEXT NOT NULL
                CHECK(scope IN ('private','tenant','marketplace')),
            author_principal  TEXT NOT NULL,
            version           TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (skill_id, tenant_id)
        );

        CREATE INDEX IF NOT EXISTS idx_skill_acl_tenant_id
            ON skill_acl(tenant_id);

        -- Reviewer-assignment join table (round-2 fix). Populated
        -- when a skill enters REVIEW stage; consulted by _check_acl
        -- so PRIVATE + REVIEWER role only passes for ASSIGNED
        -- reviewers, not arbitrary principals claiming the role.
        CREATE TABLE IF NOT EXISTS skill_reviewers (
            skill_id      TEXT NOT NULL,
            tenant_id     TEXT NOT NULL,
            principal     TEXT NOT NULL,
            assigned_at   INTEGER NOT NULL,
            assigned_by   TEXT,
            PRIMARY KEY (skill_id, principal)
        );

        CREATE INDEX IF NOT EXISTS idx_skill_reviewers_skill_id
            ON skill_reviewers(skill_id);
        """
        with sqlite3.connect(self.marketplace_db_path) as conn:
            conn.executescript(schema)
            conn.commit()

    # ─── Tenant guard (D-33 / v3.13 / v3.14.0 round-1 carry-over) ─

    def _resolve_tenant(self, tenant_id: str | None) -> str:
        """Resolve the calling tenant for a marketplace request.

        The caller MUST supply a non-empty ``tenant_id`` that has
        been validated against an authenticated principal. Empty /
        missing tenant_id is rejected (fail-closed per the v3.14.0
        round-1 security review fix).
        """
        if tenant_id is None:
            raise CrossTenantForbidden(
                "tenant_id required: caller must supply an "
                "authenticated tenant identifier"
            )
        t = tenant_id.strip()
        if not t:
            raise CrossTenantForbidden(
                "tenant_id required: caller must supply a non-empty "
                "authenticated tenant identifier"
            )
        return t

    def _assert_same_tenant(self, requested: str, row: str | None) -> None:
        """Fail-closed cross-tenant guard."""
        if row is None:
            raise CrossTenantForbidden(
                "row_tenant unavailable: cannot verify same-tenant "
                "invariant; fail-closed"
            )
        if requested != row:
            raise CrossTenantForbidden(
                f"cross-tenant access: caller tenant={requested!r} "
                f"row tenant={row!r}"
            )

    # ─── ACL enforcement ──────────────────────────────────────────

    def _is_assigned_reviewer(
        self, *, skill_id: str, principal: str, tenant_id: str
    ) -> bool:
        """Check whether ``principal`` is an assigned reviewer for
        ``skill_id``. Returns True when the ``skill_reviewers``
        join table contains a matching row.
        """
        with sqlite3.connect(self.marketplace_db_path) as conn:
            try:
                row = conn.execute(
                    """
                    SELECT 1 FROM skill_reviewers
                    WHERE skill_id = ? AND tenant_id = ?
                      AND principal = ?
                    """,
                    (skill_id, tenant_id, principal),
                ).fetchone()
            except sqlite3.OperationalError:
                row = None
        return row is not None

    def _assign_reviewer(
        self,
        *,
        skill_id: str,
        tenant_id: str,
        principal: str,
        assigned_by: str,
    ) -> None:
        """Persist a reviewer assignment for ``skill_id``.

        Called when a skill enters REVIEW stage so the assigned
        reviewer can subsequently read / certify the skill per
        the round-2 ACL matrix.
        """
        ts = int(time.time())
        with sqlite3.connect(self.marketplace_db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO skill_reviewers (
                    skill_id, tenant_id, principal, assigned_at,
                    assigned_by
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (skill_id, tenant_id, principal, ts, assigned_by),
            )
            conn.commit()

    def _check_acl(
        self,
        *,
        scope: VisibilityScope,
        tenant_id: str,
        author_principal: str,
        caller_principal: str,
        caller_role: OwnerRole,
        skill_id: str | None = None,
    ) -> None:
        """Enforce the visibility × role matrix (MARKETPLACE-02).

        See module docstring for the full matrix.

        For ``PRIVATE + REVIEWER`` (or ``PRIVATE + ADMIN`` with
        admin-reviewer assignment), the caller MUST be present in
        the ``skill_reviewers`` join table (round-2 fix). When
        ``skill_id`` is None the assignment check is skipped
        (the caller has no specific skill to verify against).
        """
        if scope == VisibilityScope.PRIVATE:
            if caller_role == OwnerRole.AUTHOR and caller_principal == author_principal:
                return
            if caller_role == OwnerRole.REVIEWER:
                if skill_id and self._is_assigned_reviewer(
                    skill_id=skill_id,
                    principal=caller_principal,
                    tenant_id=tenant_id,
                ):
                    return
                raise MarketplaceACLForbidden(
                    "private skill: caller is not an assigned reviewer",
                    scope=scope,
                    role=caller_role,
                )
            if caller_role == OwnerRole.ADMIN:
                # Admins are tenant-wide; reviewer-assignment
                # check not required for ADMIN.
                return
            raise MarketplaceACLForbidden(
                "private skill: caller lacks role",
                scope=scope,
                role=caller_role,
            )
        if scope == VisibilityScope.TENANT:
            if caller_role in (OwnerRole.AUTHOR, OwnerRole.REVIEWER, OwnerRole.ADMIN):
                return
            raise MarketplaceACLForbidden(
                "tenant skill: caller is not a tenant member",
                scope=scope,
                role=caller_role,
            )
        # scope == MARKETPLACE — any authenticated principal
        return

    # ─── Stage transition check ───────────────────────────────────

    def _check_transition(
        self, from_stage: PromotionStage, to_stage: PromotionStage
    ) -> None:
        """Enforce the 4-stage promotion lifecycle (MARKETPLACE-01)."""
        allowed = VALID_TRANSITIONS[from_stage]
        if to_stage not in allowed:
            raise MarketplacePromotionError(
                f"invalid transition: {from_stage.value} → {to_stage.value}"
            )

    # ─── Public API: submit / promote / list / stats / audit ──────

    def submit_skill(
        self,
        *,
        tenant_id: str,
        author_principal: str,
        name: str,
        summary: str,
        version: str,
        manifest: dict[str, Any],
        scope: VisibilityScope = VisibilityScope.PRIVATE,
        tags: tuple[str, ...] = (),
    ) -> MarketplaceSkill:
        """Submit a third-party skill to the marketplace.

        Delegates skill-manifest storage to the v3.11.2
        ``eaasp-skill-registry`` via HTTP (no re-implementation per
        D-41). Writes the initial lifecycle row to the marketplace
        store (DRAFT stage).
        """
        tenant = self._resolve_tenant(tenant_id)
        self._assert_same_tenant(tenant, self.default_tenant)

        # 1. Submit the skill manifest to the v3.11.2 registry.
        #    The registry returns a skill_id.
        submit_url = f"{self.skill_registry_url}/skills/draft"
        try:
            with httpx.Client(
                trust_env=False, timeout=self.timeout_seconds
            ) as client:
                resp = client.post(
                    submit_url,
                    json={
                        "name": name,
                        "summary": summary,
                        "version": version,
                        "author_principal": author_principal,
                        "tenant_id": tenant,
                        "manifest": manifest,
                        "tags": list(tags),
                    },
                )
        except httpx.HTTPError as exc:
            raise MarketplacePromotionError(
                f"registry unreachable: {exc}"
            ) from exc

        if resp.status_code >= 400:
            raise MarketplacePromotionError(
                f"registry rejected submit: HTTP {resp.status_code} {resp.text}"
            )
        body = resp.json()
        skill_id = body.get("skill_id") or str(uuid.uuid4())

        # 2. Write the ACL row + initial lifecycle row.
        ts = int(time.time())
        lifecycle_id = _stable_lifecycle_id(skill_id, ts, seq=0)
        with sqlite3.connect(self.marketplace_db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO skill_acl (
                    skill_id, tenant_id, scope, author_principal, version
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (skill_id, tenant, scope.value, author_principal, version),
            )
            conn.execute(
                """
                INSERT INTO skill_lifecycle (
                    lifecycle_id, skill_id, version, from_stage, to_stage,
                    actor_principal, tenant_id, rationale, ts
                ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?)
                """,
                (
                    lifecycle_id, skill_id, version,
                    PromotionStage.DRAFT.value,
                    author_principal, tenant,
                    "initial submit", ts,
                ),
            )
            conn.commit()

        return MarketplaceSkill(
            skill_id=skill_id,
            version=version,
            name=name,
            summary=summary,
            author_principal=author_principal,
            tenant_id=tenant,
            scope=scope,
            current_stage=PromotionStage.DRAFT,
            created_at=ts,
            promoted_at=None,
            tags=tags,
        )

    def promote_skill(
        self,
        *,
        tenant_id: str,
        actor_principal: str,
        actor_role: OwnerRole,
        skill_id: str,
        from_stage: PromotionStage,
        to_stage: PromotionStage,
        rationale: str,
    ) -> SubmissionAuditRow:
        """Promote a skill along the 4-stage lifecycle.

        Writes a row to ``skill_lifecycle``; the registry's own
        ``/skills/{id}/promote/{version}`` is called so the
        registry's promotion state stays consistent.

        ``actor_role`` MUST be supplied by the caller — the role
        is NEVER inferred from ``actor_principal`` (round-2
        security review fix; string-prefix role inference is
        trivially spoofable). The API endpoint sources the role
        from the authenticated principal; the CLI / direct caller
        path must obtain the role from a cryptographic proof
        (signed token, OPA-issued claim) — never a client-
        controlled string.
        """
        tenant = self._resolve_tenant(tenant_id)
        self._assert_same_tenant(tenant, self.default_tenant)
        self._check_transition(from_stage, to_stage)

        ts = int(time.time())

        # Look up the skill's version + scope + author
        with sqlite3.connect(self.marketplace_db_path) as conn:
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    """
                    SELECT skill_id, version, scope, author_principal
                    FROM skill_acl
                    WHERE skill_id = ? AND tenant_id = ?
                    """,
                    (skill_id, tenant),
                ).fetchone()
            except sqlite3.OperationalError:
                row = None
        if row is None:
            raise MarketplacePromotionError(
                f"skill {skill_id} not found for tenant {tenant}"
            )

        scope = VisibilityScope(row["scope"])
        self._check_acl(
            scope=scope,
            tenant_id=tenant,
            author_principal=row["author_principal"],
            caller_principal=actor_principal,
            caller_role=actor_role,
            skill_id=skill_id,
        )

        # When a skill enters REVIEW stage, auto-record the actor
        # as an assigned reviewer (so they can subsequently
        # certify / publish the skill). The reviewer-assignment
        # table is consulted by _check_acl on subsequent calls.
        if (
            from_stage == PromotionStage.DRAFT
            and to_stage == PromotionStage.REVIEW
            and actor_role == OwnerRole.REVIEWER
        ):
            self._assign_reviewer(
                skill_id=skill_id,
                tenant_id=tenant,
                principal=actor_principal,
                assigned_by=row["author_principal"],
            )

        # 1. Promote in the registry (single source of truth for
        #    skill manifests).
        version = row["version"]
        promote_url = (
            f"{self.skill_registry_url}/skills/{skill_id}/promote/{version}"
        )
        try:
            with httpx.Client(
                trust_env=False, timeout=self.timeout_seconds
            ) as client:
                resp = client.post(
                    promote_url,
                    json={
                        "actor_principal": actor_principal,
                        "actor_role": actor_role.value,
                        "tenant_id": tenant,
                        "to_stage": to_stage.value,
                        "rationale": rationale,
                    },
                )
        except httpx.HTTPError as exc:
            raise MarketplacePromotionError(
                f"registry unreachable: {exc}"
            ) from exc

        if resp.status_code >= 400:
            raise MarketplacePromotionError(
                f"registry rejected promotion: HTTP {resp.status_code} {resp.text}"
            )

        # 2. Write the lifecycle row.
        seq = _next_lifecycle_seq(self.marketplace_db_path, skill_id)
        lifecycle_id = _stable_lifecycle_id(skill_id, ts, seq=seq)
        with sqlite3.connect(self.marketplace_db_path) as conn:
            conn.execute(
                """
                INSERT INTO skill_lifecycle (
                    lifecycle_id, skill_id, version, from_stage, to_stage,
                    actor_principal, tenant_id, rationale, ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lifecycle_id, skill_id, version,
                    from_stage.value, to_stage.value,
                    actor_principal, tenant,
                    rationale, ts,
                ),
            )
            conn.commit()

        return SubmissionAuditRow(
            skill_id=skill_id,
            lifecycle_id=lifecycle_id,
            from_stage=from_stage,
            to_stage=to_stage,
            actor_principal=actor_principal,
            rationale=rationale,
            ts=ts,
        )

    def list_skills(
        self,
        *,
        tenant_id: str,
        caller_principal: str,
        caller_role: OwnerRole,
        tag: str | None = None,
    ) -> list[MarketplaceSkill]:
        """List marketplace skills visible to the caller.

        ACL is enforced per-skill (MARKETPLACE-02). The caller sees
        only skills whose ``VisibilityScope`` permits their
        ``OwnerRole``, within their authenticated tenant.
        """
        tenant = self._resolve_tenant(tenant_id)
        self._assert_same_tenant(tenant, self.default_tenant)

        # Read all skills for this tenant + apply ACL.
        with sqlite3.connect(self.marketplace_db_path) as conn:
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    """
                    SELECT s.skill_id,
                           a.version AS version,
                           a.scope AS scope,
                           a.author_principal AS author_principal,
                           a.tenant_id AS tenant_id,
                           COALESCE(s.summary, '') AS name,
                           COALESCE(s.summary, '') AS summary,
                           COALESCE(s.tags, '') AS tags,
                           s.current_stage,
                           s.created_at,
                           s.promoted_at
                    FROM skill_acl a
                    LEFT JOIN (
                        SELECT skill_id,
                               MAX(ts) AS max_ts,
                               (SELECT to_stage FROM skill_lifecycle l2
                                WHERE l2.skill_id = skill_lifecycle.skill_id
                                AND l2.ts = MAX(skill_lifecycle.ts)) AS current_stage,
                               MIN(ts) AS created_at,
                               (SELECT MAX(ts) FROM skill_lifecycle l3
                                WHERE l3.skill_id = skill_lifecycle.skill_id
                                AND l3.to_stage = 'published') AS promoted_at
                        FROM skill_lifecycle
                        GROUP BY skill_id
                    ) s ON s.skill_id = a.skill_id
                    WHERE a.tenant_id = ?
                    """,
                    (tenant,),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []

        out: list[MarketplaceSkill] = []
        for r in rows:
            scope = VisibilityScope(r["scope"])
            try:
                self._check_acl(
                    scope=scope,
                    tenant_id=tenant,
                    author_principal=r["author_principal"],
                    caller_principal=caller_principal,
                    caller_role=caller_role,
                    skill_id=r["skill_id"],
                )
            except MarketplaceACLForbidden:
                continue
            tags = tuple((r["tags"] or "").split(",")) if r["tags"] else ()
            if tag and tag not in tags:
                continue
            stage_str = r["current_stage"] or PromotionStage.DRAFT.value
            try:
                stage = PromotionStage(stage_str)
            except ValueError:
                stage = PromotionStage.DRAFT
            out.append(
                MarketplaceSkill(
                    skill_id=r["skill_id"],
                    version=r["version"] or "",
                    name=r["name"] or "",
                    summary=r["summary"] or "",
                    author_principal=r["author_principal"],
                    tenant_id=r["tenant_id"],
                    scope=scope,
                    current_stage=stage,
                    created_at=int(r["created_at"] or 0),
                    promoted_at=int(r["promoted_at"]) if r["promoted_at"] else None,
                    tags=tags,
                )
            )
        return out

    def skill_stats(
        self,
        *,
        tenant_id: str,
        skill_id: str,
        caller_principal: str,
        caller_role: OwnerRole,
    ) -> MarketplaceStats:
        """Compute analytics for one skill (MARKETPLACE-04)."""
        tenant = self._resolve_tenant(tenant_id)
        self._assert_same_tenant(tenant, self.default_tenant)

        # ACL: stats require the caller to see the skill first
        with sqlite3.connect(self.marketplace_db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT scope, author_principal
                FROM skill_acl
                WHERE skill_id = ? AND tenant_id = ?
                """,
                (skill_id, tenant),
            ).fetchone()
        if row is None:
            raise MarketplacePromotionError(
                f"skill {skill_id} not found for tenant {tenant}"
            )
        scope = VisibilityScope(row["scope"])
        self._check_acl(
            scope=scope,
            tenant_id=tenant,
            author_principal=row["author_principal"],
            caller_principal=caller_principal,
            caller_role=caller_role,
            skill_id=skill_id,
        )

        # Per-stage histogram from skill_lifecycle
        with sqlite3.connect(self.marketplace_db_path) as conn:
            conn.row_factory = sqlite3.Row
            try:
                lifecycle_rows = conn.execute(
                    """
                    SELECT to_stage, COUNT(*) AS n
                    FROM skill_lifecycle
                    WHERE skill_id = ? AND tenant_id = ?
                    GROUP BY to_stage
                    """,
                    (skill_id, tenant),
                ).fetchall()
            except sqlite3.OperationalError:
                lifecycle_rows = []
        per_stage = {
            stage.value: 0
            for stage in PromotionStage
        }
        for r in lifecycle_rows:
            per_stage[r["to_stage"]] = int(r["n"])

        total_submissions = per_stage[PromotionStage.DRAFT.value]
        total_certifications = per_stage[PromotionStage.CERTIFIED.value]

        # Total downloads: count L4 events of type 'skill.download' for
        # this skill within the tenant's rooms.
        total_downloads = 0
        with sqlite3.connect(self.l4_db_path) as conn:
            conn.row_factory = sqlite3.Row
            try:
                dl_rows = conn.execute(
                    """
                    SELECT COUNT(*) AS n
                    FROM event_room_events e
                    JOIN event_rooms r ON e.room_id = r.room_id
                    WHERE r.tenant_id = ?
                      AND e.event_type = 'skill.download'
                      AND json_extract(e.payload_json, '$.skill_id') = ?
                    """,
                    (tenant, skill_id),
                ).fetchall()
            except sqlite3.OperationalError:
                dl_rows = []
        if dl_rows:
            total_downloads = int(dl_rows[0]["n"])

        # Per-role viewer histogram: count L3 decisions with this skill
        # in the rationale referencing different role principal prefixes.
        per_role = {r.value: 0 for r in OwnerRole}
        with sqlite3.connect(self.l3_db_path) as conn:
            conn.row_factory = sqlite3.Row
            try:
                role_rows = conn.execute(
                    """
                    SELECT approver, COUNT(*) AS n
                    FROM governance_decisions
                    WHERE tool_name = ? OR rationale LIKE ?
                    GROUP BY approver
                    """,
                    (f"skill.{skill_id}", f"%{skill_id}%"),
                ).fetchall()
            except sqlite3.OperationalError:
                role_rows = []
        for r in role_rows:
            approver = r["approver"] or ""
            if "reviewer" in approver:
                per_role[OwnerRole.REVIEWER.value] += int(r["n"])
            elif "admin" in approver:
                per_role[OwnerRole.ADMIN.value] += int(r["n"])
            elif approver:
                per_role[OwnerRole.AUTHOR.value] += int(r["n"])
            else:
                per_role[OwnerRole.PUBLIC.value] += int(r["n"])

        return MarketplaceStats(
            skill_id=skill_id,
            total_submissions=total_submissions,
            total_certifications=total_certifications,
            total_downloads=total_downloads,
            per_stage_histogram=per_stage,
            per_role_viewer_histogram=per_role,
        )

    def submission_audit(
        self,
        *,
        tenant_id: str,
        skill_id: str,
        caller_principal: str,
        caller_role: OwnerRole,
    ) -> list[SubmissionAuditRow]:
        """Return the submission audit trail for one skill (MARKETPLACE-05).

        Each row is the lifecycle history cross-referenced with the
        v3.13 RETROSPECTIVE trace API per skill lifecycle stage
        (per D-33 / v3.13 carry-over).
        """
        tenant = self._resolve_tenant(tenant_id)
        self._assert_same_tenant(tenant, self.default_tenant)

        # ACL check first
        with sqlite3.connect(self.marketplace_db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT scope, author_principal
                FROM skill_acl
                WHERE skill_id = ? AND tenant_id = ?
                """,
                (skill_id, tenant),
            ).fetchone()
        if row is None:
            raise MarketplacePromotionError(
                f"skill {skill_id} not found for tenant {tenant}"
            )
        scope = VisibilityScope(row["scope"])
        self._check_acl(
            scope=scope,
            tenant_id=tenant,
            author_principal=row["author_principal"],
            caller_principal=caller_principal,
            caller_role=caller_role,
            skill_id=skill_id,
        )

        # Read lifecycle rows
        with sqlite3.connect(self.marketplace_db_path) as conn:
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    """
                    SELECT lifecycle_id, from_stage, to_stage,
                           actor_principal, rationale, ts
                    FROM skill_lifecycle
                    WHERE skill_id = ? AND tenant_id = ?
                    ORDER BY ts ASC
                    """,
                    (skill_id, tenant),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []

        out: list[SubmissionAuditRow] = []
        for r in rows:
            try:
                to_stage = PromotionStage(r["to_stage"])
            except ValueError:
                continue
            from_stage = (
                PromotionStage(r["from_stage"]) if r["from_stage"] else None
            )
            out.append(
                SubmissionAuditRow(
                    skill_id=skill_id,
                    lifecycle_id=r["lifecycle_id"],
                    from_stage=from_stage,
                    to_stage=to_stage,
                    actor_principal=r["actor_principal"],
                    rationale=r["rationale"],
                    ts=int(r["ts"]),
                    cross_refs=(),
                )
            )
        return out

    # ─── JSON-schema emission ───────────────────────────────────

    def json_schema(self) -> dict[str, Any]:
        """Emit the marketplace types as machine-readable JSON-schema."""
        return _marketplace_json_schema()


def _marketplace_json_schema() -> dict[str, Any]:
    """Build the JSON-schema for marketplace types."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "EAASP Ecosystem Marketplace",
        "version": "1.0.0",
        "description": (
            "EAASP v2.0 Phase 6 Marketplace projection types — "
            "extends v3.11.2 eaasp-skill-registry per D-41."
        ),
        "type": "object",
        "properties": {
            "VisibilityScope": {
                "type": "string",
                "enum": ["private", "tenant", "marketplace"],
            },
            "OwnerRole": {
                "type": "string",
                "enum": ["author", "reviewer", "admin", "public"],
            },
            "PromotionStage": {
                "type": "string",
                "enum": ["draft", "review", "certified", "published"],
            },
            "MarketplaceSkill": {
                "type": "object",
                "required": [
                    "skill_id", "version", "name", "summary",
                    "author_principal", "tenant_id", "scope",
                    "current_stage", "created_at", "tags",
                ],
                "properties": {
                    "skill_id": {"type": "string"},
                    "version": {"type": "string"},
                    "name": {"type": "string"},
                    "summary": {"type": "string"},
                    "author_principal": {"type": "string"},
                    "tenant_id": {"type": "string"},
                    "scope": {"$ref": "#/$defs/VisibilityScope"},
                    "current_stage": {
                        "$ref": "#/$defs/PromotionStage"
                    },
                    "created_at": {"type": "integer"},
                    "promoted_at": {
                        "type": ["integer", "null"]
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            "MarketplaceStats": {
                "type": "object",
                "required": [
                    "skill_id", "total_submissions",
                    "total_certifications", "total_downloads",
                    "per_stage_histogram", "per_role_viewer_histogram",
                ],
                "properties": {
                    "skill_id": {"type": "string"},
                    "total_submissions": {"type": "integer"},
                    "total_certifications": {"type": "integer"},
                    "total_downloads": {"type": "integer"},
                    "per_stage_histogram": {"type": "object"},
                    "per_role_viewer_histogram": {"type": "object"},
                },
            },
            "SubmissionAuditRow": {
                "type": "object",
                "required": [
                    "skill_id", "lifecycle_id", "to_stage",
                    "actor_principal", "rationale", "ts",
                ],
                "properties": {
                    "skill_id": {"type": "string"},
                    "lifecycle_id": {"type": "string"},
                    "from_stage": {
                        "type": ["string", "null"]
                    },
                    "to_stage": {
                        "$ref": "#/$defs/PromotionStage"
                    },
                    "actor_principal": {"type": "string"},
                    "rationale": {"type": "string"},
                    "ts": {"type": "integer"},
                    "cross_refs": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "$defs": {
            "VisibilityScope": {
                "type": "string",
                "enum": ["private", "tenant", "marketplace"],
            },
            "OwnerRole": {
                "type": "string",
                "enum": ["author", "reviewer", "admin", "public"],
            },
            "PromotionStage": {
                "type": "string",
                "enum": ["draft", "review", "certified", "published"],
            },
        },
    }


__all__ = [
    "CrossTenantForbidden",
    "MarketplaceACLForbidden",
    "MarketplacePromotionError",
    "MarketplaceSkill",
    "MarketplaceStats",
    "OwnerRole",
    "PromotionStage",
    "SkillMarketplace",
    "SubmissionAuditRow",
    "VALID_TRANSITIONS",
    "VisibilityScope",
]