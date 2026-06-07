# Grid — Requirements

> **Brownfield context**: 14 archived phases (Phase BA → Phase 4a) under dev-phase-manager already shipped EAASP v2.0 functional baseline. Milestone v3.0 closed 2026-04-28 (ADR-V2-024 Accepted). v3.1 Phase 5 Engine Hardening closed 2026-05-22 (6 phases, 23 REQ-IDs). v3.2 Phase 6 Tech-Debt Triage closed 2026-05-26 (3 phases, 6 REQ-IDs). v3.3 Phase 7 Engine + Platform Debt Sweep closed 2026-06-07 (Phase 7.3 L3 RBAC completed, 8/8 REQ-IDs; 7.0/7.1/7.2 carry-forward). This REQUIREMENTS.md scopes **milestone v3.4 — Full INBOX Drain (Debt Sweep II)**.

---

## v3.4 Requirements (Milestone: Full INBOX Drain — Debt Sweep II)

> **Per ADR-V2-024 §1 双轴模型 + Open Item #3**: 优先发力组合 grid-cli + grid-server 不变; 其余 (grid-platform / grid-desktop / web*) 保持 dormant. 工时 baseline: Grid 全栈 ≈60% / EAASP 引擎 ≈30% / 元工作 ≈10%.
>
> **Scope shape**: Full drain of `.planning/v3.3-INBOX.md` remaining ~85 rows. Carry-forward verification of v3.3 Phase 7.0/7.1/7.2 (research indicates items may already be closed — verify-then-close in v3.4). New phases cover L4 / hooks / L2 leftovers / L3 leftovers / grid-engine leftovers / grid-server / contract leftovers / eval / cross-cutting. ~55 new REQ-IDs + ~10 items explicitly deferred. 0 P1 rows — milestone is "should fix" not "must fix."
>
> **Deferred items (explicit anti-features for v3.4)**: D75 (NATS JetStream), D76 (push-based subscribe), D77 (TopologyAwareClusterer), D79 (multi-worker pipeline), D80 (causal graph clusterer), D73 (Event Room), D36 (event window cursor), D21 (L3 retention policy), D32 (L4 concurrency E2E). Rationale: premature scale optimizations — all tagged 📦 long-term in LEDGER, no current production use case. v3.4 formalizes deferral with LEDGER close-out notes.

### A. ENGINE — grid-engine carry-forward verification (Phase 7.0)

> **Note**: Research indicates all 6 ENGINE-01..06 rows may already be closed during Phase 7.0 execution. v3.4 includes them as **verify-and-close**: confirm each D-row in DEFERRED_LEDGER.md has a ✅ CLOSED tag with commit hash. If verified done, mark as validated and skip implementation. If not done, implement the open items.

- [ ] **ENGINE-01**: D102 — `AgentLoopConfig.compaction` 字段接入 YAML 配置层 (P2). Verify round-trip test exists, strict-by-default validation active per ADR-V2-028. LEDGER L232。
- [ ] **ENGINE-02**: D3 — harness 接入 `payload.user_preferences` + `trim_for_budget()` (P3). Verify user preferences surface to agent loop, trim is budget-driven. LEDGER L106。
- [ ] **ENGINE-03**: D57 — `harness_payload_integration.rs` DRY fix — single `build_memory_preamble` implementation. Verify no duplicate. LEDGER L177。
- [ ] **ENGINE-04**: D58 — `test_initialize_injects_memory_refs_preamble` Send full path assertion. LEDGER L178。
- [ ] **ENGINE-05**: D103 — `find_tail_boundary()` O(N²) profiled + fix or doc-only warning. LEDGER L233。
- [ ] **ENGINE-06**: D104 — 反应式 guard location decision recorded (harness vs pipeline). LEDGER L234。

### B. CONTRACT — contract carry-forward verification (Phase 7.1)

> **Note**: Research indicates all 5 CONTRACT-01..05 rows may already be closed. Verify-and-close pattern.

- [ ] **CONTRACT-01**: D137 — multi-turn observability + MCP bridge live + PRE_COMPACT 阈值 ChunkType-triggered. LEDGER L249。
- [ ] **CONTRACT-02**: D138 — skill-workflow deny-path mock LLM, no live LLM dependency. LEDGER L250。
- [ ] **CONTRACT-03**: D5 — grpc_integration tests migrated to v2 telemetry envelope. LEDGER L108。
- [ ] **CONTRACT-04**: D6 — certifier SessionPayload P1-P5 字段断言. LEDGER L109。
- [ ] **CONTRACT-05**: D55 — proto3 submessage `HasField` cross-runtime unified. LEDGER L175。

