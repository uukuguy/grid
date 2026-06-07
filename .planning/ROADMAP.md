# Grid — Roadmap

> **Milestone:** v3.4 Full INBOX Drain (Debt Sweep II) 🟡 STARTED 2026-06-07
> **Previous milestone:** v3.3 Engine + Platform Debt Sweep (Focused) ✅ SHIPPED 2026-06-07
> **Archive:** `milestones/v3.3-ROADMAP.md`

## Milestones

- ✅ **v3.0 Phase 4 — Product Scope Decision** — Phases 4.0/4.1/4.2 (shipped 2026-04-28, ADR-V2-024 Accepted)
- ✅ **v3.1 Phase 5 — Engine Hardening** — SHIPPED 2026-05-22 (6 phases, 23 REQ-IDs, 6 ADRs)
- ✅ **v3.2 Phase 6 — Tech-Debt Triage & CI Red Line Clearance** — SHIPPED 2026-05-26 (3 phases, 6 REQ-IDs)
- ✅ **v3.3 Phase 7 — Engine + Platform Debt Sweep** — SHIPPED 2026-06-07 (Phase 7.3 completed, 8/8 REQ-IDs ✅; 7.0/7.1/7.2 carry-forward to v3.4)
- 🟡 **v3.4 Phase 7/8 — Full INBOX Drain (Debt Sweep II)** — STARTED 2026-06-07

## Milestone v3.4: Full INBOX Drain (Debt Sweep II) 🟡

**Goal:** Drain ALL remaining rows from `.planning/v3.3-INBOX.md` — verify-and-close the 3 carry-forward v3.3 phases (7.0/7.1/7.2) + sweep the 7 remaining modules (L3 leftovers / contract proto / L4 / L2 leftovers / hooks / eval / cross-cutting). ~85 INBOX rows → 67 REQ-IDs over 10 phases. **Full INBOX drain** — v3.3-INBOX.md ceases to be a live doc at milestone close. 0 P1 rows — milestone is "should fix" not "must fix."

### Phases

- [ ] **Phase 7.0: grid-engine harness wiring (Verify & Close)** — 6 REQ-IDs: verify LEDGER close-out, fix if open
- [ ] **Phase 7.1: contract observability + bridge (Verify & Close)** — 5 REQ-IDs: verify LEDGER close-out, fix if open
- [ ] **Phase 7.2: L2 connection-pool + Pipeline (Verify & Close)** — 8 REQ-IDs: verify LEDGER close-out, fix if open
- [ ] **Phase 8.0: L3 Leftovers + eaasp_common Foundation** — 5 REQ-IDs: L3 P3 fixes + shared error package
- [ ] **Phase 8.1: Contract Proto + Grid-Engine/Server Cross-Cutting** — 5 REQ-IDs: EmitEvent gRPC, Terminate, MAX_TURNS config, cancel token, WS schema
- [ ] **Phase 8.2: L4 Foundation — P2 Differentiators + Safety Foundation** — 7 REQ-IDs: NLU, tenant isolation, session list + safety items
- [ ] **Phase 8.3: L4 P3 Hardening — Mechanical Copy-Paste** — 9 REQ-IDs: L4 hardening items, copy L3 patterns from Phase 7.3
- [ ] **Phase 8.4: L2 Table Stakes — Correctness Floor** — 8 REQ-IDs: L2 correctness bugs, lint config, typed errors
- [ ] **Phase 8.5: L2 Differentiators + Hooks** — 8 REQ-IDs: search quality + connection pool + hook CI/features
- [ ] **Phase 8.6: Eval + Cross-Cutting Cleanup** — 6 REQ-IDs: verify scripts, Pyright, WS schema polish

## Phase Details

### Phase 7.0: grid-engine harness wiring (Verify & Close)

**Goal**: Verify-and-close — confirm 6 ENGINE carry-forward D-items from v3.3 Phase 7.0 are ✅ CLOSED in DEFERRED_LEDGER.md with commit hash. Research indicates all 6 may already be closed; verify-then-close. If any D-row lacks ✅ CLOSED, implement the fix and close.

**Depends on**: Nothing (independent verify phase)
**Requirements**: ENGINE-01, ENGINE-02, ENGINE-03, ENGINE-04, ENGINE-05, ENGINE-06
**Verification pattern**: For each ENGINE-0X, check `docs/design/EAASP/DEFERRED_LEDGER.md` for ✅ CLOSED + commit hash. If found: mark as validated, no implementation. If missing: implement, close with commit hash, log in LEDGER §状态变更日志.

**Success Criteria** (what must be TRUE):
  1. ENGINE-01 (D102): `AgentLoopConfig.compaction` field has round-trip test from YAML→struct→YAML. LEDGER L232 shows ✅ CLOSED with commit hash. strict-by-default validation active per ADR-V2-028.
  2. ENGINE-02 (D3): harness `payload.user_preferences` surfaces to agent loop; `trim_for_budget()` is budget-driven. LEDGER L106 shows ✅ CLOSED.
  3. ENGINE-03 (D57): `build_memory_preamble` has single implementation — no duplicate between `harness_payload_integration.rs` and pipeline. LEDGER L177 shows ✅ CLOSED.
  4. ENGINE-04 (D58): `test_initialize_injects_memory_refs_preamble` asserts Send full path. LEDGER L178 shows ✅ CLOSED.
  5. ENGINE-05 (D103): `find_tail_boundary()` O(N²) profiled + either fixed OR doc-only warning with rationale recorded in LEDGER row. LEDGER L233 shows ✅ CLOSED.
  6. ENGINE-06 (D104): Reactive guard location decision (harness vs pipeline) recorded with rationale. LEDGER L234 shows ✅ CLOSED.

