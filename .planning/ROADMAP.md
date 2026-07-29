# Grid — Roadmap

> **Latest shipped milestone:** v3.9 route-catalog RBAC wiring + authorization auditor ✅ 2026-07-26
> **Latest shipped milestone:** v3.10 EAASP v2.0 platform-skeleton alignment ✅ 2026-07-26
> **Latest shipped milestone:** v3.11 EAASP Phase 3 — production OPA backend + 5-stage approval chain ✅ 2026-07-27
> **Latest shipped milestone:** v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 ✅ 2026-07-27
> **Latest shipped milestone:** v3.13 EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle) ✅ 2026-07-29 @ d0d83a23
> **Latest shipped milestone:** v3.14 EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem ✅ 2026-07-30 (4-phase ladder 03.14.0 / 03.14.1 / 03.14.2 / 03.14.3; 23 REQ-IDs / 5 categories; `tools/eaasp-ecosystem/` + `sdk/python/src/eaasp/{client,cli}/`; 98 targeted tests PASS; V310-ECOSYSTEM-01 ✅ CLOSED; **EVOLUTION_PATH §三 8-Phase 路线 ALL SHIPPED**).
> **Archive:** `milestones/v3.4-ROADMAP.md`, `milestones/v3.5-ROADMAP.md`, `milestones/v3.7-ROADMAP.md`, `milestones/v3.8-ROADMAP.md`, `milestones/v3.9-ROADMAP.md`, `milestones/v3.13-ROADMAP.md`
> **Current project root:** details in `.planning/PROJECT.md` §Current Milestone + `.planning/REQUIREMENTS.md` v3.14 section.

## Milestones

- ✅ **v3.0 Phase 4 — Product Scope Decision** — (shipped 2026-04-28, ADR-V2-024 Accepted)
- ✅ **v3.1 Phase 5 — Engine Hardening** — SHIPPED 2026-05-22 (6 phases, 23 REQ-IDs, 6 ADRs)
- ✅ **v3.2 Phase 6 — Tech-Debt Triage** — SHIPPED 2026-05-26 (3 phases, 6 REQ-IDs)
- ✅ **v3.3 Phase 7 — Engine + Platform Debt Sweep** — SHIPPED 2026-06-07 (Phase 7.3 L3 RBAC, 8/8 REQ-IDs)
- ✅ **v3.4 Phase 7/8 — Full INBOX Drain** — SHIPPED 2026-06-16 (10 phases, 67 REQ-IDs, 2 ADRs)
- ✅ **v3.5 Phase 9 — Debt Finalization** — SHIPPED 2026-06-16 (3 phases, LEDGER 100% CLOSED)
- ✅ **Grid 独立产品 Activation** — SHIPPED 2026-06-17 (8/8 phases A.0–A.8; repo renamed `grid-sandbox` → `grid`)
- ✅ **v3.6 Post-Activation Docs Sync** — SHIPPED 2026-07-19 (7 docs commits @ a29f626, 46/46 UAT PASS)
- ✅ **v3.7 实战可用性补全 (Production-Usability Closure)** — SHIPPED 2026-07-23 (3 phases: grid-cli / web/ / EAASP 本地仿真; 3.7.4 grid-server multi-user deferred to v3.8). 175/175 tests PASS, 50 commits, 76 files. Full details: `.planning/milestones/v3.7-ROADMAP.md` + `.planning/MILESTONES.md`
- ✅ **v3.8 grid-server multi-user login (Tenant + RBAC + JWT)** — SHIPPED 2026-07-24. 4 phases (03.8.0–03.8.3), 21 REQ-IDs in 6 categories, 119/119 targeted tests PASS, 3 security hotfixes. Demonstrated `requires(Action)` on 3 representative routes; remaining ~127 endpoints deferred to v3.9 per 03.8.2 plan §Task 4 / RESUME-NEXT-SESSION §Optional sidequests. Archive: `.planning/milestones/v3.8-ROADMAP.md` + `.planning/milestones/v3.8-REQUIREMENTS.md` + `.planning/milestones/v3.8-MILESTONE-AUDIT.md`.
- ✅ **v3.9 route-catalog RBAC wiring + authorization auditor** — SHIPPED 2026-07-26 (climb bootstrap). Closes v3.8.2's "full route catalog wiring" deferral. 3 phases planned (03.9.0 → 03.9.2), 20 REQ-IDs in 5 categories. Details: `.planning/PROJECT.md` §Current Milestone + `.planning/REQUIREMENTS.md` v3.9 section.
- ✅ **v3.10 EAASP v2.0 platform-skeleton alignment** — SHIPPED 2026-07-26. Four phases (03.10.0–03.10.3), 16/16 REQ-IDs, 174 targeted tests PASS. Five-layer/three-pipeline/four-card matrix, deterministic spec auditor, payload-driven MCP guard, ordered CI gate. Live real-skill walkthrough awaits LLM credentials.
- ✅ **v3.11 EAASP Phase 3 — production OPA backend + 5-stage approval chain** — SHIPPED 2026-07-27. Four phases (03.11.0 / 03.11.1 / 03.11.2 / 03.11.3), 29/29 REQ-IDs in 11 categories (OPA + INSTALL + OPA-BACKEND + REGO + FAIL-CLOSED + DISABLED + STAGE + SSE + AUDIT + DENY + LIVE). ADR-V2-034 Accepted; `make opa-install` reproducible; 5-stage approval state machine (Plan → Check → Draft → Approve → Execute) with deny-always-wins + human-in-the-loop pause; 57 + targeted regression tests PASS. Live walkthrough against real OPA sidecar v0.68.0 captured at `docs/status/PRODUCTION_USABILITY_2026-07-27.md`. `V310-OPA-01` + `V310-APPROVAL-01` CLOSED. v3.9 RBAC + v3.10 spec-audit + ADR-V2-023 P1 shared-core all preserved.
- ✅ **v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调** — SHIPPED 2026-07-27 @ 894639dd. Four phases (03.12.0 / 03.12.1 / 03.12.2 / 03.12.3), 13–16 REQ-IDs in 5 categories (SCHEMA / EVENT-ROOM / A2A / SESSION / COMPAT + TRACE). `audit.py` CHECK constraint patched to include `await_human` via idempotent `ALTER TABLE` migration (V311-AUDIT-01 CLOSED); `EventRoom` + `EventRoom.fan_out_event(...)` landed in `tools/eaasp-l4-orchestration/event_room.py`; `A2ARouter.dispatch(...)` landed in `tools/eaasp-l4-orchestration/a2a_router.py` running through v3.7.3 governance gate + v3.11.2 5-stage approval chain with `await_human` paused-state audit evidence; new `governance.session.cross` event family added to L4 SSE (V310-SESSION-01 CLOSED); cross-tenant A2A dispatch rejected with 403 (D-28). Live walkthrough captured at `docs/status/PRODUCTION_USABILITY_2026-07-28.md` (V310-A2A-01 CLOSED). v3.9 RBAC + v3.10 spec-audit + ADR-V2-023 P1 + ADR-V2-034 OPA sidecar all preserved. Tag `v3.12` pushed.
- ✅ **v3.13 EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle)** — SHIPPED 2026-07-29 @ d0d83a23. Four phases (03.13.0 / 03.13.1 / 03.13.2 / 03.13.3), 13+ REQ-IDs in 5 categories (CARD-EVENT / CARD-EVIDENCE / CARD-ACTION / CARD-APPROVAL / RETROSPECTIVE + COMPAT + TRACE). `EventCard` / `EvidenceCard` / `ActionCard` / `ApprovalCard` projection types in `tools/eaasp-l5-cowork/src/eaasp_l5_cowork/cards.py`; each card derives fields via SELECT from existing L2 / L3 / L4 / A2A tables (D-32); L4 SSE bridge emits `cowork.card.<type>.<event>` events mirroring underlying envelopes; state machine `pending → confirmed → acted` with `await_human` paused-state support; `RETROSPECTIVE` trace API (`trace_session(session_id) -> RetrospectiveChain`) with `cross_refs` linking each card to upstream causes (D-33); `L5 /v1/cowork/trace/{session_id}` endpoint + `eaasp cowork trace {session_id}` CLI command. Live walkthrough captured at `docs/status/PRODUCTION_USABILITY_2026-07-29.md` (V310-COWORK-01 CLOSED). v3.9 RBAC + v3.10 spec-audit + ADR-V2-023 P1 + ADR-V2-034 OPA sidecar + v3.12 Event Room + A2A Router all preserved. Tag `v3.13` annotated.

