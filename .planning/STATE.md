---
gsd_state_version: 1.0
milestone: v3.15.6
milestone_name: OBSTACK 实战补完 (6 阶段 v3.15.6a → 6f)
status: shipped
stopped_at: v3.15.6 **SHIPPED + tagged `v3.15.6` (2026-08-12)**。5/6 阶段完成 (6a 文档诚实化 / 6b 测试补完 / 6c 死代码激活 / 6g tag 前验证+修复 / 6h 补齐 requests.* + demo 改造);**6d web-platform Dashboard + 6e CLI 全局接入 显式 deferred → v3.16** (D-53 / D-54),不在本 tag 声称范围。6g 查出 6c 的两处假闭环并修复:(1) 6c.2/6c.3 把 emit 挂在 `on_tool_call/on_tool_result/on_stop`,而 Grid 是 Tier 1 (`native_hooks: true`),L4 从不调用这三个 hook RPC → 死代码,实测真实 tool-call turn 产出 `"scopeMetrics":[]`;(2) `init_observability` 的 `drop(provider)` 触发 `SdkMeterProviderInner::drop` → `shutdown()`,导出管道启动即死。6h 补齐最后一条无证据的 series (`requests.*` 自落地起从未被调用),顺带修 `TimeBlock` 双减 in_flight + metric-cardinality DoS (op label allowlist);并改造 demo 脚本 —— 它此前有 4 个独立缺陷,叠加后能在什么都没证明的情况下 exit 0。**L1 侧 6/6 series 真跑验证 + 关键检查配负控**。但 2026-08-12 6i 收尾复核查出 **L2/L3/L4 三层 observability 零生产调用点**(同 6c 失败模式),§0.1 由 23/23 **降为 20/23**;tag `v3.15.6` 对 L1 的声称成立,对 L2/L3/L4 的 ✅ 是继承自未验证的旧结论,**打早了**,由 `V316-L2L3L4-OBS-01` 在 v3.16 收口。100/100 tests;dual-gate PASS (134 routes / 38 rows)。EVOLUTION_PATH §三 8-Phase 路线 ALL SHIPPED (v3.10/11/12/13/14). 锁决策 D-47..D-54. plan `docs/superpowers/plans/2026-08-09-obstack-v3-15-6-completion.md`;证据 `docs/status/PRODUCTION_USABILITY_2026-08-11-obstack6g.md`. Prior milestone v3.15 SHIPPED 2026-08-02 @ `84cc0680`. Prior v3.14 SHIPPED 2026-07-30. Prior v3.13 SHIPPED 2026-07-29 @ d0d83a23.
last_updated: "2026-08-12T05:15:00.000Z"
last_activity: 2026-08-12
progress:
  total_phases: 6
  completed_phases: 5
  deferred_phases: 2
  total_plans: 6
  completed_plans: 5
  percent: 83
  prior_milestones:
    v3.14_completed_phases: 4
    v3.14_completed_plans: 4
    v3.14_percent: 100
    v3.13_completed_phases: 4
    v3.13_completed_plans: 4
    v3.13_percent: 100
    v3.12_completed_phases: 4
    v3.12_completed_plans: 4
    v3.12_percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Grid 作为 substitutable L1 runtime,通过 gRPC contract 被 EAASP L2-L4 调用,且任何符合 `contract-v1.2.0` 的对比 runtime 都能替换它。`contract-v1.1.0` 是 Phase 3 sign-off 历史契约版本(2026-04-18,42 PASS / 22 XFAIL × 7 runtime)。
**Current focus:** Milestone v3.14 (EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem) ✅ SHIPPED 2026-07-30. 4 phases planned (03.14.0 Ontology 服务 + taxonomy 路径 + cross-domain link + JSON-schema 派生 → 03.14.1 Skill Marketplace API + 第三方提交 / 4 阶段 promotion / 完整 ACL / analytics → 03.14.2 SDK scaffolding + JSON-schema 暴露 → 03.14.3 single-point live walkthrough + tag v3.14 + EVOLUTION_PATH 8-Phase 路线 ALL SHIPPED), 13–16 REQ-IDs across 5 categories (ONTOLOGY / MARKETPLACE / SDK / ECOSYSTEM-LIFECYCLE / COMPAT). Locked decisions D-38..D-46. 23 REQ-IDs / 5 categories closed; 98 targeted tests PASS; V310-ECOSYSTEM-01 ✅ CLOSED 2026-07-30; tag `v3.14` force-push.

Canonical product-status sources:

- `docs/PROJECT_PRODUCT_OVERVIEW.md` (maintained SSOT)
- `docs/status/PRODUCT_STATUS_2026-07-17.md` (dated audit snapshot)

## Current Position