### C. L2 — L2 carry-forward verification (Phase 7.2)

> **Note**: Research indicates all 8 L2-01..08 rows may already be closed. Verify-and-close pattern.

- [ ] **L2-01**: D12 — connection-per-call → connection pool for L2 memory-engine. LEDGER L115。
- [ ] **L2-02**: D94 — MemoryStore 单例 + 共享连接 (D12 收尾). LEDGER L224。
- [ ] **L2-03**: D91 — HNSW tombstone rebuild threshold trigger. LEDGER L221。
- [ ] **L2-04**: D93 — `embed_batch` 并发 fan-out with rate limit respect. LEDGER L223。
- [ ] **L2-05**: D98 — `HybridIndex.search()` no longer per-call rebuild HNSWVectorIndex. LEDGER L228。
- [ ] **L2-06**: D11 — skill-registry `scope` filter before `LIMIT` (bug fix). LEDGER L114。
- [ ] **L2-07**: D13 — L2 `archive()` hides rows from FTS. LEDGER L116。
- [ ] **L2-08**: D30 — L2/L3 `busy_timeout` unified constant. LEDGER L142。

### D. L4 — L4 Foundation (Phase 8.x, NEW)

> First time touching L4 in any milestone. 3 P2 differentiators + 13 P3 hardening — all P3 items are mechanical copy-paste patterns from Phase 7.3 L3 hardening.

#### P2 Differentiators

- [ ] **L4-01**: D34 — Intent→Skill NLU resolver. Users type natural language → system finds the right skill via fuzzy matching (`rapidfuzz`). ~100-200 LOC. LEDGER L146。
- [ ] **L4-02**: D38 — `L2Client.search_memory()` passes `user_id` for tenant memory isolation. Verify L2 API accepts `user_id` field before L4 passes it. ~15 LOC. LEDGER L149。
- [ ] **L4-03**: D41 — `eaasp-cli-v2 session list` backend endpoint + CLI wiring. Browse sessions by metadata. ~30 LOC. LEDGER L151。

#### P3 Hardening (copy-paste from L3 patterns, ~10-20 LOC each)

- [ ] **L4-04**: D28 — L4 global FastAPI exception handler (copy D22 pattern from Phase 7.3). No traceback leak. LEDGER L140。
- [ ] **L4-05**: D29 — L4 path param `session_id` validation (copy D18 pattern). LEDGER L141。
- [ ] **L4-06**: D31 — L4 loguru initialization (copy D23 pattern from Phase 7.3). LEDGER L143。
- [ ] **L4-07**: D37 — L4 `context_assembly` `allow_trim_p4` configurable (not hardcoded False). LEDGER L148。
- [ ] **L4-08**: D39 — L4 `PolicyContext.policy_version` use `hashlib` hash not `str(int)`. ~3 LOC. LEDGER L150。
- [ ] **L4-09**: D42 — CLI `test_client` covers 5xx response paths (respx mock). ~20 LOC. LEDGER L152。
- [ ] **L4-10**: D43 — Remove unused `respx>=0.21` dependency from CLI pyproject.toml. ~1 LOC. LEDGER L153。
- [ ] **L4-11**: D44 — CLI `cmd_session.show` expose `--limit` flag (not hardcoded 100). ~10 LOC. LEDGER L154。
- [ ] **L4-12**: D45 — CLI response shape guard — `dict.get()` with defaults, no `KeyError` on shape change. ~15 LOC. LEDGER L155。
- [ ] **L4-13**: D61 — `threshold-calibration-skill.md` fixture parse version from submit response (not hardcoded). ~10 LOC. LEDGER L181。
- [ ] **L4-14**: D125 — L4 event burst >500 detection + warning log (not silent loss). ~10 LOC. LEDGER L242。
- [ ] **L4-15**: D110 — `dependencies` field `kind: runtime|intent` semantics distinction (schema breaking — Phase 3+ documented). ~50 LOC + migration. LEDGER L240。
- [ ] **L4-16**: D33 — L4 SESSION_CREATED event payload dedup — reference-mode, store once. ~30 LOC + migration. LEDGER L145。

### E. L3 — L3 Leftovers (Phase 8.x, NEW)

> Continuing from L3-08 (Phase 7.3 completed). 4 mechanical fixes + 1 lightweight concurrency test.

