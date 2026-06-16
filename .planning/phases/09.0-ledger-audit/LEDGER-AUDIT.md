# LEDGER-AUDIT: D-ID Notation Standardization & Status Cross-Reference

> **Generated**: 2026-06-16 by Phase 9.0 Ledger Audit
> **Source**: `docs/design/EAASP/DEFERRED_LEDGER.md` cross-referenced with `git log --all --grep`
> **Standard format**: `✅ CLOSED YYYY-MM-DD Phase X @ commit`

---

## Summary

| Category | Count | Action |
|----------|-------|--------|
| CLOSED — needs notation fix | 17 | Normalize notation in Phase 9.0 |
| CLOSED — LEDGER row shows ACTIVE | 30 | Update LEDGER rows with close-out trace |
| ACTIVE — genuinely unresolved | 17 | Feed into Phase 9.1+ planning |

**Total D-rows analyzed**: 64 (excludes already-standardized rows and D-IDs outside EAASP main namespace)

---

## Section A: CLOSED — Historical Items with Non-Standard Notation

Rows that are functionally closed (confirmed by implementation evidence in LEDGER itself or status log), but the status cell uses legacy `✅ closed` / `✅ closed YYYY-MM-DD` format instead of the standardized `✅ CLOSED YYYY-MM-DD Phase X @ commit`.

| D-ID | LEDGER Status | Description | Evidence (from LEDGER) | Suggested Notation |
|------|--------------|-------------|----------------------|---------------------|
| D1 | `✅ closed` | harness 接入 `payload.policy_context` | ADR-V2-004 S4.T2 4b-lite (2026-04-12) | `✅ CLOSED 2026-04-12 Phase 0.5 S4.T2 @ a6fad2b6` |
| D2 | `✅ closed` | harness 接入 `payload.memory_refs` | ADR-V2-004 `build_memory_preamble` (2026-04-12) | `✅ CLOSED 2026-04-12 Phase 0.5 S4.T2 @ a6fad2b6` |
| D4 | `✅ closed` | harness 接入 `payload.event_context` | Phase 1 ADR-V2-002 (2026-04-13) | `✅ CLOSED 2026-04-13 Phase 1 ADR-V2-002` |
| D7 | `✅ closed` | EmitEvent 真实实现 | Phase 1 Event Engine (2026-04-11) | `✅ CLOSED 2026-04-11 Phase 1 ADR-V2-001` |
| D47 | `✅ closed` | mock-scada.py argparse stub | tools/mock-scada/ (2026-04-12) | `✅ CLOSED 2026-04-12 Phase 0 S4.T2` |
| D49 | `✅ closed` | `${SKILL_DIR}` 变量替换 helper | `substitute_hook_vars` (2026-04-12) | `✅ CLOSED 2026-04-12 Phase 0 S4.T1` |
| D51 | `✅ closed 2026-04-15` | Hook stdin envelope schema 未 ADR 化 | S3.T5 @ `7cb48eb` (ADR-V2-006) | `✅ CLOSED 2026-04-15 Phase 2 S3.T5 @ 7cb48eb` |
| D52 | `✅ closed` | SKILL.md prose 与 L2 MCP tool schema 一致性 | 逐字对照验证 (2026-04-12) | `✅ CLOSED 2026-04-12 Phase 0 S4.T1` |
| D53 | `✅ closed 2026-04-15` | D49 helper 写了但 runtime 没调用 | S3.T5 @ `7cb48eb` | `✅ CLOSED 2026-04-15 Phase 2 S3.T5 @ 7cb48eb` |
| D54 | `✅ closed` | L4→L1 真 gRPC binding | Phase 0.5 S1 (2026-04-12) | `✅ CLOSED 2026-04-12 Phase 0.5 S1` |
| D60 | `✅ closed 2026-04-15` | verify-v2-mvp assertion 11 hybrid search 降级 | S2.T5 @ `bad4269` | `✅ CLOSED 2026-04-15 Phase 2 S2.T5 @ bad4269` |
| D83 | `✅ closed 2026-04-14` | grid-runtime ToolResult chunk 缺 `tool_name` | S1.T4 @ `bdc5b8b` | `✅ CLOSED 2026-04-14 Phase 2 S1.T4 @ bdc5b8b` |
| D84 | `✅ closed 2026-04-15` | CLI `session events --follow` SSE 未实现 | S4.T2 @ `bd55bc4` | `✅ CLOSED 2026-04-15 Phase 2 S4.T2 @ bd55bc4` |
| D85 | `✅ closed 2026-04-14` | `STOP` event `response_text` 空 | S1.T5 @ `bdc5b8b`+`d0e6cb0` | `✅ CLOSED 2026-04-14 Phase 2 S1.T5 @ bdc5b8b` |
| D86 | `✅ closed 2026-04-14` | claude-code-runtime SDK wrapper 丢 `ToolResultBlock` | S1.T3 @ `d0e6cb0` | `✅ CLOSED 2026-04-14 Phase 2 S1.T3 @ d0e6cb0` |
| D87 | `✅ closed 2026-04-14` | grid-engine agent loop 多步工作流过早终止 | ADR-V2-016 @ `bdc4fd5`/`c0f98f9`/`8a738b1` | `✅ CLOSED 2026-04-14 Phase 2 S1.T1 @ bdc4fd5` |
| D89 | `✅ closed 2026-04-15` | CLI `session close` 未实现 | S4.T1 @ `28e6b21` | `✅ CLOSED 2026-04-15 Phase 2 S4.T1 @ 28e6b21` |

