# Grid — Roadmap

> **Latest shipped milestone:** v3.9 route-catalog RBAC wiring + authorization auditor ✅ 2026-07-26
> **Latest shipped milestone:** v3.10 EAASP v2.0 platform-skeleton alignment ✅ 2026-07-26
> **Latest shipped milestone:** v3.11 EAASP Phase 3 — production OPA backend + 5-stage approval chain ✅ 2026-07-27
> **Latest shipped milestone:** v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 ✅ 2026-07-27
> **Current active milestone:** v3.13 EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle) (bootstrapping 2026-07-28)
> **Archive:** `milestones/v3.4-ROADMAP.md`, `milestones/v3.5-ROADMAP.md`, `milestones/v3.7-ROADMAP.md`, `milestones/v3.8-ROADMAP.md`, `milestones/v3.9-ROADMAP.md`
> **Current project root:** details in `.planning/PROJECT.md` §Current Milestone + `.planning/REQUIREMENTS.md` v3.13 section.

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

---

## Milestone: v3.13 EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle) (bootstrapping 2026-07-28)

**Goal:** Begin EAASP v2.0 EVOLUTION_PATH §三 Phase 5 by delivering the **L5 Cowork UI substrate** as a four-card projection layer (Event / Evidence / Action / Approval) plus a **retrospective cycle** (回溯闭环) that lets any four-card record trace back to its full Event → Evidence → Action → Approval chain by `session_id`. v3.13 does NOT build a frontend (web/ + web-platform/ remain dormant); it lands a simulator-level backend + projection at `tools/eaasp-l5-cowork/` that derives the four cards from already-shipped L2 evidence anchor + L3 governance_decisions + L4 event_room_events + A2A review.closed events. v3.13.0 establishes the four-card data model + projection + L4 SSE bridge; v3.13.1 wires four-card SSE fan-out + state transitions + persistence; v3.13.2 builds the retrospective cycle (trace API); v3.13.3 is a single-point live walkthrough that demonstrates the full Phase 5 surface and pushes tag `v3.13`.

**Context (post-v3.12):** v3.12 SHIPPED the Event Room + multi-session coordination + A2A Router + audit.py CHECK constraint patch (including `await_human` for paused-state audit evidence). The data needed for an L5 Cowork UI is now in place — every L2 piece of evidence has an anchor, every L3 governance decision has a row, every L4 Event Room event has a `session_id` + `room_id`, every A2A dispatch has a `cross_session` audit row. v3.13's job is to project these four orthogonal data dimensions into a single Cowork substrate that operators can pivot on `session_id`. Per `EAASP_v2_0_EVOLUTION_PATH.md` §三 Phase 5: spec §4 (L5 Cowork UX) + §4.4 (four-card UI). Closes V310-COWORK-01.

**Locked decisions (from v3.13 discussion — non-negotiable):**

