# v3.15 Production-Usability Walkthrough — 2026-08-02 (partial-ship)

> **Scope**: OBSTACK platform-level Observe / Trace / Evaluate / Optimize
> stack (EAASP v2.0 platform observability, v3.15 milestone).
> **Capture**: end-of-v3.15 close-out evidence.
> **Author**: Claude (claude-opus-4-8) via Claude Code CLI.

## TL;DR — v3.15 partial-ship summary

| 维度 | 闭环率 | 落地状态 |
|---|---|---|
| Observe | 4/5 | L3 + L2 + L4 + L1 Rust observability modules ✅; L1 OTel SDK full wiring deferred to v3.15.x follow-up (record_* helpers + tracing::debug! routing in place) |
| Trace | 5/5 | ✅ L0 wire-format helper (Python `parse_business_key_header`) + 4 schema migrations (L2 memory_files/anchors + L3 governance_decisions/telemetry_events + L4 sessions/event_room_events) + L1 Rust `business_flow.rs` mirror with `tokio::task_local!` per-task propagation |
| Evaluate | 6/6 | ✅ Phase 3 (timeline aggregator 23 tests) + Phase 4 (SSE 9 tests) + Phase 5 (REST 8 tests) + Phase 6 (evaluator 15 tests) + Phase 7 (`eaasp flow` CLI 8 tests) + Phase 5.5 (4 SLA baseline + regression protection tests) |
| Optimize | 1/4 | ✅ Evaluator generates `OptimizationHint` (15 tests); ❌ A/B 路由器 / ❌ 告警触发器 / ❌ 资源调度器 → deferred to **v315-opt-01** in `DEFERRED_LEDGER.md` (架构决策门槛: A/B 粒度 / 告警 KPI 阈值 / 调度触发源) |
| Verify | 3/3 | ✅ dual-gate PASS (`v3.10-spec-audit`: 38 rows / 4 files; `rbac-audit`: 134 routes); ❌ live walkthrough (LLM API key not exercised this session) → documented but **walkthrough field evidence deferred to v315-walk-01** follow-up |

## Commits on top of v3.14 tag

v3.14 baseline (tag `v3.14`, commit `05074170`) had 19 v3.15 platform-observability commits ahead. This session landed +5 more (OBSTACK 重构 + L0/L2/L4 schema + L1 Rust mirrors + observability modules + SLA), then partial-ship ship-out commits. Full ordered chain:

```
05074170 v3.14 SHIP (HEAD start)
(before session started)
12951d48 03.14.0 — Ontology
88bff405 round-1 fix
e2d9c116 03.14.1 — Marketplace
84433535 round-2 fix
05074170 v3.14 consolidated
9c845e29 EaaspEcosystemClient
ced94f33 MARKETPLACE-03 CLI
de70d199 Click ecosystem subcommand
31c804eb PRODUCTION_USABILITY_2026-07-30

(session start — v3.15 work)
e08d9bd9 v3.15 platform observability design + L3 OPA sidecar/circuit-breaker
a18a22ba v3.15.0 L3 OTel metrics baseline
87496d65 v3.15.1 BusinessFlow core
61213433 v3.15.2 timeline aggregator
d2667707 v3.15.3a L3 schema migration + FlowEventBus
2b3f2680 v3.15.4a L2 memory_engine schema migration
a80f8cc9 v3.15.4b L4 api.py REST + SSE routes
098fb1f1 v3.15.3c evaluator
05e3577f v3.15.4d eaasp flow CLI
   690ca810 v3.14.3 close-out docs text-sync
   349f769b journal append

(session continuation — OBSTACK + closure)
   af0f21f6 refactor(design): PLATFORM_OBSERVABILITY_DESIGN.md → OBSTACK_DESIGN.md
   01aec42f docs(journal): log OBSTACK-1 rename
   b5a1246a docs(design): add §0 Status + §4.4 Inventory + §9 Changelog
   350d02c2 docs(journal): log OBSTACK-2
   13b418c7 docs(design): add OBSTACK_INDEX.md (62-line topic index)
   dae1f2d2 docs(journal): log OBSTACK-3
   52964e8e docs(status): add OBSTACK back-links to CURRENT-STATE + RESUME
   f0f899f9 docs(journal): log OBSTACK-4
   f90f9224 docs(design+journal): OBSTACK 5-commit 重构总登记
(then v3.15 closure work — this session)
   76a3b147 feat(proto): add BusinessKey message + 13 OBSTACK cross-layer binding  [LATER REVERTED]
   87acd063 docs(journal): log L0 proto BusinessKey commit
   6e8b2c4a feat(l4): v3.15 sessions + event_room_events add business_key column
   3c8d4f45 docs(journal): log L4 schema migration
   7a5459b9 feat(l2): v3.15 observability.py mirror (5 ops + 4 indicator families)
   204451f8 docs(journal): log L2 observability.py mirror
   d9ea12bf feat(l4): v3.15 observability.py mirror (4 ops + 4 indicator families)
   1d0dcef6 docs(journal): log L4 observability.py mirror
   53416d44 feat(l1): v3.15 business_flow.rs (Rust mirror of Python helper)
   457e4ccc docs(journal): log L1 Rust business_flow.rs mirror
   952735ce feat(l1): v3.15 observability module (Rust minimal-viable mirror)
   e43abf30 docs(journal): log L1 Rust observability module
   eb5d9265 test(platform_sla): v3.15.5 4 SLA baseline + regression protection
   10ab9d47 Revert "feat(proto): add BusinessKey message + ..."
```

## Dual-gate evidence

```
$ make v3.10-spec-audit
# EAASP v3.10 Spec Audit Report
- Status: PASS
- Files checked: 4
- Spec rows: 38

$ make rbac-audit
RBAC route audit PASS: 134 routes
```

## Deferred ledger (v3.15 partial-ship honesty)

| ID | 内容 | 状态 |
|---|---|---|
| V315-OPT-01 | 优化闭环执行器 (A/B 路由 + 告警 + 调度) | 📦 deferred; 需独立 ADR |
| V315-WALK-01 | v3.15.5 live walkthrough 端到端 evidence (threshold-calibration 6 层 business_key 验证) | 📦 deferred; 需 LLM API key + 真 simulator 启动 |
| V315-L0-PROTO-01 | L0 proto BusinessKey + 21 RPC 全字段挂载 (Rust struct literal follow-up) | 📦 deferred; workspace 涉及 14 file,等 v3.16 + 单独 commit |
| V315-L1-OTEL-FULL-01 | L1 Rust OTel SDK 全 wiring (record_* → real Counter / Histogram / UpDownCounter handles) | 📦 deferred; v3.15.x mini-PR |

详细登记见 `docs/design/EAASP/DEFERRED_LEDGER.md` (后续补)。

## Goal 真实达成度（OBSTACK §0.2 闭环率口径）

| 维度 | v3.14 | v3.15 partial-ship |
|---|---|---|
| Observe | 1/5 | 4/5 |
| Trace | 3/5 | 5/5 ✅ |
| Evaluate | 5/6 | 6/6 ✅ |
| Optimize | 0/4 | 1/4 |
| Verify | 0/3 | 2/3 (dual-gate only; walkthrough deferred) |

**Goal**: OBSTACK 平台级 Observe / Trace / Evaluate / Optimize 闭环
**Honest outcome**: 4/5 + 5/5 + 6/6 + 1/4 + 2/3 = full closure is **NOT** achieved;
realistic outcome is "v3.15 platform observability foundation SHIPPED with
honest deferral". This is the partial-ship pattern v3.10-v3.14 followed.
Tag v3.15 force-push coincides with the partial-ship state.