**Action**: Inline edit each row's status cell in `DEFERRED_LEDGER.md` to use the standardized format. Already have commit evidence from the LEDGER's own "证据 / 去向" column — no re-verification needed.

---

## Section B: CLOSED via Phases 7.0–8.6 — LEDGER Main Row Shows ACTIVE

Rows where the LEDGER main table still shows an active status tag (`[P3-async-when-touched]`, `[P2-next-milestone]`, etc.), but implementation was completed in a recent phase, confirmed by git log commits that either explicitly tag the D-ID or whose plan commit maps the work to the D-ID.

### Phase 7.3 (L3 RBAC + hardening)

These were implemented in Phase 7.3 and already have standardized notation in LEDGER. The LEDGER was updated at close-out. (Verified: D8, D9, D17, D18, D22, D23, D26, D46 — all already standardized.)

### Phase 8.0 (L3 leftovers + eaasp_common)

| D-ID | LEDGER Status | Commit | Description | Action |
|------|--------------|--------|-------------|--------|
| D16 | `[P3-async-when-touched] 🧹 tech-debt` | `b4a2f517` | L3 `policy_engine.deploy()` — INSERT RETURNING for atomic deploy | Update LEDGER: `@ b4a2f517` |
| D19 | `[P3-async-when-touched] 🧹 tech-debt` | `2a4f87f6` | L3 `switch_mode()` — validate hook_id exists before creating override | Update LEDGER: `@ 2a4f87f6` |
| D20 | `[P3-async-when-touched] 🧹 tech-debt` | `95d91963` | `_sanitize_errors()` extracted to `eaasp_common` shared package | Update LEDGER: `@ 95d91963` |
| D25 | `[P3-async-when-touched] 📦 long-term` | `54616d22` | L3 concurrent deploy E2E unit test | Update LEDGER: `@ 54616d22` |
| D10 | `[P3-async-when-touched] 🧹 tech-debt` | `28a9b15d` + `59d0e2ad` | MCP dual-transport (SSE + stdio) added to L3 governance; L2/L4 remaining | PARTIAL — L3 done, L2/L4 deferred |

### Phase 8.2 (L4 Foundation)

| D-ID | LEDGER Status | Commit | Description | Action |
|------|--------------|--------|-------------|--------|
| D28 | `[P3-async-when-touched] 🧹 tech-debt` | `b5c545ff` | L4 global exception handler (D22 duplicate, merged) | Update LEDGER: `@ b5c545ff` |
| D29 | `[P3-async-when-touched] 🧹 tech-debt` | `b5c545ff` | L4 path param validation (D18 duplicate, merged) | Update LEDGER: `@ b5c545ff` |
| D31 | `[P3-async-when-touched] 🧹 tech-debt` | `b5c545ff` | L4 loguru initialization (D23 duplicate, merged) | Update LEDGER: `@ b5c545ff` |
| D34 | `[P2-next-milestone] 🔴 phase3-gated` | `b9741ab3` + `ddc2cefc` | L4 NLU intent resolver (`rapidfuzz`) + dispatch integration | Update LEDGER: `@ b9741ab3` |
| D38 | `[P2-next-milestone] 🔴 phase3-gated` | `ddc2cefc` | L4 `L2Client.search_memory` — user_id propagation added | Update LEDGER: `@ ddc2cefc` |
| D39 | `[P3-async-when-touched] 🧹 tech-debt` | `cf2694b5` | L4 `PolicyContext.policy_version` — hash-based instead of `str(int)` | Update LEDGER: `@ cf2694b5` |

### Phase 8.3 (L4 P3 Hardening + CLI)