- **D-30** v3.13 scope = EAASP Phase 5 L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle). Per `EAASP_v2_0_EVOLUTION_PATH.md` §三 Phase 5 (spec §4 + §4.4). Closes V310-COWORK-01. v3.14+ = Phase 6 ecosystem expansion (V310-ECOSYSTEM-01 / V310-MAT-01).
- **D-31** L5 仍以 EAASP v2.0 spec §4 + §4.4 为权威源;本仓前端 (web/ + web-platform/) 仍为 dormant 状态;v3.13 在 `tools/eaasp-l5-cowork/` (新建) 落模拟器级四卡 backend + projection. UI activation deferred to a separate future milestone. CLAUDE.md §Frontend status + D-27 carry-over.
- **D-32** 四卡全部派生自 v3.12 已落地的 L2 evidence anchor + L3 governance_decisions + L4 event_room_events + A2A review.closed 事件;不新建独立存储. v3.13 = projection + 视图层;底层仍是 v3.7.3 / v3.10 / v3.11 / v3.12 既有数据. No new tables, no new columns, no new event types.
- **D-33** 回溯闭环 (retrospective cycle) = 任何四卡 record 都能以 `session_id` 为根 trace 到 Event → Evidence → Action → Approval 全链;新增 `tools/eaasp-l5-cowork/retrospective.py` 提供 trace API (`trace_session(session_id) -> RetrospectiveChain`). Trace is read-only, idempotent, bounded by tenant.
- **D-34** 仍以 Phase 0.5 MVP 人工可执行性为最低标尺 (threshold-calibration skill + `make dev-eaasp`);v3.13 extends the same MVP floor with a four-card walkthrough scenario.
- **D-35** v3.9 / v3.10 / v3.11 / v3.12 硬约束不动 — Owner-only 边界 / AuthMode 兼容 / CI 顺序 / grid-engine 共享核心 / ADR-V2-023 P1 / ADR-V2-028 / ADR-V2-034 OPA sidecar / v3.11.2 5-stage approval / v3.12.1 Event Room ContextVar 鉴权 / v3.12.2 A2A Router + ReviewSet 全部保留. v3.9 RBAC + v3.10 spec-audit + ADR-V2-034 OPA sidecar + v3.12 Event Room + v3.12 A2A Router all continue to PASS.
- **D-36** 探索策略 = Explore + Grep (本仓无 `.codegraph/`). Same as v3.12 D-29.
- **D-37** v3.13 不开新前端 (react/typescript);不开新服务端口;仍 `tools/eaasp-*/` 模拟器级实现. v3.13 lives in `tools/eaasp-l5-cowork/` (Python module) + `tools/eaasp-cli-v2/` (CLI command extension). The `L5 /v1/cowork/trace/{session_id}` endpoint sits behind the existing EAASP L4 service port.

**Scope ladder (4 phases, recommended ordering that puts projection first):**

| # | Phase | Goal | Requirements | Success criteria |
|---|-------|------|--------------|------------------|
| **03.13.0** | four-card data model + projection + L4 SSE bridge | `EventCard` / `EvidenceCard` / `ActionCard` / `ApprovalCard` projection types in `tools/eaasp-l5-cowork/src/eaasp_l5_cowork/cards.py`; each card derives fields via SELECT from existing L2 / L3 / L4 / A2A tables (D-32); L4 SSE bridge emits `cowork.card.<type>.<event>` events mirroring the underlying L2 / L3 / L4 envelope shape | CARD-EVENT-01, CARD-EVENT-02, CARD-EVENT-03, CARD-EVIDENCE-01, CARD-EVIDENCE-02, CARD-EVIDENCE-03, CARD-ACTION-01, CARD-ACTION-02, CARD-ACTION-03, CARD-APPROVAL-01, CARD-APPROVAL-02, CARD-APPROVAL-03, COMPAT-01, COMPAT-02, COMPAT-03, COMPAT-04, COMPAT-05, TRACE-02 | All 12 cards (3 per type) ship with `list_*_cards(session_id)` accessors; each card's fields traceable to a SELECT statement; cross-table count parity asserted by `test_four_card_projection_is_derived.py`; L4 SSE bridge emits `cowork.card.<type>.<event>` events; `make rbac-audit` + `make v3.10-spec-audit` + `make v2-phase3-e2e-rust` PASS |
| **03.13.1** | four-card SSE fan-out + state transitions + persistence | Fan `cowork.card.<type>.<event>` to all sessions bound to the same Event Room (matching v3.12.1 EVENT-ROOM-02 fan-out contract); card state transitions (`pending → confirmed → acted`) persist as L3 governance_decisions rows | CARD-EVENT-02 (SSE extension), CARD-APPROVAL-02 (state transitions), COMPAT-01, COMPAT-02, COMPAT-03, COMPAT-04, TRACE-01, TRACE-02 | SSE fan-out delivers to all bound sessions; state transitions persist to L3 ledger; cross-tenant leakage impossible by construction; v3.12.1 EVENT-ROOM regression PASS |
| **03.13.2** | retrospective cycle (trace API) | `tools/eaasp-l5-cowork/src/eaasp_l5_cowork/retrospective.py` exposes `trace_session(session_id) -> RetrospectiveChain` carrying all four card lists in canonical order + `cross_refs` linking each card to its upstream causes; `L5 /v1/cowork/trace/{session_id}` HTTP endpoint (RBAC: existing `Read` Action); `eaasp cowork trace {session_id}` CLI command (extends `tools/eaasp-cli-v2/`) | RETROSPECTIVE-01, RETROSPECTIVE-02, RETROSPECTIVE-03, RETROSPECTIVE-04, RETROSPECTIVE-05, COMPAT-01, COMPAT-02, COMPAT-03, COMPAT-04, TRACE-01, TRACE-02 | `trace_session` returns full chain; idempotent (invoked twice returns same chain); bounded by tenant (cross-tenant 403); CLI command prints human-readable four-card trace; `test_retrospective_idempotent.py` PASS |
| **03.13.3** | single-point live walkthrough + tag v3.13 | End-to-end live walkthrough against real OPA sidecar + Event Room + A2A Router + four-card projection; reproduces paused-state audit evidence end-to-end; v3.9 / v3.10 / ADR-V2-034 / v3.12 Event Room + A2A Router regression sweep; tag `v3.13` pushed | TRACE-01 (final), TRACE-02 (final), TRACE-03, COMPAT-01..05 (final), RETROSPECTIVE-04 (final) | `docs/status/PRODUCTION_USABILITY_2026-07-29.md` captures: (1) four-card projection holds under live OPA sidecar + Event Room + A2A Router, (2) `trace_session(session_id)` returns complete chain for any v3.12+v3.13 session_id, (3) `make rbac-audit` + `make v3.10-spec-audit` + `make v2-phase3-e2e-rust` PASS post-v3.13, (4) tag `v3.13` pushed. **V310-COWORK-01 → ✅ CLOSED** |