Milestone: **v3.15.6 OBSTACK 实战补完 ✅ SHIPPED + tagged 2026-08-12 — 5/6 阶段 (6a ✅ / 6b ✅ / 6c ✅ / 6g ✅ / 6h ✅;6d + 6e deferred → v3.16 per D-53/D-54)**
Scope: 6 阶段串行 (6a 文档/状态一致性 → 6b 测试补完 → 6c 死代码激活 → 6d web-platform Dashboard → 6e CLI 全局接入 → 6f 收口 + tag)。锁决策 D-47..D-54。**不开新 milestone / 不开新 EVOLUTION_PATH phase / 不开新仓 / 不开新服务端口** (D-47 + D-48)。
- **6a 文档诚实化 ✅** (`725fe82c` + `c7a5b50e` + `15e9edac` + `479f1483` + `8e42f151` + `960c7f10`) — OBSTACK_DESIGN §0.1/§0.2/§0.3 + INDEX §Goal 表 4 处 23/23 → **20/23 (87%)** per D-50 (不掩盖 counting 漏洞);4 项 `V315-*` deferred items 登记 DEFERRED_LEDGER per D-51;AGENTS.md 加 OBSTACK 段。
- **6b 测试补完 ✅** (`265c15b5` → `31267e28`, 9 commits) — `tests/e2e/business_flow/` 16 集成测试 (smoke 2 + timeline 3 + interrupted 3 + sse 4 + evaluator 4);L0 proto 5 message 加 `business_key = 100` → RPC attachment **13/21 → 21/21**,9 caller 跨 5 crate 同步;L3 `observability.py` 加 3 record helpers (1 → 4)。**32 tests PASS** (16 Python + 4 Rust + 12 L3)。
- **6c 死代码激活 ✅** (`da38e862` + `ce027817` + `40b661f8` + `efba6e83`) — `init_observability()` v3.15.5 起在 `observability/mod.rs:164` 定义但 `main.rs` 从未调用 (死代码,`METER_READY=false`);6c.1 真接 `opentelemetry-stdout` 0.5 + main.rs 调用,6c.2/6c.3 `harness.rs` emit pre/post/flow_outcome。**6 L1 metric series active**;§0.1 4 处 ⚠️→✅ 回升 **23/23 (真闭环)**。
- **6d web-platform Dashboard ⏸ deferred → v3.16** per **D-53** (双轴模型:web-platform UI 属 Grid 独立产品轴,不在 OBSTACK 闭环范围)。原计划 8 task / 5 页面 / 5 routes (dual-gate 134 → 139 routes)。
- **6e CLI 全局接入 ⏸ deferred → v3.16** per **D-54** (data/integration 轴);功能面已由 6b.1 16 集成测试覆盖。原计划 10 task。
- **6h 补齐证据 + demo 改造 ✅ (2026-08-12)** — `b1d3585e` + `9022b3e9` + `09c82d35` + `41b577fc`。(a) 补 `tool.total` 端到端实证(6g 用例未触发 tool call;改用真触发 tool 的 prompt 后 `pre`/`post` 各 =1);(b) **`requests.*` 自 OTel 模块落地起从未被调用过** —— 以 tower layer 接在 tonic HTTP 层,19 RPC 一处统一计数;顺带修掉 `TimeBlock::record_request` 的双减 in_flight(按值收 `self` 又显式 dec,`Drop` 再减一次 → 首次真用即让 gauge 变负)与 metric-cardinality DoS(`op` label 直取路径尾段 → 任意对端可无限造 series;改为 proto 21 RPC allowlist,实测 5 条恶意路径 label 集不变);(c) **demo 脚本 4 个独立缺陷**(registry 空→handshake 静默降级 / LLM 步 30s 超时且失败不致命 / 5 事件手工 ingest / Observe 检查 grep 已不存在的文本且从不失败)全部修复。**双向验证**:真跑 exit 0(560 chunk、真实 `memory_search`、16-event timeline 含 PRE/POST_TOOL_USE+STOP、4/4 required series、`in_flight`=0);负控 exit 1(喂 6g 前的单空批次日志,准确列出 4 条缺失 series)。§0.1 = **23/23**,6/6 series 有真跑证据。100/100 tests。
- **6f 收口 ✅ 由 6g + 6h 完成** — 原计划的独立 verify 脚本未单写;真实验证由改造后的 `scripts/v315-obstack-demo.sh` 承担(它现在会失败),tag `v3.15.6` 已打。
- **6g 验证与修复 ✅ (2026-08-11 晚,tag 前的拦截)** — `4defa334` + `0318aca9` + `d39db604` + `75859214`。tag 前验 6c 的 4 处 ⚠️→✅,查出 **2 项不成立**:
  - **emit 挂错层**:`record_tool` / `record_business_flow_outcome` 只被 `on_tool_call/on_tool_result/on_stop` 调用,这三者全仓唯一调用者是 `service.rs:363/387/405` 的 gRPC handler —— 而该通道是 L4 给 **Tier 2/3** runtime 准备的。Grid 是 Tier 1(`native_hooks: true` / `requires_hook_bridge: false`),L4 手写代码零处调用。**实测:真实 tool-call turn 产出 `"scopeMetrics":[]`**。6g 将 emit 移到 `map_events_to_chunks` 的 `AgentEvent` 流。
  - **provider 提前 drop**:`init_observability` 的 `drop(provider)` 触发 `SdkMeterProviderInner::drop` → `shutdown()`(SDK 0.24.1 源码确认),导出循环停止、instrument 静默降 no-op;症状为**仅启动时 1 个空批次**。6g 存入 `OnceCell`。
  - **实测结果**:批次 1 → **40+**;`llm.total{deepseek-v4-flash}=2`、`flow.outcome{complete}`×2(Completed+Done 去重生效)、`in_flight=0`(Drop guard 收支平衡)、失败 turn `flow.outcome{error}` + `errors.total{agent_error}`。
  - **约束保持**:全部改动在 `grid-runtime` 内,未动 `grid-engine` → ADR-V2-023 P1 (shared-core rule) 保持,**无需新 ADR**。
  - 95/95 tests PASS(新增 10,含把 `classify_event` 拆为纯函数以便断言映射);dual-gate PASS。