---

## Milestone: v3.14 EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem (bootstrapping 2026-07-28)

**Goal:** Close the EAASP v2.0 **EVOLUTION_PATH §三 8-Phase 路线** by delivering **Phase 6 — Ecosystem expansion**. v3.14 lands (a) an **Ontology 服务** that derives taxonomy + cross-domain links from the existing L2 evidence anchor + L3 governance_decisions + L4 event_room + L5 four-card projections (per D-40 "派生不复制" principle), (b) a **Skill Marketplace API** layered on top of the v3.11 `eaasp-skill-registry` that supports third-party submissions, a 4-stage promotion lifecycle (`draft → review → certified → published`), full ACL (per-tenant + per-role), and analytics (per D-41 — extends, does not replace, the existing registry), and (c) an **SDK scaffolding** (`sdk/python/` thin client + `tools/eaasp-ecosystem-sdk/` wrapper + JSON-schema exposition) that exposes the EAASP v2.0 surface as machine-readable JSON-schema. v3.14 is the **final phase** of the 8-Phase roadmap; once it ships, `V310-ECOSYSTEM-01` → ✅ CLOSED and the EVOLUTION_PATH 8-Phase roadmap is declared ALL SHIPPED. v3.14.0 lands the Ontology service + taxonomy paths + cross-domain link + JSON-schema derivation; v3.14.1 lands the Marketplace API + third-party submission lifecycle; v3.14.2 lands the SDK scaffolding + JSON-schema exposure; v3.14.3 is a single-point live walkthrough that demonstrates the full Phase 6 surface and pushes tag `v3.14`, closing the 8-Phase roadmap.

**Context (post-v3.13):** v3.13 SHIPPED the L5 Cowork four-card projection layer + RETROSPECTIVE trace API. The data needed for ecosystem expansion is now in place — every skill is registered in `eaasp-skill-registry`, every approval is a 5-stage state-machine row, every A2A dispatch + L4 cross-session event lives in the v3.12.1/2 SQLite stores, every four-card chain is traceable via the v3.13 RETROSPECTIVE API. v3.14's job is to expose that surface as a marketplace that third-party developers can discover, submit to, and integrate against, organized by an ontology that third-party clients can introspect programmatically via the SDK. Per EVOLUTION_PATH §三 Phase 6: spec §7.5–§7.8 (ontology / marketplace / skill promotion). Closes V310-ECOSYSTEM-01.

**Locked decisions (from v3.14 discussion — non-negotiable):**

