# Architecture Research — v3.4 New Features Integration

**Domain:** Agent Runtime Stack (EAASP + Grid)
**Researched:** 2026-06-07
**Confidence:** HIGH

## System Overview — Current Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        L4 Orchestration                          │
│  tools/eaasp-l4-orchestration/  (Python FastAPI)                │
│  ┌──────────────┐ ┌───────────────┐ ┌───────────────────────┐   │
│  │SessionOrches-│ │context_       │ │event_stream / engine / │   │
│  │trator        │ │assembly.py    │ │interceptor            │   │
│  └──┬────┬──┬───┘ └───────────────┘ └───────────────────────┘   │
│     │    │  │                                                    │
│     │    │  └─────── L3Client (httpx) ──────────────┐            │
│     │    │                                          │            │
│     │    └─────── L2Client + SkillRegistryClient ──┐│            │
│     │                      (httpx)                 ││            │
│     │                                              ││            │
│     └─────── L1RuntimeClient (gRPC) ───────┐       ││            │
│                                            │       ││            │
├────────────────────────────────────────────┼───────┼┼────────────┤
│                      L3 Governance         │       ││            │
│  tools/eaasp-l3-governance/  (Python FastAPI)      ││            │
│  ┌──────────┐ ┌──────────┐ ┌────────┐      │       ││            │
│  │api.py    │ │policy_   │ │audit.py│      │       ││            │
│  │validate  │ │engine.py │ │        │      │       ││            │
│  │session() │ │          │ │        │      │       ││            │
│  └──────────┘ └──────────┘ └────────┘      │       ││            │
│                                    ▲       │       ││            │
├────────────────────────────────────┼───────┼───────┼┼────────────┤
│                      L2 Memory Engine       │       ││            │
│  tools/eaasp-l2-memory-engine/  (Python FastAPI)    ││            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐    │       ││            │
│  │Hybrid    │ │MCP       │ │Event     │    │       ││            │
│  │Index     │ │Dispatcher│ │Index     │    │       ││            │
│  │(FTS+HNSW)│ │          │ │(HNSW)    │    │       ││            │
│  └──────────┘ └──────────┘ └──────────┘    │       ││            │
│                                            │       ││            │
├────────────────────────────────────────────┼───────┼┼────────────┤
│                      L1 Runtime             │       ││            │
│  crates/grid-runtime/  (Rust gRPC)         │       ││            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐   │       ││            │
│  │grid-     │ │harness.rs│ │pre_      │    │       ││            │
│  │engine    │ │          │ │compact_  │    │       ││            │
│  │(agent    │ │          │ │emitter.rs│    │       ││            │
│  │loop)     │ │          │ │          │    │       ││            │
│  └──────────┘ └──────────┘ └──────────┘   │       ││            │
│                                            │       ││            │
├────────────────────────────────────────────┼───────┼┼────────────┤
│                      L0 Protocol            │       ││            │
│  proto/eaasp/runtime/v2/                   │       ││            │
│  runtime.proto (16-method)  hook.proto      │       ││            │
│  common.proto (SessionPayload P1-P5)        │       ││            │
│                                            │       ││            │
│  ┌──────────┐ ┌──────────┐                 │       ││            │
│  │grid-hook-│ │hooks/    │                 │       ││            │
│  │bridge    │ │scripts/  │  (bash hooks)   │       ││            │
│  └──────────┘ └──────────┘                 │       ││            │
└────────────────────────────────────────────┴───────┴┴────────────┘
```

### Current Data Flow (create_session → send_message)

```
User/CLI
    │ intent_text, skill_id, runtime_pref, user_id
    ▼
L4 SessionOrchestrator.create_session()
    │
    ├─[1]──► L2Client.search_memory(query=intent_text)  → memory_refs (P3)
    │          POST http://L2:18085/api/v1/memory/search
    │
    ├─[2]──► L3Client.validate_session(session_id, skill_id, ...)  → policy_context (P1)
    │          POST http://L3:18083/v1/sessions/{id}/validate
    │
    ├─[2b]─► SkillRegistryClient.read_skill(skill_id)  → skill_instructions (P4)
    │          POST http://skill-registry:18081/tools/skill_read/invoke
    │
    ├─[3]──► context_assembly.build_session_payload(P1..P5)
    │          ┌─ policy_context (from L3 validate)
    │          ├─ event_context (P2, currently empty)
    │          ├─ memory_refs (from L2 search)
    │          ├─ skill_instructions (from skill registry)
    │          └─ user_preferences (P5, from env hints)
    │
    ├─[4]──► DB INSERT sessions + SESSION_CREATED event (BEGIN IMMEDIATE)
    │
    ├─[5]──► L1RuntimeClient.initialize(payload)  → gRPC → grid-runtime
    │          gRPC: grid-runtime:50051 RuntimeService.Initialize()
    │
    ├─[6]──► L1RuntimeClient.connect_mcp()  → MCP servers from skill deps
    │
    ▼