**Fallback (if any D-row open)**: Implement the open items per original v3.3 Phase 7.0 success criteria. Budget ≤2h per P3 item. ENGINE-01 (D102 P2) gets priority.

**Plans**: 1 plan

Plans:
- [x] 07.0-01-PLAN.md — Verify 5 closed D-items + implement D3 (user_preferences + budget-driven trim)
**UI hint**: no

---

### Phase 7.1: contract observability + bridge (Verify & Close)

**Goal**: Verify-and-close for 5 CONTRACT carry-forward D-items from v3.3 Phase 7.1. Same verify-then-close pattern as Phase 7.0. Cross-check LEDGER for ✅ CLOSED + commit hash.

**Depends on**: Nothing (can run in parallel with 7.0 and 7.2)
**Requirements**: CONTRACT-01, CONTRACT-02, CONTRACT-03, CONTRACT-04, CONTRACT-05

**Success Criteria** (what must be TRUE):
  1. CONTRACT-01 (D137): Multi-turn observability + MCP bridge live + PRE_COMPACT threshold ChunkType-triggered. `grid-runtime` emits turn-by-turn telemetry chunks. Contract test `make v2-phase3-e2e` grid-runtime job has multi-turn observability assertions passing. LEDGER L249 shows ✅ CLOSED.
  2. CONTRACT-02 (D138): Skill-workflow deny-path mock LLM test exists, no live LLM dependency. Reproducible deny-path test passes. LEDGER L250 shows ✅ CLOSED.
  3. CONTRACT-03 (D5): grpc_integration tests use v2 telemetry envelope — zero `telemetry_v1` references in `crates/` or `tests/`. LEDGER L108 shows ✅ CLOSED.
  4. CONTRACT-04 (D6): Certifier asserts SessionPayload P1-P5 fields. `make verify-dual-runtime` certifier report includes SessionPayload schema assertions. LEDGER L109 shows ✅ CLOSED.
  5. CONTRACT-05 (D55): Proto3 submessage `HasField` unified across 7 runtimes — cross-runtime parity test verifies absence path (Python + Rust + TS consistent). LEDGER L175 shows ✅ CLOSED.

**Fallback (if any D-row open)**: Implement per original v3.3 Phase 7.1 success criteria. CONTRACT-01/02 (P2) get priority over P3 items. Budget ≤2h per P3.

**Plans**: 1 plan

Plans:
- [x] 07.1-01-PLAN.md — Verify all 5 CONTRACT D-items (D137/D138/D5/D6/D55) ✅ CLOSED + tests pass + close-out

**UI hint**: no

---

### Phase 7.2: L2 connection-pool + Pipeline (Verify & Close)

**Goal**: Verify-and-close for 8 L2 carry-forward D-items from v3.3 Phase 7.2. Same verify-then-close pattern. Five P2 keystone items (D12/D94/D91/D93/D98) get priority verification.

**Depends on**: Nothing (can run in parallel with 7.0 and 7.1)
**Requirements**: L2-01, L2-02, L2-03, L2-04, L2-05, L2-06, L2-07, L2-08

**Success Criteria** (what must be TRUE):
  1. L2-01 (D12): Connection-per-call → connection pool for L2 memory-engine. `MemoryStore` singleton with pooled connections. High-concurrency test (>10 concurrent r/w) passes with zero `database is locked`. LEDGER L115 shows ✅ CLOSED.
  2. L2-02 (D94): `MemoryStore` singleton + shared connection (D12收尾). LEDGER L224 shows ✅ CLOSED.
  3. L2-03 (D91): HNSW tombstone rebuild threshold triggers auto-rebuild. Pytest `-k "tombstone"` suite passes with measured before/after recall. LEDGER L221 shows ✅ CLOSED.
  4. L2-04 (D93): `embed_batch` concurrent fan-out respects provider rate limit. Batch=10 scenario ≤30% of sequential time. LEDGER L223 shows ✅ CLOSED.
  5. L2-05 (D98): `HybridIndex.search()` no longer per-call rebuild HNSWVectorIndex. Search latency p99 ≥50% improvement vs baseline. LEDGER L228 shows ✅ CLOSED.
  6. L2-06 (D11): Skill-registry `scope` filter applied before `LIMIT`. Pytest: scope=X + limit=5 returns ≤5 all scope=X. LEDGER L114 shows ✅ CLOSED.
  7. L2-07 (D13): L2 `archive()` hides rows from FTS. Archived row not appearing in search results. LEDGER L116 shows ✅ CLOSED.
  8. L2-08 (D30): L2/L3 `busy_timeout` unified constant — no magic numbers scattered. LEDGER L142 shows ✅ CLOSED.