Close-out retrospective: `docs/status/RETROSPECTIVE_2026-08-11-OBSTACK-V3-15-6.md`(6a/6b/6c);6g 证据: `docs/status/PRODUCTION_USABILITY_2026-08-11-obstack6g.md`。
Prior milestone: **v3.15 OBSTACK 平台级可观测 ✅ SHIPPED 2026-08-02 @ `84cc0680`** (§0.1 声称 23/23,v3.15.6a 查出 counting 漏洞实为 20/23,6c 后真闭环)。
Prior milestone: **v3.14 EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem ✅ SHIPPED 2026-07-30 (4-phase ladder 03.14.0 / 03.14.1 / 03.14.2 / 03.14.3; 4/4 phases, 100% complete)**
Scope: 4 phases (03.14.0 Ontology 服务 + taxonomy 路径 + cross-domain link + JSON-schema 派生 → 03.14.1 Skill Marketplace API + 第三方提交 / 4 阶段 promotion / 完整 ACL / analytics → 03.14.2 SDK scaffolding + JSON-schema 暴露 → 03.14.3 single-point live walkthrough + tag v3.14 + EVOLUTION_PATH 8-Phase 路线 ALL SHIPPED). 13–16 REQ-IDs across 5 categories (ONTOLOGY / MARKETPLACE / SDK / ECOSYSTEM-LIFECYCLE / COMPAT).
v3.14.0 派生不复制 (D-40): Ontology 服务 from existing L2 evidence anchor + L3 governance_decisions + L4 event_room_events + L5 four-card projections via SELECT; no new tables, no new columns, no new event types. v3.14.1 Marketplace API extends v3.11.2 eaasp-skill-registry (no replacement; D-41). v3.14.2 SDK scaffolding is thin client that wraps marketplace + ontology endpoints (no business logic re-implementation; D-42). v3.14.3 closes EVOLUTION_PATH §三 8-Phase roadmap (D-46) by tagging `v3.14` and marking V310-ECOSYSTEM-01 ✅ CLOSED.
Prior milestone: **v3.13 EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle) ✅ SHIPPED 2026-07-29 @ d0d83a23**
Prior scope: 4 phases complete (03.13.0 four-card data model + projection + L4 SSE bridge → 03.13.1 four-card SSE fan-out + state transitions + persistence → 03.13.2 retrospective cycle trace API → 03.13.3 single-point live walkthrough + tag v3.13), 13+ REQ-IDs / 5 categories (CARD-EVENT / CARD-EVIDENCE / CARD-ACTION / CARD-APPROVAL / RETROSPECTIVE + COMPAT / TRACE cross-axis).
Prior close: V310-COWORK-01 ✅ CLOSED; tag `v3.13` annotated; `docs/status/PRODUCTION_USABILITY_2026-07-29.md` captures the live walkthrough evidence; 82 targeted tests PASS; dual-gate PASS (134 routes RBAC + 4 files / 37 rows spec-audit).
Prior-prior milestone: **v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 ✅ SHIPPED 2026-07-27 @ 894639dd**
Prior-prior scope: 4 phases complete (03.12.0 → 03.12.3), 13-16 REQ-IDs in 5 categories (SCHEMA / EVENT-ROOM / A2A / SESSION / COMPAT + TRACE cross-axis).
Prior-prior verification: 03.12.0 audit.py `DECISION_ALLOWLIST` widens to `{allow, approve, deny, gate_request, await_human}` + `db.migrate_decision_await_human` idempotent ALTER TABLE migration + `approval_state_machine.py` paused Approve stage writes `approve_pause` row carrying `DECISION_AWAIT_HUMAN` (14 new targeted tests PASS). 03.12.1 Event Room data model + SQLite migration + multi-session event fan-out + `L4 /v1/rooms/{room_id}/sessions/{session_id}/events` endpoint with `ManageRooms` Action variant + 5 rounds of security review fixes (room_id required + principal-keyed membership gate + sibling-path parity + HMAC-SHA256 + ContextVar auth + log sanitization + empty-id test + caller auth + principal required + audit reliability). 03.12.2 A2A Router + A2A protocol envelope + 5 SSE event types + ReviewSet + aggregation engine + conflict detection + A2ARouter facade over EventRoom + MultiSessionCoordinator + review_set fail-open aggregation + principal-mismatch gate + cross_session audit pivot. 03.12.3 single-point live walkthrough against real OPA sidecar + Event Room + A2A Router.
Prior-prior close: `make rbac-audit` PASS (134 routes); `make v3.10-spec-audit` PASS (4 files / 37 rows); ADR-V2-023 P1 shared-core rule preserved (no shared-crate change); ADR-V2-035 Accepted (A2A Router credential gate); V310-A2A-01 + V310-SESSION-01 + V311-AUDIT-01 ✅ CLOSED.
Prior-prior-prior milestone: **v3.11 EAASP Phase 3 — production OPA backend + 5-stage approval chain ✅ SHIPPED 2026-07-27**
Prior-prior-prior scope: 4 phases complete (03.11.0 → 03.11.3), 29/29 REQ-IDs in 11 categories (OPA + INSTALL + OPA-BACKEND + REGO + FAIL-CLOSED + DISABLED + STAGE + SSE / AUDIT / DENY + LIVE).
Prior-prior-prior verification: 57 + targeted regression tests PASS; real OPA sidecar v0.68.0 on `127.0.0.1:18181`; 5 SSE events in canonical order (seq 26–30, single request_id); 18 rows in L3 `governance_decisions` ledger across 3 chain runs; `make rbac-audit` PASS (134 routes); `make v3.10-spec-audit` PASS (4 files / 37 rows); ADR-V2-023 P1 shared-core rule preserved (no shared-crate change).

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

### v3.14.0..03.14.3 EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem ✅ SHIPPED 2026-07-30

- 4 phases planned (03.14.0 Ontology 服务 + taxonomy 路径 + cross-domain link + JSON-schema 派生 → 03.14.1 Skill Marketplace API + 第三方提交 / 4 阶段 promotion / 完整 ACL / analytics → 03.14.2 SDK scaffolding + JSON-schema 暴露 → 03.14.3 single-point live walkthrough + tag v3.14 + EVOLUTION_PATH 8-Phase 路线 ALL SHIPPED).
- 13–16 REQ-IDs across 5 categories (ONTOLOGY / MARKETPLACE / SDK / ECOSYSTEM-LIFECYCLE / COMPAT) + TRACE cross-axis carry-over.
- Locked decisions D-38..D-46 (see PROJECT.md §Key Decisions):
  - **D-38** v3.14 scope = EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem. Closes V310-ECOSYSTEM-01. v3.14 = EVOLUTION_PATH 8-Phase 路线 收口 (final phase per D-46). v3.15+ = data/integration axis (per ADR-V2-024 §1).
  - **D-39** v3.14 不开新仓;仍 tools/eaasp-*/ 模拟器级实现;不开新服务端口. v3.14 does NOT open a new repo / does NOT open a new service port. Ontology 服务 + Marketplace API live in `tools/eaasp-ecosystem/` (新建 Python module). The `L4 /v1/ecosystem/ontology` + `L4 /v1/ecosystem/marketplace/...` endpoints sit behind the existing EAASP L4 service port.
  - **D-40** Ontology 服务派生自 v3.13 已落地的 L2 evidence + L3 governance_decisions + L4 event_room + L5 four-card projections;不新建独立存储. v3.14 = projection + view layer; 底层仍是 v3.7.3 / v3.10 / v3.11 / v3.12 / v3.13 既有数据. No new tables, no new columns, no new event types. D-32 carry-over.
  - **D-41** Marketplace API 在 v3.11.2 eaasp-skill-registry 之上扩展 submission / promotion / ACL / analytics;不替换 eaasp-skill-registry. v3.14's MarketplaceSkill / SubmissionAudit is built on top of the existing v3.11.2 `eaasp-skill-registry` (no replacement).
  - **D-42** SDK scaffolding 在 sdk/python/ + tools/eaasp-ecosystem-sdk/ 之上加 thin client + JSON-schema 暴露. v3.14's SDK scaffolding is a thin client that wraps the existing marketplace + ontology endpoints; it does NOT re-implement business logic. The `sdk/python/eaasp_sdk/` package emits a typed Python client; `tools/eaasp-ecosystem-sdk/` provides the CLI wrapper + JSON-schema codegen hooks.
  - **D-43** 仍以 Phase 0.5 MVP 人工可执行性为最低标尺 (threshold-calibration skill + `make dev-eaasp`);v3.14 extends the same MVP floor with an ecosystem walkthrough scenario.
  - **D-44** v3.9 / v3.10 / v3.11 / v3.12 / v3.13 全部硬约束不动 — Owner-only 边界不动 / AuthMode 兼容不动 / CI 顺序不动 / grid-engine 共享核心不动 / ADR-V2-023 P1 / ADR-V2-028 / ADR-V2-034 OPA sidecar / v3.11.2 5-stage approval / v3.12.1 Event Room ContextVar 鉴权 / v3.12.2 A2A Router + ReviewSet / v3.13 L5 Cowork + retrospective 全部保留. v3.9 RBAC + v3.10 spec-audit + ADR-V2-034 OPA sidecar + v3.12 Event Room + v3.12 A2A Router + v3.13 RETROSPECTIVE all continue to PASS.
  - **D-45** v3.14 探索策略 = Explore + Grep (本仓无 `.codegraph/`). Same as v3.13 D-36 + v3.12 D-29.
  - **D-46** v3.14 是 EVOLUTION_PATH 8-Phase 路线最终 phase;收口后 v3.10 登记的全部 8 项 V310-* deferred items 全部 ✅ CLOSED. Per `EAASP_v2_0_EVOLUTION_PATH.md` §三 8-Phase roadmap. v3.14 = Phase 6 = final phase. EVOLUTION_PATH 8-Phase 路线 ALL SHIPPED; no further Phase 7+ planned.