- **D-38** v3.14 scope = EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem. Per `EAASP_v2_0_EVOLUTION_PATH.md` §三 Phase 6 (spec §7.5–§7.8). Closes V310-ECOSYSTEM-01. v3.14 = EVOLUTION_PATH 8-Phase 路线 收口 (final phase per D-46). v3.15+ = data/integration axis (per ADR-V2-024 §1).
- **D-39** v3.14 不开新仓;仍 tools/eaasp-*/ 模拟器级实现;不开新服务端口. v3.14 does NOT open a new repo / does NOT open a new service port. Ontology 服务 + Marketplace API live in `tools/eaasp-ecosystem/` (新建 Python module). The `L4 /v1/ecosystem/ontology` + `L4 /v1/ecosystem/marketplace/...` endpoints sit behind the existing EAASP L4 service port (per `.grid/dev-eaasp-live.sh` launch topology). D-27 + D-37 carry-over.
- **D-40** Ontology 服务派生自 v3.13 已落地的 L2 evidence + L3 governance_decisions + L4 event_room + L5 four-card projections;不新建独立存储. v3.14 = projection + view layer; 底层仍是 v3.7.3 / v3.10 / v3.11 / v3.12 / v3.13 既有数据. No new tables, no new columns, no new event types. Reuses the existing 21 RPC + `contract-v1.2.0` baseline. D-32 carry-over (projection + 视图层).
- **D-41** Marketplace API 在 v3.11.2 eaasp-skill-registry 之上扩展 submission / promotion / ACL / analytics;不替换 eaasp-skill-registry. v3.14's MarketplaceSkill / SubmissionAudit is built on top of the existing v3.11.2 `eaasp-skill-registry` (no replacement). The marketplace extends the registry's lifecycle (4-stage promotion), ACL (per-tenant + per-role), and analytics. The underlying skill_manifest / entrypoints / mcp_servers / permissions remain in `eaasp-skill-registry` (per V310-MAT-01 deferral rationale).
- **D-42** SDK scaffolding 在 sdk/python/ + tools/eaasp-ecosystem-sdk/ 之上加 thin client + JSON-schema 暴露. v3.14's SDK scaffolding is a thin client that wraps the existing marketplace + ontology endpoints; it does NOT re-implement business logic. The `sdk/python/eaasp_sdk/` package emits a typed Python client; `tools/eaasp-ecosystem-sdk/` provides the CLI wrapper + JSON-schema codegen hooks. TypeScript / Go / Java SDK deferred to v3.15+.
- **D-43** 仍以 Phase 0.5 MVP 人工可执行性为最低标尺 (threshold-calibration skill + `make dev-eaasp`);v3.14 extends the same MVP floor with an ecosystem walkthrough scenario. v3.14.3 produces `docs/status/PRODUCTION_USABILITY_2026-07-30.md` exercising `eaasp marketplace submit / promote / list / stats` end-to-end against the real OPA sidecar + Event Room + A2A Router + L5 Cowork + Ontology + Marketplace + SDK. D-25 / D-34 carry-over.
- **D-44** v3.9 / v3.10 / v3.11 / v3.12 / v3.13 全部硬约束不动. v3.9 134 routes RBAC / spec-audit 4 files 37 rows / ADR-V2-023 P1 / ADR-V2-028 / ADR-V2-034 OPA sidecar / v3.11.2 5-stage approval / v3.12.1 Event Room ContextVar 鉴权 / v3.12.2 A2A Router + ReviewSet / v3.13 L5 Cowork + retrospective 全部保留. v3.9 RBAC + v3.10 spec-audit + ADR-V2-034 OPA sidecar + v3.12 Event Room + v3.12 A2A Router + v3.13 RETROSPECTIVE all continue to PASS. D-35 carry-over.
- **D-45** v3.14 探索策略 = Explore + Grep (本仓无 `.codegraph/`). Same as v3.13 D-36 + v3.12 D-29.
- **D-46** v3.14 是 EVOLUTION_PATH 8-Phase 路线最终 phase;收口后 v3.10 登记的全部 8 项 V310-* deferred items 全部 ✅ CLOSED. Per `EAASP_v2_0_EVOLUTION_PATH.md` §三 8-Phase roadmap. v3.14 = Phase 6 = final phase. Once 03.14.3 ships, V310-ECOSYSTEM-01 → ✅ CLOSED (V310-OPA-01 / V310-APPROVAL-01 / V310-A2A-01 / V310-COWORK-01 / V310-SESSION-01 / V311-AUDIT-01 already CLOSED; V310-SANDBOX-01 + V310-MAT-01 are L1-infrastructure / typed-schema scope items, NOT Phase 6 deliverables — see v3.14 §Out of Scope + V310-MAT-01 row in DEFERRED_LEDGER.md). EVOLUTION_PATH 8-Phase 路线 ALL SHIPPED; no further Phase 7+ planned.

**Scope ladder (4 phases, recommended ordering that puts Ontology first):**

| # | Phase | Goal | Requirements | Success criteria |
|---|-------|------|--------------|------------------|
| **03.14.0** | Ontology 服务 + taxonomy 路径 + cross-domain link + JSON-schema 派生 | `TaxonomyNode` / `CrossDomainLink` / `TaxonomyGraph` projection types in `tools/eaasp-ecosystem/src/eaasp_ecosystem/ontology.py`; each derives via SELECT from existing L2 evidence anchor + L3 governance_decisions + L4 event_room_events + L5 four-card projections (D-40); `list_taxonomy(path)`, `resolve_link(...)`, `derive_taxonomy()` accessors; `GET /v1/ecosystem/ontology` endpoint emits JSON-schema | ONTOLOGY-01, ONTOLOGY-02, ONTOLOGY-03, COMPAT-01, COMPAT-02, COMPAT-03, COMPAT-04, COMPAT-05, TRACE-02 | Ontology derives a 10+ node taxonomy from existing L2 / L3 / L4 / A2A / L5 rows; `derive_taxonomy()` deterministic + bounded by tenant; JSON-schema exposes `TaxonomyNode` / `CrossDomainLink` / `TaxonomyGraph` types; `make rbac-audit` + `make v3.10-spec-audit` + `make v2-phase3-e2e-rust` PASS |
| **03.14.1** | Skill Marketplace API + 第三方提交 / 4 阶段 promotion / 完整 ACL / analytics | `MarketplaceSkill` / `SubmissionAuditRow` / `MarketplaceStats` accessors in `tools/eaasp-ecosystem/src/eaasp_ecosystem/marketplace.py`; 4-stage promotion lifecycle (`draft → review → certified → published`) with deterministic state transitions; per-skill ACL (`VisibilityScope × OwnerRole`); `eaasp marketplace submit / promote / list / stats` CLI commands; `marketplace.skill_stats` + `marketplace.submission_audit` read-only | MARKETPLACE-01, MARKETPLACE-02, MARKETPLACE-03, MARKETPLACE-04, MARKETPLACE-05, COMPAT-01, COMPAT-02, COMPAT-03, COMPAT-04, TRACE-01 | 4-stage promotion lifecycle with deterministic transitions; per-skill ACL enforced with 403 for unauthorized reads; CLI commands emit JSON-schema contract; `marketplace.skill_stats` + `marketplace.submission_audit` return correct audit trail cross-referenced with v3.13 RETROSPECTIVE |
| **03.14.2** | SDK scaffolding + JSON-schema 暴露 | `sdk/python/eaasp_sdk/` typed Python client (sync + async) with `EaaspClient` class wrapping the marketplace + ontology endpoints (no business logic re-implementation); `tools/eaasp-ecosystem-sdk/` CLI wrapper; `GET /v1/ecosystem/schema` endpoint emits EAASP v2.0 surface as JSON-schema; SDK tests against real OPA sidecar + Event Room + A2A Router + L5 Cowork | SDK-01, SDK-02, SDK-03, SDK-04, COMPAT-01, COMPAT-02, COMPAT-03, COMPAT-04, TRACE-02 | `EaaspClient` wraps marketplace + ontology endpoints without re-implementing business logic; `GET /v1/ecosystem/schema` returns machine-readable JSON-schema; SDK tests in `sdk/python/tests/` PASS against real OPA sidecar + Event Room + A2A Router + L5 Cowork |
| **03.14.3** | single-point live walkthrough + tag v3.14 + EVOLUTION_PATH 8-Phase 路线 ALL SHIPPED | End-to-end live walkthrough against real OPA sidecar + Event Room + A2A Router + L5 Cowork + Ontology + Marketplace + SDK; reproduces 10+ node taxonomy + 4-stage promotion lifecycle + typed client codegen; v3.9 / v3.10 / ADR-V2-034 / v3.12 / v3.13 regression sweep; tag `v3.14` pushed | ECOSYSTEM-LIFECYCLE-01, ECOSYSTEM-LIFECYCLE-02, ECOSYSTEM-LIFECYCLE-03, TRACE-01 (final), TRACE-02 (final), TRACE-03 (final), COMPAT-01..05 (final) | `docs/status/PRODUCTION_USABILITY_2026-07-30.md` captures: (1) ontology derives 10+ node taxonomy, (2) 3rd-party submission traverses 4-stage promotion lifecycle, (3) SDK generates typed client against JSON-schema, (4) `make rbac-audit` + `make v3.10-spec-audit` + `make v2-phase3-e2e-rust` PASS post-v3.14, (5) tag `v3.14` pushed. **`V310-ECOSYSTEM-01 → ✅ CLOSED`; EVOLUTION_PATH 8-Phase 路线 ALL SHIPPED** |

