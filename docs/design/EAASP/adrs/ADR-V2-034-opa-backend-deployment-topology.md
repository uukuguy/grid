---
adr_id: ADR-V2-034
title: EAASP L3 production OPA/Rego sidecar deployment topology
status: Accepted
date: 2026-07-26
phase: 3
deciders: Jiangwen Su + Claude
related:
  - ADR-V2-005 (Tool Sandbox Container — closed by ADR-V2-005 itself; not OPA-related)
  - ADR-V2-028 (Strict-by-default Config Validation)
  - ADR-V2-023 P1 (Shared-core rule)
  - EVOLUTION_PATH §三 Phase 3
  - PHASE_3_DESIGN.md
  - v2.0 spec §2.4 (master boundary) + §15.9 (deny-always-wins)
  - V310-OPA-01 (DEFERRED_LEDGER, 2026-05-24 baseline)
---

# ADR-V2-034 — EAASP L3 Production OPA/Rego Sidecar Deployment Topology

## Context

v3.10 platform-skeleton alignment audit recorded `V310-OPA-01` (L3 production
OPA/Rego backend) as a long-term Deferred item. The current L3 governance
component (`tools/eaasp-l3-governance/`) ships only an in-process
`PolicyEngine.evaluate_gate()` decision matrix with risk classification,
allow/approval/deny outcomes, and an append-only request/final decision
ledger. The decision backend is not yet a production-grade OPA service.

Two candidate deployment topologies were on the table:

- **sidecar OPA** — each L3 governance process ships with a local OPA
  process on `127.0.0.1:18181`; bundles are in-repo (`policies/*.rego`) plus
  atomic user bundles; failure mode is fail-closed (deny + audit
  `infra_unavailable=true`).
- **shared cluster OPA** — a separately deployed OPA cluster serves
  multiple L3 governance instances; bundles are distributed through a
  central bundle service; failure mode is the same fail-closed contract
  but adds network/CAP-dependency for every decision call.

A v3.11.0 prior attempt (`402b1ed3` from a v3.9-baseline worktree) was
aborted: the worktree was rooted at `1b42a14a` rather than the v3.10
SHIPPED `179a15a1`, which would have made the eventual fast-forward
delete the entire v3.10 platform-skeleton alignment work. The decision
recorded here re-establishes v3.11.0 on a v3.10 baseline.

## Decision

EAASP L3 governance ships with **sidecar OPA**, one process per L3
governance instance, on `127.0.0.1:18181`. Bundles are in-repo
`tools/eaasp-l3-governance/policies/*.rego` plus atomic user bundles
delivered through the existing skill/policy deploy pipeline.

Operational requirements:

1. **Topology** — Sidecar per L3 process. No shared cluster OPA in this
   milestone. Rationale: lower deployment complexity, no cluster-level
   bundle distribution, no shared cluster capacity planning, and
   horizontal scaling is per-L3 rather than per-OPA-cluster.
2. **Bundle source** — In-repo Rego templates under
   `tools/eaasp-l3-governance/policies/*.rego` plus atomic user bundles
   (per-skill / per-policy) committed alongside the EAASP code.
3. **Bundle delivery** — Reuse the existing skill / policy deploy
   pipeline (L3 `PUT /v1/policies/managed-hooks` and the skill lifecycle
   in `eaasp-skill-registry`). No new deployment surface.
4. **Failure mode (fail-closed)** — If the OPA sidecar is unreachable,
   times out, returns a transport error, or returns an unparseable
   result, L3 governance MUST:
   - return `deny` for the affected decision;
   - emit an audit row with `infra_unavailable=true` and the failure
     reason (timeout, connection-refused, parse-error, etc.);
   - keep the request ledger intact (append-only; no reordering).
5. **Runtime acquisition** — `make opa-install` downloads the official
   OPA release binary, verifies SHA256 against the official
   `sha256sums.txt`, and installs to `third_party/opac/opa`. No Docker,
   no external service account. The directory `third_party/` is
   gitignored; the binary is regenerated on demand.
6. **Strict-by-default configuration** — All OPA env vars (`L3_OPA_URL`,
   `L3_OPA_BUNDLE_DIR`, etc.) are explicit. No fallback, no default
   discovery. Per ADR-V2-028, startup fails closed when any required OPA
   env var is missing.
7. **Shared-core rule (ADR-V2-023 P1)** — The sidecar is a deployment
   topology change in `tools/eaasp-l3-governance/` and the OPA installer
   script. It does NOT touch any shared crate (`grid-engine`,
   `grid-runtime`, `grid-types`, `grid-sandbox`, `grid-hook-bridge`).
   Engine-side L1 runtimes remain L3-OPA-agnostic.