### v3.13 EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle) ✅ SHIPPED 2026-07-29 @ d0d83a23

- 4 phases SHIPPED (03.13.0 / 03.13.1 / 03.13.2 / 03.13.3), 13+ REQ-IDs in 5 categories (CARD-EVENT / CARD-EVIDENCE / CARD-ACTION / CARD-APPROVAL / RETROSPECTIVE + COMPAT + TRACE cross-axis).
- 03.13.0 four-card data model + projection + L4 SSE bridge SHIPPED: `EventCard` / `EvidenceCard` / `ActionCard` / `ApprovalCard` projection types in `tools/eaasp-l5-cowork/src/eaasp_l5_cowork/cards.py`; each card derives fields via SELECT from existing L2 / L3 / L4 / A2A tables (D-32); L4 SSE bridge emits `cowork.card.<type>.<event>` events mirroring underlying envelopes; cross-table count parity asserted by `test_four_card_projection_is_derived.py` (TRACE-03).
- 03.13.1 four-card SSE fan-out + state transitions + persistence SHIPPED: SSE fan-out delivers to all bound sessions (matching v3.12.1 EVENT-ROOM-02); state machine `pending → confirmed → acted` with `await_human` paused-state support; transitions persist as L3 governance_decisions rows.
- 03.13.2 retrospective cycle (trace API) SHIPPED: `trace_session(session_id) -> RetrospectiveChain` in `tools/eaasp-l5-cowork/src/eaasp_l5_cowork/retrospective.py` (D-33); `L5 /v1/cowork/trace/{session_id}` endpoint + `eaasp cowork trace {session_id}` CLI command; idempotent + bounded by tenant.
- 03.13.3 single-point live walkthrough + tag v3.13 SHIPPED: end-to-end live walkthrough against real OPA sidecar + Event Room + A2A Router + four-card projection; documented at `docs/status/PRODUCTION_USABILITY_2026-07-29.md`; 82 targeted tests PASS; dual-gate PASS (134 routes RBAC + 4 files / 37 rows spec-audit); tag `v3.13` annotated.
- V310-COWORK-01 → ✅ CLOSED. v3.9 RBAC + v3.10 spec-audit + ADR-V2-023 P1 + ADR-V2-034 OPA sidecar + v3.12 Event Room + A2A Router all preserved.

### v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 ✅ SHIPPED 2026-07-27 @ 894639dd

- 4 phases SHIPPED (03.12.0 / 03.12.1 / 03.12.2 / 03.12.3), 13-16 REQ-IDs in 5 categories (SCHEMA / MIGRATION / AWAIT-HUMAN / EVENT-ROOM / A2A / SESSION / COMPAT + TRACE cross-axis).
- 03.12.0 audit.py CHECK constraint patch SHIPPED: `DECISION_ALLOWLIST` widens to `{allow, approve, deny, gate_request, await_human}`; `db.migrate_decision_await_human` idempotent ALTER TABLE migration (v3.11.0 / v3.11.1 / v3.11.2 legacy DBs preserved); `approval_state_machine.py` paused Approve stage writes `approve_pause` row carrying `DECISION_AWAIT_HUMAN`; 14 new targeted tests PASS in `test_audit_decision_await_human.py` + `test_audit_await_human_migration.py`; V311-AUDIT-01 ✅ CLOSED.
- 03.12.1 Event Room + multi-session SHIPPED: `EventRoom` data model + SQLite migration + multi-session event fan-out + `L4 /v1/rooms/{room_id}/sessions/{session_id}/events` endpoint with `ManageRooms` Action variant; 5 rounds of security review fixes (room_id required + principal-keyed membership gate + sibling-path parity + HMAC-SHA256 + ContextVar auth + log sanitization + empty-id test + caller auth + principal required + audit reliability).
- 03.12.2 A2A Router SHIPPED: A2A protocol envelope + 5 SSE event types + ReviewSet + aggregation engine + conflict detection + A2ARouter facade over EventRoom + MultiSessionCoordinator + review_set fail-open aggregation + principal-mismatch gate + cross_session audit pivot; ADR-V2-035 Accepted (A2A Router credential gate).
- 03.12.3 single-point live walkthrough SHIPPED: end-to-end live walkthrough against real OPA sidecar + Event Room + A2A Router; documented at `docs/status/PRODUCTION_USABILITY_2026-07-28.md`.
- `make rbac-audit` PASS (134 routes). `make v3.10-spec-audit` PASS (4 files / 37 rows). ADR-V2-023 P1 shared-core rule preserved (no shared-crate change). ADR-V2-034 OPA sidecar ALIVE through every phase. V310-A2A-01 + V310-SESSION-01 + V311-AUDIT-01 → ✅ CLOSED. Tag `v3.12` pushed.