### Why this ladder

- **03.13.0 (projection)** MUST come first — without the projection layer, 03.13.1 SSE fan-out has no contract surface to target, and 03.13.2 retrospective trace cannot walk a complete four-card chain. The four-card data model + projection is the foundational contract that 03.13.1 / 03.13.2 / 03.13.3 all consume.
- **03.13.1 (SSE fan-out + state transitions)** — depends on 03.13.0 (projection must exist before fan-out can target it); wires SSE fan-out for new four-card events + state transitions (e.g. `pending → confirmed → acted`) and persistence to existing L4 storage.
- **03.13.2 (retrospective trace API)** — depends on 03.13.0 + 03.13.1 (trace must walk a complete four-card chain including state transitions); exposes `trace_session(session_id)` + `L5 /v1/cowork/trace/{session_id}` HTTP endpoint + `eaasp cowork trace {session_id}` CLI command.
- **03.13.3 (live walkthrough + tag v3.13)** — final; reproduce the four-card walkthrough end-to-end against real OPA sidecar + Event Room + A2A Router + four-card projection; push tag `v3.13`.

### Out of scope (deferred to v3.14+)

- **Phase 6 ecosystem expansion** — V310-ECOSYSTEM-01 / V310-MAT-01; v3.14+ scope.
- **L1 infrastructure tier changes (gVisor / Firecracker / Kata)** — V310-SANDBOX-01; long-term.
- **NATS JetStream backend for EventStream** — D75; long-term.
- **Actual L5 Cowork UI (React + Tailwind)** — separate milestone; web/ + web-platform/ remain dormant (D-31). v3.13 only ships the Python projection layer + CLI command.
- **Cross-room retrospective trace** — v3.13 trace is per-session; cross-room chained trace deferred to v3.13.2+ refinement.
- **Multi-role per user / SSO / refresh-token rotation / per-tenant Action policy override** — out of v3.13.
- **New service ports / new repository** — D-37 forbids; v3.13 stays in `tools/eaasp-*/` and reuses the existing 7 EAASP services on `.grid/dev-eaasp-live.sh` launch topology.
- **Schema migration beyond the existing L2 / L3 / L4 / A2A tables** — D-32 forbids; v3.13 = projection layer only.
- **Proto contract widening** — D-13 / D-21 carry-over; v3.13 reconciles to existing 21 RPC only.
- **L1 runtime additions or substitutions** — the 7-runtime matrix is frozen for v3.13.
- **`web-platform/` Quality 7.5→9.0** — separate milestone (carried forward).
- **`grid-desktop` Quality 6.5→9.0** — separate milestone (carried forward).
- **`grid-platform` route catalog audit** — separate milestone (carried forward).
- **Cross-tenant retrospective trace** — D-30 / D-32 confine v3.13 to per-tenant, per-session trace; cross-tenant grouping deferred.