## Consequences

Positive:

- L3 decision semantics are now produced by a real, auditable Rego
  policy engine, not by an in-process Rust-style matrix. The v2.0 §2.4
  master-boundary principle (platform provides governance; runtime
  provides execution) is reinforced.
- Bundles are reviewable as code. Rego policy changes ride through the
  same PR review process as EAASP source.
- Fail-closed default is consistent with `deny-always-wins` and with
  the risk classification already enforced by the in-process matrix.
- Sidecar acquisition is reproducible (`make opa-install`); no runtime
  surprises from a cluster OPA version drift.

Negative:

- L3 governance startup is now coupled to a successful OPA install.
  CI must run `make opa-install` (or `make opa-install` + a health
  check) before integration tests that exercise the governance gate.
- Policy hot-reload across an OPA sidecar fleet is per-instance. A
  shared cluster would give one-shot fleet-wide bundle update. This
  trade-off is acceptable in the current scope; the L3 audit row
  timestamps provide a deployment-history view.
- The `third_party/opac/opa` binary is not versioned in the repository.
  The first OPA install requires network access; CI cache is
  recommended for reproducibility.

Out of scope (Deferred to v3.11.1+ or later):

- `V310-APPROVAL-01` — 5-stage approval chain state machine
  (Plan → Check → Draft → Approve → Execute) and the corresponding
  governance.* SSE event contracts. Sidecar OPA makes it possible to
  add the state machine cleanly; that work is a separate ADR/phase.
- `V310-A2A-01` — A2A Router, Event Room, multi-session coordination.
- `V310-COWORK-01` — L5 Cowork UI.
- `V310-ECOSYSTEM-01` — Marketplace, multi-tenant, SDK.

## Verification

- `make opa-install` downloads OPA, verifies SHA256, installs to
  `third_party/opac/opa`, and prints `opa version`.
- `make opa-clean` removes the binary.
- `bash -n scripts/eaasp-install-opa.sh` passes.
- `make -n opa-install opa-clean` prints the expected targets.
- `cargo check -p eaasp-l3-governance` continues to pass without OPA
  installed (in-process fallback; v3.11.1+ will add OPA-required CI).
- `make v3.10-spec-audit` continues to pass (no shared-crate change).

## Implementation status

- v3.11.0 (this ADR + `make opa-install` + `.gitignore` + Makefile
  targets) — completed and shipped at `1bee9eb0` (worktree-anchored
  attempt) and re-established directly on `main` after a clean
  fast-forward. ADR-V2-034 is now Accepted.
- v3.11.1 — `L3 OPA backend` adapter
  (`tools/eaasp-l3-governance/src/eaasp_l3_governance/opa_backend.py`)
  with in-process fallback, Rego policy templates, fail-closed test.
  **SHIPPED 2026-07-26 on top of v3.11.0 (`84ca0a11`).** Adapter covers:
  - `OPABackend.evaluate()` calls `POST /v1/data/governance/decision` with
    `{"input": request}` envelope per OPA REST v1.
  - 5 fail-closed modes covered (connection-refused / timeout / non-2xx /
    parse-error / missing-field). Each emit a synthesized `deny` with
    `infra_unavailable=True` + a stable cause identifier in the
    rationale.
  - `PolicyEngine.evaluate_with_opa()` routes through the adapter when
    `opa_enabled=True`, maps OPA 3-state decision (`allow` /
    `approval` / `deny`) to the existing 4-state audit shape (`allow` /
    `gate_request` / `deny`), preserving the OPA `reason` in the
    rationale so the audit ledger can pivot on it.
  - In-repo Rego policy template at
    `tools/eaasp-l3-governance/policies/governance.rego` implements
    deny-always-wins (spec §15.9), risk classification (spec §6.1),
    and the 3-state decision contract (spec §6.9, §6.10). Sample data
    at `policies/data.json`.
  - 57 tests pass (30 OPABackend + 11 PolicyEngine OPA + 12 Rego
    contract + 4 in-process integration). The real-OPA sidecar test
    (`test_real_opa_sidecar_returns_truth_table`) is gated on the OPA
    binary being installed (`make opa-install`) and verifies every
    truth-table row end-to-end.
  - Verified v3.9 RBAC audit (`134 routes`) and v3.10 spec-audit
    (4 files / 37 rows) still PASS — no shared-crate changes
    (ADR-V2-023 P1 preserved).
- v3.11.2 — 5-stage approval state machine + governance.* SSE events
  + append-only ledger extension.