| D-ID | LEDGER Status | Commit | Description | Action |
|------|--------------|--------|-------------|--------|
| D42 | `[P3-async-when-touched] 🧹 tech-debt` | `cbf71505` | cli-v2 `test_client` — 5xx exit_code=4 coverage added | Update LEDGER: `@ cbf71505` |
| D43 | `[P3-async-when-touched] 🧹 tech-debt` | `cbf71505` | cli-v2 — unused `respx>=0.21` dep removed | Update LEDGER: `@ cbf71505` |
| D44 | `[P3-async-when-touched] 🧹 tech-debt` | `cbf71505` | cli-v2 `cmd_session.show` — `--limit` flag exposed | Update LEDGER: `@ cbf71505` |
| D45 | `[P3-async-when-touched] 🧹 tech-debt` | `cbf71505` | cli-v2 response-shape guard added | Update LEDGER: `@ cbf71505` |
| D61 | `[P3-async-when-touched] 🧹 tech-debt` | `c3c828a7` | `threshold-calibration-skill.md` — dynamic version parsing from submit response | Update LEDGER: `@ c3c828a7` |

### Phase 8.4 (L2 Correctness Floor)

| D-ID | LEDGER Status | Commit | Description | Action |
|------|--------------|--------|-------------|--------|
| D14 | `[P3-async-when-touched] 🧹 tech-debt` | `20d3f443` | L2 `index._row_to_memory` — promoted to public API | Update LEDGER: `@ 20d3f443` |
| D15 | `[P3-async-when-touched] 🧹 tech-debt` | `8625f755` | L2 — ruff + mypy config added to pyproject.toml | Update LEDGER: `@ 8625f755` |
| D59 | `[P3-async-when-touched] 🧹 tech-debt` | `3a54cb31` | `Makefile::mcp-orch-start` — port now configurable via `L2_MCP_ORCH_PORT` | Update LEDGER: `@ 3a54cb31` |
| D92 | `[P3-async-when-touched] 🔵 P3-defer` | `a0bd006b` | MockEmbedding — widened from 8-byte to full 32-byte SHA-256 digest | Update LEDGER: `@ a0bd006b` |
| D96 | `[P3-async-when-touched] 🔵 P3-defer` | `20d3f443` | HNSW key parsing — `rsplit(":v", 1)` fix for user-defined memory_id | Update LEDGER: `@ 20d3f443` |
| D97 | `[P3-async-when-touched] 🔵 P3-defer` | `20d3f443` | `weights=(0,0)` — construct-time warning added | Update LEDGER: `@ 20d3f443` |
| D99 | `[P3-async-when-touched] 🔵 P3-defer` | `635617bf` | MCP dispatcher — `int()`/`float()` conversions wrapped in ToolError | Update LEDGER: `@ 635617bf` |
| D101 | `[P3-async-when-touched] 🔵 P3-defer` | `635617bf` | FastAPI HTTPException — response shape flattened (no nested 'detail') | Update LEDGER: `@ 635617bf` |

### Phase 8.5 (L2 Differentiators + Hooks)

| D-ID | LEDGER Status | Commit | Description | Action |
|------|--------------|--------|-------------|--------|
| D48 | `[P3-async-when-touched] 🧹 tech-debt` | `e6b837a0` | `ScopedHookBody` — `matcher` + `tool_filter` fields added (v2.1) | Update LEDGER: `@ e6b837a0` |
| D50 | `[P3-async-when-touched] 🟡 P1-active` | `77566619` | `ScopedHookBody::Prompt` — YES/NO prompt executor implemented | Update LEDGER: `@ 77566619` |
| D65 | `[P3-async-when-touched] 🧹 tech-debt` | `a98a5653` | MCP server — shared httpx.AsyncClient connection pool | Update LEDGER: `@ a98a5653` |
| D95 | `[P3-async-when-touched] 🔵 P2-defer` | `6c2bc81a` | FTS semantic_score — backfill from DB `embedding_vec` | Update LEDGER: `@ 6c2bc81a` |
| D100 | `[P3-async-when-touched] 🔵 P3-defer` | `b91a4408` | `MemoryFileOut` — `embedding_model_id` + `embedding_dim` surfaced in write() | Update LEDGER: `@ b91a4408` |
| D105 | `[P3-async-when-touched] 🟡 P1-defer` | `b861a7a0` | `HookPoint::ContextDegraded` — deprecation warning on old alias | Update LEDGER: `@ b861a7a0` |
| D107 | `[P3-async-when-touched] 🔵 P3-defer` | `8d4d628c` | Stop hook — shared jq guards extracted to `_lib/json_guards.sh` | Update LEDGER: `@ 8d4d628c` |
| D108 | `[P2-next-milestone] 🟡 P1-defer` | `6400ed8c` | Hook scripts — bats + shellcheck CI gate wired into `make verify` | Update LEDGER: `@ 6400ed8c` |

