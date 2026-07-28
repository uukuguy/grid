# Requirements: Grid

**Defined:** 2026-07-25
**Last updated:** 2026-07-28
**Active milestone:** v3.14 (EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem, bootstrapping 2026-07-28)
**Milestone:** v3.9 (route-catalog RBAC wiring + authorization auditor) [closed 2026-07-26]; v3.10 / v3.11 / v3.12 / v3.13 SHIPPED; v3.14 active
**Core Value:** Grid 作为 substitutable L1 runtime,通过 gRPC contract 被 EAASP L2-L4 调用,且任何符合 `contract-v1.2.0` 的对比 runtime 都能替换它。

> **Read first.** This file is the **active** requirements ledger. v3.8 (2026-07-24) and earlier milestones are archived to `.planning/milestones/v3.{X}-REQUIREMENTS.md`. Locked decisions from the v3.9 / v3.10 / v3.11 / v3.12 / v3.13 / v3.14 discussion are NOT negotiated below — they are normative for their respective milestones.

---

## v3.14 Requirements — EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem 🚧 BOOTSTRAPPING 2026-07-28

**Defined:** 2026-07-28 (v3.13 SHIPPED 2026-07-29 @ d0d83a23; V310-ECOSYSTEM-01 / V310-MAT-01 were deferred from v3.10 / v3.11 / v3.12 / v3.13 to v3.14 per EVOLUTION_PATH §三 Phase 6)
**Goal:** Close the EAASP v2.0 **EVOLUTION_PATH §三 8-Phase 路线** by delivering **Phase 6 — Ecosystem expansion**. v3.14 lands (a) an **Ontology 服务** that derives taxonomy + cross-domain links from the existing L2 evidence anchor + L3 governance_decisions + L4 event_room + L5 four-card projections (per D-40 "派生不复制" principle), (b) a **Skill Marketplace API** layered on top of the v3.11 `eaasp-skill-registry` that supports third-party submissions, a 4-stage promotion lifecycle (`draft → review → certified → published`), full ACL (per-tenant + per-role), and analytics (per D-41 — extends, does not replace, the existing registry), and (c) an **SDK scaffolding** (`sdk/python/` thin client + `tools/eaasp-ecosystem-sdk/` wrapper + JSON-schema exposition) that exposes the EAASP v2.0 surface as machine-readable JSON-schema. v3.14 is the **final phase** of the 8-Phase roadmap; once it ships, `V310-ECOSYSTEM-01` → ✅ CLOSED and the EVOLUTION_PATH 8-Phase roadmap is declared ALL SHIPPED. v3.14.0 lands the Ontology service + taxonomy paths + cross-domain link + JSON-schema derivation; v3.14.1 lands the Marketplace API + third-party submission lifecycle; v3.14.2 lands the SDK scaffolding + JSON-schema exposure; v3.14.3 is a single-point live walkthrough that demonstrates the full Phase 6 surface and pushes tag `v3.14`, closing the 8-Phase roadmap.

**Context (post-v3.13):** v3.13 SHIPPED the L5 Cowork four-card projection layer + RETROSPECTIVE trace API. The data needed for ecosystem expansion is now in place — every skill is registered in `eaasp-skill-registry`, every approval is a 5-stage state-machine row, every A2A dispatch + L4 cross-session event lives in the v3.12.1/2 SQLite stores, every four-card chain is traceable via the v3.13 RETROSPECTIVE API. v3.14's job is to expose that surface as a marketplace that third-party developers can discover, submit to, and integrate against, organized by an ontology that third-party clients can introspect programmatically via the SDK. Per EVOLUTION_PATH §三 Phase 6: spec §7.5–§7.8 (ontology / marketplace / skill promotion). Closes V310-ECOSYSTEM-01.

**Status:** 🚧 BOOTSTRAPPING 2026-07-28. 4-phase ladder planned (03.14.0 → 03.14.3). 13–16 REQ-IDs across 5 categories. Locked decisions D-38..D-46.

**REQ-IDs** use v3.14 numbering (`ONTOLOGY-*`, `MARKETPLACE-*`, `SDK-*`, `ECOSYSTEM-LIFECYCLE-*`, `COMPAT-*`). 13–16 REQ-IDs across 5 categories, continue from v3.13 (no overlap with `CARD-EVENT-*` / `CARD-EVIDENCE-*` / `CARD-ACTION-*` / `CARD-APPROVAL-*` / `RETROSPECTIVE-*` / `COMPAT-*` / `TRACE-*`).