**Fallback (if any D-row open)**: Implement per original v3.3 Phase 7.2 success criteria. 5 P2 items (L2-01..05) get priority; P3 items budget ≤2h each.

**Plans**: TBD
**UI hint**: no

---

### Phase 8.0: L3 Leftovers + eaasp_common Foundation

**Goal**: Close 5 L3 P3 leftover items + create the `eaasp_common` shared package (D20) that L2 later consumes. The rmcp/MCP ServerHandler upgrade (D10) is the heaviest item — dual-transport (REST preserved + MCP added) to avoid breaking L4→L3 REST calls. All L3-internal, zero external dependencies except the new `eaasp_common` package.

**Depends on**: Nothing (L3-only, can run in parallel with Phase 8.1)
**Requirements**: L3-09, L3-10, L3-11, L3-12, L3-13

**Success Criteria** (what must be TRUE):
  1. **L3-12 (D20)**: `tools/eaasp-common/` package exists with `_sanitize_errors()` in `errors.py`. L3 imports from `eaasp_common` instead of defining locally. Atomic single-commit creation touching L3 pyproject.toml + api.py. `make dev-eaasp` passes unchanged. LEDGER L128 shows ✅ CLOSED.
  2. **L3-09 (D10)**: L3 MCP transport upgraded to Python `mcp` SDK ServerHandler — dual-transport: REST endpoints preserved as default, MCP added as opt-in path. L4→L3 REST calls continue working unchanged (`make v2-phase2-e2e` passes). `make dev-eaasp` L3 starts cleanly on expected REST port. LEDGER L113 shows ✅ CLOSED.
  3. **L3-10 (D16)**: `policy_engine.deploy()` reads `created_at` after commit — TOCTOU race fixed via `INSERT ... RETURNING`. LEDGER L124 shows ✅ CLOSED.
  4. **L3-11 (D19)**: `switch_mode()` validates hook_id exists — returns 404 for unknown, not silent create. LEDGER L127 shows ✅ CLOSED.
  5. **L3-13 (D25)**: Lightweight concurrent deploy unit test (in-process, not multi-process E2E). No `time.sleep(1.1)` anti-pattern — uses monotonic clock or mock time. LEDGER L133 shows ✅ CLOSED.

**Patterns**: D16/D19/D25 are L3-internal fixes (≤30 LOC each). D10 is the heavyweight (~80-150 LOC). D20 is cross-module refactor — must be single atomic commit.

**Plans**: TBD
**UI hint**: no

---

### Phase 8.1: Contract Proto + Grid-Engine/Server Cross-Cutting

**Goal**: Stabilize proto contracts before L4 builds on them — D74 (EmitEvent gRPC reverse channel) + D139 (双 Terminate semantic), both ⚠️ ADR-gated. Plus grid-engine config fixes (D106/D130) and grid-server WS schema fix (D90). Produces frozen proto that Phase 8.2 L4 consumes.

**Depends on**: Nothing (can run in parallel with Phase 8.0 — no shared files)
**Requirements**: CONTRACT-06, CONTRACT-07, ENGINE-07, ENGINE-08, SERVER-06

**⚠️ ADR Governance Gates**:
- **CONTRACT-06 (D74)**: Adding `EventSink` service to proto requires `/adr:new --type contract` before implementation. New gRPC direction (L1→L4).
- **CONTRACT-07 (D139)**: Terminate semantics clarification requires `/adr:new --type contract` or ADR-V2-017 §2 revision.

**Pre-commit checklist (per Pitfall 8 — contract test regression)**:
- [ ] `make check` passes (cargo check + tsc)
- [ ] `make verify` passes (static checks)
- [ ] `make v2-phase2-e2e` passes (SKIP_RUNTIMES=true if L1 unchanged)
- [ ] `make v2-phase3-e2e-rust` passes (Rust-side regression)
- [ ] If `proto/*.proto` touched: `scripts/gen_runtime_proto.py` + `make build-eaasp-all`

**Success Criteria** (what must be TRUE):
  1. **CONTRACT-06 (D74)**: ADR accepted for `EventSink` gRPC service. L4 `EventSinkServicer` gRPC server running alongside FastAPI. L1 grid-runtime emits events via gRPC client to L4. LEDGER L198 shows ✅ CLOSED.
  2. **CONTRACT-07 (D139)**: ADR or ADR-V2-017 revision specifies double-terminate semantic (NO-OP vs error). Cross-runtime test enforces consistent behavior across all 7 runtimes. LEDGER L251 shows ✅ CLOSED.
  3. **ENGINE-07 (D106)**: `MAX_TURNS_FOR_BUDGET=50` hardcode promoted to `AgentLoopConfig.task_budget_override` field with configurable default via env var. Long-running agents can exceed 50 turns without silent termination. LEDGER L236 shows ✅ CLOSED.
  4. **ENGINE-08 (D130)**: Session-lifetime vs per-turn cancel token dual-token inconsistency resolved. `ChildCancellationToken::cancel()` propagates correctly — `session kill` CLI command actually interrupts in-flight LLM calls. LEDGER L247 shows ✅ CLOSED.
  5. **SERVER-06 (D90)**: `ServerMessage::ToolResult` WebSocket schema includes `tool_name` field. Schema-only fix — no frontend consumer impact (Grid独立产品 dormant per ADR-V2-024). LEDGER L220 shows ✅ CLOSED.