- v3.11.3 — `make dev-eaasp` + `threshold-calibration` live walkthrough
  with SSE event stream + OPA traffic + audit-chain evidence.
  **SHIPPED 2026-07-27 (LIVE-01..04 ✅ CLOSED).** See
  `docs/status/PRODUCTION_USABILITY_2026-07-27.md` for the dated,
  auditable production evidence (timestamp, commands, key stdout, SSE
  event capture, OPA HTTP traffic snippets, 5-stage audit evidence,
  human-in-the-loop pause explanation). Key results:
  - OPA sidecar v0.68.0 darwin arm64 running on `127.0.0.1:18181`,
    bundle mounted at `tools/eaasp-l3-governance/policies`. Bundle
    serves `POST /v1/data/governance/decision` returning the 3-state
    decision (`allow` / `approval` / `deny`) with `obligations` and
    `reason`.
  - 7 EAASP services up (skill-registry, L2, L3 with OPA enabled,
    mock-scada, MCP orchestrator, grid-runtime, L4) via the custom
    launcher `.grid/dev-eaasp-live.sh` (skips claude / goose / nanobot).
    Real `.env` keys sourced into L3 (DashScope `qwen-turbo` OpenAI-compat).
  - Harness `.grid/live-walkthrough.py` drives the 5-stage state machine
    end-to-end through a real L4 `SessionEventStream.append(...)` bridge
    into the L4 SSE event stream. **5 SSE events captured live** in
    canonical order: `governance.approval.plan` (seq=26, `allow`) →
    `governance.approval.check` (seq=27, `allow`) →
    `governance.approval.draft` (seq=28, `allow`) →
    `governance.approval.approve` (seq=29, `approve`) →
    `governance.approval.execute` (seq=30, `allow`). All 5 share one
    `request_id=gd_approval_01d05124f5d54060`.
  - **OPA HTTP traffic captured**: 5 POST `/v1/data/governance/decision`
    requests returning 200 OK with `{"decision":"approval","obligations":
    ["notify:admin"],"reason":"write_external in enforce mode requires
    human approval (spec §6.10)"}` for the `scada_set_setpoint` tool under
    `mode=enforce`. The 3-state OPA decision contract verified end-to-end.
  - **L3 audit ledger verified**: 18 rows in `governance_decisions` across
    3 chain runs (5 stages × 3 + 3 `gate_request` initial roundtrips).
  - **Human-in-the-loop pause**: policy-driven, not LLM-driven. OPA
    `decision=approval` for `mode=enforce && risk_level=write_external`
    maps to `awaits_human` in the state machine; harness emits
    `governance.approval.approve` and halts until resume.
  - **Double-gate re-run, PASS**: `make rbac-audit` → 134 routes PASS.
    `make v3.10-spec-audit` → 4 files / 37 rows PASS.
  - **ADR-V2-023 P1 preserved**: zero edits to `grid-engine`,
    `grid-runtime`, `grid-types`, `grid-sandbox`, `grid-hook-bridge`.
    The harness + launcher are local-only scripts under `.grid/`.
  - **Known finding (filed, not auto-fixed)**: `audit.py`'s CHECK
    constraint on `governance_decisions.decision` lists only
    `{allow, approve, deny, gate_request}` — the L3 state machine's
    `DECISION_AWAIT_HUMAN` sentinel is not in that allowlist. This is
    an architectural migration (Rule 4 scope); it does NOT block
    03.11.3 because the L4 SSE path emits the canonical
    `governance.approval.approve` event cleanly. Filed as a deferred
    item for v3.12 review.

<!-- v3.11.2 implementation status -->
- v3.11.2 — 5-stage approval state machine SHIPPED 2026-07-27
  (L3 + L4, V310-APPROVAL-01 ✅ CLOSED).
  - L3: `tools/eaasp-l3-governance/src/eaasp_l3_governance/approval_state_machine.py`
    implements Plan → Check → Draft → Approve → Execute with deny-always-wins
    short-circuit, Approve-stage `awaits_human` pause, and `resume_with_human
    _decision(allow|deny)`. Each stage persists one row in
    `governance_decisions` (new nullable `stage` column, default NULL for
    backwards compatibility with v3.11.0 / v3.11.1 rows).
  - L4: `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/event_stream.py`
    adds 5 `governance.approval.<stage>` event helpers (one per stage)
    sharing the same canonical payload shape (`stage`, `decision_id`,
    `request_id`, `hook_id`, `decision`, `reason`, `caller_principal`,
    `evidence_refs`, `ts`). Coexists with pre-existing `governance.request`
    / `governance.decision` events; SSE consumers see all three families on
    the same session stream.
  - Tests: 21 new tests (17 L3 state-machine + 10 L4 SSE — 17+10 = 27
    tests total in this phase; 0 regressions across 157 L3 + 21 L4
    event-stream tests).
  - v3.9 RBAC catalog unchanged (134 routes); v3.10 spec-audit still
    PASS (4 files / 37 rows). Shared-core preserved (ADR-V2-023 P1):
    no changes under `crates/grid-engine`, `grid-runtime`, `grid-types`,
    `grid-sandbox`, `grid-hook-bridge`.