### Risks & guards

- **R-1: Four-card projection is silently wrong (the core v3.13 risk)** — D-32 forbids new storage; if the projection layer reads from the wrong source table or omits rows, the L5 Cowork UI cannot be built on top. Guard: 03.13.0 MUST produce `test_four_card_projection_is_derived.py` asserting cross-table count parity (TRACE-03); each card's fields must trace to a specific SELECT statement.
- **R-2: `contract-v1.2.0` regression** — D-13 / D-21 carry-over; the existing 21 RPC contract + 7 L1 runtime certifier must remain green. Guard: COMPAT-01 (proto wire-compat) + COMPAT-02 (`make v2-phase3-e2e-rust`) verified in 03.13.0 / 03.13.1 / 03.13.2 / 03.13.3 gates.
- **R-3: `grid-engine` shared-core bleed** — D-35; any change to `grid-types` / `grid-engine` / `grid-sandbox` / `grid-hook-bridge` must remain leg-agnostic. Guard: `test_v3_13_shared_core_unchanged` (new, COMPAT-03) snapshots public API surface pre/post v3.13.
- **R-4: Spec drift** — D-12 carry-over; EAASP v2.0 spec §4 + §4.4 are the Phase 5 sections. Guard: 03.13.0 `tools/eaasp-spec-alignment/ALIGNMENT_MATRIX.md` update (TRACE-02) lists every `### §N.M` section touched with `(status, v3.13_phase, post_v3.13_owner)`.
- **R-5: Certifier scope creep** — D-13 / D-21 carry-over; v3.13 reconciles to existing 21 RPC only. Guard: COMPAT-01 verified by `cargo test -p eaasp-certifier` PASS state pre/post each phase; new spec sections deferred.
- **R-6: Phase 3 OPA + Phase 4 A2A / Event Room regression** — D-35; the OPA sidecar + Event Room + A2A Router + 5-stage approval state machine + audit.py CHECK constraint patch must remain green through v3.13. Guard: COMPAT-04 (ADR-V2-034 + v3.12) verified at every phase; v3.11.2 / v3.12 regression tests PASS.
- **R-7: Phase 5 L5 Cowork UI slip into actual frontend work** — D-31 / D-37 confine v3.13 to projection layer + CLI command; no React/TypeScript frontend. Guard: any PR touching web/ or web-platform/ blocked by reviewer; the OOS list above is the single source of truth.
- **R-8: Retrospective trace race / cross-tenant leakage** — D-33 requires bounded-by-tenant trace; cross-tenant trace must be rejected with 403 (RETROSPECTIVE-05). Guard: `test_trace_cross_tenant_forbidden` + `test_retrospective_idempotent.py` (RETROSPECTIVE-04).
- **R-9: 03.13.3 live walkthrough blocked on missing LLM API key** — same blocker as v3.10 / v3.11 / v3.12. Guard: hermetic in-process walkthrough (using the same v3.7.3 threshold-calibration skill + v3.12 Event Room + A2A Router) is the executable baseline (D-34); live walkthrough captures whatever subset is reproducible given the LLM credential.