**Budget**: CONTRACT-06 is the heaviest (~100-150 LOC + ADR + codegen). D90/D106 are ≤5 LOC each. D130 is correctness-critical (~30-50 LOC). D139 is doc/contract work (~20 LOC doc+test).

**Plans**: TBD
**UI hint**: no

---

### Phase 8.2: L4 Foundation — P2 Differentiators + Safety Foundation

**Goal**: Ship 3 P2 L4 differentiators (NLU intentional skill discovery, tenant memory isolation, session list endpoint) + 4 foundational P3 safety items (exception handler, path validation, structured logging, policy hash fix). The marquee phase — D34 NLU is the "AI" feature of this milestone. All L4 code; D38 (user_id) crosses L4→L2 boundary.

**Depends on**: Phase 8.1 (D74 proto stable for gRPC pattern; D139 proto stable for contract consistency)
**Requirements**: L4-01, L4-02, L4-03, L4-04, L4-05, L4-06, L4-08

**⚠️ Pre-implementation checks (per Pitfall 1 — HTTP contract drift)**:
- **D38 (L2Client pass user_id)**: Verify L2's `SearchRequest` model accepts `user_id` BEFORE implementing L4 change. L2 `api.py:75` currently has no `user_id` field — may need L2 schema change. If L2 isn't ready, add `user_id` to L2 FIRST (coordinate with Phase 8.4 L2 table-stakes phase).

**Respx-mocked tests mandatory** (per Pitfall 1): Every new L4→L2/L3 call path (D34, D38, D41) must have a respx-mocked integration test asserting exact parsed output from real upstream response shapes.

**Success Criteria** (what must be TRUE):
  1. **L4-01 (D34)**: User types natural language (e.g., "deploy the SCADA calibration") → `IntentParser` resolves correct `skill_id` via fuzzy matching (rapidfuzz). Tested with full skill-registry fixture (≥10 skills). Unknown intents return graceful error, not 500 crash. LEDGER L146 shows ✅ CLOSED.
  2. **L4-02 (D38)**: `L2Client.search_memory()` passes `user_id` for tenant memory isolation. L4→L2 REST call includes `user_id` field. L2 API accepts it and filters results. Respx test asserts L2 receives the parameter. LEDGER L149 shows ✅ CLOSED.
  3. **L4-03 (D41)**: `GET /v1/sessions` REST endpoint returns session list with metadata. `eaasp-cli-v2 session list` CLI command wired to endpoint — user can browse sessions. LEDGER L151 shows ✅ CLOSED.
  4. **L4-04 (D28)**: L4 global FastAPI exception handler added (copy D22 pattern from Phase 7.3 L3). No Python traceback leakage in 5xx responses. Returns standard `{"error": {...}}` shape. LEDGER L140 shows ✅ CLOSED.
  5. **L4-05 (D29)**: L4 path param `session_id` has format validation (copy D18 pattern). Malformed IDs rejected at input boundary. LEDGER L141 shows ✅ CLOSED.
  6. **L4-06 (D31)**: L4 loguru initialized at startup (copy D23 pattern from Phase 7.3 L3). Structured logging active — no bare `print()` for errors. LEDGER L143 shows ✅ CLOSED.
  7. **L4-08 (D39)**: `PolicyContext.policy_version` uses `hashlib.sha256(json.dumps(...)).hexdigest()[:12]` — not `str(int)`. ~3 LOC fix. LEDGER L150 shows ✅ CLOSED.

**Budget**: D34 is the largest (new module, ~100-200 LOC + integration). D38 crosses L4↔L2 boundary (coordinate with L2). D41 is trivial endpoint wiring (~30 LOC). P3 safety items (D28/D29/D31) are mechanical copy-paste (~10-15 LOC each). D39 is 3 LOC.

**Plans**: TBD
**UI hint**: no

---

### Phase 8.3: L4 P3 Hardening — Mechanical Copy-Paste from L3 Patterns

**Goal**: 9 L4 P3 hardening items — ALL mechanical fixes copying established L3 patterns from Phase 7.3. Zero new design. Total LOC ~200 across all items. Includes CLI-v2 improvements (D42-D45) which are independent from L4 server work.

**Depends on**: Phase 8.2 (L4 foundation — safety items D28/D29/D31 must be in place before deeper hardening)
**Requirements**: L4-07, L4-09, L4-10, L4-11, L4-12, L4-13, L4-14, L4-15, L4-16

**⚠️ P3 budget enforcement (per Pitfall 7 — gold-plating)**: Each P3 item ≤2 hours. Pattern-match from existing L3 code, do NOT design. If a fix takes >2h, flag for milestone review as P2 scope expansion.

