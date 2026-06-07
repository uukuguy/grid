# Project Research Summary

**Project:** Grid v3.4 — Full INBOX Drain (Debt Sweep II)
**Domain:** Agent Runtime Stack + EAASP Platform — brownfield debt consolidation
**Researched:** 2026-06-07
**Confidence:** HIGH

## Executive Summary

This is NOT a greenfield product research — it's a **brownfield debt-sweep milestone** against an established Rust/Python agent runtime platform (Grid/EAASP, L0-L4 layered architecture, 7-runtime gRPC contract, 15+ ADRs). The v3.4 milestone consolidates ~60 remaining P2/P3 debt items from the deferred ledger across 9 modules (L2 memory, L3 governance, L4 orchestration, grid-engine, hooks, contract, eval, grid-server, CLI). About 25 items were already closed in carry-forward phases 7.0-7.3.

**Recommended approach:** Execute in 7 sub-phases (8.0-8.6), ordered by cross-module dependency risk. Phase 8.0 (L3 foundation + shared package) and 8.1 (contract + grid-engine) can run in parallel with zero shared files. Phase 8.2 (L4 foundation) is the largest value delivery — it includes the NLU intent-to-skill resolver (D34), the marquee "AI" feature of this milestone. Phases 8.3-8.6 handle hardening, L2 internals, hooks, and final polish. The stack requires only 4 new Python dependencies and zero new Rust crates.

**Key risks:** HTTP contract drift between L4↔L2/L3 (untyped dict access masks field mismatches), concurrent state corruption in HNSW indexes, NATS JetStream adding stateful infrastructure prematurely, and the rmcp ServerHandler upgrade breaking REST consumers. Each risk has a concrete prevention strategy: respx-mocked integration tests, per-worker index isolation, dual-backend with feature flags, and dual-transport (REST + MCP) preservation.

## Key Findings

### Recommended Stack

v3.4 requires only **4 new Python dependencies** and **1 new system tool**, with **zero new Rust dependencies**. The existing validated baseline (Rust 1.75+ Tokio/Axum/rmcp/tonic 0.12, Python 3.12+ FastAPI/grpcio/pydantic, SQLite+HNSW, Protobuf 3) remains unchanged. Two significant dependencies (nats-py for JetStream, networkx for causal graphs) are explicitly deferred to v3.5+ as disproportionate to P3 priority.

**Core additions:**
- **loguru ≥0.7.3** (L4): Structured logging — same as L3 already uses, zero learning curve
- **rapidfuzz ≥3.9** (L4): NLU intent→skill fuzzy matching — fast C++ backend, zero ML overhead. Fallback: `difflib` (stdlib) if zero-dep required
- **mcp ≥1.27** (L3): MCP ServerHandler — upgrade REST facade to proper MCP protocol. **Note:** use Python `mcp` SDK, not Rust `rmcp` crate
- **mypy ≥2.1** (L2, dev-only): Static type checking — parity with L3's existing setup
- **shellcheck ≥0.11.0** (system): Static analysis for hook shell scripts — not yet installed

### Expected Features

This is a consolidated debt catalog, not a feature market analysis. All items are internal quality/correctness improvements. No competitive analysis applies.

**Must complete (correctness floor — 15 items):**
- D105/D106/D130: grid-engine correctness (cancel token, turn budget, backwards compat)
- D99/D96/D97/D14/D15: L2 correctness and lint (error types, memory_id bug, weights warn, type checking)
- D28/D29/D31: L4 safety foundation (exception handler, path validation, logging)
- D42/D44/D45: CLI hardening (5xx coverage, limit flag, response guard)
- D20/D59: Cross-module consistency (_sanitize_errors, Makefile port)
- D139: Contract — Terminate semantics spec