## Completed Milestones

### v3.13 EAASP Phase 5 — L5 Cowork 四卡 + 回溯闭环 ✅ SHIPPED 2026-07-29 @ d0d83a23

- 4 phases (03.13.0 / 03.13.1 / 03.13.2 / 03.13.3), 13+ REQ-IDs in 5 categories (CARD-EVENT / CARD-EVIDENCE / CARD-ACTION / CARD-APPROVAL / RETROSPECTIVE) + COMPAT / TRACE cross-axis.
- 03.13.0 four-card data model + projection + L4 SSE bridge SHIPPED: `EventCard` / `EvidenceCard` / `ActionCard` / `ApprovalCard` projection types in `tools/eaasp-l5-cowork/src/eaasp_l5_cowork/cards.py`; each card derives fields via SELECT from existing L2 / L3 / L4 / A2A tables (D-32); L4 SSE bridge emits `cowork.card.<type>.<event>` events.
- 03.13.1 four-card SSE fan-out + state transitions + persistence SHIPPED: SSE fan-out delivers to all bound sessions (matching v3.12.1 EVENT-ROOM-02); state machine `pending → confirmed → acted` with `await_human` paused-state support.
- 03.13.2 retrospective cycle (trace API) SHIPPED: `trace_session(session_id) -> RetrospectiveChain` in `tools/eaasp-l5-cowork/src/eaasp_l5_cowork/retrospective.py`; `L5 /v1/cowork/trace/{session_id}` endpoint + `eaasp cowork trace {session_id}` CLI command; idempotent + bounded by tenant.
- 03.13.3 single-point live walkthrough + tag v3.13 SHIPPED: end-to-end live walkthrough against real OPA sidecar + Event Room + A2A Router + four-card projection; documented at `docs/status/PRODUCTION_USABILITY_2026-07-29.md`; 82 targeted tests PASS; dual-gate PASS (134 routes RBAC + 4 files / 37 rows spec-audit).
- V310-COWORK-01 → ✅ CLOSED. Tag `v3.13` annotated.

### v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 ✅ SHIPPED 2026-07-27 @ 894639dd

- 4 phases (03.12.0 / 03.12.1 / 03.12.2 / 03.12.3), 13-16 REQ-IDs in 5 categories (SCHEMA / EVENT-ROOM / A2A / SESSION / COMPAT) + TRACE cross-axis.
- 03.12.0 audit.py CHECK constraint patch SHIPPED: `DECISION_ALLOWLIST` widens to include `await_human`; `db.migrate_decision_await_human` idempotent ALTER TABLE migration; `approval_state_machine.py` paused Approve stage writes `approve_pause` row carrying `DECISION_AWAIT_HUMAN`; 14 new targeted tests PASS in `test_audit_decision_await_human.py` + `test_audit_await_human_migration.py`; `docs/design/EAASP/DEFERRED_LEDGER.md` V311-AUDIT-01 → ✅ CLOSED.
- 03.12.1 Event Room + multi-session SHIPPED: `EventRoom` data model + SQLite migration + multi-session event fan-out + `L4 /v1/rooms/{room_id}/sessions/{session_id}/events` endpoint with `ManageRooms` Action variant; 5 rounds of security review fixes.
- 03.12.2 A2A Router SHIPPED: A2A protocol envelope + 5 SSE event types + ReviewSet + aggregation engine + conflict detection + A2ARouter facade over EventRoom + MultiSessionCoordinator + review_set fail-open aggregation + principal-mismatch gate + cross_session audit pivot; ADR-V2-035 Accepted.
- 03.12.3 single-point live walkthrough SHIPPED: end-to-end live walkthrough against real OPA sidecar + Event Room + A2A Router.
- v3.9 RBAC audit still PASS (134 routes — unchanged). v3.10 spec-audit still PASS (4 files / 37 rows). ADR-V2-023 P1 shared-core rule preserved (no shared-crate change). ADR-V2-034 OPA sidecar ALIVE through every phase. V310-A2A-01 + V310-SESSION-01 + V311-AUDIT-01 → ✅ CLOSED. Tag `v3.12` pushed.

### v3.11 EAASP Phase 3 — production OPA backend + 5-stage approval chain ✅ SHIPPED 2026-07-27

- 4 phases (03.11.0 / 03.11.1 / 03.11.2 / 03.11.3), 29/29 REQ-IDs in 11 categories (OPA + INSTALL + OPA-BACKEND + REGO + FAIL-CLOSED + DISABLED + STAGE + SSE / AUDIT / DENY + LIVE).
- ADR-V2-034 Accepted; `make opa-install` reproducible (03.11.0); L3 OPA backend `OPABackend.evaluate()` called from `PolicyEngine.evaluate_with_opa()` when `opa_enabled=True`; Rego template `policies/governance.rego` implements deny-always-wins (spec §15.9), risk classification (spec §6.1), and 3-state decision contract (spec §6.9, §6.10); 5 fail-closed modes covered with stable cause identifiers carried in the audit rationale; 5-stage approval state machine (Plan → Check → Draft → Approve → Execute) with `governance.approval.*` SSE events + append-only `governance_decisions.stage` column extension; `V310-OPA-01` + `V310-APPROVAL-01` ✅ CLOSED.
- 57 + targeted regression tests PASS; v3.11.3 single-point live walkthrough against real OPA sidecar v0.68.0 captured at `docs/status/PRODUCTION_USABILITY_2026-07-27.md` (5 SSE events in canonical order; 18 rows in L3 ledger across 3 chain runs).
- v3.9 RBAC audit still PASS (134 routes); v3.10 spec-audit still PASS (4 files / 37 rows); ADR-V2-023 P1 shared-core rule preserved (no shared-crate change).

### v3.10 EAASP v2.0 platform-skeleton alignment ✅ SHIPPED 2026-07-26

- 4 phases (03.10.0 / 03.10.1 / 03.10.2 / 03.10.3), 16/16 REQ-IDs closed.
- Five-layer/three-pipeline/four-card matrix, deterministic spec auditor, payload-driven MCP guard, ordered CI gate.
- 174 targeted tests PASS. `make v3.10-spec-audit` exits 0.

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
  - D-06 `RouteCatalog` is the source of truth (`pub`); both manual-decorated-router and generate-catalog-from-router patterns acceptable.
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
  - D-18 Phase ladder 03.10.0 (skeleton audit + alignment matrix) → 03.10.1 (MAT axis) → 03.10.2 (PIPE axis) → 03.10.3 (VERIFY axis).