- [ ] **L3-09**: D10 — MCP REST facade upgrade to `rmcp` ServerHandler (Python `mcp` SDK). Dual-transport — keep REST + add MCP. ~80-150 LOC. LEDGER L113。
- [ ] **L3-10**: D16 — L3 `policy_engine.deploy()` read `created_at` after commit (TOCTOU fix). ~5 LOC. LEDGER L124。
- [ ] **L3-11**: D19 — L3 `switch_mode()` validate hook_id exists, 404 for unknown (not silent create). ~15 LOC. LEDGER L127。
- [ ] **L3-12**: D20 — `_sanitize_errors()` extracted to `eaasp_common` shared package, reused by L2. ~20 LOC. LEDGER L128。
- [ ] **L3-13**: D25 — L3 lightweight concurrent deploy unit test (in-process, not multi-process E2E). No `time.sleep(1.1)` anti-pattern. ~30 LOC. LEDGER L133。

### F. L2 — L2 Leftovers (Phase 8.x, NEW)

> Continuing from L2-08 (Phase 7.2 carry-forward). 8 table stakes + 3 differentiators.

#### Table Stakes

- [ ] **L2-09**: D14 — L2 `_row_to_memory` private symbol promoted to public API. ~5 LOC rename. LEDGER L117。
- [ ] **L2-10**: D15 — L2 `pyproject.toml` add `[tool.ruff]` + `[tool.mypy]` config (copy L3 pattern). ~15 LOC. LEDGER L118。
- [ ] **L2-11**: D59 — Makefile `mcp-orch-start` port configurable via env var (not hardcoded 8082). ~5 LOC. LEDGER L179。
- [ ] **L2-12**: D99 — MCP dispatcher wrap `int()`/`float()` conversions in try/except → `ToolError("invalid_arg")`. ~20 LOC. LEDGER L229。
- [ ] **L2-13**: D96 — `memory_id` HNSW key parsing fix — use `rsplit(":v", 1)` not `split(":v")`. ~3 LOC. LEDGER L226。
- [ ] **L2-14**: D97 — `HybridIndex` weights=(0,0) degenerate case emits `logger.warning`. ~2 LOC. LEDGER L227。
- [ ] **L2-15**: D92 — `MockEmbedding` seed widened from 64-bit to 32-byte digest to prevent test collisions. ~5 LOC. LEDGER L222。
- [ ] **L2-16**: D101 — FastAPI `HTTPException(detail=dict)` nesting fix — response shape matches doc contract. ~5-20 LOC. LEDGER L231。

#### Differentiators

- [ ] **L2-17**: D65 — MCP connection pool for multi-tool workloads (pre-warmed connections, latency reduction). ~80-120 LOC. LEDGER L187。
- [ ] **L2-18**: D95 — FTS hit semantic score backfill from DB `embedding_vec` blob when HNSW add fails. ~40 LOC. LEDGER L225。
- [ ] **L2-19**: D100 — `write()`/`confirm()`/`archive()` surface `embedding_model` + dimension in `MemoryFileOut`. ~15 LOC. LEDGER L230。

### G. HOOK — Hooks Testing + Features (Phase 8.x, NEW)

- [ ] **HOOK-01**: D108 — hooks script regression tests via bats + shellcheck, wired into `make verify` + CI. ~50-80 LOC. LEDGER L238。
- [ ] **HOOK-02**: D48 — `ScopedHookBody` add `matcher` + `tool_filter` fields for fine-grained hook targeting. Requires proto schema extension. ~50 LOC + migration. LEDGER L163。
- [ ] **HOOK-03**: D50 — `ScopedHookBody::Prompt` executor loop — LLM call during hook execution for meta-agent guard decisions. ~80-120 LOC. LEDGER L165。
- [ ] **HOOK-04**: D105 — `HookPoint::ContextDegraded` string alias — add deprecation warning, document backwards-compat. ~5 LOC doc. LEDGER L235。
- [ ] **HOOK-05**: D107 — shared jq fragment extracted from `check_output_anchor.sh` + `check_final_output.sh` to `_lib/json_guards.sh`. ~15 LOC. LEDGER L237。

### H. CONTRACT — Contract Leftovers (Phase 8.x, NEW)

> Continuing from CONTRACT-05 (Phase 7.1 carry-forward). Both items need ADR governance gate.