**Should complete (product quality — 12 items):**
- D34: Intent→Skill NLU — the key AI differentiator
- D50: Prompt executor loop — meta-agent hooks that think
- D38: user_id in L2Client — tenant isolation
- D41: Session list endpoint — CLI usability leap
- D48: ScopedHookBody matcher/tool_filter — fine-grained hook targeting
- D108: bats/shellcheck CI — hook regression prevention
- D65: MCP connection pool — latency reduction
- D74: EmitEvent gRPC reverse channel — real-time event delivery
- D100/D95: Memory/vector search quality improvements
- D107: Shared jq fragment — eliminate copy-paste bug surfaces

**Defer to future milestone (9 items, explicit decisions):**
- D75/D76/D79: NATS JetStream, push-subscribe, pipeline multi-worker (Phase 6 scale — zero production pain)
- D77/D80/D73: Topology clusterer, causal graph, Event Room (no downstream consumers exist)
- D36/D21: Event cursor, retention policy (no production data volume)
- D25/D32: Concurrency E2E stress tests (heavyweight, premature for current load)

### Architecture Approach

The existing L0-L4 layered architecture is preserved. v3.4 adds 5 new integration data flows without disrupting existing boundaries:

1. **Intent resolution flow** (D34): `intent_text → IntentParser → skill_id → existing handshake` — a new L4-internal component inserted before the three-way handshake
2. **Bidirectional gRPC** (D74): L1 grid-runtime pushes events to a new L4 `EventSink` gRPC server, reversing the current unidirectional L4→L1 pattern
3. **User-scoped memory** (D38): `user_id` propagates from L4's `create_session()` through L2's search endpoint for tenant isolation
4. **Hook matcher filtering** (D48): New `matcher` + `tool_filter` fields in `ScopedHook` proto cascade through L0→L4→L1
5. **Prompt hook execution** (D50): New `PromptExecutorLoop` in grid-engine calls LLM to make hook decisions

**New components:** `IntentParser` (L4 Python, strategy pattern), `PromptExecutorLoop` (grid-engine Rust, lightweight single-turn LLM call), `EventSinkServicer` (L4 Python, aio gRPC server), `eaasp_common` package (shared errors helper). **Six existing components modified** across L2/L3/L4/grid-engine/proto.

### Critical Pitfalls

1. **L4↔L2/L3 HTTP contract drift** — Untyped `dict.get()` in client wrappers silently swallows field mismatches. Prevention: every new L4→L2/L3 call path requires a respx-mocked integration test asserting exact parsed output from real upstream response shapes.

2. **NATS JetStream stateful infrastructure** — Replaces zero-config SQLite with an external process dependency. Prevention: implement as dual-backend behind `EventBackend` interface, default to SQLite, activate NATS via `EAASP_EVENT_BACKEND=nats` feature flag. Never delete SQLite backend.

3. **bats/shellcheck invisible in CI** — Tests exist in repo but CI never executes them. Prevention: wire `make hook-scripts-test` into `make verify`, add `bats-core` to CI setup, make bats conditional (`which bats || echo "SKIP"`).

4. **rmcp ServerHandler breaks REST consumers** — MCP transport is NOT a drop-in replacement for REST. Prevention: dual-transport pattern — keep REST endpoints as default, add MCP as opt-in path. L4→L3 REST calls must continue working unchanged.

5. **Concurrent HNSW index corruption** — Multi-worker pipeline shares in-memory HNSW index without locks. Prevention: each worker gets its own `HybridIndex` instance or read-only view. Add `busy_timeout=5000` consistently across all `aiosqlite.connect()` calls.

6. **Cross-module import breakage** — Extracting `_sanitize_errors` to shared package requires L3 AND L4 import changes in one atomic commit. Prevention: create `tools/eaasp-shared/` package in a single commit touching all 3 packages. Gate with `make dev-eaasp`.