L4 SessionOrchestrator.send_message(session_id, content)
    │
    ├─[1]──► DB INSERT USER_MESSAGE event
    │
    ├─[2]──► L1RuntimeClient.send()  → gRPC server-stream → grid-runtime
    │          gRPC: RuntimeService.Send() → stream of SendResponse chunks
    │
    └─[3]──► DB INSERT RESPONSE_CHUNK events (coalesced)
               └─ EventInterceptor.extract_from_chunk() → EventEngine.ingest()
```

---

## Integration Points for New Features

### 1. L4 New Integration Points

#### 1.1 D34 — Intent → skill_id NLU (P2, NEW component)

**What:** Parses free-form `intent_text` (natural language) into a resolved `skill_id` before the three-way handshake.

**Integration point:** Inserts between the `create_session()` entry and Step 1 (L2 search). Currently `skill_id` comes from the caller; after D34, the orchestrator can accept `intent_text` and resolve `skill_id` automatically.

**Data flow change:**
```
BEFORE: create_session(intent_text, skill_id, ...)
               │             │
               └─ P3 search  └─ P4 skill fetch

AFTER:  create_session(intent_text, skill_id=OPTIONAL, ...)
               │
               ├─[0]──► IntentParser.resolve(intent_text) → skill_id
               │          (NEW module: tools/eaasp-l4-orchestration/.../intent_parser.py)
               │
               ├─[1]──► L2Client.search_memory(query=intent_text)  (unchanged)
               └─[2b]─► SkillRegistryClient.read_skill(skill_id)    (unchanged)
```

**Component type:** NEW (L4-internal)
**Affected existing files:**
- `session_orchestrator.py` — add `intent_parser` parameter + resolution step
- `handshake.py` — no changes
- `api.py` (L4) — may accept `skill_id` as optional if NLU resolves it

**Dependencies:** None (L4-internal). Can be developed independently.

---

#### 1.2 D38 — L2Client pass user_id (P2, MODIFIED)

**What:** Propagate `user_id` from `create_session()` down to the L2 memory search call for tenant isolation.

**Integration point:** L4→L2 REST call chain. `L2Client.search_memory()` currently doesn't accept `user_id`; `create_session()` has `user_id` but doesn't pass it to L2.

**Data flow change:**
```
create_session(user_id="u123", ...)
    │
    ├─[1]──► L2Client.search_memory(query=..., user_id="u123")  ← NEW param
    │          POST http://L2:18085/api/v1/memory/search
    │          Body: {"query": ..., "user_id": "u123"}           ← NEW field
```

**Affected files:**
- `tools/eaasp-l4-orchestration/.../handshake.py` — L2Client.search_memory() add `user_id` param
- `tools/eaasp-l4-orchestration/.../session_orchestrator.py:116` — pass `user_id` to search_memory
- `tools/eaasp-l2-memory-engine/.../api.py:75` — L2 server must accept `user_id` in body (may need schema update)

**Dependencies:** L2 must support `user_id` filtering in its search endpoint. If L2 doesn't already, this becomes a cross-component change (L4 + L2).

---

#### 1.3 D41 — session list endpoint (P2, MODIFIED)

**What:** Expose `GET /v1/sessions` REST endpoint + wire cli-v2 `session list` to it.

**Integration point:** L4 FastAPI routing + cli-v2 HTTP client.

**Current state:** `SessionOrchestrator.list_sessions()` is **already implemented** (lines 671-719 of `session_orchestrator.py`). Only the REST handler is missing.

**Affected files:**
- `tools/eaasp-l4-orchestration/.../api.py` — add `@app.get("/v1/sessions")` handler
- `tools/eaasp-cli-v2/.../cmd_session.py` — wire `session list` CLI command to call the endpoint

**Dependencies:** None (L4-internal). `list_sessions()` already queries the L4 `sessions` table.

---

### 2. Hooks Integration Points

#### 2.1 D48 — ScopedHookBody matcher/tool_filter (P3, SCHEMA CHANGE)

**What:** Add `matcher` and `tool_filter` fields to `ScopedHook` proto message to control which hooks fire for which tools.

**Integration point:** Proto schema → Python codegen → L4 skill processing → L1 hook execution.

**Data flow:**
```
Skill SKILL.md frontmatter
    │ scoped_hooks: [{ type: "command", command: "...", matcher: {tool_name: "bash"}}]
    ▼
