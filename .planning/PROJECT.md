# Grid

## What This Is

本仓库 = **EAASP(早期研究版)+ Grid 合体**,目前同仓孵化(EAASP 未来计划分仓独立,时点未定)。两个产品共享 L0 Protocol(`proto/eaasp/runtime/v2/`):

- **EAASP** 是面向企业的 B2B 平台,提供 L2 内存与技能 / L3 治理 / L4 编排的全栈 agent platform 能力。`tools/eaasp-*/` 是其当前实现(不是上游 shadow,是本团队自己的)。
- **Grid** 是通用的 agent runtime 技术栈(L0/L1),围绕 `grid-engine` 与 `grid-runtime` 构建,目标受众包含开发者 / 单租户 / 桌面 / 工具用户。`crates/grid-*` + `lang/{6 comparison runtimes}` + `web/` 是其实现。

**职责切分**(2026-04-26 socratic baseline,详见 `.planning/phases/4.1-PRE-AUDIT-NOTES.md`):

| 维度 | User 专心做 | 他人主要做 |
|------|------------|------------|
| L0 Protocol + L1 Grid 全栈 + L2/L3/L4 各引擎 | ✅ engine 层基础组件 | — |
| 数据 + 集成横切层(客户数据 / 企业系统对接 / SSO / 第三方 API) | — | ✅ |

> ✅ ADR-V2-024(2026-04-28 Accepted, supersedes ADR-V2-023)已重新框定为双轴模型(engine vs data/integration);ADR-V2-023 字面表述 "Leg A primary / Leg B dormant" (原 Leg A / Leg B, see ADR-V2-024 supersedes ADR-V2-023) 保留作历史快照。详见 ADR-V2-024 §1 双轴模型。

## Latest Shipped Milestone: v3.11 EAASP Phase 3 — production OPA backend + 5-stage approval chain ✅ 2026-07-27

**Goal:** Stand up the production L3 OPA/Rego sidecar (ADR-V2-034) on top of the v3.7.3 in-process gate, wire the L3 OPA backend adapter with the in-repo Rego bundle, install the 5-stage approval state machine (Plan → Check → Draft → Approve → Execute, with deny-always-wins + human-in-the-loop pause at the Approve stage), and capture a single-point live walkthrough against a real OPA sidecar on `127.0.0.1:18181`.

**Source of scope:** v3.10 platform-skeleton alignment (16/16 REQ-IDs, 174 tests) + V310-OPA-01 + V310-APPROVAL-01 in `docs/design/EAASP/DEFERRED_LEDGER.md` + EVOLUTION_PATH §三 Phase 3 (production OPA approval chain). The v3.11.3 single-point live walkthrough surfaced a real architectural finding: `audit.py`'s CHECK constraint on `governance_decisions.decision` does not yet include `await_human` (the sentinel value emitted by the 5-stage state machine at the Approve stage). Filed as a v3.12 candidate item.

**Target features (v3.11.0 / 03.11.1 / 03.11.2 / 03.11.3 — 4 phases, 29 REQ-IDs total):**

- **03.11.0 OPA sidecar infrastructure** — ADR-V2-034 Accepted (sidecar on `127.0.0.1:18181`, in-repo Rego templates + atomic user bundles, fail-closed on OPA error). `scripts/eaasp-install-opa.sh` installs the OPA binary to `third_party/opac/opa` with SHA256 verification; `make opa-install` / `make opa-clean` Makefile targets. `third_party/` in `.gitignore`. No shared-crate change. `V310-OPA-01` CLOSED.
- **03.11.1 L3 OPA backend adapter + Rego templates** — `OPABackend` adapter at `tools/eaasp-l3-governance/src/eaasp_l3_governance/opa_backend.py` posting `{"input": request}` to `/v1/data/governance/decision`. 5 fail-closed modes (connection-refused / timeout / non-2xx / parse-error / missing-field) return synthesized `deny` with `infra_unavailable=True` + stable cause identifier. `PolicyEngine.evaluate_with_opa()` routes through the adapter when `opa_enabled=True`. In-repo Rego template at `policies/governance.rego` implements deny-always-wins (§15.9), risk classification (§6.1), 3-state decision (§6.9, §6.10). 57 targeted tests PASS (30 OPABackend + 11 PolicyEngine OPA + 12 Rego contract + 4 in-process integration).
- **03.11.2 5-stage approval state machine** — `ApprovalStateMachine` (Plan → Check → Draft → Approve → Execute) with `STAGE_ORDER` tuple. `record_governance_decision(..., stage=...)` extension. 5 `SessionEventStream.emit_governance_approval_<stage>(...)` SSE events. `governance_decisions.stage` column added via idempotent `ALTER TABLE` migration. Deny short-circuits remaining stages. `V310-APPROVAL-01` CLOSED.
- **03.11.3 single-point live walkthrough** — `docs/status/PRODUCTION_USABILITY_2026-07-27.md` + `docs/status/PRODUCTION_USABILITY_LOGS_2026-07-27/` capture: 7 EAASP services up via `.grid/dev-eaasp-live.sh`, 5 SSE events in canonical order (seq 26–30, single request_id), 5 OPA roundtrips, 18 rows in L3 ledger across 3 chain runs, 3-state OPA decision end-to-end. v3.9 RBAC + v3.10 spec-audit + ADR-V2-023 P1 all preserved.

**Out of scope (deferred to v3.12+):**

- **Phase 4 A2A / Event Room** — V310-A2A-01 / V310-SESSION-01; v3.12 scope.
- **Phase 5 L5 Cowork UI** — V310-COWORK-01; v3.13+ scope.
- **Phase 6 ecosystem expansion** — V310-ECOSYSTEM-01 / V310-MAT-01; v3.14+ scope.
- **L1 infrastructure tier changes (gVisor / Firecracker / Kata)** — V310-SANDBOX-01; long-term.
- `audit.py` CHECK constraint widening to include `await_human` — surfaced by v3.11.3 walkthrough §7; v3.12.0 SCOPE (D-23).
- `web-platform/` Quality 7.5→9.0 / `grid-desktop` Quality 6.5→9.0 / `grid-platform` route catalog audit — separate milestones (carried forward).