### Why this ladder

- **03.14.0 (Ontology)** MUST come first — the ontology is the schema substrate that the marketplace organizes skills around (skill tags → taxonomy nodes) and that the SDK exposes (typed cross-domain links). Without 03.14.0, 03.14.1 marketplace has no taxonomy to index skills against, and 03.14.2 SDK has no ontology types to expose.
- **03.14.1 (Marketplace)** — depends on 03.14.0 (taxonomy must exist before skills can be tagged against it); wires the marketplace surface that 03.14.2 SDK consumes.
- **03.14.2 (SDK)** — depends on 03.14.0 + 03.14.1 (SDK consumes the ontology + marketplace endpoints); lands a thin client that does NOT re-implement business logic (per D-42).
- **03.14.3 (live walkthrough + tag v3.14)** — final; reproduce the ecosystem walkthrough end-to-end against real OPA sidecar + Event Room + A2A Router + L5 Cowork + Ontology + Marketplace + SDK; push tag `v3.14`; close the EVOLUTION_PATH 8-Phase roadmap.

### Out of scope (deferred to v3.15+)

- **L1 infrastructure tier changes (gVisor / Firecracker / Kata)** — V310-SANDBOX-01; long-term.
- **NATS JetStream backend for EventStream** — D75; long-term.
- **L4 event window cursor (>10k events)** — D36; Phase 3+ scale testing.
- **Cross-tenant ontology cross-domain links** — out of v3.14; cross-tenant ontology grouping deferred.
- **TypeScript / Go / Java SDK** — v3.15+ (Python only in v3.14 per D-42).
- **Marketplace payment / billing integration** — out of v3.14; data/integration axis per ADR-V2-024 §1.
- **Actual L5 Cowork UI (React + Tailwind)** — separate milestone; web/ + web-platform/ remain dormant (D-39).
- **New service ports / new repository** — D-39 forbids; v3.14 stays in `tools/eaasp-*/` and reuses the existing 7 EAASP services on `.grid/dev-eaasp-live.sh` launch topology.
- **Schema migration beyond the existing L2 / L3 / L4 / A2A / L5 tables** — D-40 forbids; v3.14 = projection layer only.
- **Proto contract widening** — D-13 / D-21 carry-over; v3.14 reconciles to existing 21 RPC only.
- **L1 runtime additions or substitutions** — the 7-runtime matrix is frozen for v3.14.
- **`web-platform/` Quality 7.5→9.0** — separate milestone (carried forward).
- **`grid-desktop` Quality 6.5→9.0** — separate milestone (carried forward).
- **`grid-platform` route catalog audit** — separate milestone (carried forward).
- **V310-MAT-01 closure** — typed schema work; out of v3.14 (per D-46); long-term.
- **Phase 7+ roadmap** — none planned; v3.14 is the final phase of EVOLUTION_PATH §三 8-Phase 路线 per D-46.

### Risks & guards

- **R-1: Ontology projection is silently wrong (the core v3.14 risk)** — D-40 forbids new storage; if the ontology layer reads from the wrong source table or omits rows, the marketplace cannot organize skills around taxonomy nodes. Guard: 03.14.0 MUST produce `test_ontology_projection_is_derived.py` asserting cross-table count parity (TRACE-02); each taxonomy node's fields must trace to a specific SELECT statement.
- **R-2: Marketplace 替换 eaasp-skill-registry** — D-41 forbids replacement; if the marketplace accidentally replaces the registry's lifecycle / ACL / audit logic, v3.11.2 regression breaks. Guard: 03.14.1 MUST produce `test_marketplace_extends_registry.py` asserting that `eaasp-skill-registry` remains the underlying store + the marketplace layer is purely additive.
- **R-3: `contract-v1.2.0` regression** — D-13 / D-21 carry-over; the existing 21 RPC contract + 7 L1 runtime certifier must remain green. Guard: COMPAT-01 (proto wire-compat) + COMPAT-02 (`make v2-phase3-e2e-rust`) verified in 03.14.0 / 03.14.1 / 03.14.2 / 03.14.3 gates.
- **R-4: `grid-engine` shared-core bleed** — D-44; any change to `grid-types` / `grid-engine` / `grid-sandbox` / `grid-hook-bridge` must remain leg-agnostic. Guard: `test_v3_14_shared_core_unchanged` (new, COMPAT-03) snapshots public API surface pre/post v3.14.
- **R-5: Spec drift** — D-12 carry-over; EAASP v2.0 spec §7.5–§7.8 are the Phase 6 sections. Guard: 03.14.0 `tools/eaasp-spec-alignment/ALIGNMENT_MATRIX.md` update (TRACE-02) lists every `### §N.M` section touched with `(status, v3.14_phase, post_v3.14_owner)`.
- **R-6: Certifier scope creep** — D-13 / D-21 carry-over; v3.14 reconciles to existing 21 RPC only. Guard: COMPAT-01 verified by `cargo test -p eaasp-certifier` PASS state pre/post each phase; new spec sections deferred.
- **R-7: Phase 3 OPA + Phase 4 A2A / Event Room + Phase 5 L5 Cowork regression** — D-44; the OPA sidecar + Event Room + A2A Router + 5-stage approval state machine + audit.py CHECK constraint patch + four-card projection + retrospective trace API must remain green through v3.14. Guard: COMPAT-04 (ADR-V2-034 + v3.12 + v3.13) verified at every phase; v3.11.2 / v3.12 / v3.13 regression tests PASS.
- **R-8: SDK re-implements business logic** — D-42 forbids; if the SDK re-implements marketplace / ontology business logic instead of wrapping the endpoints, the source-of-truth contract breaks. Guard: 03.14.2 MUST produce `test_sdk_wraps_endpoints_only.py` asserting SDK calls are HTTP calls to the existing endpoints (no local business logic re-implementation).
- **R-9: 03.14.3 live walkthrough blocked on missing LLM API key** — same blocker as v3.10 / v3.11 / v3.12 / v3.13. Guard: hermetic in-process walkthrough (using the same v3.7.3 threshold-calibration skill + v3.12 Event Room + A2A Router + v3.13 RETROSPECTIVE) is the executable baseline (D-43); live walkthrough captures whatever subset is reproducible given the LLM credential.

