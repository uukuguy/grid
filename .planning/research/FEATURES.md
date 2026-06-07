# Feature Research: v3.4 Full INBOX Drain (Debt Sweep II)

**Domain:** Grid/EAASP agent-runtime platform — carry-forward + new debt-sweep items
**Researched:** 2026-06-07
**Confidence:** HIGH (verified against DEFERRED_LEDGER.md SSOT at commit `9842dda`, v3.3-INBOX.md snapshot, Phase 7.0–7.3 closure commits, ADR-V2-006/024)

> **KEY INSIGHT**: This is NOT a typical feature-research exercise. All 85 items are catalogued deferred debt rows with precise LEDGER entries. The research question is not "what domain ecosystem do these live in?" but **"which items are table-stakes for correctness, which add real product value, and which should be explicitly deferred as premature?"**

---

## Feature Landscape

### Critical Note: Already Closed in Carry-Forward Phases

25+ of the 85 INBOX rows were closed during v3.3 Phase 7.0/7.1/7.2/7.3 execution. Per LEDGER verification, these are **DONE** and should be marked as verified-not-rework:

**Phase 7.0 (grid-engine harness wiring)**: D102 ✅, D3 ✅, D57 ✅, D58 ✅, D103 ✅, D104 ✅
**Phase 7.1 (contract observability + bridge)**: D137 ✅, D138 ✅, D5 ✅, D6 ✅, D55 ✅
**Phase 7.2 (L2 connection-pool + Pipeline)**: D12 ✅, D94 ✅, D91 ✅, D93 ✅, D98 ✅, D11 ✅, D13 ✅, D30 ✅
**Phase 7.3 (L3 RBAC)**: D8 ✅, D9 ✅, D46 ✅, D17 ✅, D18 ✅, D22 ✅, D23 ✅, D26 ✅

### Actually Remaining Items (~60 rows across 9 modules, all P2/P3)

---

### Table Stakes (Must-Fix for Product Integrity)

Items whose absence causes _visible incorrectness_, _security gaps_, or _operational fragility_. These are NOT optional polish — leaving them open deviates from correctness/security baselines the product already claims.