**Success Criteria** (what must be TRUE):
  1. **L4-07 (D37)**: `context_assembly` `allow_trim_p4` configurable (not hardcoded `False`). Flag flip + env var. LEDGER L148 shows ✅ CLOSED.
  2. **L4-09 (D42)**: CLI `test_client` covers 5xx response paths — respx-mocked 500/503 test exists. CLI doesn't crash on server errors. LEDGER L152 shows ✅ CLOSED.
  3. **L4-10 (D43)**: Unused `respx>=0.21` removed from CLI `pyproject.toml`. ~1 LOC delete. LEDGER L153 shows ✅ CLOSED.
  4. **L4-11 (D44)**: `cmd_session.show` exposes `--limit` CLI flag (not hardcoded 100). User can view >100 sessions. LEDGER L154 shows ✅ CLOSED.
  5. **L4-12 (D45)**: CLI response shape guard — `dict.get()` with defaults, no `KeyError` on server shape change. LEDGER L155 shows ✅ CLOSED.
  6. **L4-13 (D61)**: `threshold-calibration-skill.md` fixture parses version from submit response (not hardcoded). LEDGER L181 shows ✅ CLOSED.
  7. **L4-14 (D125)**: L4 event burst >500 detection + warning log (not silent loss). ~10 LOC. LEDGER L242 shows ✅ CLOSED.
  8. **L4-15 (D110)**: `dependencies` field `kind: runtime|intent` semantics distinction. Schema-breaking change (Phase 3+ documented). ~50 LOC + migration. LEDGER L240 shows ✅ CLOSED.
  9. **L4-16 (D33)**: SESSION_CREATED event payload reference-mode dedup — store once, link. ~30 LOC + migration. LEDGER L145 shows ✅ CLOSED.

**Plans**: TBD
**UI hint**: no

---

### Phase 8.4: L2 Table Stakes — Correctness Floor

**Goal**: 8 L2 P3 table-stakes fixes — correctness bugs (memory_id parsing, typed errors, HTTPException shape), lint/dev quality (ruff/mypy config, private symbol promotion), and cross-module consistency (Makefile port, MockEmbedding seed). All L2-internal or scripts-only. Builds on Phase 8.0 D20 (eaasp_common availability). Uses existing HNSW/FTS infrastructure.

**Depends on**: Phase 8.0 (D20 eaasp_common available for L2 import; D10 rmcp upgrade may affect MCP dispatcher behavior)
**Requirements**: L2-09, L2-10, L2-11, L2-12, L2-13, L2-14, L2-15, L2-16

**Success Criteria** (what must be TRUE):
  1. **L2-09 (D14)**: `_row_to_memory` promoted to public API — `row_to_memory()` with deprecation shim for `_row_to_memory`. ~5 LOC rename. LEDGER L117 shows ✅ CLOSED.
  2. **L2-10 (D15)**: L2 `pyproject.toml` has `[tool.ruff]` + `[tool.mypy]` config (copy L3 pattern). Parity with L3. LEDGER L118 shows ✅ CLOSED.
  3. **L2-11 (D59)**: Makefile `mcp-orch-start` port configurable via env var (not hardcoded 8082). ~5 LOC. LEDGER L179 shows ✅ CLOSED.
  4. **L2-12 (D99)**: MCP dispatcher `int()`/`float()` conversions wrapped in try/except → `ToolError("invalid_arg")`. No native `ValueError`/`TypeError` leaks. ~20 LOC. LEDGER L229 shows ✅ CLOSED.
  5. **L2-13 (D96)**: `memory_id` HNSW key parsing uses `rsplit(":v", 1)` not `split(":v")`. User IDs containing `:v` no longer silently skipped. ~3 LOC. LEDGER L226 shows ✅ CLOSED.
  6. **L2-14 (D97)**: `HybridIndex` weights=(0,0) degenerate case emits `logger.warning`. Operator alerted to zero-weight search. ~2 LOC. LEDGER L227 shows ✅ CLOSED.
  7. **L2-15 (D92)**: `MockEmbedding` seed widened from 64-bit to 32-byte digest. Test collisions eliminated. ~5 LOC. LEDGER L222 shows ✅ CLOSED.
  8. **L2-16 (D101)**: FastAPI `HTTPException(detail=dict)` nesting fix — response shape matches doc contract flat shape. Either fix code (~20 LOC) or fix doc (~5 LOC). LEDGER L231 shows ✅ CLOSED.

**Budget**: All mechanical — ≤20 LOC each, total ~60 LOC plus config. P3 budget ≤2h each.

**Plans**: TBD
**UI hint**: no

---

### Phase 8.5: L2 Differentiators + Hooks

**Goal**: 3 L2 search-quality differentiators (connection pool, semantic backfill, embedding surface) + 5 hooks items (P2 regression CI gate + P3 matcher/proto, Prompt executor, HookPoint alias, jq fragment). Hooks D48 (matcher proto) and D50 (Prompt executor) are the most complex in this phase — D48 requires proto change, D50 requires new LLM-calling component in grid-engine.

**Depends on**: Phase 8.1 (D48 matcher requires proto stable from D74/D139; D50 Prompt executor builds on grid-engine provider layer) + Phase 8.4 (L2 infrastructure for D65/D95/D100)
**Requirements**: L2-17, L2-18, L2-19, HOOK-01, HOOK-02, HOOK-03, HOOK-04, HOOK-05