### Shared core rule (ADR-V2-023 P1, retained)

Changes to `grid-engine`, `grid-runtime`, `grid-types`, `grid-sandbox`, `grid-hook-bridge` must work for both engine 接入面 (EAASP) and Grid 独立产品. v3.14 is engine-axis work (L4 ecosystem endpoints + Python ontology + marketplace + SDK); any change to shared crates must be verified by `test_v3_14_shared_core_unchanged` (COMPAT-03) and must not introduce leg-specific branches. Per D-44, this rule is non-negotiable.

---

## Milestone: v3.13 EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle) ✅ SHIPPED 2026-07-29 @ d0d83a23

[Full v3.13 milestone archived at `.planning/milestones/v3.13-ROADMAP.md`. v3.13 = EVOLUTION_PATH §三 Phase 5 SHIPPED. Tag `v3.13` annotated. **V310-COWORK-01 ✅ CLOSED**.]

---

## Milestone: v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 ✅ SHIPPED 2026-07-27

[Full v3.12 milestone archived at `.planning/milestones/v3.12-ROADMAP.md`. v3.12 = EVOLUTION_PATH §三 Phase 4 SHIPPED. Tag `v3.12` pushed at commit `894639dd`. **V310-A2A-01 + V310-SESSION-01 + V311-AUDIT-01 ✅ CLOSED**.]

---

## Milestone: v3.9 route-catalog RBAC wiring + authorization auditor ✅ SHIPPED 2026-07-26

**Goal:** Make `grid-server` route-by-route authorization **explicitly declared and statically enforced**. Every non-public business HTTP route is annotated with the `Action` it requires; every public route is on an explicit allowlist; a CI auditor fails any route that has neither. The `Action` enum is extended and the `Role × Action` matrix regenerated whenever the catalog reveals an action the current 7-Action vocabulary does not express. `AuthMode::None/ApiKey` semantics are unchanged; `AuthMode::Full` runs full per-route RBAC.

**Context (post-v3.8):** v3.8 demonstrated `requires(Action)` on 3 representative routes (`/admin/users`, `/audit`, `/sessions/{id}`) and shipped JWT + RBAC + tenant isolation. The remaining ~127 endpoints registered by `crates/grid-server/src/api/mod.rs` + `router.rs` have no `requires(...)` annotation. A new route can quietly bypass RBAC without detection. v3.9 closes that gap by making "every route has either an Action or a public marker" a CI-enforced invariant.

**Locked decisions (from v3.9 discussion — non-negotiable):**

- **D-01** Cover ALL non-public business HTTP routes. No protective carve-out.
- **D-02** Public routes get an explicit allowlist (compile-time `const` next to catalog).
- **D-03** CI static auditor enforces per-route invariants. Auditor PASS = required for merges.
- **D-04** `Action` vocabulary is extensible. New variants when semantic gap (ManageHooks / ManageMemories / ManageAudit / ManageConfig / ManageSecrets / ManageSandbox / ManageScheduler etc.) plus regenerated `Role × Action` matrix in `crates/grid-engine/src/auth/roles.rs`.
- **D-05** `AuthMode::None/ApiKey` semantics fully compatible — purely additive wiring; only `AuthMode::Full` runs the new per-route RBAC.
- **D-06** RouteCatalog structure is the source of truth; both manual-decorated-router and generate-catalog-from-router patterns are acceptable; catalog is `pub`.
- **D-07** No new external crate dependency.
- **D-08** No schema migration.
- **D-09** Shared-core rule (ADR-V2-023 P1) preserved — engine-layer changes leg-agnostic; verified by new test `test_rbac_engine_layer_is_leg_agnostic`.
- **D-10** Phase ladder: 03.9.0 (catalog/allowlist) → 03.9.1 (full wiring + matrix) → 03.9.2 (CI auditor + regression).

**Scope ladder (v3.7/v3.8 proven pattern — discuss → research → patterns → plan → plan-checker → execute → verify, batched into 3 phases):**