L4 SessionOrchestrator.create_session() Step 2b
    │ resolves scoped hooks from SkillRegistryClient.read_skill()
    │ ── matcher/tool_filter fields now preserved ──
    ▼
context_assembly.build_session_payload()
    │ skill_instructions.frontmatter_hooks include matcher/tool_filter
    ▼
L1RuntimeClient.initialize(payload) → gRPC → grid-runtime
    │ proto ScopedHook carries matcher/tool_filter
    ▼
grid-engine harness
    │ reads matcher on PreToolUse/PostToolUse; skips hook if tool_name doesn't match
```

**Affected files (cascade):**
| Layer | File | Change |
|-------|------|--------|
| L0 Proto | `proto/eaasp/runtime/v2/common.proto:79-85` | Add `matcher` + `tool_filter` to `ScopedHook` message |
| L0 Proto | `proto/eaasp/runtime/v2/common.proto` | Add `HookMatcher` message: `{tool_name: string, tool_filter: repeated string}` |
| L4 Python | `l1_client.py:_dict_to_session_payload()` | Map `matcher` field from dict → proto |
| L4 Python | `session_orchestrator.py:156-169` | Preserve `matcher` during scoped hook flattening |
| L1 Rust | `grid-engine/src/agent/harness.rs` | Read `matcher` on Pre/PostToolUse; compare `tool_name` |
| L1 Rust | `grid-types` | Update `ScopedHook` type (or codegen) |

**Dependency chain:** Proto change FIRST → regenerate codegen → update L4 + L1 consumers in parallel.

---

#### 2.2 D50 — Prompt executor loop (P3, NEW component)

**What:** `ScopedHookBody::Prompt` represents a hook that sends a prompt to an LLM and acts on the yes/no response. Currently unimplemented — the `prompt` field exists in the schema but the executor loop doesn't run it.

**Integration point:** This is an **L1** implementation (grid-engine harness or grid-runtime hook executor). It's a new capability in the hook execution pipeline.

**Component type:** NEW (grid-engine or grid-runtime internal)

**Data flow (planned):**
```
PreToolUse/PostToolUse/Stop event fires
    │
    ▼
grid-engine harness / hook executor
    │ checks scoped hooks for matching event type
    │ finds ScopedHookBody with type="prompt"
    ▼
NEW: PromptExecutorLoop
    │ 1. Construct prompt from hook's prompt template + event context
    │ 2. Call LLM provider (lightweight, fast model)
    │ 3. Parse yes/no decision
    │ 4. Return allow/deny decision
    ▼