**See also (canonical sources):**
- `docs/PROJECT_PRODUCT_OVERVIEW.md` (maintained SSOT)
- `docs/design/EAASP/EAASP_v2_0_EVOLUTION_PATH.md` §三 (Phase 3 SHIPPED; Phase 4 next)
- `docs/design/EAASP/DEFERRED_LEDGER.md` (V310-OPA-01 / V310-APPROVAL-01 CLOSED; V310-A2A-01 / V310-SESSION-01 active for v3.12)
- `docs/status/PRODUCTION_USABILITY_2026-07-27.md` (v3.11.3 dated walkthrough; §7 audit.py CHECK constraint finding)
- `docs/design/EAASP/adrs/ADR-V2-034-opa-backend-deployment-topology.md` (OPA sidecar ADR)
- `tools/eaasp-l3-governance/src/eaasp_l3_governance/approval_state_machine.py` (the source of `DECISION_AWAIT_HUMAN`)
- `.planning/REQUIREMENTS.md` v3.11 sections (29 REQ-IDs)

**Key context:**
- **双轴框架 (ADR-V2-024 §1)**: engine vs data/integration. v3.11 is engine 接入面 axis (L3/L4 EAASP reference implementations); Grid 独立产品 inherits the resulting clean contract surface.
- **Priority axis (ADR-V2-024 Open Item #3)**: grid-cli + grid-server first. v3.11 deliberately pivots to engine-side L3 OPA + 5-stage approval; grid-server / grid-platform / grid-desktop are dormant this milestone.
- **Shared core rule (ADR-V2-023 P1) preserved**: v3.11.0 explicitly verified COMPAT-02 (no shared crate touched); v3.11.1 / 03.11.2 changes are constrained to `tools/eaasp-l3-governance/` + `tools/eaasp-l4-orchestration/`. No leg-specific branches introduced.

**Previous milestones:**
- **v3.10 EAASP v2.0 platform-skeleton alignment SHIPPED 2026-07-26** (4 phases: 03.10.0–03.10.3, 16/16 REQ-IDs, 174 targeted tests PASS)
- **v3.9 route-catalog RBAC wiring + authorization auditor SHIPPED 2026-07-26** (3 phases: 03.9.0–03.9.2, 20 REQ-IDs, 49 targeted tests PASS)
- **v3.8 grid-server multi-user login SHIPPED 2026-07-24** (4 phases: 03.8.0–03.8.3, 21 REQ-IDs, 119/119 targeted tests PASS, 3 security hotfixes)
- **v3.7 实战可用性补全 SHIPPED 2026-07-23** (3 phases: 3.7.1 grid-cli / 3.7.2 web/ / 3.7.3 EAASP; 3.7.4 SKIPPED → v3.8)
- **v3.6 Post-Activation Docs Sync SHIPPED 2026-07-19**
- **Grid 独立产品 Activation SHIPPED 2026-06-17** (8/8 phases A.0–A.8; repo renamed `grid-sandbox` → `grid`)
- v3.5 Debt Finalization ✅ SHIPPED 2026-06-16 (LEDGER 100% ✅ CLOSED, 56 rows normalized)
- v3.4 Full INBOX Drain ✅ SHIPPED 2026-06-16 (10 phases, ~55 REQ-IDs, ~85 INBOX rows)
- v3.3 Engine + Platform Debt Sweep ✅ SHIPPED 2026-06-07

**See also (canonical sources)**:
- `docs/PROJECT_PRODUCT_OVERVIEW.md` (maintained SSOT)
- `docs/status/PRODUCT_STATUS_2026-07-17.md` (dated audit snapshot)

**Key context:**
- 双轴框架 (ADR-V2-024 §1): engine vs data/integration. Grid independent product inherits engine layer.
- Priority axis (ADR-V2-024 Open Item #3): grid-cli + grid-server first; platform/desktop/web follow-on.
- All code must work for both engine 接入面 (EAASP) and Grid independent product (shared core rule per ADR-V2-023 P1).

## Current Milestone: v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 (bootstrapping)

**Goal:** Begin EAASP v2.0 EVOLUTION_PATH §三 Phase 4 by delivering the **A2A Router** (agent-to-agent coordination across multiple sessions) and **Event Room** (multi-session event coordination that V310-A2A-01 deferred from v3.10 and V310-SESSION-01 deferred from v3.10 require). The milestone also closes a real bug surfaced during the v3.11 single-point live walkthrough: `audit.py`'s CHECK constraint on `governance_decisions.decision` does not include the `await_human` sentinel value emitted by the 5-stage approval state machine at the Approve stage; therefore `await_human` rows cannot be persisted to the L3 audit ledger until the constraint is widened. v3.12.0 patches the schema first (idempotent `ALTER TABLE` migration per D-26); v3.12.1 lands the Event Room + multi-session coordination; v3.12.2 lands the A2A Router; v3.12.3 is a single-point live walkthrough that demonstrates the whole Phase 4 surface.

**Source of scope:** v3.11.3 live walkthrough report (`docs/status/PRODUCTION_USABILITY_2026-07-27.md` §7) surfaced the `audit.py` CHECK constraint gap as a known finding (currently filed in v3.11.3 deferred-items for v3.12 review). V310-A2A-01 + V310-SESSION-01 in `docs/design/EAASP/DEFERRED_LEDGER.md` are the deferred Phase 4 items (`📦 deferred_to_v3.12+ / Phase 4`). v3.12 is the 4-phase ladder recommended by v3.10's EVOLUTION_PATH-aligned sequencing: v3.10 (alignment) → v3.11 (Phase 3 OPA + 5-stage) → v3.12 (Phase 4 A2A + Event Room + multi-session).

**Why 4 phases (and the order that puts schema first):**

- **03.12.0 (Schema + audit constraint patch)** MUST ship before 03.12.1 / 03.12.2 — the `await_human` rows that the 5-stage state machine emits at the Approve stage must not be silently dropped by the CHECK constraint. Without 03.12.0, the live walkthrough in 03.12.3 cannot reproduce the paused-state audit evidence end-to-end.
- **03.12.1 (Event Room + multi-session)** — depends on 03.12.0 (rows may carry `await_human` + `stage`); establishes the Event Room namespace that the A2A Router dispatches into.
- **03.12.2 (A2A Router)** — depends on 03.12.1 (Event Room as dispatch target); wires the same v3.7.3 governance gate + v3.11.2 5-stage approval chain into the A2A dispatch path.
- **03.12.3 (single-point live walkthrough)** — final; reproduce the awaited-state audit evidence end-to-end against real OPA sidecar + Event Room + A2A Router.

**Target features:**

- **Schema + audit constraint patch** — extend `audit.py` so `governance_decisions.decision` CHECK constraint accepts `await_human` (alongside the existing `allow` / `approve` / `deny` / `gate_request`). Idempotent `ALTER TABLE` migration so existing DBs upgrade cleanly. Backfill considerations: no live rows to migrate (awaits_human rows are emitted by the in-process harness only, not persisted to L3 yet). The `reason` field carries the `DECISION_AWAIT_HUMAN` sentinel when the state machine pauses at the Approve stage.
- **Event Room** — multi-session coordination workspace mirroring EAASP v2.0 spec §5.3 / §14 (per `EAASP_v2_0_EVOLUTION_PATH.md` §三 Phase 4 scope). An Event Room is a logical namespace that spans multiple sessions and binds their events together; this is the substrate for A2A.
- **multi-session coordination** — the engine-layer orchestration that fans events across sessions in the same Event Room, with the L4 SSE stream carrying the fan-out. Preserve v3.11.2's existing per-session SSE contract; add a new `governance.session.cross` event family for cross-session visibility.
- **A2A Router** — agent-to-agent routing service that dispatches an outbound turn from one session to another (or to a tenant-shared router) per spec §17. Closely aligned with v3.7.3's governance gate semantics + v3.11.2's 5-stage approval state machine (`Plan → Check → Draft → Approve → Execute`); the A2A dispatch path runs through the same gate.
- **single-point live walkthrough** — confirm the audit.py CHECK constraint patch holds under live OPA sidecar, the Event Room fans events across sessions, and the A2A Router dispatches across sessions; capture dated evidence at `docs/status/PRODUCTION_USABILITY_2026-07-28.md`.

**Out of scope (deferred to v3.13+):**

- **Phase 5 L5 Cowork UI** — v3.13+ scope (per EVOLUTION_PATH §三 Phase 5).
- **Phase 6 ecosystem expansion** — v3.14+ scope (per V310-ECOSYSTEM-01 / V310-MAT-01).
- **L1 infrastructure tier changes (gVisor / Firecracker / Kata)** — long-term (V310-SANDBOX-01).
- **NATS JetStream backend for EventStream** — long-term (D75).
- **`web-platform/` Quality 7.5→9.0** — separate milestone (carried forward).
- **`grid-desktop` Quality 6.5→9.0** — separate milestone (carried forward).
- **`grid-platform` route catalog audit** — separate milestone (carried forward).
- **Multi-role per user / SSO / refresh-token rotation / per-tenant Action policy override** — out of v3.12.
- **Schema migration beyond the audit CHECK constraint** — out of v3.12 (D-26 carry-over: the constraint extension is the only schema change; new tables / columns are deferred).

**See also (canonical sources):**

- `docs/PROJECT_PRODUCT_OVERVIEW.md` (maintained SSOT)
- `docs/design/EAASP/EAASP-Design-Specification-v2.0.docx` (canonical EAASP v2.0 spec of record; §5.3 / §14 / §17 are the Phase 4 sections)
- `docs/design/EAASP/EAASP_v2_0_EVOLUTION_PATH.md` §三 (long-term cross-phase decision registry; Phase 4 scope)
- `docs/design/EAASP/DEFERRED_LEDGER.md` (cross-phase D-item SSOT; V310-A2A-01 / V310-SESSION-01 / V311-AUDIT-01)
- `docs/design/EAASP/PHASE_3_DESIGN.md` (Phase 3 design — adjacency for Phase 4; spec §6.9 / §6.10)
- `docs/status/PRODUCTION_USABILITY_2026-07-27.md` §7 (v3.11.3 audited finding that motivates `audit.py` CHECK constraint patch)
- `tools/eaasp-l3-governance/src/eaasp_l3_governance/audit.py` (target file for SCHEMA-01..03)
- `tools/eaasp-l3-governance/src/eaasp_l3_governance/approval_state_machine.py` (the source of `DECISION_AWAIT_HUMAN`; v3.11.2)
- `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/event_stream.py` (the SSE event surface; v3.7.3 + v3.11.2)
- `.planning/REQUIREMENTS.md` v3.12 section (13–16 REQ-IDs, locked decisions D-23..D-29)

**Key context:**

- **mvp-calibration skill + `make dev-eaasp` minimum bar** (D-25): the Phase 0.5 MVP human-executable floor (threshold-calibration + make dev-eaasp) is still the executable baseline; v3.12 adds a new A2A coordination walkthrough scenario on top of that floor.
- **idempotent migration pattern** (D-26): the `audit.py` CHECK constraint extension MUST use `ALTER TABLE` (matching the existing v3.11.2 `stage` column migration pattern); existing DBs upgrade cleanly without losing history. No destructive schema work.
- **no new repo / no new service port** (D-27): v3.12 stays in `tools/eaasp-*/` simulator-level implementations; no new service ports opened; the existing 7 EAASP services (skill-registry, L2, L3, mock-scada, MCP orchestrator, grid-runtime, L4) on `.grid/dev-eaasp-live.sh` launch topology are reused.
- **安全边界回归 guard** (D-28): v3.9 route-catalog RBAC (134 routes / `make rbac-audit`) + v3.10 spec-audit (4 files / 37 rows / `make v3.10-spec-audit`) + ADR-V2-023 P1 shared-core rule + ADR-V2-034 OPA sidecar ALL continue to PASS through every v3.12 phase. No shared-crate change is anticipated, but if any change is required it must remain leg-agnostic across engine 接入面 (EAASP) and Grid 独立产品.
- **探索策略** (D-29): Explore + Grep (no `.codegraph/` in this repo).

**Locked decisions (from v3.12 discussion — non-negotiable):** see `.planning/REQUIREMENTS.md` v3.12 section D-23..D-29.

## Core Value

Grid 必须是 EAASP 平台 L2–L4 通过 16-method gRPC contract 调用的 substitutable L1 runtime,且任何符合当前 `contract-v1.2.0` 的对比 runtime 都能替换它。`contract-v1.1.0` 是 Phase 3 sign-off (2026-04-18, 42 PASS / 22 XFAIL × 7 runtime) 历史契约版本。
## Requirements

### Validated

<!-- Existing capabilities — proven by Phase 2 → v3.11 delivery. -->

- ✓ **Phase 4.0 Bootstrap & Cleanup**(2026-04-27) —— GSD 治理底座 REVIEW_POLICY.md 落地 + Phase 4a 遗留 4 项 doc-cleanup(CLEANUP-01..04)归零 + GOVERNANCE-01 dry-run pass。Validated in Phase 4.0(commit `c12f425`),verifier 7/7 must-haves PASS,GSD plumbing tracer-bullet(discuss → research → patterns → plan → plan-checker → execute → verifier)全链路一次过。
- ✓ **L1 RuntimeService 16-method gRPC contract** —— `proto/eaasp/runtime/v2/runtime.proto` 冻结,7 runtime × contract-v1.1 通过(`make v2-phase3-e2e` 112/112 PASS)
- ✓ **ChunkType 闭枚举契约**(ADR-V2-021,Phase 3.5) —— 8 wire 值跨 7 runtime 1:1 一致,proto + ccb TS guard CI 双锁
- ✓ **Hook envelope contract**(ADR-V2-006) —— 子进程 stdin JSON 包络对 Pre/PostToolUse/Stop 三事件,Rust↔Python 通过 `hook_envelope_parity_test.rs` 跨语言一致
- ✓ **Two-leg shared core 边界**(ADR-V2-023 P1) —— `grid-types` / `grid-engine` / `grid-sandbox` / `grid-hook-bridge` 在两条腿中保持单一 codebase,Phase 4a 验证 0 Leg-B 假设泄漏到 shared crate
- ✓ **L2 内存混合检索**(ADR-V2-015) —— FTS5 + HNSW + time-decay 三路融合,`tools/eaasp-l2-memory-engine` 实现
- ✓ **PreCompact hook 协议**(ADR-V2-018) —— iterative summary + 跨压缩 token 预算
- ✓ **Tool namespace 契约**(ADR-V2-020) —— L0/L1/L2 工具分层,`ToolLayer` enum + `RequiredTool` parser
- ✓ **L1 runtime 生态策略**(ADR-V2-017) —— 主力(Grid)+ 样板(claude-code / nanobot / pydantic-ai)+ 对比(goose / claw-code / ccb)三轨,hermes 冻结
- ✓ **Stop hook + Scoped-hook executor**(Phase 2 S3.T4/T5) —— `StopHookDecision::{Noop, InjectAndContinue}` 三轮再注入上限
- ✓ **AgentLoop 通用性**(ADR-V2-016) —— capability matrix + Eager probe + tool_choice=Required + 不支持 provider 优雅退出
- ✓ **Phase-driven 开发流水**(Phase 2 → 4a 共 14 个归档 phase) —— ADR governance plugin + Deferred ledger SSOT
- ✓ **Debt 水位归零**(2026-04-20 @ commit `8629505`) —— D148/D149/D151/D152/D153/D154/D155 全 ✅ CLOSED 后无新 P1-active
- ✓ **Phase 4 主决策**(2026-04-28) —— 走"双轴模型(engine vs data/integration)主框架 + 两腿都推进(产品形态实例)" 路径; 详见 ADR-V2-024 (commit `f497eef`, status: Accepted, supersedes ADR-V2-023) + audit doc `docs/design/EAASP/adrs/decisions/2026-04-27-leg-decision-audit.md`
- ✓ **Phase 5 milestone (v3.1) Engine Hardening** (2026-05-22) —— Phases 5.0/5.1/5.2/5.3/5.4/5.5 全 6 phase 完成; 23/23 REQ-ID traceability ✅ (CLI 6 + SERVER 5 + CONTRACT 3 + WATCHLIST 8 + INTERFACE 1); 6 ADR Accepted: ADR-V2-025 (Phase 5.1, Runtime Tier Strategy) + ADR-V2-026 (Phase 5.3, Agent Loop ExecutionMode supersedes V2-016) + ADR-V2-027 (Phase 5.3, OpenAI-compat Quirks) + ADR-V2-028 (Phase 5.4, Strict-by-default Config Validation) + ADR-V2-029 (Phase 5.5, Engine vs Data/Integration Boundary, commit `0b23a01`) + ADR-V2-032 (Phase 5.5, TUI Log Path Convention, commit `1b9afd1`); 18 D-items closed across milestone; F3 ADR enforcement.trace baseline 33 WARN → 12 explicit-strategic + 0 unjustified. grid-cli + grid-server 优先发力组合 per ADR-V2-024 §1 双轴模型 / Open Item #3 完成; 其余 (grid-platform / grid-desktop / web*) 保持 dormant.
- ✓ **Phase 6 milestone (v3.2) Tech-Debt Triage & CI Red Line Clearance** (2026-05-26) —— Phases 6.0/6.1/6.2 全 3 phase 完成; 6/6 REQ-ID traceability ✅ (CI-01 @ `e27e300` Phase 6.0 NEW-X4 pytest fixture-scope rename + CLI-X2 @ `0595e31`+`a0a6c28` Phase 6.1 NEW-X2 sibling typed GridError + CLI-X3 @ `adf2c08`+`97f59e5` Phase 6.1 NEW-X3 --all-features Phase BA archaeology + TRIAGE-01 @ `9842dda` 93 main-NS row classify + TRIAGE-02 @ `e2a6349`+`835de4e`+`0f600b6` DEAD physical migration + TRIAGE-03 @ `24ee8ed` v3.3-INBOX.md); 0 ADRs Accepted (intentional light-triage milestone per ROADMAP Granularity 备注 v3.2 — code work scope-limited to 3 P2/P3 row, mega sweep deferred to v3.3+ per TRIAGE-03 output); 3 REQ-IDs closed via TRIAGE-01/02/03 cascade + 8 DEAD rows archived per TRIAGE-02. **Scope methodology correction**: 93 open main-namespace D-rows triaged (ROADMAP est. 102; scout claim 128 was grep-methodology error) — documented in LEDGER §状态变更日志 2026-05-26 entry, REQUIREMENTS.md left unchanged per CONTEXT.md §specifics.
- ✓ **Phase 7-9 milestones (v3.3–v3.5) Engine + Platform + INBOX Drain + Debt Finalization** (2026-06-07 → 2026-06-16) —— Phase 7.3 L3 RBAC 8/8 REQ-IDs (v3.3) + Phase 7/8 Full INBOX Drain 67 REQ-IDs / 21 plans / 39 tasks (v3.4) + LEDGER 100% ✅ CLOSED 56-row normalized (v3.5). 4 debt-sweep milestones closed (~200 D-items).
- ✓ **Grid 独立产品 Activation** (2026-06-17) —— 8/8 phases A.0–A.8 SHIPPED. Repo renamed `grid-sandbox` → `grid`. AGENTS.md / CLAUDE.md / READMEs / `docs/PROJECT_PRODUCT_OVERVIEW.md` are the maintained product-status entrypoints.
- ✓ **v3.6 Post-Activation Docs Sync** (2026-07-19) —— 7 docs commits @ `a29f626`, 46/46 UAT PASS. SSOT = `docs/PROJECT_PRODUCT_OVERVIEW.md`; frozen snapshot = `docs/status/PRODUCT_STATUS_2026-07-17.md`. AGENTS.md canonical-facts block + CLAUDE.md relative symlink.
- ✓ **v3.7 实战可用性补全 (Production-Usability Closure)** (2026-07-23, archived) —— 3 phases SHIPPED (3.7.4 SKIPPED, deferred to v3.8): 3.7.1 grid-cli 实战补全 (8/9 REQ-AUDITs), 3.7.2 web/ dashboard 实战化 (9 REQ-WEB), 3.7.3 EAASP 本地仿真实战补全 (8/8 REQ-EAASP). 175/175 tests PASS total across milestone. 50 commits, 76 files, 17,095 insertions. All 10 locked decisions (D-01..D-10) honored; default mode preserved; existing tests unaffected; live walkthrough BLOCKED on missing LLM API key per CLAUDE.md §Runtime Verification Tasks.
- ✓ **v3.8 grid-server multi-user login (Tenant + RBAC + JWT)** (2026-07-24, archived) —— 4 phases SHIPPED (03.8.0–03.8.3), 21 REQ-IDs in 6 categories, 119/119 targeted tests PASS, 3 security hotfixes (CRITICAL blacklist bypass, HIGH refresh stale-claim, HIGH audit IDOR). Demonstrated `requires(Action)` on 3 representative routes; remaining ~127 endpoints deferred to v3.9 per 03.8.2 plan §Task 4 + RESUME-NEXT-SESSION §Optional sidequests. Full archive: `.planning/milestones/v3.8-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md`.
- ✓ **v3.9 route-catalog RBAC wiring + authorization auditor** (2026-07-26, archived) —— 3 phases SHIPPED (03.9.0–03.9.2), 20 REQ-IDs in 5 categories (CAT / AUD / RBAC / MODE / TEST+DOC). 49/49 targeted tests PASS, 134-entry route catalog, 20-variant `Action` enum + regenerated `Role × Action` matrix (D-04), `make rbac-audit` + CI gate ordering `cargo check → rbac-audit → cargo test` (D-03), 3 post-ship security fixes (PUBLIC_ROUTE_ALLOWLIST unification / JWT `user` role mapping / catalog_rbac_middleware Public/Requires/distinguish). `AuthMode::None/ApiKey` semantics bit-for-bit unchanged (D-05). Archive: `.planning/milestones/v3.9-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md`.
- ✓ **v3.10 EAASP v2.0 platform-skeleton alignment** (2026-07-26, archived) —— 4 phases SHIPPED (03.10.0–03.10.3), 16/16 REQ-IDs in 5 categories (MAT / PIPE / VERIFY / COMPAT / TRACE), 174 targeted tests PASS. Section-by-section alignment matrix + deterministic spec audit + ordered CI gate delivered. Live real-skill walkthrough awaits LLM credentials per `docs/status/PRODUCTION_USABILITY_2026-07-26.md`.
- ✓ **v3.11 EAASP Phase 3 — production OPA backend + 5-stage approval chain** (2026-07-27, archived) —— 4 phases SHIPPED (03.11.0 / 03.11.1 / 03.11.2 / 03.11.3), 29 REQ-IDs in 5 categories (OPA / INSTALL / OPA-BACKEND / REGO / FAIL-CLOSED / DISABLED / STAGE / SSE / AUDIT / DENY / LIVE; 6 + 9 + 14 + LIVE-01..04). Real OPA sidecar v0.68.0 on `127.0.0.1:18181`; 5-stage approval state machine with deny-always-wins + human-in-the-loop pause at Approve stage; 5 SSE events in canonical order; 18 rows in L3 governance_decisions across 3 chain runs. `V310-OPA-01` + `V310-APPROVAL-01` CLOSED. Live walkthrough captured at `docs/status/PRODUCTION_USABILITY_2026-07-27.md` + `docs/status/PRODUCTION_USABILITY_LOGS_2026-07-27/`. v3.9 RBAC + v3.10 spec-audit + ADR-V2-023 P1 all preserved.

### Active

<!-- v3.12 next-milestone scope is the open scope. v3.11 surface-complete base. -->

- [ ] **v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调** — bootstrapping (this commit). 4 phases planned (03.12.0 schema + audit constraint patch → 03.12.1 Event Room + multi-session → 03.12.2 A2A Router → 03.12.3 single-point live walkthrough). 13–16 REQ-IDs across 5 categories (SCHEMA / EVENT-ROOM / A2A / SESSION / COMPAT). Closes V310-A2A-01 + V310-SESSION-01 + V311-AUDIT-01 (audit.py CHECK constraint gap surfaced by v3.11.3 walkthrough §7).
- [ ] **EAASP v2.0 platform-evolution gaps (carry forward, future milestones)**: Phase 5 L5 Cowork UI (V310-COWORK-01) / Phase 6 ecosystem expansion (V310-ECOSYSTEM-01 / V310-MAT-01) / L1 infrastructure tier changes (V310-SANDBOX-01). Per `docs/design/EAASP/EAASP_v2_0_EVOLUTION_PATH.md`.

### Out of Scope

- **仓库改名 ✅** (2026-06-17) —— `grid-sandbox` → `grid`。Grid 独立产品 Activation milestone SHIPPED 后触发（per ADR-V2-023 §P6）。
- **`git push origin main`** —— 累积 ~14 unpushed commits(Phase 3.5 + 3.6 + 4a + cutover prep + 接管 commits),保留人类决策
- **Phase 0–2.5 历史 retrofit**(Phase 4a project review 发现 sign_off_commit 字段缺失) —— 接受历史不完美,git history 为准,不回填
- **132 个历史 plan 文件 + 14 archived phase 迁入 GSD ROADMAP.md** —— 冻结为只读历史存档,GSD 仅管 Phase 4 起的新工作
- **F4 lint 52 个 module-overlap 警告 reconcile** —— Phase 4a session-04-26 audit 已确认无 Decision-text 矛盾,advisory-only 接受
- **EAASP 与 Grid 立即分仓** —— per `.planning/phases/4.1-PRE-AUDIT-NOTES.md` §A.1 同仓孵化,分仓时点由 Phase 4.1 audit 决定;现阶段不动
- **超出当前 baseline 的 Grid Platform / Server / Desktop / Web 增量功能开发** —— per `.planning/phases/4.1-PRE-AUDIT-NOTES.md` §C.3 #3,Grid 产品化路径优先级待 audit 决定;在此之前任何 PR 触碰这几个 crate 需 reviewer justification(checklist 由 CLEANUP-03 落地)
- **替换现有 Plan 流水到 `docs/plans/2026-*-plan.md` 单文件结构** —— GSD 用 `.planning/phases/<phase>/PLAN.md` 多目录结构,各管各的
- **v3.11 out-of-scope items** (`.planning/REQUIREMENTS.md` v3.11 §Out of Scope): Phase 4 A2A / Phase 5 L5 / Phase 6 ecosystem / proto contract widening / L1 runtime additions or substitutions — all deferred to v3.12+ or later
- **v3.12 out-of-scope items** (`.planning/REQUIREMENTS.md` v3.12 §Out of Scope, D-26 / D-27): Phase 5 L5 / Phase 6 ecosystem / L1 infrastructure tier changes / NATS JetStream backend / new service ports / new tables or columns beyond the audit CHECK constraint extension — all deferred to v3.13+ or later

## Context

**Brownfield 切换背景**(2026-04-26):本项目从 2026-04-04 起在 dev-phase-manager + superpowers 体系下推进,经过 14 个归档 phase(Phase BA → Phase 4a)交付 EAASP v2.0 全部里程碑(Phase 2 / 2.5 / 3 / 3.5 / 3.6 / 4a)。Phase 4a 末尾 debt 水位归零后,切换到 GSD 体系是因为 GSD 的 **workstreams + resume-work + plan-checker + map-codebase** 在 brownfield + 多 workstream 场景比 dev-phase-manager 更合适。

**项目所处生态位**:本仓库 = EAASP(早期研究版)+ Grid 合体,**两者均由本团队同仓孵化**(详见 `.planning/phases/4.1-PRE-AUDIT-NOTES.md` §A)。Grid 是 EAASP 的旗舰 L1 runtime,EAASP 是 Grid 的 L2/L3/L4 平台层消费者。`tools/eaasp-*/` 是 EAASP 的当前实现(不是上游 shadow,虽然 ADR-V2-023 §P3 字面说"shadow",那是 forward-looking 占位描述,描述未来分仓后的状态)。engine 接入面 (原 Leg A, see ADR-V2-024 supersedes ADR-V2-023) 的契约对接由本仓库的 7 个 L1 runtime 集体验证,任何 contract-v1.1 通过的 runtime 都能替换 Grid 作为 EAASP 的 L1。

**未来计划**: EAASP 分仓独立(时点由 Phase 4.1 audit 决定);分仓后 data + integration 横切层由他人主要负责,user 工时持续投在 Grid 全栈 + EAASP 各层引擎基础组件。

**技术栈成熟度**:13 Rust crate(~178K LOC)+ 5 Python lang/runtime + 9 EAASP tools(~29K LOC)+ 226 test files。Cargo workspace 严格依赖纪律(`[workspace.dependencies]` 40+ pin),Python 全 `uv` 管理,Pyright `pyrightconfig.json` 9 per-env executionEnvironments,proto codegen 走 `scripts/gen_runtime_proto.py` 单 SoT。`unsafe` 全工程零块。

**治理底座**:17 ADR(`docs/design/EAASP/adrs/ADR-V2-001..V2-034`),F1-F5 lint 由 ADR governance plugin 强制(`/adr:audit` + `.github/workflows/adr-audit.yml`)。Deferred 账本 `docs/design/EAASP/DEFERRED_LEDGER.md` 是跨 phase 单 SSOT,**保留作 GSD 例外**(GSD 自身的 backlog 不取代它)。

## Constraints

- **Tech stack(冻结)**: Rust 1.75+ edition 2021,Python 3.12+(uv 管理),TypeScript 5.x(Bun),Protobuf 3,gRPC(tonic + grpcio),SQLite + HNSW
- **Authoritative source 优先级(锁在 CLAUDE.md)**: ADR(`docs/design/EAASP/adrs/`)> EAASP/(子目录)> Grid/(子目录)> 代码 > root-level `docs/design/*.md`(后者全是 PRE-EAASP-v2 LEGACY,2026-02 至 03 月,不可作为当前架构引用)
- **Two-leg P1 规则(ADR-V2-023)**: shared core(`grid-types` / `grid-engine` / `grid-sandbox` / `grid-hook-bridge`)对两条腿都要工作。No leg-specific branches in core code
- **L1 contract 不可破坏**: 修改 `proto/eaasp/runtime/v2/*.proto` 必须经 ADR 走流水(F4 reviewer 强制)
- **Hook envelope 跨 runtime 一致**: ADR-V2-006 §2-§3 envelope shape 在 Rust + Python 两侧通过 `hook_envelope_parity_test.rs` 验证,新增运行时必须通过
- **No live LLM in unit tests**: 所有 unit test mock provider 或 monkeypatch SDK call;live LLM 只在 e2e harness 与 manual runbook
- **Commit 格式**: subject ≤72 chars + 强制 footer `Generated-By: Claude (claude-<model>) via Claude Code CLI` + `Co-Authored-By: claude-flow <ruv@ruv.net>`
- **Test discipline(per CLAUDE.md)**: 不自动跑全 workspace test suite。targeted test only;full run 需先问 user
- **Documentation language**: CLAUDE.md / README.md → English;`docs/design/`/`docs/plans/` → Chinese;ADR 双语标题 + 英文 frontmatter

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|--------|
| **DEFERRED_LEDGER.md 作为单 SSOT 保留(GSD 例外)** | GSD backlog 是 999.x phase 散文件,会断 D87→D148→D152 跨 phase trace。本项目 14 phase 全部用 ledger 追了 100+ D-item,这套机制成熟,不替换 | ✓ Good — sticky |
| **WORK_LOG.md 继续 prepend-on-top(GSD 例外)** | `.planning/STATE.md` 是 current state,WORK_LOG 是时间线 history,二者并存。STATE 给 resume-work,WORK_LOG 给 archeology | ✓ Good — sticky |
| **ADR plugin 完全独立于 GSD** | `/adr:*` 与 GSD 不耦合,15 ADR 已成 governance 底座。继续 PreToolUse `adr-guard.sh` 强制 + F1-F5 CI lint | ✓ Good — sticky |
| **Historical phases(132 plan + 14 archived)冻结不迁移** | 自动迁入 ROADMAP.md 风险大、价值低,git log 已记录。Phase 4 起步从 .planning/ 干净开 | ✓ Good — locked |
| **engine 接入面 vs Grid 独立产品 决策推迟到 Phase 4.1** (原 Leg A vs Leg B, see ADR-V2-024 supersedes ADR-V2-023) | 触发条件在 ADR-V2-023 §P5,需先 socratic discuss 而非预判 | ✓ Resolved — Phase 4.2 ADR-V2-024 双轴模型 Accepted |
| **Two-stage review 用 superpowers 而非 GSD 单 reviewer** | Phase 4a 经验:T5/T6 高风险 task 靠 superpowers 抓出 I1/I2/I3 类细节 issue。GSD `gsd-code-review` 是 broad-stroke,互补使用 | ✓ Good — locked via REVIEW_POLICY.md(Step 3) |
| **新 phase 高风险 task 靠 PLAN.md frontmatter `review_protocol: superpowers-two-stage` 显式标记** | 比"plan-checker 动态决定"更可控,比"人工每次说"更标准化 | — Pending REVIEW_POLICY.md 落地 |
| **GSD 模型 profile = Quality** | Phase 4 决策阶段值得 Opus 跑 researcher / roadmapper;成本可接受 | ✓ Good |
| **GSD parallel plan execution 打开** | Phase 2.5 W1∥W2 并行经验证明本项目适合 | ✓ Good |
| **Granularity = Standard** | 5-8 phases / milestone, 3-5 plans / phase。匹配 Phase 2 / 3 历史粒度 | ✓ Good |
| **v3.9 RouteCatalog as source of truth** (D-06) | v3.9 needs an auditor's stable target; manual-decoration vs generate-from-router both acceptable as long as catalog is `pub` and consumed by auditor + tests | ✓ Locked (v3.9 bootstrap) |
| **v3.9 Action vocabulary is extensible** (D-04) | 7-Action baseline is a starting point; auditor surfaces semantic gaps that warrant new variants; matrix regeneration is part of the deliverable | ✓ Locked (v3.9 bootstrap) |
| **v3.9 AuthMode None/ApiKey parity is mandatory** (D-05) | v3.9 wiring is purely additive; only `AuthMode::Full` runs the new per-route RBAC; regression guarded by `test_auth_modes` 8/8 | ✓ Locked (v3.9 bootstrap) |
| **v3.10 EAASP v2.0 platform-skeleton alignment scope** (D-11) | v3.10 aligns `tools/eaasp-*` reference implementations with the canonical EAASP v2.0 spec along three axes (MAT/PIPE/VERIFY); without widening `contract-v1.2.0` surface or adding new dependencies; precondition for EVOLUTION_PATH §三 Phase 3–6 | ✓ Locked (v3.10 bootstrap) |
| **v3.10 Three-axis skeleton mapping** (D-12) | MAT (memory/manifest), PIPE (orchestration pipes), VERIFY (certifier conformance); each axis has its own 03.10.x phase; skeleton alignment is honest about gaps (spec-only fields surfaced as `missing`, not silently dropped) | ✓ Locked (v3.10 bootstrap) |
| **v3.10 Backward-compatible contract surface** (D-13) | `proto/eaasp/runtime/v2/` 21 RPC + `contract-v1.2.0` tests must remain green; no proto-breaking changes; new spec sections surfaced via `certifier_surface.md` as `not_certified` and deferred | ✓ Locked (v3.10 bootstrap) |
| **v3.10 L1 substitutability guard preserved** (D-14) | All 7 L1 runtimes (`grid-runtime` + 6 comparison; `hermes` frozen per ADR-V2-017) must continue to pass `contract-v1.2.0` certifier after each v3.10 phase; verified by `make v2-phase3-e2e-rust` | ✓ Locked (v3.10 bootstrap) |
| **v3.10 No new external crate dependency** (D-15) | D-07 carry-over; same rule for Python (no new PyPI deps beyond existing `uv` lockfile); v3.10 uses existing `grid-types`/`grid-engine`/`eaasp-certifier`/`eaasp-l2-memory-engine`/`eaasp-l3-governance`/`eaasp-l4-orchestration`/`eaasp-skill-registry`/`eaasp-mcp-orchestrator` toolchain | ✓ Locked (v3.10 bootstrap) |
| **v3.10 No schema migration** (D-16) | D-08 carry-over; v3.10 skeleton alignment is Rust + Python source + spec documentation only; no DB migration, no proto schema migration | ✓ Locked (v3.10 bootstrap) |
| **v3.10 Shared-core rule (ADR-V2-023 P1) preserved** (D-17) | D-09 carry-over; any change to `grid-types`/`grid-engine`/`grid-sandbox`/`grid-hook-bridge` must remain leg-agnostic; verified by `test_v3_10_shared_core_unchanged` (new, COMPAT-03) | ✓ Locked (v3.10 bootstrap) |
| **v3.10 Phase ladder 03.10.0 → 03.10.1 → 03.10.2 → 03.10.3** (D-18) | 03.10.0 = skeleton audit + alignment matrix (foundation; every later phase consumes the matrix); 03.10.1 = MAT axis; 03.10.2 = PIPE axis; 03.10.3 = VERIFY axis; COMPAT + TRACE run cross-axis | ✓ Locked (v3.10 bootstrap) |
| **v3.11 OPA sidecar deployment topology** (D-19) | ADR-V2-034 — sidecar OPA on `127.0.0.1:18181`, in-repo Rego templates + atomic user bundles, fail-closed on OPA error; `make opa-install` downloads official OPA binary with SHA256 verify; `third_party/` in `.gitignore` | ✓ Locked (v3.11.0 bootstrap) |
| **v3.11 No shared-crate change** (D-20) | v3.11.0 / 03.11.1 / 03.11.2 / 03.11.3 must NOT touch `grid-types` / `grid-engine` / `grid-sandbox` / `grid-hook-bridge`; ADR-V2-023 P1 (shared-core rule) preserved; COMPAT-02 verified at every phase | ✓ Locked (v3.11.0 bootstrap) |
| **v3.11 Backward-compatible contract surface** (D-21) | `proto/eaasp/runtime/v2/` 21 RPC + `contract-v1.2.0` tests remain green; no proto-breaking changes; new spec sections deferred to v3.12+ (D-13 carry-over) | ✓ Locked (v3.11.0 bootstrap) |
| **v3.11 Phase ladder 03.11.0 → 03.11.1 → 03.11.2 → 03.11.3** (D-22) | 03.11.0 = sidecar + ADR; 03.11.1 = L3 OPA backend + Rego; 03.11.2 = 5-stage approval state machine; 03.11.3 = single-point live walkthrough | ✓ Locked (v3.11.0 bootstrap) |
| **v3.12 audit.py CHECK constraint patch is mandatory phase 0** (D-23) | v3.11.3 live walkthrough §7 surfaced that `audit.py`'s CHECK constraint on `governance_decisions.decision` does not include `await_human`; the 5-stage state machine emits `await_human` at the Approve stage; without this fix, 03.12.1 / 03.12.2 / 03.12.3 cannot reproduce paused-state audit evidence. v3.12.0 MUST patch the schema first; no implementation work in 03.12.1 / 03.12.2 may proceed before 03.12.0 ships | ✓ Locked (v3.12 bootstrap) |
| **v3.12 scope = EAASP Phase 4** (D-24) | v3.12 delivers A2A Router + Event Room + multi-session coordination per EAASP_v2_0_EVOLUTION_PATH.md §三 Phase 4 scope (spec §5.3 / §14 / §17). Closes V310-A2A-01 + V310-SESSION-01 + V311-AUDIT-01. v3.13+ = Phase 5 L5 / Phase 6 ecosystem (V310-COWORK-01 / V310-ECOSYSTEM-01 / V310-MAT-01) | ✓ Locked (v3.12 bootstrap) |
| **v3.12 MVP executable baseline + new A2A coordination scenario** (D-25) | Phase 0.5 MVP human-executable floor (`threshold-calibration` skill + `make dev-eaasp`) remains the minimum bar; v3.12 adds a new A2A coordination walkthrough scenario on top of that floor (request A's approve stage pauses; event room fans out; another session's A2A dispatch resumes the chain) | ✓ Locked (v3.12 bootstrap) |
| **v3.12 audit.py CHECK constraint extension uses idempotent migration** (D-26) | The `audit.py` CHECK constraint extension MUST use `ALTER TABLE` (matching the existing v3.11.2 `stage` column migration pattern); existing DBs upgrade cleanly without losing history. No destructive schema work. No new tables / no new columns beyond the CHECK constraint extension | ✓ Locked (v3.12 bootstrap) |
| **v3.12 stays in `tools/eaasp-*/` simulator-level implementations** (D-27) | v3.12 does not open a new repo / does not open a new service port; uses the existing 7 EAASP services (skill-registry / L2 / L3 / mock-scada / MCP orchestrator / grid-runtime / L4) on `.grid/dev-eaasp-live.sh` launch topology. Event Room + A2A Router live in `tools/eaasp-l4-orchestration/` (per v3.7.3 L4 ownership pattern) | ✓ Locked (v3.12 bootstrap) |
| **v3.12 安全边界 + shared-core rule + rbac-audit + v3.10-spec-audit + OPA sidecar all continue to PASS** (D-28) | v3.9 route-catalog RBAC (134 routes / `make rbac-audit`) + v3.10 spec-audit (4 files / 37 rows / `make v3.10-spec-audit`) + ADR-V2-023 P1 shared-core rule + ADR-V2-034 OPA sidecar ALL continue to PASS through every v3.12 phase. No shared-crate change is anticipated, but if any change is required it must remain leg-agnostic across engine 接入面 (EAASP) and Grid 独立产品 | ✓ Locked (v3.12 bootstrap) |
| **v3.12 探索策略** (D-29) | Explore + Grep (本仓无 `.codegraph/`, no MCP codegraph tool available). Codebase pattern reads gate by CLAUDE.md "Level 1+ single-pass reads" rule | ✓ Locked (v3.12 bootstrap) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---

*Last updated: 2026-07-27 — v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 bootstrapped (4-phase ladder 03.12.0 → 03.12.3, 13–16 REQ-IDs / 5 categories, locked decisions D-23..D-29). v3.11 EAASP Phase 3 — production OPA backend + 5-stage approval chain SHIPPED 2026-07-27 (29/29 REQ-IDs, 4 phases, archived). v3.10 EAASP v2.0 platform-skeleton alignment SHIPPED 2026-07-26 (16 REQ-IDs, 4 phases, archived). v3.9 (route-catalog RBAC wiring + authorization auditor) SHIPPED 2026-07-26, archived to `.planning/milestones/v3.9-*`. v3.8 (grid-server multi-user login) ✅ SHIPPED 2026-07-24, archived to `.planning/milestones/v3.8-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md`. v3.7 (实战可用性补全) ✅ SHIPPED 2026-07-23, archived to `.planning/milestones/v3.7-ROADMAP.md`. v3.6 (Post-Activation Docs Sync) ✅ SHIPPED 2026-07-19. Grid 独立产品 Activation ✅ SHIPPED 2026-06-17 (8/8 phases A.0–A.8). v3.5/v3.4/v3.3/v3.2/v3.1/v3.0 ✅ CLOSED.*