| # | Phase | Goal | Requirements | Success criteria |
|---|-------|------|--------------|------------------|
| **03.9.0** | Route catalog + public allowlist | `RouteCatalog` data structure + `allowlist` const + `build_catalog()` consuming `build_router()`; both decorated-router and generate-from-router patterns acceptable | CAT-01, CAT-02, CAT-04 | `RouteCatalog` exists at `crates/grid-server/src/rbac/catalog.rs`, lists every `api::routes()` endpoint; allowlist covers `/api/health`, `/api/health/live`, `/api/v1/auth/login`; hermetic test asserts `api::routes().len() == catalog.len()` |
| **03.9.1** | Full business-route wiring + Action matrix | Annotate every non-public business route with `Requires(Action)`; extend `Action` enum + regenerate `Role × Action` matrix when catalog surfaces an unmapped action; `AuthMode::None/ApiKey` paths untouched | RBAC-05, RBAC-06, RBAC-07, RBAC-08, CAT-03, MODE-01, MODE-02, MODE-03 | Every route in `api::routes()` has a `Requires(Action)`; Owner still always succeeds; Viewer cannot call non-Read; `test_auth_modes None/ApiKey` 8/8 still PASS (regression); all 8 v3.8 `test_full` cases still PASS |
| **03.9.2** | CI auditor + regression sweep | Static auditor binary or `cargo test -p grid-server --test route_auditor`; wired into `.github/workflows/ci.yml`; `make rbac-audit` target; dated `PRODUCTION_USABILITY_2026-07-25.md` walkthrough | AUD-01, AUD-02, AUD-03, TEST-07, TEST-08, TEST-09, DOC-04, DOC-05, DOC-06 | `make rbac-audit` exits 0; auditor self-test on synthetic unplugged route exits 1 with named report; v3.7 175-test baseline ASK-before-running per `feedback_no_full_tests`; v3.8 34/34 hermetic tests still PASS |

### Why this ladder

- **03.9.0 (catalog)** must come first — every later phase consumes the catalog structure.
- **03.9.1 (wiring)** — depends on 03.9.0 (catalog must exist before annotating routes); produces the green auditor PASS state.
- **03.9.2 (auditor + regression)** — final; the auditor catches future drift; the regression sweep proves `AuthMode` parity.

### Out of scope (deferred to v3.10+)

- **SSO / SAML / OIDC / OAuth2** — JWT + local creds only
- **Per-tenant Action policy override** — engine-layer Role × Action is global
- **Per-route custom predicates beyond Role** — structure lays down for future extension without rewrite
- **`grid-platform` route catalog audit** — separate milestone; v3.9 only audits `grid-server`
- **Rate limiting per Role** — `RateLimiter` left untouched
- **EAASP Phase 3 production OPA / Phase 4 A2A / Phase 5 L5 / Phase 6 ecosystem** — untouched
- **`web-platform/` Quality 7.5→9.0** — separate milestone
- **`grid-desktop` Quality 6.5→9.0** — separate milestone
- **Refresh-token rotation** — v3.8.1 §Out of scope; v3.9+=scope

### Risks & guards

- **R-1: Single-user / ApiKey regression** — D-05 requires bit-for-bit identical `AuthMode::None/ApiKey` behavior; existing `test_auth_modes 8/8` is the gate; verified in 03.9.1.
- **R-2: `grid-engine` shared-core bleed** — D-09; new `Action` variants must work for engine 接入面 (EAASP) and Grid 独立产品; verified by `test_rbac_engine_layer_is_leg_agnostic`.
- **R-3: Action vocabulary explosion** — D-04 lets us grow, but a "manage everything" catch-all is forbidden; each new Action must map to a coherent semantic. Auditor surfaces gaps in 03.9.1.
- **R-4: Catalog drift** — D-06 makes the catalog `pub` and the auditor its only enforcement. v3.9.2's CI job catches drift on every PR.
- **R-5: Full v3.7 baseline regression** — TEST-09 covers it but the full `cargo test --workspace` is gated behind `feedback_no_full_tests`; ASK before running per project rule.

### Shared core rule (ADR-V2-023 P1, retained)

Changes to `grid-engine`, `grid-runtime`, `grid-types`, `grid-sandbox`, `grid-hook-bridge` must work for both engine 接入面 (EAASP) and Grid 独立产品. v3.9 adds Action variants to `grid-engine::auth::roles::Action` and updates `Role::can` — these are engine-layer and must remain leg-agnostic. EAASP does not currently consume `Role::can(Action)` for HTTP routing, so extending variants is safe; D-09 test verifies.

---

## Milestone: v3.8 grid-server multi-user login (Tenant + RBAC + JWT) ✅ SHIPPED 2026-07-24

[Full v3.8 milestone archived at `.planning/milestones/v3.8-ROADMAP.md`. v3.8 = Grid 独立产品 activation milestone part 1. **3 security hotfixes (CRITICAL blacklist bypass / HIGH refresh stale-claim / HIGH audit IDOR) SHIPPED.**]