Continue with allow/deny/mutate decision
```

**Dependencies:** grid-engine provider layer (for LLM call). Probably a lightweight provider call (not a full agent loop). Could be a separate gRPC call or in-process.

---

#### 2.3 D108 — Hook script regression tests (P2, NEW test infra)

**What:** Automated regression tests for bash hook scripts using bats/shellcheck CI integration.

**Integration point:** CI pipeline + `scripts/test_hook_scripts.sh` enhancement.

**Affected files:**
- `scripts/test_hook_scripts.sh` — extend or create bats test suite
- `examples/skills/*/hooks/*` — add bats test cases per skill hook

**Dependencies:** None (test infrastructure only).

---

#### 2.4 D107 — Stop hook jq fragment (P3, internal)

**What:** Extract the shared three-way empty-string check (`has(x) and (x != null) and (x != "")`) from individual hook scripts into a shared `jq` helper.

**Integration point:** `scripts/` internal. No cross-module impact.

---

### 3. L2 Integration Points (P3 sweep)

Most L2 P3 items are **L2-internal** with no cross-module integration impact:

| D-item | Integration impact |
|--------|-------------------|
| D79 — Pipeline multi-worker | L2-internal. Parallel event processing pipeline. |
| D99 — MCP dispatcher typed errors | L2-internal. Affects MCP tool callers (L1, L4) only via error response shape. |
| D65 — MCP connection pool | L2-internal. L4 MCP resolver consumes L2-enriched config; no contract change. |
| D80 — Causal graph clusterer | L2-internal. Consumes `parent_event_id` from event stream. |
| D78 — Vector indexing | L2-internal. The `/api/v1/events/ingest` endpoint already exists; D78 enhances the indexer. |
| D75 — EventStream NATS | L2 backend change. Affects L4 only if L4 directly reads L2's event stream (currently it doesn't). |
| D76 — subscribe push-based | L2-internal. |
| D77 — TopologyAwareClusterer | L2-internal. |
| D92–D97, D100, D101 | L2-internal fixes. |

**One L2→L4 integration note:** D65 (MCP connection pool) may surface richer MCP config through `McpResolver.resolve()` → `mcp_deps` → L4 `session_orchestrator.py:293-328`. No contract change expected.

---

### 4. L3 Integration Points (P3 sweep)

Most L3 P3 items are **L3-internal** with one cross-cutting exception:

| D-item | Integration impact |
|--------|-------------------|
| D20 — `_sanitize_errors` reuse | **Cross-module.** Extract from L3 `api.py:268-286` into a shared `eaasp_common` package. Affects L2 (no sanitize_errors) and L3 (already has it). This is a refactor with import-path changes but no behavior change. |
| D10 — rmcp ServerHandler upgrade | L3-internal. Impacts only L3's MCP tool facade. |
| D16 — deploy created_at fix | L3-internal. |
| D19 — switch_mode validation | L3-internal. |
| D21 — retention | L3-internal. |
| D25 — concurrency E2E | L3 tests only. |

**D20 integration detail:**
```
BEFORE:  tools/eaasp-l3-governance/.../api.py → defines _sanitize_errors()
         tools/eaasp-l2-memory-engine/.../api.py → does NOT have _sanitize_errors()

AFTER:   tools/eaasp-common/ → _sanitize_errors()  (NEW shared module)
         tools/eaasp-l3-governance/.../api.py → import from eaasp_common
         tools/eaasp-l2-memory-engine/.../api.py → import from eaasp_common
         tools/eaasp-l4-orchestration/.../api.py → import from eaasp_common (future)
```

---

### 5. grid-engine + grid-server Integration Points

All **grid-engine internal** — no cross-module integration impact:

| D-item | Integration impact |
|--------|-------------------|
| D105 — HookPoint alias | grid-engine internal. `runtime.rs:1899` string-key dispatcher. |
| D106 — MAX_TURNS hardcode | grid-engine internal. Config promotion (`AgentLoopConfig.task_budget_override`). |
| D130 — cancel token | grid-engine internal. Token propagation refactor. |

**D90 — WS ToolResult schema** (grid-server):
- Affects: `crates/grid-server/src/ws.rs` (WebSocket message struct)
- Integration: Grid-server's WS schema → frontend `web/` (dormant). Since frontend is dormant per ADR-V2-024, this is a **schema-only fix** with no consumer impact. Safe to do alone.

---

### 6. Contract Integration Points

#### 6.1 D74 — EmitEvent gRPC reverse channel (P3, NEW proto direction)

**What:** Currently L4 calls L1 (L4 is gRPC client, L1 is server). D74 adds the reverse: L1 calls L4's EmitEvent endpoint (L1 becomes gRPC client, L4 becomes gRPC server). This enables L1 to push events (thinking, tool usage, pre-compact) to L4 in real-time.

**Integration point:** A NEW gRPC service at L4 + new client at L1.

**Architecture change:**
```
BEFORE (unidirectional):
    L4 ──gRPC──► L1  (Initialize, Send, ConnectMCP, Terminate)

AFTER (bidirectional):
    L4 ──gRPC──► L1  (Initialize, Send, ConnectMCP, Terminate)
    L1 ──gRPC──► L4  (EmitEvent)  ← NEW direction
```

**Affected files:**
| Layer | File | Change |
|-------|------|--------|
| L0 Proto | `proto/eaasp/runtime/v2/runtime.proto:76` | `EmitEvent` RPC already defined! Needs `service EventSink { rpc EmitEvent(...) }` at L4 side |
| L0 Proto | `proto/eaasp/runtime/v2/runtime.proto:263-269` | `EventStreamEntry` message already defined |
| L1 Rust | `crates/grid-runtime/src/service.rs` | Already has EmitEvent handler — needs gRPC client addition |
| L1 Rust | `crates/grid-runtime/src/pre_compact_emitter.rs` | Already file-writes events; add gRPC stream path |
| L4 Python | `tools/eaasp-l4-orchestration/.../event_engine.py` | Add gRPC server for `EventSink` |
| L4 Python | `tools/eaasp-l4-orchestration/.../main.py` | Start gRPC server alongside FastAPI |

**Dependency chain:** Add `EventSink` service to proto FIRST → regenerate Python codegen → implement L4 gRPC server → add L1 gRPC client → wire L1 emitter to call it.

---

#### 6.2 D139 — 双 Terminate semantic (P3, contract clarification)

**What:** Clarify whether double-terminate is idempotent (NO-OP) or errors (FAILED_PRECONDITION).

**Integration point:** Contract decision → proto comments/doc → grid-runtime behavior → certifier assertions.

**Affected files:**
- `proto/eaasp/runtime/v2/runtime.proto` — document semantic on `Terminate` RPC
- `crates/grid-runtime/src/service.rs` — adjust Terminate behavior
- `tools/eaasp-certifier/` — update certification assertions

**Dependencies:** None (contract clarification only).

---

### 7. Eval + Cross-cutting

All items are **standalone**:
- D56, D126-D129: verify scripts internal
- D24: Pyright config
- D73: Event Room (long-term Phase 4, may skip in v3.4)

---

## Component Summary: New vs Modified

| Component | New / Modified | Phase scope |
|-----------|---------------|-------------|
| **IntentParser (L4)** | **NEW** | 8.0 L4 Foundation (D34) |
| **PromptExecutorLoop (grid-engine)** | **NEW** | 8.4 Hooks P3 (D50) |
| **EventSink gRPC server (L4)** | **NEW** | 8.1 Contract (D74) |
| **EmitEvent gRPC client (L1)*** | **NEW** | 8.1 Contract (D74) |
| **eaasp_common package** | **NEW** | 8.0 Foundation (D20) |
| **bats test suite (scripts/)** | **NEW** | 8.3 Hooks (D108) |
| SessionOrchestrator (L4) | Modified | D34, D38, D41 |
| L2Client (L4) | Modified | D38 (add user_id param) |
| context_assembly.py (L4) | Modified | D37, D39 |
| L4 api.py | Modified | D28, D29, D31, D41 |
| proto/.../common.proto | Modified | D48 (ScopedHook matcher) |
| proto/.../runtime.proto | Modified | D74 (EventSink service), D139 |
| grid-engine harness.rs | Modified | D48, D105, D106, D130 |
| grid-server ws.rs | Modified | D90 |
| L2 api.py | Modified | D38 (accept user_id) |
| L3 api.py | Modified | D20 (import path change) |
| L2 internal (index, mcp, pipeline) | Modified | D65, D75-D80, D99 |
| L3 internal (policy, deploy) | Modified | D10, D16, D19, D21 |
| eval/verify scripts | Modified | D56, D126-D129 |
| cli-v2 | Modified | D41, D42-D45 |

## Data Flow Changes Summary

### New data flows introduced by v3.4:

1. **Intent resolution flow** (D34):
   ```
   intent_text → IntentParser → skill_id → existing handshake
   ```

2. **User-scoped memory search** (D38):
   ```
   user_id ──added to──► L2Client.search_memory() ──► L2 /api/v1/memory/search
   ```

3. **Bidirectional gRPC** (D74):
   ```
   L1 grid-runtime ──EmitEvent gRPC──► L4 EventSink server
        ↑ (new direction, currently file-based only)
   ```

4. **Hook matcher filtering** (D48):
   ```
   ScopedHook.matcher ──added to──► proto ScopedHook ──► grid-engine harness
       {tool_name: "bash"}                     │ skips hook if tool doesn't match
   ```

5. **Prompt hook execution** (D50):
   ```
   ScopedHook(type="prompt") → PromptExecutorLoop → LLM call → allow/deny decision
   ```

---

## Suggested Build Order (Phase 8.0+)

The carry-forward phases (7.0, 7.1, 7.2) execute first as defined in v3.3. New v3.4 phases follow this order:

### Phase 8.0 — L3 Leftovers + Cross-cutting Foundation (6 rows)

**Rationale:** D20 creates the `eaasp_common` shared package that L2 will later consume. D10 is a foundational MCP upgrade. These should land early so L2 P3 can consume them later.

| D-item | Description | Type |
|--------|-------------|------|
| D20 | Extract `_sanitize_errors` → `eaasp_common` | Cross-module refactor (L2+L3) |
| D10 | rmcp ServerHandler upgrade | L3-internal |
| D16 | deploy `created_at` fix | L3-internal |
| D19 | switch_mode validation | L3-internal |
| D21 | retention policy | L3-internal |
| D25 | concurrency E2E test | L3 tests only |

**Build order rationale:** L3-only phase with one cross-cutting dependency (D20 benefits L2 later). No external dependencies. Safe to run in parallel with Phase 8.1 if using workstreams.

---

### Phase 8.1 — Contract + grid-engine Foundation (5 rows)

**Rationale:** D74 introduces the bidirectional gRPC pattern that future L4 work may consume. Contract changes (D74, D139) should stabilize before L4 phase so L4's new gRPC server can be built against a frozen proto.

| D-item | Description | Type |
|--------|-------------|------|
| D74 | EmitEvent gRPC reverse channel | Proto + L1 + L4 (bidirectional) |
| D139 | 双 Terminate semantic | Contract clarification |
| D105 | HookPoint alias | grid-engine internal |
| D106 | MAX_TURNS hardcode → config | grid-engine internal |
| D130 | cancel token consolidation | grid-engine internal |

**Build order rationale:** D74 MUST precede L4 P3 work that could use EmitEvent streaming. D74 creates the gRPC server pattern at L4 that D36 (event window cursor) might use. grid-engine items (D105-D130) have no cross-module deps, can run in parallel with proto work.

**⚠️ Proto change gate:** D74 adds a new `EventSink` service to proto. Per project constraints, proto changes require ADR review. This phase should start with an ADR.

---

### Phase 8.2 — L4 Foundation (7 rows, 3 P2 + 4 P3)

**Rationale:** All L4 P2 items land here. D34 (NLU) is the largest new component in v3.4. D38 crosses L4→L2 boundary and needs L2 to accept `user_id` — coordinate with L2 team.

| D-item | Description | Type | Priority |
|--------|-------------|------|----------|
| D34 | Intent → skill NLU | NEW (L4) | P2 |
| D38 | L2Client pass user_id | Modified (L4+L2) | P2 |
| D41 | Session list endpoint | Modified (L4) | P2 |
| D28 | Global exception handler | Modified (L4) | P3 |
| D29 | Path param validation | Modified (L4) | P3 |
| D31 | loguru init | Modified (L4) | P3 |
| D39 | policy_version hash | Modified (L4) | P3 |

**Build order rationale:** D34→D38→D41 ordered by complexity. D34 is self-contained (new module), D38 needs L2 coordination, D41 is trivial endpoint wiring. P3 items (D28/D29/D31) can be done in parallel with D34 since they touch different L4 files. D39 depends on L3's `managed_settings_version` response shape — coordinate with Phase 8.0 if L3 changes that.

**⚠️ D38 L2 dependency:** If L2's `/api/v1/memory/search` doesn't currently accept `user_id`, this becomes a cross-phase dependency: the L2 search endpoint must be updated first. Check L2 `api.py:75` — currently the `SearchRequest` model has `query`, `top_k`, `scope`, `category` but no `user_id`. This needs L2 schema change.

---

### Phase 8.3 — L4 P3 Hardening (6 rows)

**Rationale:** Deeper L4 fixes that build on the foundation from Phase 8.2.

| D-item | Description | Type |
|--------|-------------|------|
| D36 | Event window cursor | Modified (L4 event_stream) |
| D37 | allow_trim_p4 hardcode → configurable | Modified (L4 context_assembly) |
| D33 | SESSION_CREATED payload reference-mode | Modified (L4 event store) |
| D42 | cli-v2 test_client 5xx coverage | cli-v2 tests |
| D43 | cli-v2 unused dep removal | cli-v2 cleanup |
| D44 | cli-v2 cmd_session.show limit flag | cli-v2 enhancement |
| D45 | cli-v2 response-shape guard | cli-v2 hardening |

**Build order rationale:** D36 and D37 are independent. D37 (trim_p4) relates to D3 in 7.0 carry-forward — coordinate if D3 changes trim behavior. cli-v2 items (D42-D45) are independent from L4 work.

---

### Phase 8.4 — L2 P3 Sweep (8-10 rows)

**Rationale:** L2 internal improvements. Can run after L2 connection-pool foundation from carry-forward Phase 7.2 is done.

| D-item | Description | Type |
|--------|-------------|------|
| D79 | Pipeline multi-worker | L2-internal |
| D99 | MCP dispatcher typed errors | L2-internal |
| D65 | MCP connection pool | L2-internal |
| D78 | Vector indexing (event payload) | L2-internal |
| D80 | Causal graph clusterer | L2-internal |
| D75 | EventStream NATS | L2 backend |
| D76 | subscribe push-based | L2-internal |
| D95 | FTS semantic_score backfill | L2-internal |
| D96 | memory_id `:v` parsing fix | L2-internal |
| D92 | MockEmbedding seed collision | L2-internal |

**Build order rationale:** Pick the most impactful items first. D79 (pipeline)=highest impact, D65 (connection pool)=second. D75 (NATS) is the largest backend change — defer within phase. D99 affects downstream error handling — do early to let consumers adapt.

---

### Phase 8.5 — Hooks P2 + P3 (4 rows)

**Rationale:** Hook changes are mostly self-contained. D48 (matcher) has a proto change cascade — schedule after Phase 8.1's proto stabilization.

| D-item | Description | Type | Priority |
|--------|-------------|------|----------|
| D108 | Hook script regression tests | NEW (tests) | P2 |
| D48 | ScopedHookBody matcher/tool_filter | Schema change | P3 |
| D50 | Prompt executor loop | NEW (grid-engine) | P3 |
| D107 | Stop hook jq fragment | scripts internal | P3 |

**Build order rationale:** D108 (bats/shellcheck) first — validates existing hooks before D48/D50 change hook behavior. D48 MUST follow Phase 8.1 (proto stable) because it modifies common.proto. D50 is the most complex — new LLM-calling component in grid-engine.

---

### Phase 8.6 — Eval + Cleanup + grid-server (7 rows)

**Rationale:** Final polish phase. All items are standalone, no cross-module deps.

| D-item | Description | Type |
|--------|-------------|------|
| D56 | verify-v2-mvp.sh cleanup | eval script |
| D126 | .venv missing pre-flight WARNING | eval script |
| D127 | skill-registry dir cleanup | eval script |
| D128 | @assertion NOTE ordering | eval polish |
| D129 | cleanup trap port sweep guard | eval script |
| D90 | WS ToolResult schema tool_name | grid-server |
| D73 | Event Room | cross-cutting (may skip) |

**Build order rationale:** Grid-server D90 is minimal (schema field addition). Can run anywhere in the phase. D73 (Event Room) is a Phase 4 item — include only if time permits.

---

## Architectural Patterns for New Components

### Pattern 1: L4 IntentParser (D34)

**Pattern:** Strategy pattern with pluggable resolvers.
```python
# tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/intent_parser.py
class IntentParser:
    """Resolve intent_text → skill_id via pluggable strategies."""
    def __init__(self, resolver: IntentResolver):
        self._resolver = resolver  # NLU model, keyword matcher, or mock

    async def resolve(self, intent_text: str, user_id: str | None = None) -> str:
        return await self._resolver.resolve(intent_text, user_id)

# Usage in SessionOrchestrator
class SessionOrchestrator:
    def __init__(self, ..., intent_parser: IntentParser | None = None):
        self.intent_parser = intent_parser
```

**Why:** Allows MVP with keyword matching, later swap to NLU/embedding model without changing orchestrator.

### Pattern 2: L4 EventSink gRPC Server (D74)

**Pattern:** Mirror of L1's gRPC server pattern — aio grpc server alongside FastAPI.
```python
# tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/event_sink.py
class EventSinkServicer(event_sink_pb2_grpc.EventSinkServicer):
    async def EmitEvent(self, request, context):
        await self.event_engine.ingest(request)
        return common_pb2.Empty()
```

**Why:** Follows the existing L1 pattern. L4 main.py already manages FastAPI lifespan; add gRPC server in same lifespan.

### Pattern 3: PromptExecutorLoop (D50)

**Pattern:** Lightweight LLM call within hook pipeline — NOT a full agent loop.
```rust
// crates/grid-engine/src/hooks/prompt_executor.rs
pub struct PromptExecutorLoop {
    provider: Arc<dyn Provider>,
    model: String,
    max_tokens: u32,
}

impl PromptExecutorLoop {
    pub async fn execute(&self, prompt: &str, context: &HookContext) -> Result<Decision> {
        // 1. Format prompt with context
        // 2. Call provider.complete(prompt, max_tokens=small)
        // 3. Parse yes/no from response
        // 4. Return allow/deny
    }
}
```

**Why:** Uses existing `Provider` trait. Lightweight (single-turn, no tools, small token budget). Separate from agent loop to avoid circular deps.

---

## Cross-Phase Dependency Graph

```
Phase 7.0 (grid-engine carry-forward) ─────────────────────────────┐
    │ D102 (AgentLoopConfig YAML), D3/D57/D58/D103/D104            │
    │                                                               │
Phase 7.1 (contract carry-forward) ────────────────────────────┐    │
    │ D137 (multi-turn observability), D138 (deny-path mock),   │    │
    │ D5/D6/D55 (telemetry/schema)                              │    │
    │                                                           │    │
Phase 7.2 (L2 carry-forward) ─────────────────────────┐         │    │
    │ D12/D94/D91/D93/D98 (connection-pool + perf)    │         │    │
    │                                                 │         │    │
    ▼                                                 ▼         ▼    ▼
Phase 8.0  L3 + eaasp_common  ◄── independent, no upstream deps
    │ D20 (shared)→ benefits L2 later
    │
    ▼
Phase 8.1  Contract + grid-engine  ◄── depends on nothing; PRODUCES D74 proto
    │ D74 (EmitEvent proto change) ──► consumed by Phase 8.2+ L4
    │ D139 (Terminate semantic)  ──► consumed by Phase 8.6 eval
    │
    ▼
Phase 8.2  L4 Foundation  ◄── depends on D74 proto (8.1) for gRPC pattern
    │ D34 (NLU), D38 (user_id→L2), D41 (session list)
    │ D38 ──► depends on L2 api.py accepting user_id
    │
    ▼
Phase 8.3  L4 P3 Hardening  ◄── depends on 8.2 foundation
    │
    ▼
Phase 8.4  L2 P3 Sweep  ◄── depends on 7.2 carry-forward + 8.0 D20 shared helper
    │
    ▼
Phase 8.5  Hooks P2+P3  ◄── D48 depends on 8.1 proto stable
    │
    ▼
Phase 8.6  Eval + Cleanup  ◄── depends on everything preceding being done
```

### Parallelization Opportunities

- **Phases 8.0 + 8.1 can run in parallel** (L3-only vs contract, no shared files)
- **Phase 8.4 (L2) can partially overlap with 8.2 (L4)** if they touch different files
- **Phase 8.5 (hooks) can partially overlap with 8.4 (L2)** — no shared code

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Proto change without full cascade plan

**What goes wrong:** Adding `matcher` to `ScopedHook` proto without mapping out every consumer (Python codegen → L4 dict→proto helper → grid-engine type → harness dispatch).

**Prevention:** For D48 (matcher) and D74 (EventSink), write the full cascade list BEFORE touching proto.

### Anti-Pattern 2: Mixed-priority phase

**What goes wrong:** Putting P2 NLU (D34) alongside P3 L2 internals in the same phase — different risk profiles, different review intensity.

**Prevention:** Each phase above groups items by module AND priority tier. P2 items get their own focused phases.

### Anti-Pattern 3: L4→L2 cross-change without L2 readiness check

**What goes wrong:** Adding `user_id` to L4's call without verifying L2's search endpoint accepts it.

**Prevention:** For D38, verify L2 `SearchRequest` model BEFORE implementing L4 change. If L2 needs the field, implement L2 first or simultaneously.

### Anti-Pattern 4: Skipping the proto ADR gate

**What goes wrong:** D74 (new EventSink service) or D48 (ScopedHook field addition) bypassing ADR governance — F4 lint catches it later, wasting rework.

**Prevention:** Run `/adr:new --type contract` for any proto change before implementation.

---

## Scaling Considerations

| Scale Point | Concern | Relevant D-items |
|-------------|---------|-----------------|
| 1K sessions | L4 event stream polling limit (D125: 500/burst) | D36 (event window cursor), D125 |
| 10K sessions | L2 HybridIndex per-search rebuild (D98: closed in 7.2) | D98 (cached), D65 (MCP pool) |
| 100K sessions | Single L4 SQLite → contention | D73 (Event Room, Phase 4) |

v3.4 focuses on correctness and debt, not scale. Scale items (NATS D75, push-based D76, multi-worker D79) are P3 — implement correctly but without premature scale optimization.

---

## Sources

- **Project context:** `.planning/PROJECT.md` — milestone v3.4 scope, constraints, key decisions
- **Debt catalog:** `.planning/v3.3-INBOX.md` — full 85-row P2/P3 catalog across 8 modules
- **Deferred ledger:** `docs/design/EAASP/DEFERRED_LEDGER.md` — detailed D-item descriptions, resolution histories
- **Proto contracts:** `proto/eaasp/runtime/v2/{common, runtime, hook}.proto` — L0 contract definitions
- **L4 orchestrator:** `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/session_orchestrator.py` — 753 lines, the main L4 entry point
- **L4 clients:** `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/{handshake, l1_client, context_assembly}.py` — L4→L2/L3/L1 integration
- **L3 API:** `tools/eaasp-l3-governance/src/eaasp_l3_governance/api.py` — L3 endpoints + validate_session
- **L2 API:** `tools/eaasp-l2-memory-engine/src/eaasp_l2_memory_engine/api.py` — L2 endpoints + search/ingest
- **ADR-V2-024** — 双轴模型 (engine vs data/integration), grid-platform dormant rule
- **ADR-V2-028** — Strict-by-default config validation pattern (applies to D106 config promotion)

---

*Architecture research for: v3.4 Full INBOX Drain — New Feature Integration Points*
*Researched: 2026-06-07*
*Confidence: HIGH — all findings verified against current source code at `tools/eaasp-*/` and `proto/eaasp/runtime/v2/`*