- **v3.11 locked decisions** (from v3.11.0 bootstrap, 2026-07-26):
  - D-19 OPA sidecar deployment topology: ADR-V2-034 — sidecar OPA on `127.0.0.1:18181`, in-repo Rego templates + atomic user bundles, fail-closed on OPA error. `make opa-install` downloads official OPA binary with SHA256 verify.
  - D-20 No shared-crate change: v3.11.0 / 03.11.1 / 03.11.2 / 03.11.3 must NOT touch `grid-types` / `grid-engine` / `grid-sandbox` / `grid-hook-bridge`; ADR-V2-023 P1 (shared-core rule) preserved; COMPAT-02 verified at every phase.
  - D-21 Backward-compatible contract surface: `proto/eaasp/runtime/v2/` 21 RPC + `contract-v1.2.0` tests remain green; no proto-breaking changes; new spec sections deferred to v3.12+ (D-13 carry-over).
  - D-22 Phase ladder 03.11.0 (sidecar + ADR) → 03.11.1 (L3 OPA backend + Rego) → 03.11.2 (5-stage approval state machine) → 03.11.3 (single-point live walkthrough).
- **v3.12 locked decisions** (from v3.12 bootstrap, 2026-07-27 — non-negotiable):
  - D-23 `audit.py` CHECK constraint patch is mandatory phase 0. v3.11.3 live walkthrough §7 surfaced that `audit.py`'s CHECK constraint on `governance_decisions.decision` does not include `await_human`; the 5-stage state machine emits `await_human` at the Approve stage; without this fix, 03.12.1 / 03.12.2 / 03.12.3 cannot reproduce paused-state audit evidence. v3.12.0 MUST patch the schema first; no implementation work in 03.12.1 / 03.12.2 may proceed before 03.12.0 ships. Closes `V311-AUDIT-01`.
  - D-24 v3.12 scope = EAASP Phase 4. v3.12 delivers A2A Router + Event Room + multi-session coordination per EAASP_v2_0_EVOLUTION_PATH.md §三 Phase 4 scope (spec §5.3 / §14 / §17). Closes V310-A2A-01 + V310-SESSION-01 + V311-AUDIT-01. v3.13+ = Phase 5 L5 / Phase 6 ecosystem.
  - D-25 MVP executable baseline + new A2A coordination scenario. Phase 0.5 MVP human-executable floor (`threshold-calibration` skill + `make dev-eaasp`) remains the minimum bar; v3.12 adds a new A2A coordination walkthrough scenario on top of that floor.
  - D-26 `audit.py` CHECK constraint extension uses idempotent `ALTER TABLE` migration. The extension MUST use `ALTER TABLE` (matching the existing v3.11.2 `stage` column migration pattern at the same `audit.py` module); existing DBs upgrade cleanly without losing history. No destructive schema work. No new tables / no new columns beyond the CHECK constraint extension.
  - D-27 v3.12 stays in `tools/eaasp-*/` simulator-level implementations. v3.12 does not open a new repo / does not open a new service port; uses the existing 7 EAASP services (skill-registry / L2 / L3 / mock-scada / MCP orchestrator / grid-runtime / L4) on `.grid/dev-eaasp-live.sh` launch topology. Event Room + A2A Router live in `tools/eaasp-l4-orchestration/` (per v3.7.3 L4 ownership pattern).
  - D-28 v3.12 安全边界 + shared-core rule + rbac-audit + v3.10-spec-audit + OPA sidecar all continue to PASS. v3.9 route-catalog RBAC (134 routes / `make rbac-audit`) + v3.10 spec-audit (4 files / 37 rows / `make v3.10-spec-audit`) + ADR-V2-023 P1 shared-core rule + ADR-V2-034 OPA sidecar ALL continue to PASS through every v3.12 phase. No shared-crate change is anticipated, but if any change is required it must remain leg-agnostic across engine 接入面 (EAASP) and Grid 独立产品.
  - D-29 v3.12 探索策略 = Explore + Grep. No `.codegraph/` in this repo; no MCP codegraph tool available. Codebase pattern reads gate by CLAUDE.md "Level 1+ single-pass reads" rule.
- **v3.13 locked decisions** (from v3.13 bootstrap, 2026-07-27 — non-negotiable):
  - D-30 v3.13 scope = EAASP Phase 5 L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle). Per `EAASP_v2_0_EVOLUTION_PATH.md` §三 Phase 5 (spec §4 + §4.4). Closes `V310-COWORK-01`.
  - D-31 L5 仍以 EAASP v2.0 spec §4 + §4.4 为权威源;本仓前端 (web/ + web-platform/) 仍为 dormant 状态;v3.13 在 `tools/eaasp-l5-cowork/` (新建) 落模拟器级四卡 backend + projection.
  - D-32 四卡全部派生自 v3.12 已落地的 L2 evidence anchor + L3 governance_decisions + L4 event_room_events + A2A review.closed 事件;不新建独立存储. v3.13 = 投影 + 视图层;底层仍是 v3.7.3 / v3.10 / v3.11 / v3.12 既有数据.
  - D-33 回溯闭环 (retrospective cycle) = 任何四卡 record 都能以 `session_id` 为根 trace 到 Event → Evidence → Action → Approval 全链;新增 `tools/eaasp-l5-cowork/retrospective.py` 提供 trace API (`trace_session(session_id) -> RetrospectiveChain`).
  - D-34 仍以 Phase 0.5 MVP 人工可执行性为最低标尺 (threshold-calibration skill + `make dev-eaasp`);v3.13 extends the same MVP floor with a four-card walkthrough scenario.
  - D-35 v3.9 / v3.10 / v3.11 / v3.12 硬约束不动 — Owner-only 边界不动 / AuthMode 兼容不动 / CI 顺序不动 / grid-engine 共享核心不动 / ADR-V2-023 P1 / ADR-V2-028 / ADR-V2-034 OPA sidecar / v3.11.2 5-stage approval / v3.12.1 Event Room ContextVar 鉴权 / v3.12.2 A2A Router + ReviewSet 全部保留.
  - D-36 探索策略保持 Explore + Grep (本仓无 `.codegraph/`).
  - D-37 v3.13 不开新前端 (react/typescript);仍 `tools/eaasp-*/` 模拟器级实现;不开新服务端口。
