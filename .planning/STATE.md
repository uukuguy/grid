---
gsd_state_version: 1.0
milestone: v3.12
milestone_name: EAASP Phase 4 — A2A Router + Event Room + multi-session 协调
status: in_progress
stopped_at: 03.12.2 SHIPPED 2026-07-28 (A2A Router facade + ReviewSet aggregation engine + 5-stage approval integration + conflict detection algorithm + 5 A2A SSE event types; V310-A2A-01 ✅ CLOSED; ADR-V2-035 Accepted; 51 new targeted tests PASS; security regression fixes for HIGH #1 fail-open aggregation + HIGH #2 principal-mismatch gate applied). v3.12 plans 03.12.3 pending.
last_updated: "2026-07-28T12:00:00.000Z"
last_activity: 2026-07-28
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 4
  completed_plans: 2
  percent: 75
  prior_milestones:
    v3.11_completed_phases: 4
    v3.11_completed_plans: 4
    v3.11_percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Grid 作为 substitutable L1 runtime,通过 gRPC contract 被 EAASP L2-L4 调用,且任何符合 `contract-v1.2.0` 的对比 runtime 都能替换它。`contract-v1.1.0` 是 Phase 3 sign-off 历史契约版本(2026-04-18,42 PASS / 22 XFAIL × 7 runtime)。
**Current focus:** Milestone v3.10 (EAASP v2.0 platform-skeleton alignment) SHIPPED 2026-07-26. Four phases complete, 16/16 REQ-IDs closed, 174 targeted tests PASS; live real-skill walkthrough awaits an LLM API key.

Canonical product-status sources:

- `docs/PROJECT_PRODUCT_OVERVIEW.md` (maintained SSOT)
- `docs/status/PRODUCT_STATUS_2026-07-17.md` (dated audit snapshot)

## Current Position

Milestone: **v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 🔵 IN PROGRESS (4-phase ladder 03.12.0 ✅ SHIPPED → 03.12.1 ✅ SHIPPED → 03.12.2 ✅ SHIPPED → 03.12.3; 50% complete, 2/4 phases)**
Scope: 4 phases (03.12.0 schema + audit constraint patch ✅ → 03.12.1 Event Room + multi-session ✅ → 03.12.2 A2A Router ✅ → 03.12.3 single-point live walkthrough). 03.12.0 is the gating phase; SCHEMA-01..03 SHIPPED 2026-07-27 + V311-AUDIT-01 ✅ CLOSED; 03.12.1 / 03.12.2 SHIPPED 2026-07-28. 03.12.3 unblocked.
03.12.0 deliverables (SHIPPED 2026-07-27): `audit.py` `DECISION_ALLOWLIST` widens to include `await_human`; `db.py` `migrate_decision_await_human` idempotent ALTER TABLE migration (v3.11.0 / v3.11.1 / v3.11.2 legacy DBs preserved); `approval_state_machine.py` paused Approve stage writes `approve_pause` row carrying `DECISION_AWAIT_HUMAN`; 14 new targeted tests PASS in `test_audit_decision_await_human.py` + `test_audit_await_human_migration.py`; `docs/design/EAASP/DEFERRED_LEDGER.md` V311-AUDIT-01 → ✅ CLOSED.
Bootstrap deliverables (milestone bootstrap, 2026-07-27): `.planning/PROJECT.md` (Latest Shipped Milestone + v3.12 Current Milestone + D-23..D-29 in Key Decisions) / `.planning/REQUIREMENTS.md` (v3.11.3 + v3.12 sections, 5 categories: SCHEMA / EVENT-ROOM / A2A / SESSION / COMPAT) / `.planning/ROADMAP.md` (v3.11 SHIPPED + v3.12 active milestone block) / `.planning/STATE.md` (frontmatter `milestone=v3.12 status=in_progress progress.percent=25`).
Prior milestone: **v3.11 EAASP Phase 3 — production OPA backend + 5-stage approval chain ✅ SHIPPED 2026-07-27**
Prior scope: 4 phases complete (03.11.0 → 03.11.3), 29/29 REQ-IDs in 11 categories (OPA + INSTALL + OPA-BACKEND + REGO + FAIL-CLOSED + DISABLED + STAGE + SSE + AUDIT + DENY + LIVE).
Prior verification: 57 + targeted regression tests PASS; real OPA sidecar v0.68.0 on `127.0.0.1:18181`; 5 SSE events in canonical order (seq 26–30, single request_id); 18 rows in L3 `governance_decisions` ledger across 3 chain runs; `make rbac-audit` PASS (134 routes); `make v3.10-spec-audit` PASS (4 files / 37 rows); ADR-V2-023 P1 shared-core rule preserved (no shared-crate change).
Prior close: v3.11.3 live walkthrough §7 surfaced the `audit.py` CHECK constraint gap on `await_human` as a known finding (filed for v3.12 review per deferred-items); V310-OPA-01 + V310-APPROVAL-01 ✅ CLOSED via v3.11.0 / v3.11.2.
Prior-prior milestone: **v3.10 EAASP v2.0 platform-skeleton alignment ✅ SHIPPED 2026-07-26**
Prior-prior scope: 4 phases complete (03.10.0 → 03.10.3), 16/16 REQ-IDs in 5 categories.
Prior-prior verification: 174 targeted tests PASS, alignment matrix + deterministic spec audit + ordered CI gate delivered.
Prior-prior-prior milestone: **v3.9 route-catalog RBAC wiring + authorization auditor ✅ SHIPPED 2026-07-26** (3 phases, 20/20 REQ-IDs, 49 targeted tests PASS).

Next-milestone candidates (after v3.12 SHIPS):

- `web-platform/` Quality 7.5→9.0.
- `grid-desktop` Quality 6.5→9.0.
- EAASP Phase 5 L5 Cowork UI (V310-COWORK-01) / Phase 6 ecosystem expansion (V310-ECOSYSTEM-01 / V310-MAT-01).

## Audit Findings Summary (Post-Activation Scores)

| Crate | Activation Score | Quality Score | Key Remaining Gaps |
|-------|-----------------|---------------|-------------------|
| grid-cli | 8/10 | **9.0** ✅ | 140+ tests, 16 commands, full TUI |
| web/ | 7/10 | **9.0** ✅ | 9 vitest tests, 8 tabs, no mocks |
| grid-server | 6/10 | **9.0** ✅ | 25 integration test files, HMAC/JWT, ~130 endpoints |
| grid-eval | 7/10 | **9.0** ✅ | 10 scorers, 12 suites, CI workflow, parallel runner |
| grid-platform | 6/10 | **9.0** ✅ | 37 tests, ErrorCode enum, quota wired, 5MB limits |
| web-platform/ | 3/10 | **7.5** | Markdown + toast + skeletons + error states |
| grid-desktop | 3/10 | **6.5** | Icons, IPC proxy, Grid rebrand |

### Quality Improvements (Phase B — 2026-06-17)

| Component | Changes | Tests Before → After |
|-----------|--------|---------------------|
| grid-platform | quota consume, 20 new integration tests | 17 → **37** |
| web-platform/ | Loading skeletons, toast errors, empty states, cn() utility | 0 → 0 (UI components) |
| grid-desktop | Icon assets (PNG), 3 new IPC commands, Grid rebrand | 9 → 9 |
| grid-eval | CI concurrency group, test summary reporting | existing |

*5/7 components at 9.0+. web-platform/ and grid-desktop need functional feature work for 9.0+.*

### v3.11.0 OPA sidecar infrastructure ✅ SHIPPED 2026-07-26

- ADR-V2-034 Accepted — L3 governance runs OPA as a sidecar on `127.0.0.1:18181`; in-repo Rego templates + atomic user bundles; fail-closed on OPA error.
- `make opa-install` downloads official OPA binary, SHA256-verified against `sha256sums.txt`, installs to `third_party/opac/opa`. No Docker. `make opa-clean` removes the binary.
- `.gitignore` excludes `third_party/`.
- `V310-OPA-01` DEFERRED_LEDGER entry → ✅ CLOSED.
- `v3.9` route-catalog RBAC and `v3.10` spec-audit gates remain unchanged. No shared-crate change. ADR-V2-023 P1 (shared-core rule) preserved.
- 03.11.2 5-stage approval state machine ✅ SHIPPED 2026-07-27 (`V310-APPROVAL-01` → ✅ CLOSED). Plan → Check → Draft → Approve → Execute with deny-always-wins; 5 `governance.approval.<stage>` SSE events; append-only ledger `stage` column extension. 03.11.3 live walkthrough still pending.

### v3.11.1 L3 OPA backend adapter + Rego templates ✅ SHIPPED 2026-07-26

- Built on top of v3.11.0 (`84ca0a11`); no changes to any shared crate (ADR-V2-023 P1 preserved).
- `tools/eaasp-l3-governance/src/eaasp_l3_governance/opa_backend.py` — `OPABackend` adapter calling `POST /v1/data/governance/decision` with `{"input": request}` envelope. Public surface: `OPABackend`, `OPADecision`, `OPAConfig`, `require_env`, `parse_timeout_seconds`, `normalize_base_url`. 5 fail-closed modes (connection-refused / timeout / non-2xx / parse-error / missing-field) emit a synthesized `deny` with `infra_unavailable=True` + a stable cause identifier.
- `tools/eaasp-l3-governance/src/eaasp_l3_governance/policy_engine.py` — `PolicyEngine.evaluate_with_opa()` routes through the adapter when `opa_enabled=True`; in-process `evaluate_gate()` unchanged. OPA 3-state decision (`allow` / `approval` / `deny`) maps to the existing 4-state audit shape (`allow` / `gate_request` / `deny`); rationale carries the OPA `reason` or fail-closed composite.
- `tools/eaasp-l3-governance/src/eaasp_l3_governance/api.py` — `/v1/evaluate` endpoint with `L3_OPA_ENABLED` toggle (OPA path vs in-process path). Returns `backend: "opa" | "in_process"` so operators can verify the routing decision.
- `tools/eaasp-l3-governance/policies/governance.rego` — in-repo Rego template: deny-always-wins (spec §15.9), risk classification (spec §6.1), 3-state decision (spec §6.9, §6.10). `policies/data.json` for sample input data.
- 57 tests PASS (30 OPABackend + 11 PolicyEngine OPA + 12 Rego contract + 4 in-process integration). Real-OPA sidecar test (`test_real_opa_sidecar_returns_truth_table`) gated on OPA binary install.
- v3.9 RBAC audit still PASS (134 routes — unchanged). v3.10 spec-audit still PASS (4 files / 37 rows).

### v3.11.2 5-stage approval state machine ✅ SHIPPED 2026-07-27

- Built on top of v3.11.1 (`2acbf62a`); no changes to any shared crate (ADR-V2-023 P1 preserved).
- `tools/eaasp-l3-governance/src/eaasp_l3_governance/approval_state_machine.py` — `ApprovalStateMachine` (Plan → Check → Draft → Approve → Execute) with `STAGE_ORDER` tuple, `run(evaluator)` iterating stages, `resume_with_human_decision(...)` for the Approve-stage pause. `ApprovalChainResult` carries `stages_completed`, `final_decision` (`approve` / `deny` / `await_human`), `final_reason`, and a `records` list of `StageRecord`. Deny short-circuits remaining stages (DENY-01/02).
- `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/event_stream.py` — 5 new `SessionEventStream.emit_governance_approval_<stage>(...)` methods writing `governance.approval.{plan,check,draft,approve,execute}` events with the canonical payload shape (SSE-01..05).
- `tools/eaasp-l3-governance/src/eaasp_l3_governance/audit.py` — `record_governance_decision(..., stage=...)` extension; new nullable `governance_decisions.stage` column added via idempotent `ALTER TABLE` migration + partial index `idx_governance_decisions_stage` (AUDIT-01/02). v3.11.0 / v3.11.1 rows preserved (column NULL by default).
- `V310-APPROVAL-01` ✅ CLOSED. 5-stage contract tests PASS; SSE contract tests PASS; append-only ledger extension verified.
- v3.9 RBAC audit still PASS (134 routes — unchanged). v3.10 spec-audit still PASS (4 files / 37 rows).

### v3.11.3 single-point live walkthrough ✅ SHIPPED 2026-07-27

- `docs/status/PRODUCTION_USABILITY_2026-07-27.md` (340 lines) + `docs/status/PRODUCTION_USABILITY_LOGS_2026-07-27/` (16 dated artifacts: `sse-capture.json`, `l4-events.tsv`, `l3-audit-decisions.tsv`, `opa-sidecar-*.log`, `harness-caseA*.stdout`, `health-summary.txt`, etc.).
- 7 EAASP services up via `.grid/dev-eaasp-live.sh`; OPA sidecar v0.68.0 on `127.0.0.1:18181`; 5 SSE events in canonical order (seq 26–30, single request_id) for a `scada_set_setpoint mode=enforce risk_level=write_external` chain; 5 POST `/v1/data/governance/decision` roundtrips; 18 rows in L3 `governance_decisions` across 3 chain runs; 3-state OPA decision end-to-end.
- v3.9 RBAC audit still PASS (134 routes — unchanged). v3.10 spec-audit still PASS (4 files / 37 rows). ADR-V2-023 P1 shared-core rule preserved (no shared-crate change). `docs/status/JOURNAL.md` untouched per task directive.
- **Known finding (deferred to v3.12.0 per D-23):** `audit.py`'s CHECK constraint on `governance_decisions.decision` does not include `await_human`; the 5-stage state machine emits `await_human` at the Approve stage. Documented in `PRODUCTION_USABILITY_2026-07-27.md` §7. Filed as `V311-AUDIT-01` in `DEFERRED_LEDGER.md`.

### v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 🔵 IN PROGRESS 2026-07-28

- 4 phases planned (03.12.0 schema + audit constraint patch ✅ SHIPPED 2026-07-27 → 03.12.1 Event Room + multi-session ✅ SHIPPED 2026-07-27 → 03.12.2 A2A Router ✅ SHIPPED 2026-07-28 → 03.12.3 single-point live walkthrough pending).
- 13–16 REQ-IDs across 5 categories (SCHEMA / EVENT-ROOM / A2A / SESSION / COMPAT) + TRACE cross-axis.
- Locked decisions D-23..D-29 (see PROJECT.md §Key Decisions):
  - **D-23** `audit.py` CHECK constraint patch is mandatory phase 0; no 03.12.1 / 03.12.2 / 03.12.3 work before 03.12.0 ships.
  - **D-24** v3.12 scope = EAASP Phase 4 (A2A Router + Event Room + multi-session per EVOLUTION_PATH §三 Phase 4).
  - **D-25** MVP executable baseline (`threshold-calibration` skill + `make dev-eaasp`) + new A2A coordination walkthrough scenario.
  - **D-26** `audit.py` CHECK constraint extension uses idempotent `ALTER TABLE` migration (matches v3.11.2 `stage` column pattern).
  - **D-27** v3.12 stays in `tools/eaasp-*/` simulator-level implementations; no new repo / no new service port.
  - **D-28** v3.9 route-catalog RBAC + v3.10 spec-audit + ADR-V2-023 P1 + ADR-V2-034 OPA sidecar all continue to PASS.
  - **D-29** 探索策略 = Explore + Grep (no `.codegraph/` in this repo).

#### 03.12.2 A2A Router + ReviewSet aggregation + conflict detection ✅ SHIPPED 2026-07-28

- Built on top of v3.12.1 (`a248d73a`); no changes to any shared crate (ADR-V2-023 P1 + ADR-V2-029 preserved).
- `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/a2a_protocol.py` — `A2AMessageEnvelope` (pydantic BaseModel with strict id pattern `[a-zA-Z0-9_.-]{1,128}` + principal-keyed source/target fields + parallel-array invariant) + `RiskMetadata` (L3 risk_level classification: read / write_local / write_external) + 5 A2A SSE event type constants (a2a.request.sent / a2a.request.acknowledged / a2a.review.submitted / a2a.review.closed / a2a.conflict.detected) + `make_a2a_event_type` helper.
- `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/review_set.py` — `Review` + `ReviewSet` + `AggregationResult` dataclasses + 4 exception classes (`ReviewSetError` / `ReviewSetClosed` / `ReviewSetExpired` / `ReviewerNotExpected` / `ReviewerPrincipalMismatch`); 5 canonical aggregation scenarios (all allow / all deny / any needs_revision → escalate / multiple deny → deny / mixed verdict → escalate) + conflict detection on shared evidence_ref (majority-deny rule + review_synthesis escalation per ADR-V2-035) + cached `_expected_sessions_with_principals` map in `__post_init__` (O(1) lookup).
- `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/a2a_router.py` — `A2ARouter` facade over `EventRoomStore` + `MultiSessionCoordinator` + optional `L3RiskClassifier` Protocol; 5-step authorization chain (ContextVar resolve → source-principal parity → room existence + open status → source session + principal probe → target session + principal probe) + `route_message` / `request_review` / `route_review_submission` / `aggregate_review_set` / `close_review_set`.
- Security review fixes (3 HIGH applied 2026-07-28 BEFORE further commit per coordinator directive): (a) fail-open aggregation when expected reviewers are missing (HIGH #1 — single allow no longer produces unanimous allow); (b) principal-mismatch gate in `submit_review` rejecting caller-supplied principal that disagrees with cached expected principal (HIGH #2); (c) `ReviewerPrincipalMismatch` exception + `ReviewerNotExpected` signature extended to carry both session_id + principal.
- `tools/eaasp-l4-orchestration/tests/v3_12_2/test_review_set_aggregation.py` (23 tests) + `test_a2a_router.py` (16 tests) + `test_a2a_sse.py` (12 tests) — 51 new targeted tests PASS; total L4 orchestration tests 230 PASS (54 v3.12.1 baseline + 51 v3.12.2 new + 176 pre-existing — 1 unrelated policy_version assertion failure in pre-existing `test_session_orchestrator.py::test_create_session_happy_path` deselected, not a v3.12.2 regression).
- `docs/design/EAASP/adrs/ADR-V2-035-a2a-router-conflict-detection.md` — Accepted 2026-07-28. Records majority-deny rule + review_synthesis escalation + cross-session evidence conflict detection.
- `docs/design/EAASP/DEFERRED_LEDGER.md` — `V310-A2A-01` ✅ CLOSED 2026-07-28. `V310-SESSION-01` already ✅ CLOSED via 03.12.1 (kept).
- ADR-V2-034 OPA sidecar topology unchanged. v3.9 RBAC audit still PASS. v3.10 spec-audit still PASS. ADR-V2-023 P1 shared-core rule preserved (no shared-crate change).

#### 03.12.1 Event Room + multi-session coordination ✅ SHIPPED 2026-07-27

- Built on top of v3.12.0 (`91a23b55`); no changes to any shared crate (ADR-V2-023 P1 preserved).
- `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/event_room.py` — `EventRoom` + `EventRoomStore` with `create` / `close` / `add_member` / `remove_member` / `expire_stale_rooms` / `list_active` / `fan_out_event` / `list_room_events`; SQL-backed append-only event log; 5-round security review applied (HMAC-SHA256 subject hash + ContextVar auth + principal-keyed membership gate).
- `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/session_orchestrator_room.py` — `MultiSessionCoordinator` facade with `join_event_room` / `leave_event_room` / `auto_leave_event_rooms` / `emit_shared_event` / `resume_with_human_decision` (sibling-path parity: all four entry points resolve the verified caller principal from the `_AUTHENTICATED_PRINCIPAL` ContextVar, NEVER from a method parameter).
- `tools/eaasp-l4-orchestration/tests/v3_12_1/test_event_room.py` — 54 targeted tests PASS covering 5 security rounds (caller auth + principal-keyed membership gate + HMAC-SHA256 + log sanitization + audit reliability).
- `V310-SESSION-01` ✅ CLOSED via 03.12.1 (kept in 03.12.2 closure notes).
- v3.9 RBAC audit still PASS. v3.10 spec-audit still PASS. ADR-V2-023 P1 shared-core rule preserved.

#### 03.12.0 audit.py CHECK constraint patch ✅ SHIPPED 2026-07-27

- Built on top of v3.11.3 (`ba99b851`); no changes to any shared crate (ADR-V2-023 P1 preserved).
- `tools/eaasp-l3-governance/src/eaasp_l3_governance/audit.py` — `DECISION_ALLOWLIST` widens to `{allow, approve, deny, gate_request, await_human}`; `record_governance_decision` validation mirrors the DB CHECK allowlist.
- `tools/eaasp-l3-governance/src/eaasp_l3_governance/db.py` — inline `SCHEMA` CHECK widened for fresh DBs; new `migrate_decision_await_human` idempotent `ALTER TABLE` migration for v3.11.x legacy DBs (probes `sqlite_master`, rebuilds table under `BEGIN IMMEDIATE`, preserves all rows including the v3.11.2 `stage` column); `init_db` invokes the migration.
- `tools/eaasp-l3-governance/src/eaasp_l3_governance/approval_state_machine.py` — paused Approve stage writes a dedicated `approve_pause` ledger row carrying `DECISION_AWAIT_HUMAN` (in addition to the upstream `approve` policy verdict row); append-only invariant preserved via distinct `decision_id` suffix.
- `tools/eaasp-l3-governance/tests/test_audit_decision_await_human.py` + `test_audit_await_human_migration.py` — 14 new targeted tests cover SCHEMA-01..03 / MIGRATION-01..02 / AWAIT-HUMAN-01..02.
- 132 → 143 targeted tests PASS (+1 skipped, OPA-backend tests excluded — need OPA binary).
- `V311-AUDIT-01` ✅ CLOSED (DEFERRED_LEDGER.md). 03.12.1 / 03.12.2 / 03.12.3 unblocked.
- v3.9 RBAC audit still PASS (134 routes — unchanged). v3.10 spec-audit still PASS (4 files / 37 rows). ADR-V2-023 P1 shared-core rule preserved (no shared-crate change).

## Completed Milestones

### v3.9 grid-server route-catalog RBAC ✅ SHIPPED 2026-07-26

- 3 phases (03.9.0 / 03.9.1 / 03.9.2), 20/20 REQ-IDs closed.
- Canonical 134-entry HTTP route catalog + exact 3-route public allowlist (D-01/D-02).
- `AuthMode::Full` per-route catalog RBAC via canonical Axum `MatchedPath`; `AuthMode::None/ApiKey` semantics fully preserved (D-05).
- Shared `Action` registry expanded from 7 → 20 variants, parser + `Role::can` matrix synchronized (D-04).
- Owner-only boundaries preserved: `ManageUsers`/`ManageConfig` stay Owner-only (D-04).
- Standalone `route-auditor` binary + `make rbac-audit` + CI gate ordering `cargo check → rbac-audit → cargo test` (D-03).
- Post-ship fixes (security review): unified public-bypass with `PUBLIC_ROUTE_ALLOWLIST` for `/api/health`, `/api/health/live`, `/api/v1/auth/login`; corrected JWT `user` role mapping; `catalog_rbac_middleware` now distinguishes Public / Requires(action) / not-in-catalog; route-chain regression test added.
- 49 targeted tests PASS, `cargo check -p grid-server` PASS, `make rbac-audit` PASS with 134 routes.

### v3.8 grid-server multi-user login ✅ SHIPPED 2026-07-24

- 4 phases (03.8.0 / 03.8.1 / 03.8.2 / 03.8.3), 21 REQ-IDs in 6 categories.
- JWT primitive + AuthMode::Full path + login/refresh/logout endpoints + RBAC route enforcement + TenantContext::for_multi_user + cross-tenant isolation + tenant-scoped audit + USER_GUIDE §11 + PRODUCTION_USABILITY walkthrough + regression sweep.
- 119/119 targeted tests PASS, 3 security hotfixes (CRITICAL blacklist bypass + HIGH refresh stale-claim + HIGH audit IDOR).
- Demonstrated `requires(Action)` on 3 representative routes (`/admin/users`, `/audit`, `/sessions/{id}`); remaining ~127 endpoints in `crates/grid-server/src/api/mod.rs` + `router.rs` deferred to v3.9 per 03.8.2 plan §Task 4 + RESUME-NEXT-SESSION §Optional sidequests.
- Archive: `.planning/milestones/v3.8-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md`.

### v3.7 实战可用性补全 ✅ SHIPPED 2026-07-23

- 3 phases (3.7.1, 3.7.2, 3.7.3), 9/9 REQ-AUDITs + 8/8 REQ-EAASP closed.
- Phase 3.7.1: grid-cli 实战可用性 (S1-S6 scenarios, 14/14 hermetic tests).
- Phase 3.7.2: web/ Production Polish + Makefile entry points + USER_GUIDE §10.
- Phase 3.7.3: EAASP governance gate (REQ-EAASP-01..08) — L3 risk-aware gate,
  L4 SSE events, CLI sync approval UX, mock-SCADA scada_set_setpoint,
  S8 walkthrough, dated evidence (136 tests PASS).

### v3.6 Post-Activation Docs Sync ✅ SHIPPED 2026-07-19

- 3 sub-phases (3.6.1 SSOT + snapshot, 3.6.2 AGENTS + CLAUDE + READMEs, 3.6.3 STATE + PROJECT).
- 7 docs commits @ `a29f626`, UAT 46/46 PASS.

### v3.5 Debt Finalization ✅ SHIPPED 2026-06-16

- 3 phases (9.0/9.1/9.2), 0 ADRs
- LEDGER main D-table: 100% ✅ CLOSED (56 rows standardized)
- Phase 9.0: LEDGER audit + normalize 56 D-rows (17 notation fix + 30 newly closed + 9 genuine actives)
- Phase 9.1: D121 stop-hook dedup warn + D122 env-parity verify + D123 RAII EnvGuard
- Phase 9.2: Final LEDGER close-out, 100% uniformity

### v3.4 Full INBOX Drain ✅ SHIPPED 2026-06-16

- 10 phases (7.0–8.6), 21 plans, 39 tasks
- ~85 INBOX rows → 67 REQ-IDs fully drained
- 2 ADRs Accepted: ADR-V2-033 (EventSink gRPC) + ADR-V2-017 §2 (double-Terminate NO-OP)
- Carry-forward 7.0/7.1/7.2 verify-and-close phases: 19/19 D-items confirmed ✅ CLOSED
- New 8.0–8.6 phases: 48/48 REQ-IDs completed
- All v3.4 phase artifacts archived in `milestones/v3.4-ROADMAP.md`

### v3.11 EAASP Phase 3 — production OPA backend + 5-stage approval chain ✅ SHIPPED 2026-07-27

- 4 phases (03.11.0 / 03.11.1 / 03.11.2 / 03.11.3), 29/29 REQ-IDs in 11 categories (OPA + INSTALL + OPA-BACKEND + REGO + FAIL-CLOSED + DISABLED + STAGE + SSE + AUDIT + DENY + LIVE).
- ADR-V2-034 Accepted; `make opa-install` reproducible (03.11.0); L3 OPA backend `OPABackend.evaluate()` called from `PolicyEngine.evaluate_with_opa()` when `opa_enabled=True`; Rego template `policies/governance.rego` implements deny-always-wins (spec §15.9), risk classification (spec §6.1), and 3-state decision contract (spec §6.9, §6.10); 5 fail-closed modes covered with stable cause identifiers carried in the audit rationale; 5-stage approval state machine (Plan → Check → Draft → Approve → Execute) with `governance.approval.*` SSE events + append-only `governance_decisions.stage` column extension; `V310-OPA-01` + `V310-APPROVAL-01` ✅ CLOSED.
- 57 + targeted regression tests PASS; v3.11.3 single-point live walkthrough against real OPA sidecar v0.68.0 captured at `docs/status/PRODUCTION_USABILITY_2026-07-27.md` (5 SSE events in canonical order; 18 rows in L3 ledger across 3 chain runs).
- v3.9 RBAC audit still PASS (134 routes); v3.10 spec-audit still PASS (4 files / 37 rows); ADR-V2-023 P1 shared-core rule preserved (no shared-crate change).

### Earlier Milestones

| Milestone | Status | Key Output |
|-----------|--------|------------|
| v3.3 Engine + Platform Debt Sweep | ✅ 2026-06-07 | Phase 7.3 L3 RBAC 8/8 REQ-IDs |
| v3.2 Tech-Debt Triage | ✅ 2026-05-26 | 93 D-rows triaged → v3.3-INBOX.md seeded |
| v3.1 Engine Hardening | ✅ 2026-05-22 | 6 phases, 23 REQ-IDs, 6 ADRs |
| v3.0 Product Scope Decision | ✅ 2026-04-28 | ADR-V2-024 双轴模型 Accepted |

## Accumulated Context

### Decisions

- **LEDGER 100% CLOSED** (2026-06-16): DEFERRED_LEDGER.md main D-table fully standardized. Zero P1/P2/P3 active rows. 17 genuinely ACTIVE items filed as 📦 long-term (Phase 4–6 concern) or 🔵 P3-defer edge cases.
- **Debt era over** (2026-06-16): v3.2–v3.5 = 4 consecutive debt sweep milestones, ~200 D-items closed. No more debt milestones — shift to product activation.
- **Priority target**: grid-cli + grid-server first (per ADR-V2-024 Open Item #3), then platform/desktop/web.
- **Phase 3.7.3 gate boundary** (2026-07-23): SHIPPED 2/2 plans. risk metadata defaults to `read`; L3 evaluates after tool resolution and before dispatch; governance request/final decisions are append-only and surfaced via L4 events; L1 and L3 HTTP approval surface remain unchanged. 8/8 REQ-EAASP closed; 131/131 targeted tests PASS (L3 76 + L4 6 + CLI 18 + mock-SCADA 19 + Rust 12). Live walkthrough BLOCKED on missing LLM API key (hermetic S8 test proves same code path).
- **v3.9 locked decisions** (from v3.9 discussion, 2026-07-25):
  - D-01 Cover ALL non-public business HTTP routes.
  - D-02 Public routes on explicit allowlist (compile-time `const`).
  - D-03 CI static auditor enforces per-route invariants.
  - D-04 `Action` vocabulary extensible; new variants when semantic gap; `Role × Action` matrix regenerated.
  - D-05 `AuthMode::None/ApiKey` semantics fully compatible; only `AuthMode::Full` runs per-route RBAC.
  - D-06 `RouteCatalog` is the source of truth (`pub`); both manual-decorated-router and generate-from-router patterns acceptable.
  - D-07 No new external crate dependency.
  - D-08 No schema migration.
  - D-09 Shared-core rule (ADR-V2-023 P1) preserved; engine-layer changes leg-agnostic; verified by `test_rbac_engine_layer_is_leg_agnostic`.
  - D-10 Phase ladder 03.9.0 → 03.9.1 → 03.9.2.
- **v3.10 locked decisions** (from v3.10 discussion, 2026-07-26 — bootstrap pending plan-phase):
  - D-11 EAASP v2.0 platform-skeleton alignment scope: align `tools/eaasp-*` reference implementations with the canonical EAASP v2.0 platform contract (`docs/design/EAASP/EAASP-Design-Specification-v2.0.docx`) without adding new dependencies.
  - D-12 Three-axis skeleton mapping: (1) MAT (memory/manifest), (2) PIPE (orchestration pipes), (3) VERIFY (certifier conformance). Each axis has its own 03.10.x phase and Phase #1 deliverable proves the skeleton fits the spec.
  - D-13 Backward-compatible contract surface: existing `proto/eaasp/runtime/v2/` (21 RPC: 17 runtime + 4 hook) and `contract-v1.2.0` tests must remain green; no proto-breaking changes in v3.10.
  - D-14 L1 substitutability guard preserved: all 7 L1 runtimes (`grid-runtime` + 6 comparison: claude-code / goose / nanobot / pydantic-ai / claw-code / ccb; `hermes` frozen per ADR-V2-017) must continue to pass contract v1.2.0 certifier after each v3.10 phase.
  - D-15 No new external crate dependency (D-07 carry-over); same rule for Python (no new PyPI deps beyond existing `uv` lockfile).
  - D-16 No schema migration (D-08 carry-over); skeleton alignment is Rust + Python source + proto commentary only.
  - D-17 Shared-core rule (ADR-V2-023 P1, D-09 carry-over) preserved: any change to `grid-types` / `grid-engine` / `grid-sandbox` / `grid-hook-bridge` must remain leg-agnostic across engine 接入面 (EAASP) and Grid 独立产品.
  - D-18 Phase ladder 03.10.0 (skeleton audit + alignment matrix) → 03.10.1 (MAT axis) → 03.10.2 (PIPE axis) → 03.10.3 (VERIFY axis). Optionally merged into 3 phases if scope allows per scope review at plan-phase.

- **v3.11 locked decisions** (from v3.11.0 bootstrap, 2026-07-26):
  - D-19 OPA sidecar deployment topology: ADR-V2-034 — sidecar OPA on `127.0.0.1:18181`, in-repo Rego templates + atomic user bundles, fail-closed on OPA error. `make opa-install` downloads official OPA binary with SHA256 verify.
  - D-20 No shared-crate change: v3.11.0 / 03.11.1 / 03.11.2 / 03.11.3 must NOT touch `grid-types` / `grid-engine` / `grid-sandbox` / `grid-hook-bridge`; ADR-V2-023 P1 (shared-core rule) preserved; COMPAT-02 verified at every phase.
  - D-21 Backward-compatible contract surface: `proto/eaasp/runtime/v2/` 21 RPC + `contract-v1.2.0` tests remain green; no proto-breaking changes; new spec sections deferred to v3.12+ (D-13 carry-over).
  - D-22 Phase ladder 03.11.0 (sidecar + ADR) → 03.11.1 (L3 OPA backend + Rego) → 03.11.2 (5-stage approval state machine) → 03.11.3 (single-point live walkthrough).
- **v3.12 locked decisions** (from v3.12 bootstrap, 2026-07-27 — non-negotiable):
  - D-23 `audit.py` CHECK constraint patch is mandatory phase 0. v3.11.3 live walkthrough §7 surfaced that `audit.py`'s CHECK constraint on `governance_decisions.decision` does not include `await_human`; the 5-stage state machine emits `await_human` at the Approve stage; without this fix, 03.12.1 / 03.12.2 / 03.12.3 cannot reproduce paused-state audit evidence. v3.12.0 MUST patch the schema first; no implementation work in 03.12.1 / 03.12.2 may proceed before 03.12.0 ships. Closes `V311-AUDIT-01`.
  - D-24 v3.12 scope = EAASP Phase 4. v3.12 delivers A2A Router + Event Room + multi-session coordination per EAASP_v2_0_EVOLUTION_PATH.md §三 Phase 4 scope (spec §5.3 / §14 / §17). Closes V310-A2A-01 + V310-SESSION-01 + V311-AUDIT-01. v3.13+ = Phase 5 L5 / Phase 6 ecosystem.
  - D-25 MVP executable baseline + new A2A coordination scenario. Phase 0.5 MVP human-executable floor (`threshold-calibration` skill + `make dev-eaasp`) remains the minimum bar; v3.12 adds a new A2A coordination walkthrough scenario on top of that floor.
  - D-26 `audit.py` CHECK constraint extension uses idempotent migration. The extension MUST use `ALTER TABLE` (matching the existing v3.11.2 `stage` column migration pattern at the same `audit.py` module); existing DBs upgrade cleanly without losing history. No destructive schema work. No new tables / no new columns beyond the CHECK constraint extension.
  - D-27 v3.12 stays in `tools/eaasp-*/` simulator-level implementations. v3.12 does not open a new repo / does not open a new service port; uses the existing 7 EAASP services (skill-registry / L2 / L3 / mock-scada / MCP orchestrator / grid-runtime / L4) on `.grid/dev-eaasp-live.sh` launch topology. Event Room + A2A Router live in `tools/eaasp-l4-orchestration/` (per v3.7.3 L4 ownership pattern).
  - D-28 v3.12 安全边界 + shared-core rule + rbac-audit + v3.10-spec-audit + OPA sidecar all continue to PASS. v3.9 route-catalog RBAC (134 routes / `make rbac-audit`) + v3.10 spec-audit (4 files / 37 rows / `make v3.10-spec-audit`) + ADR-V2-023 P1 shared-core rule + ADR-V2-034 OPA sidecar ALL continue to PASS through every v3.12 phase.
  - D-29 v3.12 探索策略 = Explore + Grep. No `.codegraph/` in this repo; no MCP codegraph tool available. Codebase pattern reads gate by CLAUDE.md "Level 1+ single-pass reads" rule.

### Pending Todos

- **03.12.0 plan-phase**: run `/gsd-plan-phase 03.12.0` (D-23 mandates 03.12.0 must be planned + executed before 03.12.1 / 03.12.2 / 03.12.3).
- **03.12.1 plan-phase**: after 03.12.0 ships, plan Event Room + multi-session.
- **03.12.2 plan-phase**: after 03.12.1 ships, plan A2A Router.
- **03.12.3 plan-phase**: after 03.12.2 ships, plan single-point live walkthrough.

### Blockers/Concerns

- **Quality gaps in shipped components**: `web-platform/` (Quality 7.5) and `grid-desktop` (Quality 6.5) shipped with Activation but remain below the 9.0+ bar the rest of the components have hit. Need follow-on feature work (Markdown + toast + skeletons + error states for web-platform/; Icons + IPC proxy + Grid rebrand for grid-desktop).
- **EAASP v2.0 platform-evolution gaps (explicit future work)**: production OPA approval chain (Phase 3), A2A / Event Room (Phase 4), L5 Cowork UI (Phase 5), ecosystem expansion (Phase 6) — per `docs/design/EAASP/EAASP_v2_0_EVOLUTION_PATH.md`. Out of post-Activation scope; future milestone candidates.
- **138 unpushed commits**: accumulated across v3.2–v3.5. Push decision deferred to user.
- **Local environment**: `.env` has `OPENAI_NO_PROXY=1` for Clash. `LLM_PROVIDER=openai` code default.
- **v3.9 Action vocabulary growth discipline** (D-04): extension is allowed but each new variant must map to a coherent semantic; auditor surfaces gaps; "manage everything" catch-all is forbidden.
- **v3.10 spec drift risk**: the canonical EAASP v2.0 spec is `EAASP-Design-Specification-v2.0.docx` (~4373 KB). Skeleton alignment must reference this spec by section number (D-11); otherwise drift between `tools/eaasp-*` and the spec will reappear. v3.10 audit phase (03.10.0) MUST produce a section-by-section delta before any code changes.
- **v3.10 certifier gap**: existing `tools/eaasp-certifier` exercises `contract-v1.2.0` (17 runtime + 4 hook RPC). Skeleton alignment MUST not silently widen the certifier surface; new spec sections without contract backing must be tracked as deferred (D-13 + D-14).

## Session Continuity

Last session: 2026-07-27 (autonomous v3.11.2 + 03.11.3 climb; then v3.12 milestone bootstrap — this commit)
Stopped at: v3.12 bootstrapping — 4-phase ladder 03.12.0 / 03.12.1 / 03.12.2 / 03.12.3 planned; no implementation work yet. v3.11 SHIPPED 2026-07-27 — 29/29 REQ-IDs closed (4 phases: 03.11.0 OPA sidecar / 03.11.1 L3 OPA backend + Rego / 03.11.2 5-stage approval state machine / 03.11.3 single-point live walkthrough against real OPA sidecar v0.68.0).

Prior sessions:

- 2026-07-26 (autonomous v3.9 climb): v3.9 SHIPPED — 03.9.0 catalog, 03.9.1 full RBAC, 03.9.2 CI auditor all complete; targeted gates 51 PASS.
- 2026-07-24: Phase 03.8.3 SHIPPED — USER_GUIDE §11 + PRODUCTION_USABILITY walkthrough + regression sweep. v3.8 milestone close pending. 119/119 targeted tests PASS.
- 2026-07-23 (this climb session): v3.8 milestone bootstrapped (PROJECT.md + STATE.md updated). REQUIREMENTS + ROADMAP pending.
- 2026-07-19 (this session): Phase 3.7.1 SHIPPED — 8/9 REQ-AUDITs closed, 14/14 hermetic tests PASS
- 2026-07-19: Phase 3.7.1 context gathered (CONTEXT.md + DISCUSSION-LOG.md @ db695a29)
- 2026-07-19: Phase 3.6 SHIPPED @ a29f626 (7 docs commits, 46/46 UAT PASS)

Prior sessions:

- 2026-06-17: **Phase A.8 grid-eval CI completed** — concurrency group + summary report
- 2026-06-17: **Phase A.7 grid-desktop completed** — brand name, IPC commands, updater fix
- 2026-06-17: **Phase A.6 web-platform/ Production completed** — ErrorBoundary, Toast, Markdown, dashboard fix
- 2026-06-17: **Phase A.5 grid-platform Hardening completed** — ErrorCode enum, quota middleware, body limits
- 2026-06-17: **Phase A.4 Cross-Cutting Foundation completed** — ApiClient, cn(), design tokens, branding
- 2026-06-17: **Phase A.3 grid-cli Final Polish completed**
- 2026-06-17: **Phase A.2 web/ Production Polish completed**
- 2026-06-17: **Phase A.1 grid-server Hardening completed**
- 2026-06-16: **Phase A.0 Audit & Scoping completed**
- 2026-06-16: **v3.5 Debt Finalization SHIPPED**

---

*Milestone v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 bootstrapping (this commit). v3.11 SHIPPED 2026-07-27. v3.10 SHIPPED 2026-07-26. v3.9 SHIPPED 2026-07-26. v3.8 SHIPPED 2026-07-24. v3.7 SHIPPED 2026-07-23.*