### Shared core rule (ADR-V2-023 P1, retained)

Changes to `grid-engine`, `grid-runtime`, `grid-types`, `grid-sandbox`, `grid-hook-bridge` must work for both engine 接入面 (EAASP) and Grid 独立产品. v3.13 is engine-axis work (L4 SSE bridge + retrospective trace Python module + CLI command); any change to shared crates must be verified by `test_v3_13_shared_core_unchanged` (COMPAT-03) and must not introduce leg-specific branches. Per D-35, this rule is non-negotiable.

---

## Milestone: v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 ✅ SHIPPED 2026-07-27

**Goal:** Begin EAASP v2.0 EVOLUTION_PATH §三 Phase 4 by delivering the **A2A Router** (agent-to-agent coordination across multiple sessions) and **Event Room** (multi-session event coordination that V310-A2A-01 deferred from v3.10 and V310-SESSION-01 deferred from v3.10 require). The milestone also closes a real bug surfaced during the v3.11 single-point live walkthrough (§7 of `docs/status/PRODUCTION_USABILITY_2026-07-27.md`): `audit.py`'s CHECK constraint on `governance_decisions.decision` does not include the `await_human` sentinel value emitted by the 5-stage approval state machine at the Approve stage. v3.12.0 patches the schema first (idempotent `ALTER TABLE` migration per D-26); v3.12.1 lands the Event Room + multi-session coordination; v3.12.2 lands the A2A Router; v3.12.3 is a single-point live walkthrough that demonstrates the whole Phase 4 surface.

**Context (post-v3.11):** v3.11 SHIPPED the production OPA sidecar + L3 OPA backend + 5-stage approval state machine + single-point live walkthrough. 29/29 REQ-IDs closed. The v3.11.3 walkthrough surfaced an architectural finding: the `await_human` sentinel value emitted by the 5-stage state machine at the Approve stage (Phase 0.5 MVP human-in-the-loop pause) cannot be persisted to the L3 audit ledger because `audit.py`'s CHECK constraint allowlist does not include it. Until v3.12.0 patches the schema, paused-state audit evidence cannot be reproduced end-to-end. Separately, V310-A2A-01 + V310-SESSION-01 in `docs/design/EAASP/DEFERRED_LEDGER.md` are the deferred Phase 4 items (`📦 deferred_to_v3.12+ / Phase 4`). v3.12 is the 4-phase ladder recommended by v3.10's EVOLUTION_PATH-aligned sequencing: v3.10 (alignment) → v3.11 (Phase 3 OPA + 5-stage) → v3.12 (Phase 4 A2A + Event Room + multi-session).

**Locked decisions (from v3.12 discussion — non-negotiable):**

- **D-23** `audit.py` CHECK constraint patch is mandatory phase 0. v3.11.3 live walkthrough §7 surfaced that `audit.py`'s CHECK constraint on `governance_decisions.decision` does not include `await_human`; the 5-stage state machine emits `await_human` at the Approve stage; without this fix, 03.12.1 / 03.12.2 / 03.12.3 cannot reproduce paused-state audit evidence. v3.12.0 MUST patch the schema first; no implementation work in 03.12.1 / 03.12.2 may proceed before 03.12.0 ships. Closes `V311-AUDIT-01`.
- **D-24** v3.12 scope = EAASP Phase 4. v3.12 delivers A2A Router + Event Room + multi-session coordination per EAASP_v2_0_EVOLUTION_PATH.md §三 Phase 4 scope (spec §5.3 / §14 / §17). Closes V310-A2A-01 + V310-SESSION-01 + V311-AUDIT-01. v3.13+ = Phase 5 L5 / Phase 6 ecosystem.
- **D-25** MVP executable baseline (`threshold-calibration` skill + `make dev-eaasp`) + new A2A coordination walkthrough scenario. v3.12 adds a new A2A coordination walkthrough scenario on top of the Phase 0.5 MVP floor.
- **D-26** `audit.py` CHECK constraint extension uses idempotent `ALTER TABLE` migration (matching v3.11.2 `stage` column pattern). No destructive schema work. No new tables / no new columns beyond the CHECK constraint extension.
- **D-27** v3.12 stays in `tools/eaasp-*/` simulator-level implementations. No new repo / no new service port. Reuses the existing 7 EAASP services on `.grid/dev-eaasp-live.sh`.
- **D-28** v3.9 route-catalog RBAC (134 routes / `make rbac-audit`) + v3.10 spec-audit (4 files / 37 rows / `make v3.10-spec-audit`) + ADR-V2-023 P1 shared-core rule + ADR-V2-034 OPA sidecar ALL continue to PASS through every v3.12 phase. (D-28)
- **D-29** 探索策略 = Explore + Grep. No `.codegraph/` in this repo; no MCP codegraph tool available. (D-29)