**⚠️ Research flags** (per SUMMARY.md):
- **D50 Prompt Executor**: LLM model selection needs AI-SPEC contract during planning. Fast model (≤2s), cheap — likely Haiku or GPT-4o-mini.
- **D48 proto cascade**: Full cascade plan required BEFORE touching proto. Affects L0 proto → Python codegen → L4 dict→proto → grid-engine type → harness dispatch.

**Success Criteria** (what must be TRUE):
  1. **HOOK-01 (D108)**: bats + shellcheck CI gate active — `make verify` includes `hook-scripts-test`. Regression tests for all existing hook scripts. bats conditional in CI (`which bats || echo "SKIP"`). LEDGER L238 shows ✅ CLOSED.
  2. **L2-17 (D65)**: MCP connection pool for multi-tool workloads — pre-warmed connections, latency reduction. Pool manager with health-check before handoff. LEDGER L187 shows ✅ CLOSED.
  3. **L2-18 (D95)**: FTS hit `semantic_score` backfill from DB `embedding_vec` blob when HNSW add fails. ~40 LOC. Search quality improvement — 0-score artifacts eliminated. LEDGER L225 shows ✅ CLOSED.
  4. **L2-19 (D100)**: `write()`/`confirm()`/`archive()` surface `embedding_model` + `dimension` in `MemoryFileOut`. Observability for memory pipeline. LEDGER L230 shows ✅ CLOSED.
  5. **HOOK-02 (D48)**: `ScopedHookBody` has `matcher` + `tool_filter` fields for fine-grained hook targeting. Proto schema extended → codegen regenerated → L4 + L1 consumers updated. Hooks only fire for matched tools. LEDGER L163 shows ✅ CLOSED.
  6. **HOOK-03 (D50)**: `ScopedHookBody::Prompt` executor loop runs — LLM call during hook execution for meta-agent guard decisions. Single-turn, lightweight model, ≤2s timeout. LEDGER L165 shows ✅ CLOSED.
  7. **HOOK-04 (D105)**: `HookPoint::ContextDegraded` string alias preserved with deprecation warning. Backwards-compat doc: existing YAML/JSON hook configs continue working. LEDGER L235 shows ✅ CLOSED.
  8. **HOOK-05 (D107)**: Shared jq fragment extracted from `check_output_anchor.sh` + `check_final_output.sh` to `_lib/json_guards.sh`. Copy-paste bug surface eliminated. LEDGER L237 shows ✅ CLOSED.

**Plans**: TBD
**UI hint**: no

---

### Phase 8.6: Eval + Cross-Cutting Cleanup

**Goal**: 6 standalone eval/cleanup items — verify script robustness, IDE config fix, cosmetic @assertion polish. All items zero cross-module deps. Can run independently. Final polish phase — ships after all preceding phases complete, but not on critical path.

**Depends on**: Nothing strong (standalone items), but naturally runs last as final polish
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06

**Success Criteria** (what must be TRUE):
  1. **EVAL-01 (D126)**: `lang/claude-code-runtime-python/.venv` existence checked before A8 test — fails early with actionable error message. ~10 LOC. LEDGER L243 shows ✅ CLOSED.
  2. **EVAL-02 (D127)**: `data/verify-v2-phase2-skill-registry/` directory auto-cleanup after test run. ~5 LOC. LEDGER L244 shows ✅ CLOSED.
  3. **EVAL-03 (D128)**: `@assertion` decorator prints NOTE before PASS — UX polish, correct ordering. ~5 LOC. LEDGER L245 shows ✅ CLOSED.
  4. **EVAL-04 (D129)**: `verify-v2-phase2.sh` cleanup trap doesn't sweep external ports on pre-flight failure. ~15 LOC. LEDGER L246 shows ✅ CLOSED.
  5. **EVAL-05 (D24)**: IDE Pyright missing-import false positives fixed in `pyrightconfig.json`. ~10 LOC config. LEDGER L132 shows ✅ CLOSED.
  6. **EVAL-06 (D56)**: `verify-v2-mvp.sh` cleanup scope expanded beyond SQLite-only — covers all artifacts. ~10 LOC. LEDGER L176 shows ✅ CLOSED.

**Plans**: TBD
**UI hint**: no

---

## Progress (v3.4)

**Execution Order:**
Phases execute in numeric order. Parallelization opportunities (per GSD config):
- **7.0 ∥ 7.1 ∥ 7.2**: All verify-only, no shared files — execute in parallel
- **8.0 ∥ 8.1**: L3-only vs contract/grid-engine, no shared files — execute in parallel
- **8.2 → 8.3**: Sequential — L4 hardening builds on L4 foundation
- **8.3 ∥ 8.4**: L4 vs L2, different codebases — partial overlap
- **8.4 → 8.5**: L2 infrastructure → L2 differentiators — sequential
- **8.5 ∥ 8.6**: Hooks vs eval, no shared code — partial overlap

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 7.0 grid-engine harness wiring (V&C) | 0/1 | 🟡 Planned | - |
| 7.1 contract observability + bridge (V&C) | 0/1 | 🟡 Planned | - |
| 7.2 L2 connection-pool + Pipeline (V&C) | 0/0 | 🟡 Not started | - |
| 8.0 L3 Leftovers + eaasp_common | 0/0 | 🟡 Not started | - |
| 8.1 Contract Proto + Engine/Server | 0/0 | 🟡 Not started | - |
| 8.2 L4 Foundation | 0/0 | 🟡 Not started | - |
| 8.3 L4 P3 Hardening | 0/0 | 🟡 Not started | - |
| 8.4 L2 Table Stakes | 0/0 | 🟡 Not started | - |
| 8.5 L2 Differentiators + Hooks | 0/0 | 🟡 Not started | - |
| 8.6 Eval + Cross-Cutting Cleanup | 0/0 | 🟡 Not started | - |