| Feature (D-ID) | Why Expected | Complexity | What Goes Wrong If Skipped |
|---------|--------------|------------|-------|
| **D105: HookPoint alias removal** | BACKWARDS COMPAT — `HookPoint::ContextDegraded` string alias in the dispatcher keeps existing YAML/JSON hook configs working. Premature removal at Phase 3 would silently break all deployed hook configs. | LOW — doc-note + deprecation warning; 0 code change needed. | Existing skill hooks stop firing with no error; deployment configs silently break. |
| **D106: MAX_TURNS_FOR_BUDGET=50 hardcode** | Long-running autonomous agents can hit this ceiling unexpectedly. A 50-turn budget is a hidden throttle — agents needing 51+ turns just stop. | LOW — promote to `AgentLoopConfig` field with default; 1 struct field + 1 config wire. | Agent silently terminates at turn 50 with "budget exhausted" — user has no knob to override. |
| **D130: Session/Per-turn Cancel Token** | The cancel-session path requires TWO signals (registry flag + channel message) to actually interrupt an in-flight turn. If either path breaks, cancel_session() becomes a no-op. | MEDIUM — `ChildCancellationToken::cancel()` propagation + `AgentLoopConfig` plumbing. ~30-50 LOC but correctness-critical. | `session kill` CLI command appears to succeed but in-flight LLM call keeps burning tokens. |
| **D99: MCP Dispatcher Untyped Errors** | L2 MCP tools throw native `ValueError`/`TypeError` when args don't parse, bypassing the `ToolError("invalid_arg")` contract. Downstream callers (L4, grid-runtime) handle `ToolError` — native exceptions become 500s. | LOW — wrap `int()`/`float()` conversions in try/except returning `ToolError("invalid_arg", ...)`. Mechanical, ~20 LOC. | MCP tool call failures surface as opaque 500s instead of structured "invalid argument: limit=abc" errors. |
| **D96: memory_id `:v` Parsing Bug** | User-supplied `memory_id` containing `:v` (e.g., `"invoice:v2"`) causes HNSW key `split(":v")` to produce 3 segments → key silently skipped. Correctness bug for any user with such IDs. | LOW — `rsplit(":v", 1)` or add `memory_id` validation rejecting `:v`. ~3 LOC. | Memory stored but irretrievable via HNSW; silent data loss for affected memory_ids. |
| **D97: Weights=(0,0) Degenerate Case** | `HybridIndex` with both weights zero produces unordered results (all scores=0, insertion order wins). No warning means operator thinks search is working. | LOW — add `logger.warning("Both weights zero")` at `__init__`. ~2 LOC. | Search returns insertion-ordered results masquerading as relevance-ranked; operator never alerted. |
| **D14: L2 Cross-Module Private Symbol Access** | `_row_to_memory` accesses private `_` symbols across module boundary. Python allows this but it's brittle — internal refactor breaks downstream silently. | LOW — promote to public (`row_to_memory`) or add `__all__` export. ~5 LOC rename. | Future L2 module refactor breaks without compile/import error; only surfaces at runtime. |
| **D15: Missing ruff/mypy Config** | No `[tool.ruff]`/`[tool.mypy]` in L2 `pyproject.toml` means no automated style/type checking. Bugs slip through that CI would catch. | LOW — copy config from sibling L3 `pyproject.toml`. ~15 LOC. | Type errors, style violations accumulate undetected; future contributor hits them at PR review. |
| **D20: `_sanitize_errors` L2 Reuse** | `_sanitize_errors()` only exists in L3 but L2 needs it too (D99 is the consequence — errors not sanitized). Inconsistency between layers. | LOW — extract to `eaasp_common` shared helper. ~20 LOC. | L2 error responses leak internal details; inconsistent error shapes across L2/L3. |
| **D28: L4 Global Exception Handler** | L4 has no global exception handler. Unhandled exceptions → raw FastAPI 500 with traceback leakage. Same pattern that D22 fixed for L3 (done in Phase 7.3). | LOW — copy D22 pattern verbatim. ~15 LOC. | Production exceptions leak Python tracebacks to API consumers. |
| **D29: L4 Path Param Unvalidated** | `/v1/sessions/{id}/*` accepts any string including spaces, special chars. Security/correctness gap — same pattern D18 fixed for L3 (done in Phase 7.3). | LOW — copy D18 pattern (`Annotated[Path(...)]`). ~8 LOC. | Malformed session IDs bypass input validation; potential injection vectors. |
| **D31: L4 Loguru Init** | L4 has no structured logging (no loguru). All errors go to unformatted print() — invisible in production. Same issue D23 fixed for L3 (done in Phase 7.3). | LOW — copy D23 setup pattern. ~10 LOC. | Zero production observability for L4; debugging requires code changes. |
| **D42: CLI 5xx Uncovered** | `test_client` never exercises 5xx response paths. CLI may crash or produce wrong exit code on server errors. | LOW — add 1-2 respx mock tests for 500/503. ~20 LOC. | Server down → CLI gives misleading exit code; scripting around CLI breaks. |
| **D43: Unused `respx>=0.21` Dep** | Dead dependency in `pyproject.toml`. Not used anywhere. Bloat + potential supply chain risk. | LOW — delete 1 line. | Zero now, but accumulates over time. |
| **D44: CLI `limit=100` Hardcode** | `cmd_session.show` has a hardcoded `limit=100`. User with 150 sessions can't see them all — and doesn't know why. | LOW — expose as `--limit` CLI flag. ~10 LOC. | Users with many sessions hit invisible ceiling; no knob to adjust. |
| **D45: CLI Response Shape Guard** | CLI assumes response shape; if server changes shape, CLI crashes with `KeyError` instead of clean error. | LOW — add `dict.get()` with defaults + test. ~15 LOC. | Server API evolution breaks CLI with opaque Python traceback. |
| **D59: Makefile Port Hardcode** | `mcp-orch-start` hardcoded to `--port 8082`. If port conflicts, script fails silently or connects to wrong service. | LOW — make it configurable via env var or just document. ~5 LOC. | Port conflicts in multi-instance dev environments cause mysterious failures. |
| **D61: Threshold Fixture Version Hardcode** | `threshold-calibration-skill.md` hardcodes `version: ...` — must be manually kept in sync. Drift causes skill registration to reject. | LOW — parse from submit response instead. ~10 LOC. | Fixture drift → skill registration fails → E2E test breaks with cryptic error. |
| **D139: Double-Terminate Semantics** | Contract v1 doesn't specify whether calling `Terminate` on already-closed session is NO-OP or error. Runtime behavior is inconsistent across adapters. | LOW — ADR-V2-017 §2 revision + enforce in test. Doc/contract work. | Multi-turn E2E tests flake; runtime differences between grid and comparison runtimes break contract portability. |
| **D19: L3 switch_mode Silent Create** | `switch_mode()` accepts any `hook_id` and silently creates an override. Wrong hook_id → wrong hook fires, no error. | LOW — add validation + 404 for unknown hook_id. ~15 LOC. | Misconfigured switch_mode silently activates wrong hook; hours to debug. |
| **D10: L2/L3 MCP→rmcp Upgrade** | MCP REST facade uses manual HTTP calls; should use `rmcp` ServerHandler for proper MCP protocol compliance. | MEDIUM — switch REST facade to rmcp library. ~80-150 LOC. | Future MCP protocol features (notifications, sampling, roots) unavailable; fall behind MCP spec. |
| **D107: Shared jq Fragment** | Two hook scripts (`check_output_anchor.sh`, `check_final_output.sh`) share identical three-way empty-string check. Copy-paste caused a bug (missed `!= ""` branch) already. | LOW — extract to shared `_lib/json_guards.sh`. ~15 LOC. | Future hook script gets the same copy-paste bug; regression on already-fixed issue. |
| **D92: MockEmbedding Seed Collision** | 64-bit hash of test fixtures can collide in tests → flaky test results. Tests-only concern but test reliability matters. | LOW — widen to 32-byte digest or document as tests-only. ~5 LOC + doc. | Test flakes in CI; developer wastes time re-running. |
| **D101: FastAPI HTTPException Nesting** | REST 409/404 responses nest `detail` key: `resp.json()['detail']['code']` instead of `resp.json()['code']`. Contract erratum — doc says flat shape. | LOW — either fix response shape or fix doc. ~5 LOC (doc) or ~20 LOC (code). | External consumers reading the API see unexpected nesting; integration breaks. |
| **D37: L4 context_assembly allow_trim Hardcode** | `allow_trim_p4=False` hardcode means P4 (SkillInstructions) can't be trimmed. For skills with large instructions, this wastes context window. Chained to D3 (user_preferences + trim_for_budget). | LOW-MEDIUM — depends on D3 decision. A flag flip + test. | Large skill instructions consume context budget; agent has less room for actual conversation. |
| **D125: L4 Event Burst Silent Loss** | Events stream polls at 500/s max; burst >500 events in 500ms → silent lag. Not a current problem (no production data), but architectural landmine. | LOW — add overflow detection + warning log. ~10 LOC. | Under sustained load, events silently lag behind; operator unaware. |