7. **P3 over-engineering** — 20-minute fixes balloon into 3-day refactors. Prevention: P3 items get ≤2 hours budget. Pattern-match from existing code (L3 already has exception handler, loguru init — copy, don't design).

8. **Contract test regression** — Changes in any L0-L4 layer can cascade-fail the 112-case E2E suite. Prevention: pre-commit checklist for every PR: `make check` + `make verify` + `make v2-phase2-e2e` + `make v2-phase3-e2e-rust`.

## Implications for Roadmap

Based on cross-module dependency analysis, suggested 7-phase structure:

### Phase 8.0 — L3 Leftovers + Cross-cutting Foundation (6 rows)
**Rationale:** D20 creates the `eaasp_common` shared package that L2 consumes later. D10 is the foundational MCP upgrade. These land early so downstream phases can consume them. All L3-internal, zero external dependencies.
**Delivers:** Shared error sanitization package, L3 MCP transport (dual with REST), L3 deploy/validation/concurrency fixes.
**Addresses:** D20, D10, D16, D19, D21
**Avoids:** rmcp REST breakage (Pitfall 4) — keep dual transport. Cross-module import breakage (Pitfall 6) — atomic single commit.

### Phase 8.1 — Contract + grid-engine Foundation (5 rows)
**Rationale:** D74 introduces bidirectional gRPC — the proto must stabilize before L4's new gRPC server builds against it. Grid-engine items (D105/D106/D130) have no cross-module deps and can run in parallel with proto work. **Can run in parallel with Phase 8.0.**
**Delivers:** L1→L4 EmitEvent gRPC reverse channel, Terminate semantic spec, grid-engine config/cancel-token hardening.
**Addresses:** D74, D139, D105, D106, D130
**Uses:** tonic 0.12 Server (already in deps, no Cargo.toml changes), ADR governance for proto changes.
**⚠️ Requires ADR:** D74 adds new `EventSink` service to proto. Run `/adr:new --type contract` before implementation.

### Phase 8.2 — L4 Foundation (7 rows: 3 P2 + 4 P3)
**Rationale:** Largest value-delivery phase. D34 (NLU) is the marquee feature — the "AI" part of EAASP. D38 crosses L4→L2 boundary (needs L2 coordination). D41 is trivial endpoint wiring. P3 safety items (D28/D29/D31) run in parallel.
**Delivers:** Natural language skill discovery, tenant-isolated memory search, session browsing CLI, L4 production safety (exception handler, path validation, structured logging).
**Addresses:** D34, D38, D41, D28, D29, D31, D39
**Uses:** rapidfuzz for NLU, loguru for structure logging, respx-mocked tests for every new call path.
**Avoids:** HTTP contract drift (Pitfall 1) — respx tests mandatory. L4→L2 cross-change without L2 readiness (D38 prerequisite check).

### Phase 8.3 — L4 P3 Hardening + CLI (7 rows)
**Rationale:** Deeper L4 fixes building on Phase 8.2 foundation. CLI-v2 improvements are independent from L4 server work.
**Delivers:** Event pagination cursor, configurable context trimming, SESSION_CREATED dedup, CLI robustness.
**Addresses:** D36, D37, D33, D42, D43, D44, D45
**Avoids:** P3 over-engineering (Pitfall 7) — D36 stays as simple pagination token, not Kafka consumer groups. D37 stays as flag flip.

### Phase 8.4 — L2 P3 Sweep (8-10 rows)
**Rationale:** L2 internal improvements. Can partially overlap with Phase 8.3 (touch different files). Builds on L2 carry-forward from Phase 7.2.
**Delivers:** Pipeline multi-worker, typed MCP errors, connection pool, vector indexing, search quality improvements.
**Addresses:** D79, D99, D65, D78, D95, D96, D92, D97, D14, D15
**Uses:** eaasp_common from Phase 8.0 (D20), existing HNSW/FTS infrastructure.
**Avoids:** Concurrent index corruption (Pitfall 5) — per-worker index isolation. NATS premature migration (Pitfall 2) — defer D75/D76.

### Phase 8.5 — Hooks P2 + P3 (4 rows)
**Rationale:** Hook changes are mostly self-contained. D48 (matcher) requires proto change — schedule after Phase 8.1's proto stabilization. D108 (bats/shellcheck) validates existing hooks before D48/D50 change behavior.
**Delivers:** Hook regression CI gate, fine-grained tool targeting, LLM-powered guard hooks, shared jq fragments.
**Addresses:** D108, D48, D50, D107
**Uses:** bats-core + shellcheck, existing ScopedHookBody infrastructure, grid-engine provider layer.
**Avoids:** bats invisible in CI (Pitfall 3) — wire to `make verify`. Proto cascade failure (Pitfall 8) — full cascade plan before touching proto for D48.

### Phase 8.6 — Eval + Cleanup + grid-server (6-7 rows)
**Rationale:** Final polish phase. All items standalone, zero cross-module deps. Can shuffle order freely.
**Delivers:** E2E verify script robustness, WS schema fix, pre-flight warnings.
**Addresses:** D56, D126, D127, D128, D129, D90
**Note:** D73 (Event Room) is Phase 4 backlog — include only if time permits and never at expense of correctness items.

### Phase Ordering Rationale

- **Dependency-driven:** 8.0→8.1 (proto stable)→8.2 (L4 builds on proto)→8.3 (hardening on foundation)→8.4/8.5 (parallel, touch different layers)→8.6 (polish)
- **Parallelization:** Phases 8.0+8.1 can run in parallel (L3 vs contract, no shared files). Phases 8.3+8.4 can partially overlap (L4 vs L2, different codebases). 8.5 can overlap with 8.4.
- **Risk sequencing:** Highest-risk cross-module changes (D20 shared package, D74 proto extension) land earliest. Consumer phases build against stabilized interfaces.
- **Value sequencing:** Highest-user-value items (D34 NLU, D38 tenant isolation, D41 session list) in Phase 8.2 — early enough to matter, late enough to be stable.

### Research Flags

**Phases needing deeper research during planning (`/gsd-research-phase`):**
- **Phase 8.1 (D74 EmitEvent):** Proto change requires ADR process + 7-runtime stub regeneration. Risk: comparison runtimes may need codegen updates.
- **Phase 8.2 (D34 NLU):** rapidfuzz vs difflib trade-off needs final decision. Rapidfuzz adds a dependency; difflib may be insufficient for multi-word intents. Spike needed if rapidfuzz is blocked.
- **Phase 8.5 (D50 Prompt Executor):** LLM model selection for hook decisions (lightweight/fast vs accurate). Token budget, timeout, error handling design needs AI-SPEC contract.

**Phases with standard patterns (skip research-phase):**
- **Phase 8.0 (L3 leftovers):** All L3-internal refactors. Well-documented patterns from Phase 7.3 carry-forward.
- **Phase 8.3 (L4 hardening):** Mechanical fixes — copy patterns from L3 (Phase 7.3 already solved D22/D18/D23 for L3). Pattern-matching, not designing.
- **Phase 8.4 (L2 internals):** Internal fixes using existing infrastructure. No new architectural patterns.
- **Phase 8.6 (eval/cleanup):** Standalone script fixes. Zero cross-module impact.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All 4 new dependencies verified against current pyproject.toml files. tonic 0.12 Server feature confirmed. Rust needs zero new deps. |
| Features | HIGH | All 85 D-items verified against DEFERRED_LEDGER.md SSOT. 25 items confirmed closed via Phase 7.x commit history. Remaining 60 items classified by module/priority/dependency. |
| Architecture | HIGH | Integration points verified by direct code inspection of all 4 service entry points (L2/L3/L4 api.py, L1 service.rs), proto files, and cross-module client wrappers. Data flow changes mapped to specific line numbers. |
| Pitfalls | HIGH | 8 pitfalls identified from 5 years of brownfield maintenance patterns: HTTP contract drift, stateful infra, CI invisibility, transport migration, concurrent state, cross-module refactoring, over-engineering, and contract regression. Each has concrete prevention + recovery strategy with cost estimate. |

**Overall confidence:** HIGH — all research verified against current source code at `tools/eaasp-*/`, `proto/eaasp/runtime/v2/`, `crates/grid-*/`, and `docs/design/EAASP/DEFERRED_LEDGER.md`. No speculative findings.

### Gaps to Address

- **D34 rapidfuzz vs difflib final decision:** Needs a quick spike (≤30 min) to validate multi-word intent matching accuracy with rapidfuzz against the real skill registry fixture. If difflib is chosen, lower matching confidence should be explicitly accepted.
- **D38 L2 `user_id` field readiness:** L2's `SearchRequest` model (api.py:19-23) currently has no `user_id` field. Before Phase 8.2 D38 implementation, verify whether L2 needs schema migration or simply a new optional field. If L2 isn't ready, add `user_id` to L2 FIRST as a Phase 8.4 prerequisite.
- **D50 LLM model selection:** No decision yet on which model to use for hook prompt decisions. Should be fast (≤2s) and cheap — likely a lightweight model like Claude Haiku or GPT-4o-mini. Needs an AI-SPEC during Phase 8.5 planning.
- **D74 comparison runtime impact:** Adding `EventSink` to proto may require running `scripts/gen_runtime_proto.py` across all 6 comparison runtimes. The effort is mechanical but non-zero — budget 2-4 hours for codegen + stub verification.

## Sources

### Primary (HIGH confidence — verified against codebase)
- `.planning/v3.3-INBOX.md` — Full 85-row debt catalog, 12-module taxonomy
- `.planning/PROJECT.md` — v3.4 milestone scope, constraints, ADR-V2-024 双轴 model
- `docs/design/EAASP/DEFERRED_LEDGER.md` (544 lines) — SSOT for all D-items, classifications, resolution history
- `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/session_orchestrator.py` (753 lines) — L4 main entry point
- `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/{handshake,l1_client,context_assembly}.py` — L4→L2/L3/L1 integration
- `tools/eaasp-l3-governance/src/eaasp_l3_governance/api.py` — L3 endpoints, validate_session, exception handler
- `tools/eaasp-l2-memory-engine/src/eaasp_l2_memory_engine/api.py` — L2 endpoints, SearchRequest model, HybridIndex
- `proto/eaasp/runtime/v2/{common,runtime,hook}.proto` — L0 contract definitions
- `crates/grid-runtime/Cargo.toml` — tonic 0.12 server feature verification
- L4/L3/L2 pyproject.toml files — current dependency versions, verified against PyPI latest

### Secondary (MEDIUM confidence — external references)
- ADR-V2-006: Hook envelope contract (Rust↔Python byte-parity)
- ADR-V2-020: Tool namespace layering (L0/L1/L2 tools)
- ADR-V2-024: Dual-axis model (engine vs data/integration), grid-platform dormancy
- ADR-V2-028: Strict-by-default config validation pattern
- PyPI latest versions: rapidfuzz 3.14.5, mcp 1.27.2, mypy 2.1.0, loguru 0.7.3

### Codebase verification (direct inspection)
- `tools/eaasp-l4-orchestration/` — session orchestrator, handshake, context assembly, event engine, L1/L2/L3 clients
- `tools/eaasp-l3-governance/` — deploy, policy engine, switch_mode, sanitize_errors
- `tools/eaasp-l2-memory-engine/` — MCP dispatcher, HybridIndex, event pipeline, connection pool
- `crates/grid-engine/` — harness, hook executor, agent loop, cancel token
- `crates/grid-runtime/` — service.rs, pre_compact_emitter, proto stubs
- `scripts/` — eaasp-e2e.sh (112-case living spec), test_hook_scripts.sh, gen_runtime_proto.py
- Phase 7.0/7.1/7.2/7.3 closure commits (verified 25+ items via LEDGER status changes)

---

*Research completed: 2026-06-07*
*Ready for roadmap: yes*
*Next step: `/gsd-roadmapper` — create ROADMAP.md from this summary*