<!-- v3.12.0 implementation status -->
- v3.12.0 — 03.12.0 audit.py CHECK constraint patch + DECISION_AWAIT_HUMAN
  SHIPPED 2026-07-27 (`V311-AUDIT-01` ✅ CLOSED; gates 03.12.1 / 03.12.2
  / 03.12.3 implementation work per D-23):
  - L3 — `tools/eaasp-l3-governance/src/eaasp_l3_governance/audit.py`
    exposes `DECISION_ALLOWLIST` constant widened to
    `{allow, approve, deny, gate_request, await_human}`. The in-process
    enum validation in `record_governance_decision` mirrors the DB
    CHECK allowlist so callers see a clean `ValueError` (not an
    `aiosqlite.IntegrityError`) on every code path. Before v3.12.0
    the 5-stage state machine's `DECISION_AWAIT_HUMAN` sentinel was
    silently swallowed at the paused Approve stage — the paused
    audit evidence never reached the ledger.
  - L3 — `tools/eaasp-l3-governance/src/eaasp_l3_governance/db.py`
    adds `migrate_decision_await_human(path)` idempotent migration.
    Probes the current CHECK clause via `sqlite_master`; if it
    already contains `await_human` the call is a NO-OP. Otherwise,
    renames the legacy table, recreates it with the widened
    CHECK (5-value allowlist), copies every row across (projecting
    only the columns the legacy row carries so v3.11.0 / v3.11.1
    rows land with `stage = NULL`), and drops the legacy table. All
    operations wrapped in `BEGIN IMMEDIATE` per audit §C1.
    `init_db` invokes the migration so legacy DBs upgrade cleanly.
    Indexes on `governance_decisions` are created in
    `_create_governance_decisions_indexes` (after the v3.11.2
    conditional `stage` column add) so pre-v3.11.2 DBs without
    the `stage` column don't fail with `no such column: stage`.
  - L3 — `tools/eaasp-l3-governance/src/eaasp_l3_governance/approval_state_machine.py`
    routes the paused Approve stage's `DECISION_AWAIT_HUMAN` sentinel
    through `_append_audit_row` with a dedicated `approve_pause`
    stage suffix (distinct `decision_id` PK). Append-only invariant
    preserved; in-memory `records` list mirrors the ledger.
  - Tests — `tools/eaasp-l3-governance/tests/test_audit_decision_await_human.py`
    + `test_audit_await_human_migration.py` (14 new tests). Covers
    the `DECISION_ALLOWLIST` widening, idempotent migration on
    hand-constructed v3.11.0 / v3.11.2 legacy schemas, row
    preservation through the migration, and the 5-stage state
    machine writing the `await_human` audit row at the paused
    Approve stage (no silent swallowing) plus the resume-time
    allow/deny rows.
  - 132 → 143 targeted tests PASS (+1 skipped, OPA-backend tests
    excluded — require OPA binary).
  - v3.9 RBAC catalog unchanged (134 routes); v3.10 spec-audit
    still PASS (4 files / 37 rows); OPA sidecar topology unchanged.
    Shared-core preserved (ADR-V2-023 P1): no changes under
    `crates/grid-engine`, `grid-runtime`, `grid-types`,
    `grid-sandbox`, `grid-hook-bridge`.
- v3.12.2 — A2A Router + ReviewSet aggregation + conflict detection
  + 5 A2A SSE event types (a2a.request.sent /
  a2a.request.acknowledged / a2a.review.submitted /
  a2a.review.closed / a2a.conflict.detected). The 5-stage approval
  chain (Plan → Check → Draft → Approve → Execute) remains the
  canonical gating surface for the A2A dispatch path. The
  `ReviewSet` aggregation engine's output (`allow` / `deny` /
  `escalate`) feeds into
  `ApprovalStateMachine.resume_with_human_decision(...)` via the
  API layer (deferred to 03.12.3 live walkthrough per D-25).
  ADR-V2-035 (conflict-detection algorithm) Accepted. OPA sidecar
  topology unchanged. v3.9 RBAC audit + v3.10 spec-audit still
  PASS. ADR-V2-023 P1 shared-core rule preserved (no shared-crate
  change). **SHIPPED 2026-07-28 on top of v3.12.1 (`a248d73a`).**