- [ ] **CONTRACT-06**: D74 — EmitEvent gRPC reverse channel (L1→L4 gRPC server). Proto `EmitEvent` RPC + `EventStreamEntry` message already exist — implementation is wiring: L1 gRPC client, L4 gRPC server in FastAPI lifespan. Needs ADR for contract extension. ~100-150 LOC. LEDGER L198。
- [ ] **CONTRACT-07**: D139 — Phase 2.5 S0.T4 双 Terminate + 未知 session 语义: specify in ADR (NO-OP vs error) + enforce in cross-runtime test. Doc/contract work. ~20 LOC doc + test. LEDGER L251。

### I. ENGINE — Grid-Engine Leftovers (Phase 8.x, NEW)

> Continuing from ENGINE-06 (Phase 7.0 carry-forward).

- [ ] **ENGINE-07**: D106 — `MAX_TURNS_FOR_BUDGET=50` hardcode → `AgentLoopConfig` field with configurable default. ~1 struct field + config wire. LEDGER L236。
- [ ] **ENGINE-08**: D130 — Session-lifetime vs per-turn cancel token dual-token inconsistency. `ChildCancellationToken::cancel()` propagation. ~30-50 LOC. LEDGER L247。

### J. SERVER — Grid-Server Leftovers (Phase 8.x, NEW)

> Continuing from SERVER-05 (v3.1).

- [ ] **SERVER-06**: D90 — `ServerMessage::ToolResult` WS schema add `tool_name` field. ~5 LOC. LEDGER L220。

### K. EVAL — Eval + Cross-Cutting Cleanup (Phase 8.x, NEW)

- [ ] **EVAL-01**: D126 — `lang/claude-code-runtime-python/.venv` check before A8 test — fail early with actionable error. ~10 LOC. LEDGER L243。
- [ ] **EVAL-02**: D127 — `data/verify-v2-phase2-skill-registry/` directory auto-cleanup. ~5 LOC. LEDGER L244。
- [ ] **EVAL-03**: D128 — `@assertion` decorator print NOTE before PASS (UX polish). ~5 LOC. LEDGER L245。
- [ ] **EVAL-04**: D129 — `verify-v2-phase2.sh` cleanup trap — don't sweep external ports on pre-flight failure. ~15 LOC. LEDGER L246。
- [ ] **EVAL-05**: D24 — IDE Pyright missing-import false positives fix (cross-cutting). ~10 LOC pyrightconfig. LEDGER L132。
- [ ] **EVAL-06**: D56 — `verify-v2-mvp.sh` cleanup scope expanded beyond SQLite-only. ~10 LOC. LEDGER L176。

---

## v3.3 Requirements (CLOSED 2026-06-07 — historical reference)

> v3.3 = Phase 7 Engine + Platform Debt Sweep (Focused). Shipped 2026-06-07. Phase 7.3 L3 RBAC completed (8/8 REQ-IDs). Phases 7.0/7.1/7.2 carry-forward to v3.4 for verification. Section kept for traceability lineage.

### D. L3 — L3 RBAC + hardening (Phase 7.3, COMPLETED ✅)

- [x] **L3-01**: D8 — `access_scope` 真实 RBAC 执行 (P2). LEDGER L111。
- [x] **L3-02**: D9 — `skill_usage` 返回真实遥测 (P2). LEDGER L112。
- [x] **L3-03**: D46 — Skill `access_scope` namespace 校验 (P2). LEDGER L161。
- [x] **L3-04**: D22 — L3 global FastAPI exception handler (P3). LEDGER L130。
- [x] **L3-05**: D23 — L3 loguru/logging 初始化 (P3). LEDGER L131。
- [x] **L3-06**: D17 — L3 `validate_session()` hook_id KeyError 修复 (P3). LEDGER L125。
- [x] **L3-07**: D18 — L3 session_id path param 校验 (P3). LEDGER L126。
- [x] **L3-08**: D26 — L3 tests flaky `time.sleep(1.1)` 修复 (P3). LEDGER L134。

---

## v3.2 Requirements (CLOSED 2026-05-26 — historical reference)

> v3.2 = Phase 6 Tech-Debt Triage & CI Red Line Clearance. Shipped 2026-05-26. 3 phases / 6 REQ-IDs. 93 main-NS D-rows triaged, 8 DEAD archived, v3.3-INBOX.md seeded.

## v3.1 Requirements (CLOSED 2026-05-22 — historical reference)

> v3.1 = Phase 5 Engine Hardening. Shipped 2026-05-22. 6 phases / 23 REQ-IDs. 6 ADRs Accepted. grid-cli + grid-server priority axis delivered.

---

## Future Requirements (deferred to v3.5+)