---

## Coverage Index (v3.4)

### Carry-Forward (Phase 7.0–7.2)

| REQ-ID | D-ID | Phase | Priority | Status |
|--------|------|-------|----------|--------|
| ENGINE-01 | D102 | 7.0 (V&C) | P2 | 🟡 Pending |
| ENGINE-02 | D3 | 7.0 (V&C) | P3 | 🟡 Pending |
| ENGINE-03 | D57 | 7.0 (V&C) | P3 | 🟡 Pending |
| ENGINE-04 | D58 | 7.0 (V&C) | P3 | 🟡 Pending |
| ENGINE-05 | D103 | 7.0 (V&C) | P3 | 🟡 Pending |
| ENGINE-06 | D104 | 7.0 (V&C) | P3 | 🟡 Pending |
| CONTRACT-01 | D137 | 7.1 (V&C) | P2 | 🟡 Pending |
| CONTRACT-02 | D138 | 7.1 (V&C) | P2 | 🟡 Pending |
| CONTRACT-03 | D5 | 7.1 (V&C) | P3 | 🟡 Pending |
| CONTRACT-04 | D6 | 7.1 (V&C) | P3 | 🟡 Pending |
| CONTRACT-05 | D55 | 7.1 (V&C) | P3 | 🟡 Pending |
| L2-01 | D12 | 7.2 (V&C) | P2 | 🟡 Pending |
| L2-02 | D94 | 7.2 (V&C) | P2 | 🟡 Pending |
| L2-03 | D91 | 7.2 (V&C) | P2 | 🟡 Pending |
| L2-04 | D93 | 7.2 (V&C) | P2 | 🟡 Pending |
| L2-05 | D98 | 7.2 (V&C) | P2 | 🟡 Pending |
| L2-06 | D11 | 7.2 (V&C) | P3 | 🟡 Pending |
| L2-07 | D13 | 7.2 (V&C) | P3 | 🟡 Pending |
| L2-08 | D30 | 7.2 (V&C) | P3 | 🟡 Pending |

### New v3.4 (Phase 8.0–8.6)

| REQ-ID | D-ID | Phase | Priority | Status |
|--------|------|-------|----------|--------|
| L3-09 | D10 | 8.0 | P3 | 🟡 Pending |
| L3-10 | D16 | 8.0 | P3 | 🟡 Pending |
| L3-11 | D19 | 8.0 | P3 | 🟡 Pending |
| L3-12 | D20 | 8.0 | P3 | 🟡 Pending |
| L3-13 | D25 | 8.0 | P3 | 🟡 Pending |
| CONTRACT-06 | D74 | 8.1 | P3 ⚠️ ADR | 🟡 Pending |
| CONTRACT-07 | D139 | 8.1 | P3 ⚠️ ADR | 🟡 Pending |
| ENGINE-07 | D106 | 8.1 | P3 | 🟡 Pending |
| ENGINE-08 | D130 | 8.1 | P3 | 🟡 Pending |
| SERVER-06 | D90 | 8.1 | P3 | 🟡 Pending |
| L4-01 | D34 | 8.2 | P2 🌟 | 🟡 Pending |
| L4-02 | D38 | 8.2 | P2 | 🟡 Pending |
| L4-03 | D41 | 8.2 | P2 | 🟡 Pending |
| L4-04 | D28 | 8.2 | P3 | 🟡 Pending |
| L4-05 | D29 | 8.2 | P3 | 🟡 Pending |
| L4-06 | D31 | 8.2 | P3 | 🟡 Pending |
| L4-08 | D39 | 8.2 | P3 | 🟡 Pending |
| L4-07 | D37 | 8.3 | P3 | 🟡 Pending |
| L4-09 | D42 | 8.3 | P3 | 🟡 Pending |
| L4-10 | D43 | 8.3 | P3 | 🟡 Pending |
| L4-11 | D44 | 8.3 | P3 | 🟡 Pending |
| L4-12 | D45 | 8.3 | P3 | 🟡 Pending |
| L4-13 | D61 | 8.3 | P3 | 🟡 Pending |
| L4-14 | D125 | 8.3 | P3 | 🟡 Pending |
| L4-15 | D110 | 8.3 | P3 | 🟡 Pending |
| L4-16 | D33 | 8.3 | P3 | 🟡 Pending |
| L2-09 | D14 | 8.4 | P3 | 🟡 Pending |
| L2-10 | D15 | 8.4 | P3 | 🟡 Pending |
| L2-11 | D59 | 8.4 | P3 | 🟡 Pending |
| L2-12 | D99 | 8.4 | P3 | 🟡 Pending |
| L2-13 | D96 | 8.4 | P3 | 🟡 Pending |
| L2-14 | D97 | 8.4 | P3 | 🟡 Pending |
| L2-15 | D92 | 8.4 | P3 | 🟡 Pending |
| L2-16 | D101 | 8.4 | P3 | 🟡 Pending |
| L2-17 | D65 | 8.5 | P3 | 🟡 Pending |
| L2-18 | D95 | 8.5 | P3 | 🟡 Pending |
| L2-19 | D100 | 8.5 | P3 | 🟡 Pending |
| HOOK-01 | D108 | 8.5 | P2 | 🟡 Pending |
| HOOK-02 | D48 | 8.5 | P3 | 🟡 Pending |
| HOOK-03 | D50 | 8.5 | P3 ⚠️ AI-SPEC | 🟡 Pending |
| HOOK-04 | D105 | 8.5 | P3 | 🟡 Pending |
| HOOK-05 | D107 | 8.5 | P3 | 🟡 Pending |
| EVAL-01 | D126 | 8.6 | P3 | 🟡 Pending |
| EVAL-02 | D127 | 8.6 | P3 | 🟡 Pending |
| EVAL-03 | D128 | 8.6 | P3 | 🟡 Pending |
| EVAL-04 | D129 | 8.6 | P3 | 🟡 Pending |
| EVAL-05 | D24 | 8.6 | P3 | 🟡 Pending |
| EVAL-06 | D56 | 8.6 | P3 | 🟡 Pending |