**Goal:** Take `grid-server` from `AuthMode::ApiKey` + `TenantContext::for_single_user` to a real multi-user tenancy: JWT-issued sessions carrying `tenant_id` + `role` claims, RBAC enforced at the route handler layer, cross-user session isolation. Auth surface stays as **Grid 独立产品** (per ADR-V2-024 双轴 framework — engine 接入面 uses EAASP's own auth, not Grid); types live in `grid-engine` and are shared but the JWT issuance/refresh/logout endpoints live only in `grid-server`.

**Context:** Auth primitives already exist: `AuthMode { None, ApiKey, Full }`, `Role { Viewer, User, Admin, Owner }`, `Action { Read, CreateSession, RunAgent, ManageMcp, ManageSkills, ManageUsers, ManageBilling }`, `Permission { Read, Write, Admin }`, complete `Role × Action` matrix in `crates/grid-engine/src/auth/roles.rs`. v3.8 wires enforcement and ships endpoints.

**Scope ladder (per v3.7 proven pattern — discuss → research → patterns → plan → plan-checker → execute → verify, batched into 4 phases):**

| # | Phase | Goal | Requirements | Success criteria |
|---|-------|------|--------------|------------------|
| **03.8.0** | JWT primitive + AuthMode::Full path | Mint + verify JWT with `tenant_id`/`user_id`/`role` claims; wire through existing middleware | AUTH-01, AUTH-04, AUTH-05 | hermetic mint+verify test, tampered signature → 401, missing claim → 401 |
| **03.8.1** | Login + refresh + logout endpoints + audit | `POST /auth/login` + `/auth/refresh` + `/auth/logout`; token blacklist; audit stamping | AUTH-02, AUTH-03, AUDIT-01 | 3 hermetic integration tests, audit rows carry tenant_id |
| **03.8.2** | RBAC route-layer enforcement + TenantContext::for_multi_user | `requires(Action)` middleware; cross-tenant scope enforcement | RBAC-01..04, TENANT-01..03, SESSION-01..03 | 6 hermetic tests (role escalation, cross-tenant block, list scoping, concurrent isolation, etc.) |
| **03.8.3** | Docs + UAT walkthrough + regression guard | USER_GUIDE §11, env-var reference, dated walkthrough, regression sweep | DOC-01..03, TEST-05, TEST-06 | 5/5 UAT, all v3.7 single-user tests still PASS in `GRID_MODE=single_user` |

### Why this ladder

- **03.8.0 (foundation)** must come first — every later phase depends on JWT verification working
- **03.8.1 (endpoints)** — surfaces the auth surface to clients; depends on 03.8.0
- **03.8.2 (RBAC + isolation)** — depends on 03.8.1 (because enforcement reads `req.extensions().get::<Claims>()` set by 03.8.1 middleware)
- **03.8.3 (docs + UAT + regression)** — final; writes dated evidence and verifies the single-user mode path is untouched

### Out of scope (deferred to v3.9+)

- **SSO / SAML / OIDC** — JWT + local creds only this milestone
- **`web-platform/` multi-tenant UI** wiring — separate milestone
- **`grid-desktop` 6.5→9.0** — untouched
- **`grid-platform` Quality 9.0 push** — already 9.0+ per v3.7 audit, no scope here
- **EAASP Phase 3 production OPA / Phase 4 A2A / Phase 5 L5 / Phase 6 ecosystem** — untouched
- **OAuth2 Authorization Code / PKCE** — JWT-only this milestone
- **Full route-catalog `requires(Action)` wiring** — `crates/grid-server/src/api/mod.rs` + `router.rs` have ~130 endpoints; v3.8.2 demonstrated on 3; remaining ~127 → v3.9

### Risks & guards

- **R-1: Single-user regression** — `GRID_MODE=multi_user` opt-in; default = `single_user`; existing 175/175 tests from v3.7 must still PASS
- **R-2: `grid-engine` shared-core bleed** — per ADR-V2-023 P1; only ADD to `AuthConfig` (new `multi_user_tenant_ids` field); never delete or rename existing fields
- **R-3: JWT secret hardcoding** — `GRID_JWT_SECRET` fail-fast per ADR-V2-028 strict-by-default
- **R-4: Cross-tenant data leak** — every handler that reads a resource by id MUST use `OwnedResource::fetch(tenant_id, id)`; covered by `requires(Read)` middleware that injects `Claims`; verified in 03.8.2 isolated tests

### Shared core rule (ADR-V2-023 P1, retained)

Changes to `grid-engine`, `grid-runtime`, `grid-types`, `grid-sandbox`, `grid-hook-bridge` must work for both engine 接入面 (EAASP) and Grid 独立产品. v3.8 only ADDs to `grid-engine::auth::AuthConfig`; does not break engine-facing path.

---

## Milestone: Grid 独立产品 Activation ✅ SHIPPED

[Full activation milestone archived at `.planning/milestones/activation-ROADMAP.md`.]

**Goal:** Activate the dormant Grid independent product leg per ADR-V2-024. All technical debt cleared (DEFERRED_LEDGER.md 100% ✅ CLOSED). Shift from debt-sweep mode to product-building mode.

**Context:** Grid has been built primarily through its engine 接入面 (EAASP integration). The independent product crates (`grid-server`, `grid-platform`, `grid-desktop`, `web/`, `web-platform/`, `grid-eval`) exist but are dormant — scaffolding or partially-featured. The engine layer is production-ready. Now activate the product surface.

**Activation targets (priority-ordered per ADR-V2-024 Open Item #3):**

| Crate/App | Current State | Score | Activation Needed |
|-----------|--------------|-------|-------------------|
| **grid-cli** | 16 commands, full TUI, streaming, 140+ tests | 8/10 | Eval bridge stubs, MCP logs, config persist |
| **web/** (single-user UI) | 8 tabs, WS streaming, Markdown, 20k LOC | 7/10 | Remove mocks, standardize errors, add tests, sidebar |
| **grid-server** | ~130 endpoints, HMAC/JWT auth, WS protocol | 6/10 | Wire RBAC, fix ApiError, budget, context, hot-reload |
| **grid-platform** | JWT auth, tenant isolation, 25 routes | 6/10 | Tests, rate limiting, proper errors |
| **grid-eval** | 8 scorers, 12 suites, multi-model compare | 7/10 | Web UI, CI, parallel runner |
| **grid-desktop** | Tauri 2 shell, tray, 6 IPC | 3/10 | Agent/session IPC, asset bundling |
| **web-platform/** (multi-tenant UI) | Auth layer, basic chat, no Markdown | 3/10 | Chat history, Markdown, ErrorBoundary, dashboard fix |

**Shared core rule (ADR-V2-023 P1):** changes to `grid-engine`, `grid-runtime`, `grid-types`, `grid-sandbox`, `grid-hook-bridge` must work for both engine 接入面 and Grid independent product.

### Phase Plan (refined from A.0 audit)

#### Wave 1: Single-User Workbench (priority targets per ADR-V2-024)

- [x] **Phase A.1: grid-server Hardening** — Wire RBAC middleware to all routes, replace ad-hoc error tuples with `ApiError`, fix budget endpoint to read real usage, fix context snapshot/zones to read live session, make CORS/log_level hot-reload effective, remove deprecated `/ws` legacy path. *8 P1 gaps, 3-4 plans.*
- [x] **Phase A.2: web/ Production Polish** — Remove MCP mock fallbacks, standardize error handling (toast everywhere), add Vitest + critical-path tests, replace `window.__GRID_TOKEN` with config-based token, add sidebar + settings. *7 P2 gaps, 3-4 plans.*
- [x] **Phase A.3: grid-cli Final Polish** — Implement eval bridge (connect CLI eval commands to grid-eval library), MCP live log streaming, `config set` persistence, doctor `--repair` for all 10 checks. *4 P2/P3 gaps, 2 plans.*

#### Wave 2: Multi-Tenant Platform

- [x] **Phase A.4: Cross-Cutting Foundation** — Merge web/ and web-platform/ design system (shared ApiClient, components, theme tokens). Standardize brand name to "Grid" (from "Octo"). *1 plan.*
- [x] **Phase A.5: grid-platform Hardening** — Full test coverage (auth, API handlers, tenant lifecycle), rate limiting per tenant, proper `ErrorCode` enum replacing `String`. *3 P3 gaps, 2 plans.*
- [x] **Phase A.6: web-platform/ Production** — Fix chat history loading, add Markdown rendering (reuse web/ components), add ErrorBoundary + toast system, fix dashboard stats copy-paste bug, wire user profile button. *6 P2/P3 gaps, 3 plans.*

#### Wave 3: Desktop + Eval

- [x] **Phase A.7: grid-desktop Feature Work** — Add IPC commands for agent/session interaction, bundle frontend assets in app, fix auto-updater endpoint. *3 P3 gaps, 2 plans.*
- [x] **Phase A.8: grid-eval Web UI** — Build web dashboard for eval results, CI integration (GitHub Actions workflow), parallel runner. *3 features, 2 plans.*

### Dependencies

```
A.1 grid-server ──┬── A.2 web/ polish
                  │
                  ├── A.4 cross-cutting foundation ──┬── A.5 grid-platform ── A.6 web-platform/
                  │                                  │
                  └── A.3 grid-cli polish             └── A.7 grid-desktop (after A.6)

A.8 grid-eval — independent, can run anytime with web/ components
```

### Success Criteria

1. grid-server: RBAC wired, ApiError used consistently, budget/context endpoints functional, hot-reload works
2. web/: no mock fallbacks, consistent error handling, tests passing, sidebar + settings
3. grid-cli: eval commands functional (not stubs), all doctor checks repairable
4. web-platform/: chat history loads, Markdown renders, dashboard shows real data
5. grid-platform: test coverage ≥70%, rate limiting active
6. grid-desktop: can start/stop agents from desktop IPC
7. grid-eval: web dashboard shows results, CI workflow runs on PR

---

## Progress

| Phase | Plans | Status | Priority |
|-------|-------|--------|----------|
| A.0 Audit & Scoping | 1/1 | ✅ Complete | — |
| A.1 grid-server Hardening | 1/1 | ✅ Complete | P1 |
| A.2 web/ Production Polish | 1/1 | ✅ Complete | P1 |
| A.3 grid-cli Final Polish | 1/1 | ✅ Complete | P1 |
| A.4 Cross-Cutting Foundation | 1/1 | ✅ Complete | P2 |
| A.5 grid-platform Hardening | 1/1 | ✅ Complete | P2 |
| A.6 web-platform/ Production | 1/1 | ✅ Complete | P2 |
| A.7 grid-desktop Feature Work | 1/1 | ✅ Complete | P3 |
| A.8 grid-eval CI Enhancement | 1/1 | ✅ Complete | P3 |
| **03.9.0** Route catalog + public allowlist | 1/1 | ✅ Complete | v3.9 P1 |
| **03.9.1** Full business-route wiring + Action matrix | 1/1 | ✅ Complete | v3.9 P1 |
| **03.9.2** CI auditor + regression sweep | 1/1 | ✅ Complete | v3.9 P1 |
| **03.10.0** Skeleton audit + alignment matrix | 1/1 | ✅ Complete | v3.10 |
| **03.10.1** MAT axis | 1/1 | ✅ Complete | v3.10 |
| **03.10.2** PIPE axis | 1/1 | ✅ Complete | v3.10 |
| **03.10.3** VERIFY axis | 1/1 | ✅ Complete | v3.10 |
| **03.11.0** OPA sidecar infrastructure | 1/1 | ✅ Complete | v3.11 |
| **03.11.1** L3 OPA backend adapter + Rego templates | 1/1 | ✅ Complete | v3.11 |
| **03.11.2** 5-stage approval state machine | 1/1 | ✅ Complete | v3.11 |
| **03.11.3** single-point live walkthrough | 1/1 | ✅ Complete | v3.11 |
| **03.12.0** Schema + audit constraint patch | 1/1 | ✅ Complete | v3.12 |
| **03.12.1** Event Room + multi-session | 1/1 | ✅ Complete | v3.12 |
| **03.12.2** A2A Router | 1/1 | ✅ Complete | v3.12 |
| **03.12.3** single-point live walkthrough | 1/1 | ✅ Complete | v3.12 |
| **03.13.0** four-card data model + projection + L4 SSE bridge | 1/1 | ✅ Complete | v3.13 |
| **03.13.1** four-card SSE fan-out + state transitions + persistence | 1/1 | ✅ Complete | v3.13 |
| **03.13.2** retrospective cycle (trace API) | 1/1 | ✅ Complete | v3.13 |
| **03.13.3** single-point live walkthrough + tag v3.13 | 1/1 | ✅ Complete | v3.13 |
| **03.14.0** Ontology 服务 + taxonomy 路径 + cross-domain link + JSON-schema 派生 | 1/1 | ✅ Complete v3.14 | v3.14 |
| **03.14.1** Skill Marketplace API + 第三方提交 / 4 阶段 promotion / 完整 ACL / analytics | 1/1 | ✅ Complete v3.14 | v3.14 |
| **03.14.2** SDK scaffolding + JSON-schema 暴露 | 1/1 | ✅ Complete v3.14 | v3.14 |
| **03.14.3** single-point live walkthrough + tag v3.14 + EVOLUTION_PATH 8-Phase 路线 ALL SHIPPED | 1/1 | ✅ Complete v3.14 | v3.14 |

---

## Coverage Index

To be populated after Phase A.0 audit — REQ-IDs will map to specific gaps discovered.

---

*Last updated: 2026-07-28 — v3.14 EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem bootstrapped (4-phase ladder 03.14.0 → 03.14.3, 13–16 REQ-IDs / 5 categories, locked decisions D-38..D-46). v3.13 EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle) ✅ SHIPPED 2026-07-29 @ d0d83a23 (4-phase ladder 03.13.0 → 03.13.3, 13+ REQ-IDs / 5 categories, tag `v3.13` annotated, V310-COWORK-01 ✅ CLOSED). v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 ✅ SHIPPED 2026-07-27 @ 894639dd (4 phases, 13–16 REQ-IDs / 5 categories, tag `v3.12` pushed). v3.11 EAASP Phase 3 — production OPA backend + 5-stage approval chain SHIPPED 2026-07-27 (29/29 REQ-IDs, 4 phases, archived). v3.10 EAASP v2.0 platform-skeleton alignment SHIPPED 2026-07-26 (16 REQ-IDs, 4 phases, archived). v3.9 SHIPPED 2026-07-26; v3.8 SHIPPED 2026-07-24; v3.7 SHIPPED 2026-07-23.*