- **v3.14 locked decisions** (from v3.14 bootstrap, 2026-07-28 — non-negotiable):
  - D-38 v3.14 scope = EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem. Per `EAASP_v2_0_EVOLUTION_PATH.md` §三 Phase 6 (spec §7.5–§7.8). Closes V310-ECOSYSTEM-01. v3.14 = EVOLUTION_PATH 8-Phase 路线 收口 (final phase per D-46). v3.15+ = data/integration axis (per ADR-V2-024 §1).
  - D-39 v3.14 不开新仓;仍 tools/eaasp-*/ 模拟器级实现;不开新服务端口. v3.14 does NOT open a new repo / does NOT open a new service port. Ontology 服务 + Marketplace API live in `tools/eaasp-ecosystem/` (新建 Python module). The `L4 /v1/ecosystem/ontology` + `L4 /v1/ecosystem/marketplace/...` endpoints sit behind the existing EAASP L4 service port. D-27 + D-37 carry-over.
  - D-40 Ontology 服务派生自 v3.13 已落地的 L2 evidence + L3 governance_decisions + L4 event_room + L5 four-card projections;不新建独立存储. v3.14 = projection + view layer; 底层仍是 v3.7.3 / v3.10 / v3.11 / v3.12 / v3.13 既有数据. No new tables, no new columns, no new event types. Reuses the existing 21 RPC + `contract-v1.2.0` baseline. D-32 carry-over (projection + 视图层).
  - D-41 Marketplace API 在 v3.11.2 eaasp-skill-registry 之上扩展 submission / promotion / ACL / analytics;不替换 eaasp-skill-registry. v3.14's MarketplaceSkill / SubmissionAudit is built on top of the existing v3.11.2 `eaasp-skill-registry` (no replacement). The marketplace extends the registry's lifecycle (4-stage promotion), ACL (per-tenant + per-role), and analytics. The underlying skill_manifest / entrypoints / mcp_servers / permissions remain in `eaasp-skill-registry` (per V310-MAT-01 deferral rationale).
  - D-42 SDK scaffolding 在 sdk/python/ + tools/eaasp-ecosystem-sdk/ 之上加 thin client + JSON-schema 暴露. v3.14's SDK scaffolding is a thin client that wraps the existing marketplace + ontology endpoints; it does NOT re-implement business logic. The `sdk/python/eaasp_sdk/` package emits a typed Python client; `tools/eaasp-ecosystem-sdk/` provides the CLI wrapper + JSON-schema codegen hooks. TypeScript / Go / Java SDK deferred to v3.15+.
  - D-43 仍以 Phase 0.5 MVP 人工可执行性为最低标尺 (threshold-calibration skill + `make dev-eaasp`);v3.14 extends the same MVP floor with an ecosystem walkthrough scenario. v3.14.3 produces `docs/status/PRODUCTION_USABILITY_2026-07-30.md` exercising `eaasp marketplace submit / promote / list / stats` end-to-end against the real OPA sidecar + Event Room + A2A Router + L5 Cowork + Ontology + Marketplace + SDK. D-25 / D-34 carry-over.
  - D-44 v3.9 / v3.10 / v3.11 / v3.12 / v3.13 全部硬约束不动. v3.9 134 routes RBAC / spec-audit 4 files 37 rows / ADR-V2-023 P1 / ADR-V2-028 / ADR-V2-034 OPA sidecar / v3.11.2 5-stage approval / v3.12.1 Event Room ContextVar 鉴权 / v3.12.2 A2A Router + ReviewSet / v3.13 L5 Cowork + retrospective 全部保留. v3.9 RBAC + v3.10 spec-audit + ADR-V2-034 OPA sidecar + v3.12 Event Room + v3.12 A2A Router + v3.13 RETROSPECTIVE all continue to PASS. D-35 carry-over.
  - D-45 v3.14 探索策略 = Explore + Grep (本仓无 `.codegraph/`). Same as v3.13 D-36 + v3.12 D-29.
  - D-46 v3.14 是 EVOLUTION_PATH 8-Phase 路线最终 phase;收口后 v3.10 登记的全部 8 项 V310-* deferred items 全部 ✅ CLOSED. Per `EAASP_v2_0_EVOLUTION_PATH.md` §三 8-Phase roadmap. v3.14 = Phase 6 = final phase. Once 03.14.3 ships, V310-ECOSYSTEM-01 → ✅ CLOSED (V310-OPA-01 / V310-APPROVAL-01 / V310-A2A-01 / V310-COWORK-01 / V310-SESSION-01 / V311-AUDIT-01 already CLOSED; V310-SANDBOX-01 + V310-MAT-01 are L1-infrastructure / typed-schema scope items, NOT Phase 6 deliverables — see v3.14 §Out of Scope + V310-MAT-01 row in DEFERRED_LEDGER.md). EVOLUTION_PATH 8-Phase 路线 ALL SHIPPED; no further Phase 7+ planned.

### Pending Todos

- **`V316-L2L3L4-OBS-01`(6i 新发现,建议优先)** — L2/L3/L4 三层 `observability.py` 定义齐全但 **0 处生产调用**,meter 恒为 noop;各层测试只测 helper 自身,无一条断言生产路径会调用。修复判据沿用 L1 6g/6h:接入调用点 + 真跑看计数器动 + 配负控。
- **v3.16 scope 决策** (下一步) — per ADR-V2-024 data/integration 轴候选:`grid-server multi-user`(3.7.4 deferred)/ `web-platform 7.5 → 9.0` / `grid-desktop 6.5 → 9.0` / 6d + 6e 顺延。
- **6d web-platform Dashboard** (deferred → v3.16, D-53) — 5 页面 (FlowsOverview / FlowDetail / FlowOptimize / Alerts / Stats) + `obstackClient.ts` + App.tsx 5 routes + grid-server `rbac/catalog.rs` 5 路由;dual-gate 134 → **139 routes**。
- **6e CLI 全局接入 + 工具生态** (deferred → v3.16, D-54) — `eaasp flow list/top-failed/top-slow` 3 verb + business_key 列贯穿 session/memory/skill/policy + grid-eval 接 OBSTACK + marketplace 健康度。

### Blockers/Concerns