> Items explicitly deferred from v3.4 as premature scale optimizations or speculative infrastructure. All tagged 📦 long-term in DEFERRED_LEDGER.md.

### Scale Optimizations (NATS + Pipeline)

- **DEFER-01**: D75 — NATS JetStream migration. Keep SQLite EventStream; revisit when >1k events/sec sustained.
- **DEFER-02**: D76 — Subscribe push-based. Keep polling; reduce interval if latency becomes issue.
- **DEFER-03**: D79 — Pipeline multi-worker parallel processing. Profile first; parallelize when single worker saturates.

### Speculative Infrastructure (no current consumer)

- **DEFER-04**: D77 — TopologyAwareClusterer (L2 Ontology Service input). No ontology service exists.
- **DEFER-05**: D80 — Causal graph clusterer (parent_event_id → DAG). No consumer for causal event graphs.
- **DEFER-06**: D73 — Event Room. Product concept with no design doc; defer to Grid 独立产品 activation.

### Premature Scale Guards

- **DEFER-07**: D36 — Event window cursor (>10k events). Implement when >10k events observed in production.
- **DEFER-08**: D21 — L3 retention policy for managed_settings/telemetry. Monitor table sizes first.
- **DEFER-09**: D32 — L4 concurrency E2E stress test. Targeted unit tests sufficient; multi-process when needed.

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| `grid-sandbox` 仓库改名 | Grid 独立产品激活前不动 (per ADR-V2-023 §P6) |
| `git push origin main` | Push 时机由人决策 |
| Phase 0–2.5 历史 sign_off_commit retrofit | 历史不完美接受 |
| 132 个历史 plan + 14 archived phase 迁入 GSD ROADMAP | 冻结只读历史 |
| F4 lint 52 module-overlap 警告 reconcile | Advisory-only 接受 |
| grid-platform / grid-desktop / web* 增量功能 | Dormant per ADR-V2-024 双轴 framework |
| EAASP 与 Grid 分仓 | 时点由后续 milestone 决定 |

---

## Traceability

> Filled by `/gsd-roadmapper` 2026-06-07. 67/67 REQ-IDs mapped (19 carry-forward + 48 new), 0 orphans, 0 double-mapped. 9 items explicitly deferred (DEFER-01..09).

### Carry-Forward (Phase 7.0–7.2 — Verify & Close)

| Requirement | D-ID | Phase | Priority | Status |
|-------------|------|-------|----------|--------|
| ENGINE-01 | D102 | 7.0 (V&C) | P2 | Pending |
| ENGINE-02 | D3 | 7.0 (V&C) | P3 | Pending |
| ENGINE-03 | D57 | 7.0 (V&C) | P3 | Pending |
| ENGINE-04 | D58 | 7.0 (V&C) | P3 | Pending |
| ENGINE-05 | D103 | 7.0 (V&C) | P3 | Pending |
| ENGINE-06 | D104 | 7.0 (V&C) | P3 | Pending |
| CONTRACT-01 | D137 | 7.1 (V&C) | P2 | Pending |
| CONTRACT-02 | D138 | 7.1 (V&C) | P2 | Pending |
| CONTRACT-03 | D5 | 7.1 (V&C) | P3 | Pending |
| CONTRACT-04 | D6 | 7.1 (V&C) | P3 | Pending |
| CONTRACT-05 | D55 | 7.1 (V&C) | P3 | Pending |
| L2-01 | D12 | 7.2 (V&C) | P2 | Pending |
| L2-02 | D94 | 7.2 (V&C) | P2 | Pending |
| L2-03 | D91 | 7.2 (V&C) | P2 | Pending |
| L2-04 | D93 | 7.2 (V&C) | P2 | Pending |
| L2-05 | D98 | 7.2 (V&C) | P2 | Pending |
| L2-06 | D11 | 7.2 (V&C) | P3 | Pending |
| L2-07 | D13 | 7.2 (V&C) | P3 | Pending |
| L2-08 | D30 | 7.2 (V&C) | P3 | Pending |

### New v3.4 (Phase 8.0–8.6)