**Scope ladder (4 phases, recommended ordering that puts schema first):**

| # | Phase | Goal | Requirements | Success criteria |
|---|-------|------|--------------|------------------|
| **03.12.0** ✅ | Schema + audit constraint patch | Extend `audit.py` CHECK constraint on `governance_decisions.decision` to include `await_human` via idempotent `ALTER TABLE` migration; update in-process enum validation; add `DECISION_AWAIT_HUMAN` sentinel constant | SCHEMA-01 ✅, SCHEMA-02 ✅, SCHEMA-03 ✅, MIGRATION-01 ✅, MIGRATION-02 ✅, AWAIT-HUMAN-01 ✅, AWAIT-HUMAN-02 ✅, COMPAT-01..04 ✅, TRACE-02 ✅ | `await_human` row persists to L3 ledger; idempotent migration verified by re-running on existing DB; existing v3.11.2 / v3.11.3 rows preserved (column NULL by default); `test_audit_decision_allowlist_contains_await_human` PASS; `test_audit_alter_table_migration_idempotent` PASS; `make rbac-audit` + `make v3.10-spec-audit` + `make v2-phase3-e2e-rust` PASS |
| **03.12.1** ✅ | Event Room + multi-session | Build `EventRoom` abstraction in `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/event_room.py`; multi-session event fan-out via `EventRoom.fan_out_event(...)`; L4 SSE extension adds `governance.session.cross` event family; `L4 /v1/rooms/{room_id}/sessions/{session_id}/events` endpoint with `ManageRooms` Action variant | EVENT-ROOM-01 ✅, EVENT-ROOM-02 ✅, EVENT-ROOM-03 ✅, SESSION-01 ✅, SESSION-03 ✅, COMPAT-01 ✅, COMPAT-02 ✅, COMPAT-03 ✅, COMPAT-04 ✅, TRACE-01 ✅ | `EventRoom.create/bind_session/list_sessions/list_rooms` public; fan-out delivers to all bound sessions; cross-tenant leakage impossible by construction; v3.11.2 `test_governance_sse.py` PASS (regression); TRACE-01 mid-milestone update |
| **03.12.2** ✅ | A2A Router | Build `A2ARouter` in `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/a2a_router.py`; `A2ARouter.dispatch(from_session_id, to_session_id, payload, evidence_refs)` runs through v3.7.3 governance gate + v3.11.2 5-stage approval state machine; cross-session fan-out via Event Room; `L4 /v1/rooms/{room_id}/sessions/{session_id}/dispatch` endpoint | A2A-01 ✅, A2A-02 ✅, A2A-03 ✅, A2A-04 ✅, SESSION-02 ✅, SESSION-03 ✅, COMPAT-01 ✅, COMPAT-02 ✅, COMPAT-03 ✅, COMPAT-04 ✅, TRACE-01 ✅ | 5 SSE events with `cross_session: true` field; 5 rows in `governance_decisions` ledger (including `await_human` row at Approve stage); cross-room / cross-tenant dispatch rejected with 403; `audit ledger pivotable on cross_session=True` |
| **03.12.3** ✅ | single-point live walkthrough | End-to-end live walkthrough against real OPA sidecar; reproduces paused-state audit evidence; cross-session A2A dispatch end-to-end; v3.9 / v3.10 / ADR-V2-034 regression sweep | LIVE-01 ✅ (v3.12-context), LIVE-02 ✅ (v3.12-context), LIVE-03 ✅ (v3.12-context), LIVE-04 ✅ (v3.12-context), TRACE-01 ✅ (final), TRACE-02 ✅ (final) | `docs/status/PRODUCTION_USABILITY_2026-07-28.md` captures: (1) `await_human` row persisted, (2) Event Room fans across 2+ sessions, (3) A2A dispatch end-to-end with paused Approve stage, (4) `make rbac-audit` + `make v3.10-spec-audit` + `make v2-phase3-e2e-rust` PASS; **V310-A2A-01 + V310-SESSION-01 + V311-AUDIT-01 → ✅ CLOSED** |