### Differentiators (Add Real Product Value)

Items that elevate the product beyond "correct" to "powerful" or "polished." These are the items where effort yields visible capability gains.

| Feature (D-ID) | Value Proposition | Complexity | Why It Matters |
|---------|-------------------|------------|-------|
| **D34: Intent→Skill NLU** | Users type "deploy the SCADA calibration" → system finds the right skill automatically. Natural language skill discovery — this is the core AI experience. | MEDIUM-HIGH — need NLU pipeline (could use existing LLM or lightweight classifier). ~100-200 LOC + integration. | Without this, users must know exact skill_id. This is the "AI" part of EAASP — otherwise it's just a CLI dispatcher. |
| **D50: Prompt Executor Loop** | `ScopedHookBody::Prompt` fires an LLM call during hook execution to make a yes/no decision (e.g., "Does this tool output look dangerous?"). This is a _meta-agent_ pattern — hooks that think. | MEDIUM — LLM call with structured output parsing, timeout, error handling. ~80-120 LOC. Blueprint §F already designed. | Opens an entire class of "guard hooks" — security review, quality check, compliance verification — all driven by LLM judgment. |
| **D38: user_id in L2Client** | Tenant isolation — when L4 calls L2 for memory search, it passes the user's identity. Without this, all users share one memory space. | LOW — add `user_id` parameter to `search_memory` RPC. ~15 LOC + test. D8/D9/D46 (RBAC) already done in Phase 7.3 as prerequisite. | Multi-tenant memory isolation. Without it, user A sees user B's memories. |
| **D41: Session List Endpoint** | `eaasp-cli-v2 session list` actually works — shows all sessions with metadata. Single-session CLI is a demo; list makes it a tool. | LOW — existing data, just needs REST endpoint + CLI wiring. ~30 LOC. | CLI goes from "type session_id from memory" to "browse my work." UX leap. |
| **D108: Hook Script Regression Tests** | bats/shellcheck CI for all hook scripts. The C1-class regression (empty-string check missed) was found manually — would have been caught automatically. | LOW — bats test files + CI integration. ~50-80 LOC. | Prevents hook script bugs from reaching production. Investment that pays back every future hook change. |
| **D48: ScopedHookBody Matcher/Tool Filter** | Hooks can target specific tools (e.g., "only fire PreToolUse for `write_file`"). Without this, hooks fire on every tool — wasteful and often incorrect. | MEDIUM — schema extension (`matcher`/`tool_filter` fields) + executor logic. ~50 LOC + schema migration. | Fine-grained hook targeting. Current hooks fire indiscriminately — noisy and slow. |
| **D100: Embedding Model Surface** | `write()`/`confirm()`/`archive()` return which embedding model was used and its dimension. Observability for the memory pipeline. | LOW — add fields to `MemoryFileOut`. ~15 LOC. | Operators can verify "am I using model X or Y?" Without it, embedding model is a black box. |
| **D95: Semantic Score Backfill** | When HNSW add fails silently but FTS still hits, the result gets `sem_score=0`. Backfill from DB `embedding_vec` blob corrects this — search quality improvement. | MEDIUM — unpack BLOB + cosine calc. ~40 LOC + test. | Hybrid search results are more accurate; 0-score artifacts disappear. |
| **D65: MCP Connection Pool** | Multiple concurrent MCP tool calls share a pool of pre-warmed connections instead of creating new ones per call. Latency reduction for multi-tool workloads. | MEDIUM — connection pool manager + config. ~80-120 LOC. D10 (rmcp upgrade) is a soft prerequisite. | Multi-tool agent runs are faster. Currently each tool call pays connection setup. |
| **D74: EmitEvent gRPC Reverse Channel** | L1 runtime can push events back to L4 via gRPC (currently L4 polls). Enables real-time event delivery without polling overhead. | MEDIUM — L1 gRPC server + L4 client. ~100-150 LOC. Contract extension needed. | Real-time event fan-out. Pairs with D76 (push-based subscribe) as the "event-driven architecture" endgame. |
| **D33: SESSION_CREATED Dedup** | L4 stores duplicate SESSION_CREATED event payloads (same data stored N times). Reference-mode: store once, link. | LOW-MEDIUM — schema change to reference-mode. ~30 LOC + migration. | Storage savings; event table stays clean. |
| **D100+D95+D78: Memory/Vector Search Quality** | Combined improvement to search accuracy — embedding model visibility + backfill + indexing. Each individually small, collectively a quality leap. | MEDIUM (collectively) | Better search → better agent answers. Core differentiator for L2 memory. |
| **D110: Dependencies Soft/Runtime Semantics** | Distinguish "I mention this service" from "I need this service to run." L4 can skip soft-intent services, saving resources. | MEDIUM — schema breaking change (`kind: runtime|intent` tag). Already documented as Phase 3+ breaking. | Resource efficiency; prevents L4 from spinning up services a skill doesn't actually use. |