### ONTOLOGY — Ontology 服务 + taxonomy 路径 + cross-domain link + JSON-schema 派生

> Phase 0 MUST ship before 03.14.1 / 03.14.2 — the ontology is the schema substrate that the marketplace organizes skills around (skill tags → taxonomy nodes) and that the SDK exposes (typed cross-domain links). Without 03.14.0, 03.14.1 marketplace has no taxonomy to index skills against, and 03.14.2 SDK has no ontology types to expose.

- [ ] **ONTOLOGY-01**: `tools/eaasp-ecosystem/src/eaasp_ecosystem/ontology.py` exposes `TaxonomyNode` / `CrossDomainLink` / `TaxonomyGraph` projection types. Each derives via SELECT from existing L2 evidence anchor + L3 governance_decisions + L4 event_room_events + L5 four-card projections (per D-40; "派生不复制"). No new tables, no new columns, no new event types.
- [ ] **ONTOLOGY-02**: `list_taxonomy(path) -> list[TaxonomyNode]` / `resolve_link(from_node_id, to_node_id) -> CrossDomainLink` / `derive_taxonomy() -> TaxonomyGraph` are public accessors. `derive_taxonomy()` is deterministic (same input → same output) and bounded by tenant (D-33-style tenant guard).
- [ ] **ONTOLOGY-03**: `GET /v1/ecosystem/ontology` endpoint emits the taxonomy + cross-domain links as JSON-schema. Endpoint sits behind the existing EAASP L4 service port (per D-39). JSON-schema emits `TaxonomyNode` / `CrossDomainLink` / `TaxonomyGraph` types as machine-readable schemas consumable by the v3.14.2 SDK scaffolding.

### MARKETPLACE — Skill Marketplace API + 第三方提交 / 4 阶段 promotion / 完整 ACL / analytics

> Depends on 03.14.0 (taxonomy must exist before skills can be tagged against it). Extends v3.11.2 `eaasp-skill-registry` (no replacement; D-41).

- [ ] **MARKETPLACE-01**: `tools/eaasp-ecosystem/src/eaasp_ecosystem/marketplace.py` exposes the 4-stage promotion lifecycle (`draft → review → certified → published`) with deterministic state transitions (e.g. `draft → review` allowed; `review → draft` rejected with `MarketplacePromotionError`). Each transition persists a row to the existing `eaasp-skill-registry` lifecycle table; no new tables.
- [ ] **MARKETPLACE-02**: Per-skill ACL supports `VisibilityScope.{Private, Tenant, Marketplace}` × `OwnerRole.{Author, Reviewer, Admin, Public}` matrix. `marketplace.list_skills(filter, visibility_scope, owner_role)` enforces ACL before returning the result list; unauthorized reads return 403 (matching v3.9 RBAC auditor contract, D-04 + D-44).
- [ ] **MARKETPLACE-03**: `eaasp marketplace submit / promote / list / stats` CLI commands added to `tools/eaasp-cli-v2/`. Each command emits the same JSON-schema contract exposed by the marketplace endpoint (so SDK scaffolding can wrap them uniformly).
- [ ] **MARKETPLACE-04**: `marketplace.skill_stats(skill_id) -> MarketplaceStats` returns: total submissions, total certifications, total downloads (per-tenant), per-stage histogram, per-role viewer histogram. Reads from existing L3 governance_decisions + L4 event_room_events; no new analytics tables.
- [ ] **MARKETPLACE-05**: `marketplace.submission_audit(skill_id) -> list[SubmissionAuditRow]` returns the full audit trail (who submitted, who promoted, who reviewed) cross-referenced with the v3.13 RETROSPECTIVE trace API per skill lifecycle stage. Read-only, idempotent, bounded by tenant.

### SDK — SDK scaffolding + JSON-schema 暴露

> Depends on 03.14.0 + 03.14.1 (SDK consumes the ontology + marketplace endpoints). Thin client that wraps the marketplace + ontology endpoints; does NOT re-implement business logic (per D-42).