### Why this ladder

- **03.12.0 (schema)** MUST come first — without the `await_human` row persisting, 03.12.1 / 03.12.2 / 03.12.3 cannot reproduce paused-state audit evidence. The audit row is the canonical evidence of the human-in-the-loop pause; if it can't be written, the pause is invisible to the audit ledger.
- **03.12.1 (Event Room)** — depends on 03.12.0 (rows may carry `await_human` + `stage`); establishes the Event Room namespace that the A2A Router dispatches into.
- **03.12.2 (A2A Router)** — depends on 03.12.1 (Event Room as dispatch target); wires the same v3.7.3 governance gate + v3.11.2 5-stage approval chain into the A2A dispatch path.
- **03.12.3 (live walkthrough)** — final; reproduce the awaited-state audit evidence end-to-end against real OPA sidecar + Event Room + A2A Router.

### Out of scope (deferred to v3.13+)

- **Phase 5 L5 Cowork UI** — V310-COWORK-01; v3.13 scope (D-30).
- **Phase 6 ecosystem expansion** — V310-ECOSYSTEM-01 / V310-MAT-01; v3.14+ scope.
- **L1 infrastructure tier changes (gVisor / Firecracker / Kata)** — V310-SANDBOX-01; long-term.
- **NATS JetStream backend for EventStream** — D75; long-term.
- **Cross-tenant A2A dispatch** — out of v3.12; v3.13+ scope.
- **`web-platform/` Quality 7.5→9.0** — separate milestone (carried forward).
- **`grid-desktop` Quality 6.5→9.0** — separate milestone (carried forward).
- **`grid-platform` route catalog audit** — separate milestone (carried forward).
- **Schema migration beyond the audit CHECK constraint** — D-26 carry-over.
- **New service ports / new repository** — D-27 forbids.

### Risks & guards