| Requirement | D-ID | Phase | Priority | Status |
|-------------|------|-------|----------|--------|
| L3-09 | D10 | 8.0 | P3 | Pending |
| L3-10 | D16 | 8.0 | P3 | Pending |
| L3-11 | D19 | 8.0 | P3 | Pending |
| L3-12 | D20 | 8.0 | P3 | Pending |
| L3-13 | D25 | 8.0 | P3 | Pending |
| CONTRACT-06 | D74 | 8.1 | P3 ⚠️ ADR | Pending |
| CONTRACT-07 | D139 | 8.1 | P3 ⚠️ ADR | Pending |
| ENGINE-07 | D106 | 8.1 | P3 | Pending |
| ENGINE-08 | D130 | 8.1 | P3 | Pending |
| SERVER-06 | D90 | 8.1 | P3 | Pending |
| L4-01 | D34 | 8.2 | P2 🌟 | Pending |
| L4-02 | D38 | 8.2 | P2 | Pending |
| L4-03 | D41 | 8.2 | P2 | Pending |
| L4-04 | D28 | 8.2 | P3 | Pending |
| L4-05 | D29 | 8.2 | P3 | Pending |
| L4-06 | D31 | 8.2 | P3 | Pending |
| L4-08 | D39 | 8.2 | P3 | Pending |
| L4-07 | D37 | 8.3 | P3 | Pending |
| L4-09 | D42 | 8.3 | P3 | Pending |
| L4-10 | D43 | 8.3 | P3 | Pending |
| L4-11 | D44 | 8.3 | P3 | Pending |
| L4-12 | D45 | 8.3 | P3 | Pending |
| L4-13 | D61 | 8.3 | P3 | Pending |
| L4-14 | D125 | 8.3 | P3 | Pending |
| L4-15 | D110 | 8.3 | P3 | Pending |
| L4-16 | D33 | 8.3 | P3 | Pending |
| L2-09 | D14 | 8.4 | P3 | Pending |
| L2-10 | D15 | 8.4 | P3 | Pending |
| L2-11 | D59 | 8.4 | P3 | Pending |
| L2-12 | D99 | 8.4 | P3 | Pending |
| L2-13 | D96 | 8.4 | P3 | Pending |
| L2-14 | D97 | 8.4 | P3 | Pending |
| L2-15 | D92 | 8.4 | P3 | Pending |
| L2-16 | D101 | 8.4 | P3 | Pending |
| L2-17 | D65 | 8.5 | P3 | Pending |
| L2-18 | D95 | 8.5 | P3 | Pending |
| L2-19 | D100 | 8.5 | P3 | Pending |
| HOOK-01 | D108 | 8.5 | P2 | Pending |
| HOOK-02 | D48 | 8.5 | P3 | Pending |
| HOOK-03 | D50 | 8.5 | P3 ⚠️ AI-SPEC | Pending |
| HOOK-04 | D105 | 8.5 | P3 | Pending |
| HOOK-05 | D107 | 8.5 | P3 | Pending |
| EVAL-01 | D126 | 8.6 | P3 | Pending |
| EVAL-02 | D127 | 8.6 | P3 | Pending |
| EVAL-03 | D128 | 8.6 | P3 | Pending |
| EVAL-04 | D129 | 8.6 | P3 | Pending |
| EVAL-05 | D24 | 8.6 | P3 | Pending |
| EVAL-06 | D56 | 8.6 | P3 | Pending |

### Deferred (out of v3.4 scope)

| Requirement | D-ID | Rationale |
|-------------|------|-----------|
| DEFER-01 | D75 | NATS JetStream — premature; keep SQLite EventStream |
| DEFER-02 | D76 | Push-based subscribe — keep polling for now |
| DEFER-03 | D79 | Pipeline multi-worker — profile first |
| DEFER-04 | D77 | TopologyAwareClusterer — no ontology service consumer |
| DEFER-05 | D80 | Causal graph clusterer — no DAG consumer |
| DEFER-06 | D73 | Event Room — no product design doc |
| DEFER-07 | D36 | Event window cursor — no >10k events in production |
| DEFER-08 | D21 | L3 retention policy — no production data volume |
| DEFER-09 | D32 | L4 concurrency E2E — targeted unit tests sufficient |

**Coverage:**
- ✅ 67/67 REQ-IDs mapped (19 carry-forward + 48 new); 0 orphans; 0 double-mapped
- 9 items explicitly deferred (DEFER-01..09)
- v3.3 completed: 8 REQ-IDs (L3-01..08 ✅) — historical reference

---

*Requirements defined: 2026-06-07 via v3.4 new-milestone Step 9 (research-complemented scoping). Source: `.planning/v3.3-INBOX.md` remaining rows + `.planning/research/SUMMARY.md` deferral recommendations.*
*Traceability filled: 2026-06-07 by /gsd-roadmapper — 55/55 REQ-IDs mapped across 10 phases.*