- [ ] **SDK-01**: `sdk/python/eaasp_sdk/` exposes a typed Python client (sync + async variants) with `EaaspClient` class. The client wraps the existing `L4 /v1/ecosystem/ontology` + `L4 /v1/ecosystem/marketplace/...` endpoints; no re-implementation of business logic. Sync variant uses `httpx.Client` with `trust_env=False` (per `feedback_env_var_conventions` Clash proxy gotcha).
- [ ] **SDK-02**: `tools/eaasp-ecosystem-sdk/` exposes `EaaspCli` wrapper that consumes `EaaspClient` and provides `eaasp-sdk ontology / marketplace / submit / promote / list / stats` commands (thin wrapper over the marketplace API).
- [ ] **SDK-03**: `GET /v1/ecosystem/schema` endpoint emits the EAASP v2.0 surface as machine-readable JSON-schema. Third-party clients can use this schema to generate typed clients (per-language code-gen hooks documented for v3.15+; Python implemented in `sdk/python/` per D-42).
- [ ] **SDK-04**: SDK tests exercise the full marketplace + ontology surface against the real OPA sidecar + Event Room + A2A Router + L5 Cowork. SDK tests live in `sdk/python/tests/` and use `pytest` (matching the project's Python test convention).

### ECOSYSTEM-LIFECYCLE — single-point live walkthrough + tag v3.14 + EVOLUTION_PATH 8-Phase 路线 ALL SHIPPED

> Final phase. Reproduce the ecosystem walkthrough end-to-end against real OPA sidecar + Event Room + A2A Router + L5 Cowork + Ontology + Marketplace + SDK; push tag `v3.14`; close the EVOLUTION_PATH 8-Phase roadmap.

- [ ] **ECOSYSTEM-LIFECYCLE-01**: `docs/status/PRODUCTION_USABILITY_2026-07-30.md` captures: ontology derives a 10+ node taxonomy from existing L2 / L3 / L4 / A2A / L5 rows; a third-party submission traverses the 4-stage promotion lifecycle; the SDK generates a typed client against the JSON-schema. The walkthrough exercises `eaasp marketplace submit / promote / list / stats` end-to-end against the real OPA sidecar + Event Room + A2A Router + L5 Cowork + Ontology + Marketplace + SDK (per D-43).
- [ ] **ECOSYSTEM-LIFECYCLE-02**: `V310-ECOSYSTEM-01` marked `✅ CLOSED 2026-07-30` in `docs/design/EAASP/DEFERRED_LEDGER.md` (per D-46). `V310-MAT-01` remains `📦 long-term` (typed schema is out of v3.14 scope per D-44 / D-46 carry-over).
- [ ] **ECOSYSTEM-LIFECYCLE-03**: Tag `v3.14` pushed. The EVOLUTION_PATH §三 8-Phase roadmap declared ALL SHIPPED (Phase 0 / 0.5 / 0.75 / 1 / 2 / 2.5 SHIPPED 2026-04 historical; Phase 3 = v3.11 SHIPPED 2026-07-27; Phase 4 = v3.12 SHIPPED 2026-07-27; Phase 5 = v3.13 SHIPPED 2026-07-29; Phase 6 = v3.14 SHIPPED via 03.14.3).

### COMPAT — Contract + L1 substitutability + 安全边界 guards (v3.14 cross-axis)

- [ ] **COMPAT-01**: `proto/eaasp/runtime/v2/{common,runtime,hook}.proto` remain wire-compatible with `contract-v1.2.0`. No new RPC methods, no removed RPC methods, no breaking field-type changes in v3.14. Verified by `cargo test -p eaasp-certifier` PASS state pre and post each phase.
- [ ] **COMPAT-02**: All 7 L1 runtimes (`grid-runtime` + claude-code / goose / nanobot / pydantic-ai / claw-code / ccb; `hermes` frozen per ADR-V2-017) continue to pass `contract-v1.2.0` certifier after each v3.14 phase. Verified by `make v2-phase3-e2e-rust` + per-runtime `make v2-phase3-e2e` runs. L1 substitutability guard (D-14 carry-over) is the gate.
- [ ] **COMPAT-03**: Shared-core rule (ADR-V2-023 P1) preserved across any v3.14 changes — `grid-types` / `grid-engine` / `grid-sandbox` / `grid-hook-bridge` remain leg-agnostic across engine 接入面 (EAASP) and Grid 独立产品. Verified by the existing `test_rbac_engine_layer_is_leg_agnostic` + a new `test_v3_14_shared_core_unchanged` that snapshots `grid-engine::auth` + `grid-types::session` + `grid-types::runtime` public API surface pre/post v3.14. (D-44)
- [ ] **COMPAT-04**: v3.9 route-catalog RBAC (134 routes / `make rbac-audit`) + v3.10 spec-audit (4 files / 37 rows / `make v3.10-spec-audit`) + v3.11 OPA sidecar (ADR-V2-034) + v3.12 Event Room ContextVar auth + v3.12.2 A2A Router + ReviewSet + v3.13 L5 Cowork + retrospective trace API all continue to PASS through every v3.14 phase. (D-44)
- [ ] **COMPAT-05**: v3.14 不开新服务端口 (D-39);`tools/eaasp-ecosystem/` is a third-party Python module that consumes the existing 7 EAASP services via HTTP — no new listening port.

### TRACE — Spec traceability evidence (v3.14 cross-axis)

- [ ] **TRACE-01**: `docs/status/PRODUCTION_USABILITY_2026-07-30.md` dated walkthrough: (1) ontology derives a 10+ node taxonomy from existing L2 / L3 / L4 / A2A / L5 rows, (2) a third-party submission traverses the 4-stage promotion lifecycle, (3) the SDK generates a typed client against the JSON-schema, (4) `make rbac-audit` + `make v3.10-spec-audit` + `make v2-phase3-e2e-rust` PASS post-v3.14. Reuses the v3.13.3 PRODUCTION_USABILITY_2026-07-29.md pattern. (D-43)
- [ ] **TRACE-02**: `tools/eaasp-spec-alignment/ALIGNMENT_MATRIX.md` cross-index update: every EAASP v2.0 spec section that v3.14 touches (spec §7.5–§7.8) is listed with `(status, v3.14_phase, post_v3.14_owner)`. Gaps above the `contract-v1.2.0` baseline are explicitly listed as `deferred_to_v3.15+` with rationale. (D-12 carry-over)
- [ ] **TRACE-03**: The EVOLUTION_PATH §三 8-Phase roadmap is declared ALL SHIPPED via `docs/status/PRODUCTION_USABILITY_2026-07-30.md` §8. Verified by `git log --grep "v3.14"` showing 4 phase commits + `git tag --list v3.14` showing the tag.

## Future Requirements (deferred — explicit v3.14+ backlog)

- **L1 infrastructure tier changes (gVisor / Firecracker / Kata)** — V310-SANDBOX-01; long-term.
- **NATS JetStream backend for EventStream** — D75; long-term.
- **L4 event window cursor (>10k events)** — D36; Phase 3+ scale testing.
- **Cross-tenant ontology cross-domain links** — out of v3.14; cross-tenant ontology grouping deferred.
- **TypeScript / Go / Java SDK** — v3.15+ (Python only in v3.14 per D-42).
- **Marketplace payment / billing integration** — out of v3.14; data/integration axis per ADR-V2-024 §1.
- **`web-platform/` Quality 7.5→9.0** — separate milestone.
- **`grid-desktop` Quality 6.5→9.0** — separate milestone.
- **`grid-platform` route catalog audit** — separate milestone.
- **V310-MAT-01 closure** — typed schema work; out of v3.14 (per D-46); long-term.
- **Phase 7+ roadmap** — none planned; v3.14 is the final phase of EVOLUTION_PATH §三 8-Phase 路线 per D-46.

## Out of Scope (v3.14)

- **L1 infrastructure tier changes** — long-term.
- **NATS JetStream backend for EventStream** — long-term.
- **New service ports / new repository** — D-39 forbids; v3.14 stays in `tools/eaasp-*/` simulator-level implementations.
- **Schema migration beyond existing L2 / L3 / L4 / A2A / L5 tables** — D-40 forbids; v3.14 = projection + view layer only.
- **Cross-tenant ontology cross-domain links** — out of v3.14; cross-tenant ontology grouping deferred.
- **TypeScript / Go / Java SDK** — v3.15+ (Python only in v3.14 per D-42).
- **Marketplace payment / billing integration** — out of v3.14; data/integration axis per ADR-V2-024 §1.
- **New frontend (React / TypeScript / Vite)** — D-39 forbids; web/ + web-platform/ remain dormant.
- **Proto contract widening** — D-13 / D-21 carry-over; v3.14 reconciles to existing 21 RPC only.
- **L1 runtime additions or substitutions** — the 7-runtime matrix is frozen for v3.14.
- **`web-platform/` Quality 7.5→9.0** — separate milestone.
- **`grid-desktop` Quality 6.5→9.0** — separate milestone.
- **`grid-platform` route catalog audit** — separate milestone.

## Locked Decisions (from v3.14 discussion — non-negotiable)

| # | Decision | Source |
|---|----------|--------|
| D-38 | **v3.14 scope = EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem.** Per `EAASP_v2_0_EVOLUTION_PATH.md` §三 Phase 6 (spec §7.5–§7.8). Closes V310-ECOSYSTEM-01. v3.14 = EVOLUTION_PATH 8-Phase 路线 收口 (final phase per D-46). v3.15+ = data/integration axis (per ADR-V2-024 §1). | user directive |
| D-39 | **v3.14 不开新仓;仍 tools/eaasp-*/ 模拟器级实现;不开新服务端口.** v3.14 does NOT open a new repo / does NOT open a new service port. Ontology 服务 + Marketplace API live in `tools/eaasp-ecosystem/` (新建 Python module). The `L4 /v1/ecosystem/ontology` + `L4 /v1/ecosystem/marketplace/...` endpoints sit behind the existing EAASP L4 service port (per `.grid/dev-eaasp-live.sh` launch topology). D-27 + D-37 carry-over. | user directive |
| D-40 | **Ontology 服务派生自 v3.13 已落地的 L2 evidence + L3 governance_decisions + L4 event_room + L5 four-card projections;不新建独立存储.** v3.14 = projection + view layer; 底层仍是 v3.7.3 / v3.10 / v3.11 / v3.12 / v3.13 既有数据. No new tables, no new columns, no new event types. Reuses the existing 21 RPC + `contract-v1.2.0` baseline. D-32 carry-over (projection + 视图层). | user directive |
| D-41 | **Marketplace API 在 v3.11.2 eaasp-skill-registry 之上扩展 submission / promotion / ACL / analytics;不替换 eaasp-skill-registry.** v3.14's MarketplaceSkill / SubmissionAudit is built on top of the existing v3.11.2 `eaasp-skill-registry` (no replacement). The marketplace extends the registry's lifecycle (4-stage promotion), ACL (per-tenant + per-role), and analytics. The underlying skill_manifest / entrypoints / mcp_servers / permissions remain in `eaasp-skill-registry` (per V310-MAT-01 deferral rationale). | user directive |
| D-42 | **SDK scaffolding 在 sdk/python/ + tools/eaasp-ecosystem-sdk/ 之上加 thin client + JSON-schema 暴露.** v3.14's SDK scaffolding is a thin client that wraps the existing marketplace + ontology endpoints; it does NOT re-implement business logic. The `sdk/python/eaasp_sdk/` package emits a typed Python client; `tools/eaasp-ecosystem-sdk/` provides the CLI wrapper + JSON-schema codegen hooks. TypeScript / Go / Java SDK deferred to v3.15+. | user directive |
| D-43 | **仍以 Phase 0.5 MVP 人工可执行性为最低标尺 (threshold-calibration skill + `make dev-eaasp`);v3.14 extends the same MVP floor with an ecosystem walkthrough scenario.** v3.14.3 produces `docs/status/PRODUCTION_USABILITY_2026-07-30.md` exercising `eaasp marketplace submit / promote / list / stats` end-to-end against the real OPA sidecar + Event Room + A2A Router + L5 Cowork + Ontology + Marketplace + SDK. D-25 / D-34 carry-over. | CLAUDE.md §Runtime Verification Tasks + D-25 carry-over |
| D-44 | **v3.9 / v3.10 / v3.11 / v3.12 / v3.13 全部硬约束不动.** v3.9 134 routes RBAC / spec-audit 4 files 37 rows / ADR-V2-023 P1 / ADR-V2-028 / ADR-V2-034 OPA sidecar / v3.11.2 5-stage approval / v3.12.1 Event Room ContextVar 鉴权 / v3.12.2 A2A Router + ReviewSet / v3.13 L5 Cowork + retrospective 全部保留. v3.9 RBAC + v3.10 spec-audit + ADR-V2-034 OPA sidecar + v3.12 Event Room + v3.12 A2A Router + v3.13 RETROSPECTIVE all continue to PASS. D-35 carry-over. | D-09 / D-14 / D-17 / D-20 / D-28 / D-35 carry-over |
| D-45 | **v3.14 探索策略 = Explore + Grep (本仓无 `.codegraph/`).** Same as v3.13 D-36 + v3.12 D-29. | CLAUDE.md §Tool & MCP Usage |
| D-46 | **v3.14 是 EVOLUTION_PATH 8-Phase 路线最终 phase;收口后 v3.10 登记的全部 8 项 V310-* deferred items 全部 ✅ CLOSED.** Per `EAASP_v2_0_EVOLUTION_PATH.md` §三 8-Phase roadmap. v3.14 = Phase 6 = final phase. Once 03.14.3 ships, V310-ECOSYSTEM-01 → ✅ CLOSED (V310-OPA-01 / V310-APPROVAL-01 / V310-A2A-01 / V310-COWORK-01 / V310-SESSION-01 / V311-AUDIT-01 already CLOSED; V310-SANDBOX-01 + V310-MAT-01 are L1-infrastructure / typed-schema scope items, NOT Phase 6 deliverables — see v3.14 §Out of Scope + V310-MAT-01 row in DEFERRED_LEDGER.md). EVOLUTION_PATH 8-Phase 路线 ALL SHIPPED; no further Phase 7+ planned. | user directive |

## Traceability (filled by roadmapper — bootstrap pending)

| Phase | REQ-IDs |
|-------|---------|
| **03.14.0 Ontology 服务 + taxonomy 路径 + cross-domain link + JSON-schema 派生** | ONTOLOGY-01, ONTOLOGY-02, ONTOLOGY-03, COMPAT-01..05, TRACE-02 |
| **03.14.1 Skill Marketplace API + 第三方提交 / 4 阶段 promotion / 完整 ACL / analytics** | MARKETPLACE-01..05, COMPAT-01..05, TRACE-01 |
| **03.14.2 SDK scaffolding + JSON-schema 暴露** | SDK-01..04, COMPAT-01..05, TRACE-02 |
| **03.14.3 single-point live walkthrough + tag v3.14 + EVOLUTION_PATH 8-Phase 路线 ALL SHIPPED** | ECOSYSTEM-LIFECYCLE-01..03, TRACE-01 (final), TRACE-02 (final), TRACE-03 (final), COMPAT-01..05 (final) |
| **Total** | **13–16 REQ-IDs / 4 phases / 5 categories** (ONTOLOGY / MARKETPLACE / SDK / ECOSYSTEM-LIFECYCLE / COMPAT + TRACE cross-axis) |

---

## v3.9 Requirements ✅ SHIPPED 2026-07-26

[Full v3.9 requirements archived at `.planning/milestones/v3.9-REQUIREMENTS.md`.]

---

## v3.10 Requirements — EAASP v2.0 platform-skeleton alignment ✅ SHIPPED 2026-07-26

[Full v3.10 requirements archived at `.planning/milestones/v3.10-REQUIREMENTS.md`.]

---

## v3.11 Requirements — EAASP Phase 3 — production OPA backend + 5-stage approval chain ✅ SHIPPED 2026-07-27

[Full v3.11 requirements archived at `.planning/milestones/v3.11-REQUIREMENTS.md`.]

**Status (post-2026-07-27 walkthrough):** ✅ SHIPPED. All 4 phases (03.11.0 / 03.11.1 / 03.11.2 / 03.11.3) complete. Tag `v3.11` annotated. V310-OPA-01 + V310-APPROVAL-01 ✅ CLOSED. v3.9 RBAC + v3.10 spec-audit + ADR-V2-023 P1 + ADR-V2-034 OPA sidecar all preserved.

### v3.11.3 Requirements — single-point live walkthrough (LIVE-01..04)

- [x] **LIVE-01**: 7 EAASP services up via `.grid/dev-eaasp-live.sh`. ✅ SHIPPED
- [x] **LIVE-02**: 5 SSE events emitted in canonical order. ✅ SHIPPED
- [x] **LIVE-03**: 5 POST `/v1/data/governance/decision` roundtrips captured. ✅ SHIPPED
- [x] **LIVE-04**: v3.9 RBAC audit + v3.10 spec-audit + ADR-V2-023 P1 + ADR-V2-034 OPA sidecar all PASS. **`docs/status/JOURNAL.md` untouched** per task directive. ✅ SHIPPED

**Live walkthrough known finding (deferred to v3.12.0 per D-23):** `audit.py`'s CHECK constraint on `governance_decisions.decision` does not include `await_human` — closed via v3.12.0 SCHEMA-01 + AWAIT-HUMAN-01..02 (V311-AUDIT-01 ✅ CLOSED).

---

## v3.12 Requirements — EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 ✅ SHIPPED 2026-07-27 @ 894639dd

[Full v3.12 requirements archived at `.planning/milestones/v3.12-REQUIREMENTS.md`.]

**Status (post-2026-07-27 walkthrough):** ✅ SHIPPED. All 4 phases (03.12.0 / 03.12.1 / 03.12.2 / 03.12.3) complete. Tag `v3.12` pushed at commit `894639dd`. V310-A2A-01 + V310-SESSION-01 + V311-AUDIT-01 ✅ CLOSED. v3.9 RBAC + v3.10 spec-audit + ADR-V2-023 P1 + ADR-V2-034 OPA sidecar all preserved.

### SCHEMA — `audit.py` CHECK constraint patch ✅ SHIPPED 2026-07-27

- [x] **SCHEMA-01**: `audit.py`'s CHECK constraint on `governance_decisions.decision` extended to include `await_human`. ✅ SHIPPED
- [x] **SCHEMA-02**: Idempotent `ALTER TABLE` migration. Existing DBs upgrade cleanly without losing history. ✅ SHIPPED
- [x] **SCHEMA-03**: `audit.py`'s in-process enum validation accepts `await_human`. ✅ SHIPPED

### MIGRATION — `audit.py` CHECK constraint migration coverage ✅ SHIPPED 2026-07-27

- [x] **MIGRATION-01**: `db.migrate_decision_await_human(path)` idempotent. ✅ SHIPPED
- [x] **MIGRATION-02**: Migration preserves all pre-existing rows verbatim. ✅ SHIPPED

### AWAIT-HUMAN — `DECISION_AWAIT_HUMAN` ledger evidence ✅ SHIPPED 2026-07-27

- [x] **AWAIT-HUMAN-01**: `audit.DECISION_ALLOWLIST` exposes `await_human`. ✅ SHIPPED
- [x] **AWAIT-HUMAN-02**: 5-stage state machine paused Approve stage routes `DECISION_AWAIT_HUMAN` through full flow. ✅ SHIPPED

### EVENT-ROOM — Multi-session Event Room substrate ✅ SHIPPED 2026-07-27

- [x] **EVENT-ROOM-01..03**: `EventRoom` + multi-session fan-out + L4 SSE bridge for `governance.session.cross` event family. ✅ SHIPPED

### A2A — Agent-to-agent Router ✅ SHIPPED 2026-07-27

- [x] **A2A-01..04**: `A2ARouter` + cross-session dispatch + `cross_session=True` audit + cross-tenant rejection. ✅ SHIPPED

### SESSION — Multi-session coordination ✅ SHIPPED 2026-07-27

- [x] **SESSION-01..03**: New `L4 /v1/rooms/.../events` + `L4 /v1/rooms/.../dispatch` endpoints + preserved per-session SSE contract. ✅ SHIPPED

### COMPAT — Contract + L1 substitutability + 安全边界 guards ✅ SHIPPED 2026-07-27

- [x] **COMPAT-01..04** (v3.12) — v3.9 RBAC + v3.10 spec-audit + ADR-V2-023 P1 + ADR-V2-034 OPA sidecar all preserved through every v3.12 phase. ✅ SHIPPED

### TRACE — Spec traceability evidence ✅ SHIPPED 2026-07-27

- [x] **TRACE-01..02** (v3.12) — `docs/status/PRODUCTION_USABILITY_2026-07-28.md` walkthrough + ALIGNMENT_MATRIX.md cross-index update. ✅ SHIPPED

---

## v3.13 Requirements — EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle) ✅ SHIPPED 2026-07-29 @ d0d83a23

[Full v3.13 requirements archived at `.planning/milestones/v3.13-REQUIREMENTS.md`.]

**Status (post-2026-07-29 SHIP):** ✅ SHIPPED 2026-07-29. 4-phase ladder complete (03.13.0 / 03.13.1 / 03.13.2 / 03.13.3); 13+ REQ-IDs / 5 categories closed; tag `v3.13` annotated. V310-COWORK-01 ✅ CLOSED.

### CARD-EVENT — Event card (L4 Event Room + A2A envelope) ✅ SHIPPED 2026-07-29

- [x] **CARD-EVENT-01..03**: `EventCard` projection + keyed accessors + deterministic `payload_summary`. ✅ SHIPPED

### CARD-EVIDENCE — Evidence card (L2 evidence anchor) ✅ SHIPPED 2026-07-29

- [x] **CARD-EVIDENCE-01..03**: `EvidenceCard` projection + keyed accessors + deterministic `content_summary`. ✅ SHIPPED

### CARD-ACTION — Action card (L5 sandbox / tool invocation record) ✅ SHIPPED 2026-07-29

- [x] **CARD-ACTION-01..03**: `ActionCard` projection + keyed accessors + canonical `risk_level` from v3.11.1 Rego. ✅ SHIPPED

### CARD-APPROVAL — Approval card (L3 governance_decisions + 5-stage state machine) ✅ SHIPPED 2026-07-29

- [x] **CARD-APPROVAL-01..03**: `ApprovalCard` projection + keyed accessors + canonical 5-state decision + `await_human` paused-state support. ✅ SHIPPED

### RETROSPECTIVE — Retrospective cycle (回溯闭环) ✅ SHIPPED 2026-07-29

- [x] **RETROSPECTIVE-01..05**: `trace_session` + `L5 /v1/cowork/trace/{session_id}` + `eaasp cowork trace {session_id}` CLI + read-only idempotent + bounded by tenant. ✅ SHIPPED

### COMPAT — Contract + L1 substitutability + 安全边界 guards (v3.13 cross-axis) ✅ SHIPPED 2026-07-29

- [x] **COMPAT-01..05** (v3.13) — contract-v1.2.0 + 7 L1 runtimes + ADR-V2-023 P1 + v3.9-v3.12 hard constraints all preserved. ✅ SHIPPED

### TRACE — Spec traceability evidence (v3.13 cross-axis) ✅ SHIPPED 2026-07-29

- [x] **TRACE-01..03** (v3.13) — `docs/status/PRODUCTION_USABILITY_2026-07-29.md` walkthrough + ALIGNMENT_MATRIX.md cross-index update + four-card projection derivation invariant. ✅ SHIPPED

## Future Requirements (deferred — explicit v3.13+ backlog → all moved to v3.14 active)

- **Phase 6 ecosystem expansion** — V310-ECOSYSTEM-01 / V310-MAT-01; ✅ moved to v3.14 active scope.

## Out of Scope (v3.13) — closed

- **Phase 6 ecosystem expansion** — ✅ moved to v3.14 active scope.
- **All v3.13 out-of-scope items** carried forward as v3.14 out-of-scope items per D-44.

## Locked Decisions (from v3.13 discussion — non-negotiable)

[Full v3.13 D-30..D-37 archived at `.planning/milestones/v3.13-REQUIREMENTS.md` §Locked Decisions. All preserved through v3.14 per D-44.]

## Traceability (filled by roadmapper — closed) ✅

| Phase | REQ-IDs |
|-------|---------|
| **03.13.0 Event/Evidence/Action/Approval four-card data model + projection + L4 SSE bridge ✅ SHIPPED 2026-07-29** | CARD-EVENT-01..03 ✅, CARD-EVIDENCE-01..03 ✅, CARD-ACTION-01..03 ✅, CARD-APPROVAL-01..03 ✅, COMPAT-01..05 ✅, TRACE-02 ✅ |
| **03.13.1 Four-card SSE fan-out + state transitions + persistence ✅ SHIPPED 2026-07-29** | CARD-EVENT-02 (SSE extension) ✅, CARD-APPROVAL-02 (state transitions) ✅, COMPAT-01..04 ✅, TRACE-01 ✅, TRACE-02 ✅ |
| **03.13.2 Retrospective cycle (trace API) ✅ SHIPPED 2026-07-29** | RETROSPECTIVE-01..05 ✅, COMPAT-01..04 ✅, TRACE-01 ✅, TRACE-02 ✅ |
| **03.13.3 single-point live walkthrough + tag v3.13 ✅ SHIPPED 2026-07-29** | TRACE-01 (final) ✅, TRACE-02 (final) ✅, TRACE-03 ✅, COMPAT-01..05 (final) ✅, RETROSPECTIVE-04 (final) ✅ |
| **Total** | **13–16 REQ-IDs / 4 phases / 5 categories** ✅ |

---

*Last updated: 2026-07-28 — v3.14 EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem bootstrapped. 13–16 REQ-IDs across 5 categories (ONTOLOGY / MARKETPLACE / SDK / ECOSYSTEM-LIFECYCLE / COMPAT). Locked decisions D-38..D-46. v3.13 EAASP Phase 5 — L5 Cowork 四卡 + 回溯闭环 ✅ SHIPPED 2026-07-29 @ d0d83a23 (V310-COWORK-01 ✅ CLOSED). v3.12 EAASP Phase 4 ✅ SHIPPED 2026-07-27 @ 894639dd. v3.11 EAASP Phase 3 ✅ SHIPPED 2026-07-27 (V310-OPA-01 / V310-APPROVAL-01 ✅ CLOSED). v3.10 EAASP v2.0 platform-skeleton alignment ✅ SHIPPED 2026-07-26. v3.9 route-catalog RBAC + authorization auditor ✅ SHIPPED 2026-07-26. v3.8 grid-server multi-user login ✅ SHIPPED 2026-07-24. v3.7 实战可用性补全 ✅ SHIPPED 2026-07-23. v3.6 Post-Activation Docs Sync ✅ SHIPPED 2026-07-19. Grid 独立产品 Activation ✅ SHIPPED 2026-06-17. v3.5/v3.4/v3.3/v3.2/v3.1/v3.0 ✅ CLOSED.*