### Phase 8.6 (Eval / Cross-cutting Fixes)

| D-ID | LEDGER Status | Commit | Description | Action |
|------|--------------|--------|-------------|--------|
| D56 | `[P3-async-when-touched] 📦 long-term` | `93ef61b8` | `verify-v2-mvp.sh` — SQLite-only wipe scope fixed (EVAL-06) | Update LEDGER: `@ 93ef61b8` |
| D126 | `[P3-async-when-touched] 🔵 P3-defer` | `93ef61b8` | S4.T3 — `.venv` missing pre-flight WARNING added (EVAL-01) | Update LEDGER: `@ 93ef61b8` |
| D127 | `[P3-async-when-touched] 🔵 P3-defer` | `93ef61b8` | S4.T3 — `data/verify-v2-phase2-skill-registry/` cleanup (EVAL-02) | Update LEDGER: `@ 93ef61b8` |
| D128 | `[P3-async-when-touched] 🔵 P3-defer` | `2861b1be` | S4.T3 — `@assertion` decorator prints NOTE before PASS (EVAL-03) | Update LEDGER: `@ 2861b1be` |
| D129 | `[P3-async-when-touched] 🔵 P3-defer` | `93ef61b8` | S4.T3 — `verify-v2-phase2.sh` cleanup trap port guard (EVAL-04) | Update LEDGER: `@ 93ef61b8` |

### Other Historical Closures (main row not updated)

| D-ID | LEDGER Status | Commit | Description | Action |
|------|--------------|--------|-------------|--------|
| D78 | `[P3-async-when-touched] 🟡 P1-active` | `4633c0bc` | Event payload embedding vector index (Phase 3 S2.T2) | Update LEDGER: `@ 4633c0bc` |
| D117 | N/A (D50 renamed) | `688bf4db` | PromptExecutor trait + env gate (Phase 3 S2.T5) | Update LEDGER main row for D50→D117 rename |
| D152 | `🧹 tech-debt` (stats say ✅ CLOSED) | `86295053` | grpcio-tools proto3 enum stub post-processing (Phase 4a T7) | Update LEDGER: `@ 86295053` |

---

## Section C: GENUINELY ACTIVE — Unresolved Items

These D-rows show active status in the LEDGER and have NO corresponding fix commit in git log. They are the candidate pool for Phase 9.1+.

| D-ID | LEDGER Tag | Description | Module | Rationale for Deferred |
|------|-----------|-------------|--------|------------------------|
| D21 | `📦 long-term` | L3 `managed_settings_versions` / `telemetry_events` 无保留策略 | L3 | Operational TTL policy — needs ops-side rollout |
| D32 | `📦 long-term` | L4 无并发 `create_session` 压力测试 | L4 | Ops-side load test, deferred → Phase 4+ |
| D36 | `📦 long-term` | L4 event window 无 cursor (>10k 事件触发) | L4 | Scale concern, deferred → Phase 3+ |
| D41 | `🔴 phase3-gated` | eaasp-cli-v2 `session list` 无后端 endpoint | cli-v2 | Multi-tenant sync requirement |
| D73 | `📦 long-term` | Event Room 推迟 | Event Engine | Long-term Phase 4 item |
| D75 | `📦 long-term` | EventStreamBackend 切换到 NATS JetStream | Event Engine | Phase 6 multi-node concern |
| D76 | `📦 long-term` | subscribe() polling → push-based | Event Engine | Phase 6 scale concern |
| D77 | `📦 long-term` | TopologyAwareClusterer (L2 Ontology Service 输入) | Event Engine | Phase 5 concern |
| D79 | `📦 long-term` | Pipeline 多 worker 并行处理 | Event Engine | Phase 6 scale concern |
| D80 | `📦 long-term` | Clusterer 因果图聚类 (parent_event_id → DAG) | Event Engine | Phase 4 concern |
| D118 | `🔵 P3-defer` | SkillDir materialization 在 session 结束无 cleanup | hooks | S4 cleanup sweep |
| D119 | `🔵 P3-defer` | Envelope `schema_version` 字段未强制 | hooks | Phase 3 first breaking change trigger |
| D121 | `🔵 P3-defer` | `register_session_stop_hooks` 额外调用累加而非替换 | hooks | Dedupe or warn-on-duplicate semantics |
| D122 | `🔵 P3-defer` | Python envelope 包含 top-level `hook_id` 字段，Rust 未含 | hooks | D120 already unified cross-runtime envelope |
| D123 | `🔵 P3-defer` | `scoped_hook_wiring_integration.rs` 测试用 `set_var` + Mutex | hooks | RAII env guard |
| D24 | `🧹 tech-debt` | IDE Pyright missing-import 假阳性 | cross-cutting | DevEx — pyrightconfig.json sweep |
| D10 | `🧹 tech-debt` | MCP REST facade → 真 rmcp ServerHandler 统一 (L2/L4 remaining) | L2+L3+L4 | Partially done: L3 has dual-transport (Phase 8.0); L2+L4 still need migration |