### Anti-Features: Should NOT Build in This Milestone

Items from the INBOX that seem useful but would add **complexity without solving a current problem**. These should be **explicitly deferred** — closed as "long-term, no v3.4 action" with a rationale note in LEDGER.

| Feature (D-ID) | Why Requested | Why Problematic | What to Do Instead |
|---------|---------------|-----------------|-------------|
| **D75: NATS JetStream Migration** | Event streaming at scale (Phase 6 multi-node). | NATS adds a new operational dependency (server, clustering, auth). Current SQLite-based EventStream works fine for single-node. Zero production scale data. | Keep SQLite EventStream; revisit when measured events/sec exceeds 1k sustained. LEDGER already tags this 📦 long-term Phase 6. |
| **D76: Subscribe Push-Based** | Real-time push instead of poll. | Poll-based subscribe works at current scale. Push-based requires connection state management, reconnection logic, backpressure — all complexity with no current pain. | Keep polling; reduce poll interval if latency becomes an issue. LEDGER already 📦 long-term Phase 6. |
| **D77: TopologyAwareClusterer** | Semantic topology from ontology service. | No ontology service exists in the codebase. No consumer for clustering results. Building the clusterer first is building infrastructure for a use case that doesn't exist. | Wait until an L2 consumer (e.g., memory dedup, event correlation) demands it. LEDGER already 📦 long-term Phase 5. |
| **D79: Pipeline Multi-Worker** | Parallel event processing for throughput. | Single-worker pipeline handles current load. Multi-worker introduces concurrency bugs (ordering, state sharing) without a measured bottleneck. Premature optimization. | Profile first; parallelize only when a single worker saturates. LEDGER already 📦 long-term Phase 6. |
| **D80: Causal Graph Clusterer** | DAG-based event clustering (parent_event_id). | No consumer for causal event graphs. The data model supports `parent_event_id` but nothing reads it. Clusterer creates complexity with no downstream use. | Wait until event correlation features are planned. LEDGER already 📦 long-term Phase 4. |
| **D73: Event Room** | Collaborative event workspace. | Product concept with no design doc, no consumers, no demand signal. Building it now = speculative infrastructure that rots. | Defer to Grid独立产品 activation. LEDGER already 📦 long-term Phase 4. |
| **D36: Event Window Cursor** | Cursor-based pagination for >10k event windows. | No production deployment has >10k events. Cursor-based pagination is complexity for a scale we haven't reached. | When events >10k observed in production, implement then. LEDGER already 📦 long-term Phase 3+. |
| **D21: L3 Retention Policy** | TTL-based cleanup of `managed_settings_versions` / `telemetry_events`. | No production data volume to warrant retention management. Adding TTL before understanding actual data growth patterns is premature. | Monitor table sizes in production; implement when growth is observed. LEDGER already 📦 long-term. |
| **D25: L3 Concurrency E2E** | Formal concurrency stress tests for L3. | Concurrency correctness is important, but formal E2E stress tests are heavyweight (need multiple processes, synchronization). L3 already has `busy_timeout` protection (D30 done in Phase 7.2). | Add targeted concurrent-deploy unit tests (lightweight, in-process). Defer multi-process E2E until production load surfaces issues. |
| **D32: L4 Concurrency Stress Test** | Same as D25 but for L4. | Same rationale — heavyweight E2E is premature. | Same approach — targeted unit tests, defer multi-process. |
| **D56: verify-v2-mvp Full Cleanup** | Script only wipes SQLite, not other artifacts. | Script is a manual verification tool, not a CI gate. Full cleanup adds complexity to a tool used once per release. | Document what's not cleaned; add cleanup when the script is promoted to CI. LEDGER already 📦 long-term. |