- **R-1: Audit CHECK constraint migration breaks existing DBs** — D-26 requires idempotent `ALTER TABLE` migration matching the v3.11.2 `stage` column pattern. Guard: `test_audit_alter_table_migration_idempotent` runs migration twice on a DB and asserts schema convergence; pre-existing v3.11.2 / v3.11.3 rows are preserved (column NULL by default). ✅ Mitigated.
- **R-2: A2A dispatch races / cross-tenant leakage** — D-28 forbids cross-tenant leakage. Guard: `test_a2a_dispatch_cross_tenant_forbidden` + `test_event_room_fanout_bounded_by_room_list`; cross-tenant dispatch returns 403 with a stable cause identifier in the audit row. ✅ Mitigated.
- **R-3: `grid-engine` shared-core bleed** — D-28 carry-over; any change to `grid-types` / `grid-engine` / `grid-sandbox` / `grid-hook-bridge` must remain leg-agnostic. Guard: `test_v3_12_shared_core_unchanged` (new, COMPAT-03) snapshots public API surface pre/post v3.12. ✅ Mitigated.
- **R-4: Spec drift** — D-12 carry-over; EAASP v2.0 spec §5.3 / §14 / §17 are the Phase 4 sections. Guard: 03.12.0 `tools/eaasp-spec-alignment/ALIGNMENT_MATRIX.md` update (TRACE-02) lists every `### §N.M` section touched with `(status, v3.12_phase, post_v3.12_owner)`. ✅ Mitigated.
- **R-5: Certifier scope creep** — D-13 / D-21 carry-over; v3.12 reconciles to existing 21 RPC only. Guard: COMPAT-01 verified by `cargo test -p eaasp-certifier` PASS state pre/post each phase; new spec sections deferred. ✅ Mitigated.
- **R-6: Phase 3 OPA regression** — D-28 carry-over; the 5-stage state machine + OPA sidecar must remain green through v3.12. Guard: COMPAT-04 (ADR-V2-034 OPA sidecar) verified at every phase; v3.11.2 `test_approval_state_machine.py` + `test_governance_sse.py` PASS (regression). ✅ Mitigated.
- **R-7: A2A / Event Room slip into Phase 5 / Phase 6** — D-24 confines v3.12 to Phase 4 scope only. Guard: any PR touching L5 Cowork / ecosystem expansion is blocked by reviewer; the OOS list above is the single source of truth. ✅ Mitigated.
- **R-8: 03.12.3 live walkthrough blocked on missing LLM API key** — same blocker as v3.10 / v3.11. Guard: hermetic in-process walkthrough (using the same v3.7.3 threshold-calibration skill) is the executable baseline (D-25); live walkthrough captures whatever subset is reproducible given the LLM credential. ✅ Mitigated.

### Shared core rule (ADR-V2-023 P1, retained)

Changes to `grid-engine`, `grid-runtime`, `grid-types`, `grid-sandbox`, `grid-hook-bridge` must work for both engine 接入面 (EAASP) and Grid 独立产品. v3.12 is engine-axis work (L3 audit + L4 Event Room + A2A Router); any change to shared crates must be verified by `test_v3_12_shared_core_unchanged` (COMPAT-03) and must not introduce leg-specific branches. Per D-28, this rule is non-negotiable.

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
| **03.13.0** four-card data model + projection + L4 SSE bridge | 0/0 | 🔵 Bootstrapping | v3.13 |
| **03.13.1** four-card SSE fan-out + state transitions + persistence | 0/0 | 🔵 Bootstrapping | v3.13 |
| **03.13.2** retrospective cycle (trace API) | 0/0 | 🔵 Bootstrapping | v3.13 |
| **03.13.3** single-point live walkthrough + tag v3.13 | 0/0 | 🔵 Bootstrapping | v3.13 |

---

## Coverage Index

To be populated after Phase A.0 audit — REQ-IDs will map to specific gaps discovered.

---

*Last updated: 2026-07-28 — v3.13 EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle) bootstrapped (4-phase ladder 03.13.0 → 03.13.3, 13–16 REQ-IDs / 5 categories, locked decisions D-30..D-37). v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 ✅ SHIPPED 2026-07-27 @ 894639dd (4 phases, 13–16 REQ-IDs / 5 categories, tag `v3.12` pushed). v3.11 EAASP Phase 3 — production OPA backend + 5-stage approval chain SHIPPED 2026-07-27 (29/29 REQ-IDs, 4 phases, archived). v3.10 EAASP v2.0 platform-skeleton alignment SHIPPED 2026-07-26 (16/16 REQ-IDs, 4/4 phases, 174 targeted tests PASS). v3.9 SHIPPED 2026-07-26; v3.8 SHIPPED 2026-07-24; v3.7 SHIPPED 2026-07-23.*