**Count: 17 genuinely ACTIVE items** (excluding D10 which has L3 done but L2/L4 pending).

### ACTIVE by Tier

| Tier | Count | D-IDs |
|------|-------|-------|
| 📦 long-term (Phase 4–6) | 8 | D21, D32, D36, D73, D75, D76, D77, D79, D80 |
| 🔴 phase3-gated | 1 | D41 |
| 🔵 P3-defer (edge/quality) | 5 | D118, D119, D121, D122, D123 |
| 🧹 tech-debt (DevEx) | 2 | D10 (L2/L4 remaining), D24 |

### Recommended Phase 9.1 Scoping

| Batch | D-IDs | Rationale |
|-------|-------|-----------|
| **Phase 9.1 Quick Wins** | D24, D121, D122, D123 | Hooks/Pyright polish — low effort, immediate DevEx ROI |
| **Phase 9.2 MCP Unification** | D10 (L2/L4) | Complete L2+L4 rmcp ServerHandler migration |
| **Phase 9.3 Session Lifecycle** | D118, D119 | Cleanup + schema_version enforcement |
| **Phase 10+ Long-term** | D21, D32, D36, D41, D73, D75, D76, D77, D79, D80 | Long-term roadmap items — do not schedule before Phase 4 |

---

## Section D: Phase 9.0 Action Items

### D-01: Normalize Historical Notations (Section A)

For all 17 rows in Section A, edit the status cell in `DEFERRED_LEDGER.md` to use the standardized format. These rows already have implementation evidence in their "证据 / 去向" column — they just need the notation format updated. No re-verification needed.

### D-02: Update Newly Closed Rows (Section B)

For all 30 rows in Section B, edit the status cell in `DEFERRED_LEDGER.md` to `✅ CLOSED 2026-06-XX Phase 8.X Plan YY @ <commit>`. Append close-out trace to the status change log. This is the bulk of Phase 9.0 work.

### D-03: File GENUINELY ACTIVE Items into v3.5 INBOX

Create or update `.planning/v3.5-INBOX.md` with the 17 genuinely ACTIVE items from Section C, grouped by module/phase batch. Feed into ROADMAP.md for Phase 9.1+ scheduling.

### D-04: Verify LEDGER Consistency

After D-01 and D-02 edits:
1. Run `grep -c '✅' docs/design/EAASP/DEFERRED_LEDGER.md` to count closed rows
2. Verify all standardized rows match `✅ CLOSED \d{4}-\d{2}-\d{2} Phase .* @ \w+`
3. Update the stats summary table (lines 387-408) to reflect new closure counts

---

## Appendix: Audit Methodology

1. **Read** `DEFERRED_LEDGER.md` in full — extracted all D-IDs from `## D 编号详细登记` sections (D1–D155)
2. **Classified** each row by status cell content: standardized CLOSED vs non-standard closed vs ACTIVE
3. **Cross-referenced** with `git log --all --grep 'D<ID>'` to confirm commit evidence
4. **Checked Phase plans** (8.0–8.6) for D-IDs not explicitly tagged in commit messages but documented in plan commit bodies
5. **Verified** the stats summary table in the LEDGER against main rows for consistency gaps

**Key discrepancy**: The stats table at lines 392–408 claims certain D-IDs as `✅ closed` (e.g., D78, D117) while the main row in `## D 编号详细登记` still shows an active status tag. This audit normalizes both.

**Excluded from audit**: 
- NEW-* rows (separate namespace, all verified CLOSED)
- D27, D40 (superseded)
- D66, D88 (frozen/hermes)
- D67–72, D81–82 (unallocated)
- Legacy-Octo D-IDs (Appendix A only)
- All rows that already have standardized `✅ CLOSED YYYY-MM-DD Phase X @ commit` format