---

## Feature Dependencies

```
D34 (Intent→Skill NLU)
    └──requires──> Skill registry (already exists, Phase 2 S4.T1)
    └──enhances──> D41 (session list) — NLU picks skill, list shows results

D38 (L2Client user_id)
    └──requires──> D8/D9/D46 (RBAC infrastructure) ✅ DONE (Phase 7.3)

D50 (Prompt Executor Loop)
    └──requires──> ScopedHookBody infrastructure ✅ DONE (Phase 2 S3.T5)
    └──requires──> LLM provider integration (already exists in grid-engine)

D48 (matcher/tool_filter)
    └──requires──> Hook schema v2.1 (breaking change)
    └──conflicts──> D105 (HookPoint alias) — both touch hook schema; batch together

D65 (MCP Connection Pool)
    └──soft-requires──> D10 (rmcp upgrade) — easier with rmcp, possible without

D74 (EmitEvent gRPC)
    └──requires──> gRPC contract extension (proto change → contract review)

D95 (semantic_score backfill)
    └──depends-on──> Existing HNSW + FTS infrastructure ✅ DONE
    └──enhances──> D100 (embedding model surface) — together improve search quality

D139 (Terminate Semantics)
    └──requires──> ADR-V2-017 §2 revision (governance step before code)
    └──conflicts──> D74 — both touch gRPC contract; coordinate

D110 (Dependencies Semantics)
    └──is-implemented-after──> Phase 3 schema breaking release (explicitly deferred)
    └──enhances──> D34 (NLU) — smarter dependency resolution during skill selection

D107 (Shared jq Fragment)
    └──enhances──> D108 (bats/shellcheck tests) — shared lib + CI tests = robust hook scripts

L4 P3 Cluster (D28/D29/D31/D37/D39/D42-D45/D61/D110/D125)
    All are independent mechanical fixes. Batch by module for efficiency.
    
L3 Leftovers (D10/D16/D19/D20/D21/D25)
    D20 → D10: _sanitize_errors in common → used during rmcp upgrade
    D19 is independent; D16 is independent
    D21/D25 deferred (anti-features)

L2 Leftovers (D14/D15/D59/D65/D92/D95/D96/D97/D99/D100/D101)
    Mostly independent. D65 soft-depends on D10.
    
Hooks P3 (D48/D50/D107/D108)
    D50 is the biggest item. D48/D107/D108 are mechanical. Batch hooks together.
```