- ~~`tool.total` / `requests.*` 缺端到端实证~~ → **6h 已闭环**,6/6 series 真跑验证。
- ~~demo 脚本仍是半真~~ → **6h 已改造**:手工 ingest 删除、LLM 步失败致命、Observe 改 JSON 断言并配负控。
- **L2/L3/L4 observability 是死代码(6i 已确认,登记 `V316-L2L3L4-OBS-01`)** — 三层 `record_*` 定义齐全但 `src/` 全域 0 处生产调用,`main.py` 0 提及,meter 恒为 `_NoopMeter`。**这是 6c 同一缺陷的第 2/3/4 次出现,属系统性问题**:本仓把"写了 observability 模块 + 测了该模块"当成了"接入了可观测性"。
- **`.env` 影子变量陷阱** — shell 中导出的旧 `DEEPSEEK_API_KEY` 会盖住 `.env`(dotenvy 不覆盖已存在环境变量),表现为 401 且极难一眼看出。跑 live 验证前先 `unset` 或比对哈希。
- **L4 `/v1/sessions/{id}/message` 挂起** — 240s 无响应;skill-registry 报 `threshold-calibration not found`。与 OBSTACK 改动无关,独立问题,未排期。
- **CI 两条 workflow 长期 FAIL (非本次引入,2026-08-11 push 后复核确认)**:
  - `Phase 3 Contract Matrix` — `make v2-phase2_5-ci-setup` 目标在 Makefile 中**根本不存在** (grep 0 命中);历史 8 次运行全部同因 FAIL。即 MEMORY.md 记的 "CI Makefile tier gap"。
  - `CI` — `glib-sys v0.18.1` 构建失败 (grid-desktop / Tauri 系统库在 runner 缺失);历史多次同因 FAIL。
  - 二者均为**既有环境/配置缺口**,与 v3.15.6 无因果关系。修复未排期。
- **Quality gaps in shipped components**: `web-platform/` (Quality 7.5) and `grid-desktop` (Quality 6.5) shipped with Activation but remain below the 9.0+ bar the rest of the components have hit. Need follow-on feature work (Markdown + toast + skeletons + error states for web-platform/; Icons + IPC proxy + Grid rebrand for grid-desktop).
- **EAASP v2.0 platform-evolution gaps**: L1 infrastructure tier changes (V310-SANDBOX-01); V310-MAT-01 typed schema work; data/integration axis (per ADR-V2-024 §1). Per `docs/design/EAASP/EAASP_v2_0_EVOLUTION_PATH.md`.
- **Local environment**: `.env` has `OPENAI_NO_PROXY=1` for Clash. `LLM_PROVIDER=deepseek`,model `deepseek-v4-flash`(reasoning model,`reasoning_content` 会吃掉小 max_tokens 预算)。
- **v3.9 Action vocabulary growth discipline** (D-04): extension is allowed but each new variant must map to a coherent semantic; auditor surfaces gaps; "manage everything" catch-all is forbidden.
- **v3.13 L5 frontend dormant** (D-31 / D-37 / D-39 / D-53): web/ + web-platform/ remain dormant through v3.15.6; UI activation deferred to v3.16.

## Session Continuity

Last session: 2026-08-11 晚 → 2026-08-12 (v3.15.6 6g — tag 前验证 + 修复) — 准备执行 6f 时先验 6c 的 4 处 ⚠️→✅ 是否站得住,查出 **2 项不成立**:6c.2/6c.3 的 emit 挂在 Tier 1 runtime 永不经过的 hook RPC 上(实测真实 tool-call turn 产出 `"scopeMetrics":[]`);更底层 `drop(provider)` 令导出管道启动即 shutdown(仅 1 个空批次)。两者均已修复,真实 deepseek turn 实测 4/6 series 出数(批次 1 → 40+)。§0.1 由 23/23 诚实降为 **21/23**。顺带修好自 6b.2b 起就断的 `cargo check --workspace`。**未 tag** —— tag 等于给"真闭环"背书,而 `tool.total` 端到端实证仍缺。本 session 早段另完成:20 commits push + CI 判因(两条 FAIL 均为既有缺口)+ 状态文件刷新 + JOURNAL 补记 6b.2~6c.7 空档。

Stopped at: **v3.15.6 4/6 阶段完成** — 6a ✅ / 6b ✅ / 6c ✅(经 6g 修正)/ 6g ✅;6d + 6e deferred → v3.16 (D-53/D-54);**6f 待执行且前置条件已扩大**(见 Pending Todos)。HEAD `75859214`(+ 本次 state/journal commit),working tree clean。

Prior sessions:

- 2026-08-09 → 2026-08-11 (v3.15.6 OBSTACK 实战补完 3 阶段 climb): 19 commits 跨 6a 文档 / 6b 测试 / 6c 死代码激活;retrospective `docs/status/RETROSPECTIVE_2026-08-11-OBSTACK-V3-15-6.md`。其自述教训 "cargo check exit 0 ≠ Rust 真编译" 方向正确,但**执行上仍未真跑验证**,导致 6c 的修复本身又是死代码 —— 6g 才用真实 turn 拦下。
- 2026-07-27 (autonomous v3.12 climb): v3.12 SHIPPED — 4 phases (03.12.0 audit.py CHECK constraint patch + 03.12.1 Event Room + multi-session + 03.12.2 A2A Router + 03.12.3 single-point live walkthrough; tag `v3.12` pushed 894639dd; then v3.13 milestone bootstrap).
- 2026-07-27 (autonomous v3.11.2 + 03.11.3 climb): v3.11 SHIPPED — 29/29 REQ-IDs closed (4 phases: 03.11.0 OPA sidecar / 03.11.1 L3 OPA backend + Rego / 03.11.2 5-stage approval state machine / 03.11.3 single-point live walkthrough against real OPA sidecar v0.68.0).
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

*Milestone v3.14 EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem bootstrapping (this commit). v3.13 EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle) ✅ SHIPPED 2026-07-29 @ d0d83a23 (4 phases, 13+ REQ-IDs / 5 categories, tag `v3.13` annotated, V310-COWORK-01 ✅ CLOSED). v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 ✅ SHIPPED 2026-07-27 @ 894639dd (4 phases, 13-16 REQ-IDs / 5 categories, tag `v3.12` pushed). v3.11 EAASP Phase 3 — production OPA backend + 5-stage approval chain ✅ SHIPPED 2026-07-27. v3.10 EAASP v2.0 platform-skeleton alignment ✅ SHIPPED 2026-07-26. v3.9 SHIPPED 2026-07-26. v3.8 SHIPPED 2026-07-24. v3.7 SHIPPED 2026-07-23.*