**Total v3.4 coverage**: 67/67 REQ-IDs mapped (19 carry-forward + 48 new); 0 orphans; 0 double-mapped.

**Deferred items** (DEFER-01..09, not in phase plan): Explicit anti-features for v3.4 per REQUIREMENTS.md §Future Requirements. All tagged 📦 long-term in DEFERRED_LEDGER.md.

---

## Granularity Rationale (v3.4)

v3.4 = 10 phases. Per-phase row budget ≤12 (max 9 in Phase 8.3). Module batching follows dependency chain: carry-forward verify → foundation (L3 eaasp_common + proto stabilize) → L4 build → L4 harden → L2 fix → hooks + L2 diff → polish.

| Granularity check | Phase ratio | Verdict |
|--|--|--|
| **Granularity = Standard** | 10 phases / milestone | ✓ Intentionally above standard 5-8 range — justified by ~55 row scope and module diversity (L2/L3/L4/hooks/contract/engine/eval across Python + Rust + bash) |
| **Mapping density** | avg 5.5 REQ/phase (range 5-9) | ✓ Within ≤12 per-phase budget |
| **P2 distribution** | 11 P2 across 9 phases | ✓ P2 concentrated in 8.2 (3 P2 L4 Foundation) + 8.5 (1 P2 hooks CI); carry-forward P2 verified not reworked in 7.0/7.1/7.2 |
| **Parallelization** | 6 phases benefit from parallel execution | ✓ 7.0∥7.1∥7.2 + 8.0∥8.1 + 8.3∥8.4 + 8.5∥8.6 |

**ADR governance gates**: 2 items (CONTRACT-06 D74 + CONTRACT-07 D139 in Phase 8.1) require ADR before implementation. Flagged ⚠️ ADR in phase and coverage index.

**AI-SPEC contract**: 1 item (HOOK-03 D50 Prompt Executor in Phase 8.5) needs AI-SPEC.md contract for LLM model selection during planning. Flagged ⚠️ AI-SPEC.

---

<details>
<summary>✅ v3.0—v3.3 Completed Milestones (historical — collapsed)</summary>

### v3.0 Phase 4 — Product Scope Decision (Shipped 2026-04-28)
3 phases: 4.0 Bootstrap & Cleanup, 4.1 Discuss & Audit, 4.2 Decide & Document. ADR-V2-024 Accepted.

### v3.1 Phase 5 — Engine Hardening (Shipped 2026-05-22)
6 phases: 5.0 Hook Envelope Baseline, 5.1 Runtime Tier ADR, 5.2 CLI Hardening, 5.3 Contract Evolution, 5.4 Server Hardening, 5.5 Interface ADR. 23 REQ-IDs. 6 ADRs Accepted.

### v3.2 Phase 6 — Tech-Debt Triage (Shipped 2026-05-26)
3 phases: 6.0 CI Red Clearance, 6.1 grid-cli Anti-pattern, 6.2 Debt Ledger Triage. 6 REQ-IDs. 93 D-rows triaged → v3.3-INBOX.md seeded.

### v3.3 Phase 7 — Engine + Platform Debt Sweep (Shipped 2026-06-07)
Phase 7.3 L3 RBAC completed (8/8 REQ-IDs ✅). Phases 7.0/7.1/7.2 carry-forward to v3.4 for verification. Full v3.3 archive at `milestones/v3.3-ROADMAP.md`.

</details>

---

*Last updated: 2026-06-07 — Milestone v3.4 ROADMAP created. Next: `/gsd-discuss-phase 7.0` or `/gsd-plan-phase 7.0`.*