---

## MVP Definition for v3.4

### Must Complete (Correctness Floor)

Items that would cause visible failures if left open:

- [ ] **D105 + D106 + D130** (grid-engine correctness) — cancel token, turn budget, backwards compat
- [ ] **D99 + D96 + D97 + D14 + D15** (L2 correctness/lint) — error types, memory_id bug, weights warn
- [ ] **D28 + D29 + D31** (L4 safety — exception handler, path validation, logging)
- [ ] **D42 + D44 + D45** (CLI hardening — 5xx coverage, limit flag, response guard)
- [ ] **D20 + D59** (cross-module consistency — _sanitize_errors, Makefile port)
- [ ] **D139** (contract — Terminate semantics spec)

### Should Complete (Product Quality)

Items that make the product feel polished and capable:

- [ ] **D34** (Intent→Skill NLU) — the AI feature
- [ ] **D38** (user_id in L2Client) — tenant isolation
- [ ] **D41** (session list endpoint) — CLI usability
- [ ] **D50** (Prompt executor loop) — meta-agent hooks
- [ ] **D48** (matcher/tool_filter) — fine-grained hook targeting
- [ ] **D108** (bats/shellcheck) — hook regression prevention

### Defer to Future Milestone (Explicit Decisions)

Items that should be CLOSED in this milestone with a "long-term, no v3.4 action" rationale:

- [ ] **D75 + D76 + D79** (Phase 6 scale: NATS, push-subscribe, multi-worker)
- [ ] **D77 + D80 + D73** (Phase 4/5: topology clusterer, causal graph, Event Room)
- [ ] **D36 + D21 + D25 + D32 + D56** (Premature for current data/load)
- [ ] **D110** (Phase 3 schema breaking change — explicitly deferred)
- [ ] **D33** (SESSION_CREATED dedup — nice to have but no pain yet)
- [ ] **D126 + D127 + D128 + D129** (eval polish — cosmetic, non-blocking)

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority for v3.4 |
|---------|------------|---------------------|----------|
| D105 HookPoint alias | LOW (backwards compat) | LOW | P2 |
| D106 MAX_TURNS hardcode | MEDIUM (agent UX) | LOW | P2 |
| D130 cancel token | HIGH (correctness) | MEDIUM | P2 |
| D99 MCP dispatcher errors | MEDIUM (error UX) | LOW | P2 |
| D96 memory_id parsing | LOW (edge case) | LOW | P3 |
| D97 weights warning | LOW (edge case) | LOW | P3 |
| D14 cross-module access | LOW (tech debt) | LOW | P3 |
| D15 ruff/mypy config | MEDIUM (dev quality) | LOW | P2 |
| D20 _sanitize_errors reuse | MEDIUM (consistency) | LOW | P2 |
| D28 L4 exception handler | MEDIUM (safety) | LOW | P2 |
| D29 L4 path validation | MEDIUM (security) | LOW | P2 |
| D31 L4 loguru | MEDIUM (observability) | LOW | P2 |
| D42 CLI 5xx coverage | LOW (edge coverage) | LOW | P3 |
| D43 unused dep | LOW (cleanup) | LOW | P3 |
| D44 CLI limit flag | MEDIUM (UX) | LOW | P2 |
| D45 CLI response guard | LOW (robustness) | LOW | P3 |
| D59 Makefile port | LOW (dev UX) | LOW | P3 |
| D61 threshold fixture | LOW (dev UX) | LOW | P3 |
| D139 Terminate semantics | MEDIUM (contract) | LOW | P2 |
| D19 switch_mode validate | LOW (safety) | LOW | P3 |
| D10 rmcp upgrade | MEDIUM (future-proof) | MEDIUM | P2 |
| D107 shared jq fragment | LOW (quality) | LOW | P3 |
| D92 MockEmbedding seed | LOW (test only) | LOW | P3 |
| D101 HTTPException nesting | LOW (doc/code) | LOW | P3 |
| D37 allow_trim hardcode | LOW-MEDIUM | LOW-MEDIUM | P3 |
| D125 event burst warn | LOW | LOW | P3 |
| **D34 Intent→Skill NLU** | **HIGH** | MEDIUM-HIGH | **P2 (key differentiator)** |
| **D50 Prompt executor** | **HIGH** | MEDIUM | **P2 (key differentiator)** |
| D38 user_id L2Client | HIGH (multi-tenancy) | LOW | P2 |
| D41 session list | MEDIUM (UX) | LOW | P2 |
| D108 bats/shellcheck | MEDIUM (quality) | LOW | P2 |
| D48 matcher/tool_filter | MEDIUM | MEDIUM | P3 |
| D100 embedding surface | LOW (observability) | LOW | P3 |
| D95 semantic backfill | MEDIUM (quality) | MEDIUM | P3 |
| D65 MCP connection pool | MEDIUM (perf) | MEDIUM | P3 |
| D74 EmitEvent gRPC | MEDIUM (architecture) | MEDIUM | P3 |
| D33 SESSION_CREATED dedup | LOW | LOW-MEDIUM | P3 |
| D110 dependencies semantics | MEDIUM | MEDIUM | **DEFER to Phase 3+** |
| D75 NATS JetStream | LOW (no pain) | HIGH | **DEFER** |
| D76 push subscribe | LOW (no pain) | MEDIUM | **DEFER** |
| D77 TopologyClusterer | LOW (no consumer) | HIGH | **DEFER** |
| D79 multi-worker | LOW (no bottleneck) | MEDIUM | **DEFER** |
| D80 causal graph | LOW (no consumer) | HIGH | **DEFER** |
| D73 Event Room | LOW (no consumer) | HIGH | **DEFER** |
| D36 event cursor | LOW (no scale) | MEDIUM | **DEFER** |
| D21 retention policy | LOW (no data) | MEDIUM | **DEFER** |
| D25 concurrency E2E | LOW (covered) | HIGH | **DEFER** |
| D32 concurrency E2E | LOW (covered) | HIGH | **DEFER** |
| D56 full cleanup | LOW (dev only) | LOW | **DEFER** |

---

## Competitor Feature Analysis

Not applicable for this milestone — these are all internal debt items, not competitive features. The Grid/EAASP product already has its competitive positioning established (7-runtime contract portability, ADR governance, L0-L4 layered architecture, hook envelope contract). The v3.4 items are gap-fills within that positioning.

---

## Sources

- `docs/design/EAASP/DEFERRED_LEDGER.md` (544 lines, SSOT for all D-items, verified 2026-06-07)
- `.planning/v3.3-INBOX.md` (snapshot @ 2026-05-26, Phase 6.2 TRIAGE-03)
- `.planning/PROJECT.md` (v3.4 milestone definition, verified 2026-06-07)
- `docs/design/EAASP/adrs/ADR-V2-006-hook-envelope-contract.md` (hook envelope schema)
- `docs/design/EAASP/adrs/ADR-V2-024-phase4-product-scope-decision.md` (双轴 model, engine vs data/integration)
- Phase 7.0/7.1/7.2/7.3 closure commits (verified 25+ items ✅ via LEDGER status changes dated 2026-06-01 through 2026-06-07)

---

*Feature research for: Grid/EAASP v3.4 Full INBOX Drain (Debt Sweep II)*
*Researched: 2026-06-07*
*Confidence: HIGH — all items verified against LEDGER SSOT + Phase 7.x closure commits*
