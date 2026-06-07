# Pitfalls Research

**Domain:** Brownfield agent-platform debt sweep (Grid/EAASP v3.4 INBOX drain)
**Researched:** 2026-06-07
**Confidence:** HIGH

## Critical Pitfalls

Mistakes that cause rewrites, broken contracts, or silent production failures.

---

### Pitfall 1: L4↔L2/L3 HTTP Contract Drift — Field Rename Rips All Integrations

**What goes wrong:**
L4's `L2Client.search_memory()` and `L3Client.validate_session()` make untyped HTTP calls to L2/L3. The response dict is consumed by field name (e.g., `data.get("hits", [])`). When a field name changes in L2 or L3, L4 swallows the error silently, returns `[]` or `{}`, and the three-way handshake appears to succeed — but with zero memory refs or zero hooks attached.

**Why it happens:**
- No shared schema package between L2↔L4 or L3↔L4. Each service owns its own response shape.
- httpx responses are parsed as `dict[str, Any]` without Pydantic validation in the client wrapper (seen in `handshake.py:85-89`).
- The `handshake.py` error taxonomy only catches transport errors (5xx, connection refused) — schema mismatches return 200 with wrong shape and get default-empty fallbacks.
- D34 (NLU) will add a NEW L4-initiated call path (intent → skill_id resolution). This new path has zero integration tests verifying L4's client-side parsing against real L2 response shapes.

**How to avoid:**
1. **Every new L4→L2/L3 call path MUST have a RESPX-mocked integration test** that asserts the exact parsed output from the real upstream response shape. The conftest already provides `respx` interception — extend it for D34/D38/D41.
2. **D38 (user_id propagation):** Before adding `user_id` to `L2Client.search_memory()`, add a respx test that asserts L2 receives the parameter. The existing `test_handshake.py` should be extended.
3. **D41 (session list):** The list endpoint must handle L2/L3 returning unknown extra fields without breakage — add Pydantic response models in the client layer, not bare dict access.
4. **ADR check:** Verify no ADR-V2-020 (Tool namespace) or ADR-V2-006 (Hook envelope) contract is violated by new field additions.

**Warning signs:**
- `data.get("hits", [])` → returns empty list but upstream returned data
- `resp.json()` → no type assertion before consumption
- New `L2Client` method added without companion `test_handshake.py` case

**Phase to address:**
Phase 8.0 (L4 orchestration P2) — D34/D38/D41 must ship with respx-mocked tests as part of acceptance criteria.

---

### Pitfall 2: NATS JetStream — Stateful Infrastructure Snuck Into a Stateless Python Service

**What goes wrong:**
D75 switches `EventStreamBackend` from SQLite polling to NATS JetStream. NATS introduces:
1. **External process dependency** — NATS server must be running before L4 starts (adds a new `make dev-eaasp` service).
2. **Persistent consumer state** — JetStream consumers track their own cursor in the NATS server. If a consumer is NOT created with `Durable` name, a service restart loses position and replays all events.
3. **Connection lifecycle** — The FastAPI lifespan currently creates `SqliteWalBackend` inside `create_app()`. NATS client needs `async def connect()` + graceful drain on shutdown. Missing drain → orphaned NATS subscriptions that continue receiving on old connections.
4. **Schema migration** — Existing events in SQLite need migration to JetStream (or co-exist). Deleting them breaks the `list_events` API for historical sessions.

**Why it happens:**
- SQLite is file-backed and zero-config — the current architecture conflates "database" with "infrastructure". NATS is a separate service requiring its own lifecycle management.
- The `eaasp-l4-orchestration/tests/` suite runs against SQLite. Adding NATS tests requires either a test NATS container OR a NATS-in-process mock. Neither exists today.
- `make dev-eaasp` currently starts 6 services (L2 memory + L2 MCP + L3 governance + L4 orchestrator + skill-registry + MCP orchestrator). Adding NATS as service #7 changes the `scripts/dev-eaasp.sh` orchestration script — which is bash and hard to test.

**How to avoid:**
1. **Abstract the backend behind `EventBackend` protocol** — the existing `event_backend.py` already defines an interface. Ensure `SqliteWalBackend` and `NatsJetStreamBackend` share the same interface, with an env-var switch (`EAASP_EVENT_BACKEND=nats`).
2. **Start with NATS as optional feature-flag (opt-in)** — default remains SQLite. Activate NATS via `EAASP_EVENT_BACKEND=nats` env var. This makes the feature merge-safe and testable without breaking all existing tests.
3. **Add a NATS integration test with testcontainer** — use `testcontainers-python` or a `nats-server -js` subprocess in conftest with a dedicated fixture that only activates when `EAASP_EVENT_BACKEND=nats`.
4. **Do NOT delete SQLite backend** — keep it as the default and as the migration source. The two backends co-exist behind the same interface.
5. **Update `scripts/dev-eaasp.sh`** to optionally start a NATS server.

**Warning signs:**
- `pip install nats-py` added to pyproject without dev-eaasp.sh update
- `EventBackend` abstract class gains NATS-specific methods (leaky abstraction)
- Tests fail when `EAASP_EVENT_BACKEND=nats` is set but NATS server is not running

**Phase to address:**
Phase 8.x (L2 leftovers) — D75 must ship with dual-backend pattern + feature flag + testcontainer fixture.

---

### Pitfall 3: bats/shellcheck (D108) — Test Framework Invisible in CI

**What goes wrong:**
D108 adds bats + shellcheck for hook script regression tests. But:
1. **CI doesn't know about bats** — existing `.github/workflows/` runs `cargo test` and `pytest`. bats produces TAP output, not JUnit XML. CI won't execute bats tests unless a new workflow step is added.
2. **bats requires brew install** — on macOS CI runners, `brew install bats-core` is needed. On Linux, `apt-get install bats`. This is a new CI dependency with platform-specific package names.
3. **shellcheck isn't installed by default** — `shellcheck` is a separate binary. Missing on both macOS and Ubuntu CI unless explicitly installed.
4. **Bats test files have no enforcement** — bats `.bats` files live in `examples/skills/*/hooks/`. Without a CI gate, they become stale. A hook script changes, the bats test is forgotten, and the regression guard is hollow.

**Why it happens:**
- The existing `make hook-scripts-test` target exists (line 1168-1171) but isn't wired to `make verify` or CI.
- bats is a niche tool in Python/Rust ecosystems — most developers won't have it installed.
- Shellcheck is a lint tool for shell scripts, but the project has almost no other shell scripts under CI monitoring (`scripts/eaasp-e2e.sh` is not shellchecked).

**How to avoid:**
1. **Wire `make hook-scripts-test` into `make verify`** — this is the single integration point that CI already runs. Add `hook-scripts-test` as a dependency of `verify`.
2. **Add a pre-commit hook for shellcheck** — or better, add it to CI as a standalone job that only runs when `.sh` files change.
3. **Make bats conditional in CI** — `which bats || echo "SKIP: bats not installed"` so CI doesn't break on fresh runners. Add `bats-core` to the CI setup steps for the runner that runs `make verify`.
4. **Co-locate .bats files with the hook scripts** — `examples/skills/*/hooks/*.bats` next to `*.sh`. This makes it obvious when a hook change needs a bats update.

**Warning signs:**
- `make verify` passes but `make hook-scripts-test` was never run
- `bats` not installed → tests skipped silently
- Hook `.sh` file changed, `.bats` file unchanged → regression undetected

**Phase to address:**
Phase 8.x (hooks P2) — D108 must ship with CI gate + `make verify` integration.

---

### Pitfall 4: rmcp ServerHandler (D10) — REST→MCP Transport Change Breaks All Consumers

**What goes wrong:**
D10 upgrades L3's "MCP REST facade" to a real `rmcp ServerHandler`. But:
1. **L4 calls L3 via REST** — `L3Client.validate_session()` makes `POST /v1/sessions/{id}/validate` via httpx. If L3 switches to MCP transport (JSON-RPC over stdio/SSE), L4's HTTP client breaks.
2. **Skill Registry also calls L3** — if any cross-service call uses REST, it breaks.
3. **MCP protocol has different error semantics** — JSON-RPC errors use `{"jsonrpc":"2.0","error":{"code":...,"message":...},"id":...}` not HTTP status codes. The L4 error taxonomy (`UpstreamError.kind: unavailable/error/no_policy`) maps HTTP codes → needs remapping for JSON-RPC errors.
4. **The "facade" is currently a thin REST wrapper** — L3's current `api.py` exposes REST endpoints. Replacing with rmcp means the MCP server runs as a separate process (or the FastAPI app gets an MCP transport layer). Two patterns: (a) add MCP transport alongside REST (dual transport), or (b) replace REST with MCP and add an HTTP→MCP bridge in L4.

**Why it happens:**
- "Upgrade MCP REST facade to rmcp ServerHandler" sounds like a clean refactor, but MCP protocol is NOT a drop-in replacement for REST — it's a different transport (JSON-RPC), different lifecycle (initialize → notify → shutdown), and different error model.
- The L3 is deeply integrated with FastAPI (lifespan, Depends, exception handlers). rmcp has its own server abstraction — these don't compose naturally.
- No existing project code uses rmcp ServerHandler in Python (rmcp is a Rust crate). Python MCP server would use `mcp` Python SDK.

**How to avoid:**
1. **D10 is a "Dual-transport" change, not a replacement** — keep the existing REST endpoints AND add MCP transport. REST remains the default connection path for L4. MCP becomes available for future L1 runtimes that connect via MCP.
2. **Verify L4→L3 REST health check** before and after: `make dev-eaasp` must continue to work unmodified. Run `make v2-phase2-e2e` as a regression gate.
3. **Use Python `mcp` SDK, not rmcp** — rmcp is the Rust crate already in Cargo workspace. L3 is Python — use `pip install mcp` instead. The Python MCP SDK has Server, StdioServerTransport, and SSEServerTransport.
4. **Add a new MCP endpoint** (e.g., `/mcp/sse` as SSE transport) alongside existing REST. L4 continues to call REST. Future L4/L1 can optionally use MCP.

**Warning signs:**
- Old REST endpoint returns 404 after change
- `make dev-eaasp` breaks on L3 startup
- L4 `L3Client.validate_session()` 503 (upstream unavailable) after L3 is replaced

**Phase to address:**
Phase 8.x (L3 leftovers) — D10 must ship with dual-transport (REST preserved + MCP added) AND a pass on `make v2-phase2-e2e`.

---

### Pitfall 5: Concurrent Processing (D79, D25) — Shared State Without Synchronization

**What goes wrong:**
D79 adds multi-worker parallel processing to the L2 Pipeline. D25 adds concurrent deployment E2E to L3. Both touch shared mutable state:
1. **L2 Pipeline workers share `HybridIndex`** — if workers A and B both call `index.search()` while worker C calls `index.insert()`, the HNSW index may serve stale results or crash with concurrent-write corruption.
2. **L3 concurrent deployment** — `PolicyEngine.deploy()` reads `created_at` before commit (D16). In concurrent deploy, two deployers race on version ordering — the second deployer reads `created_at` before the first deployer's commit completes, creating duplicate versions.
3. **SQLite WAL contention** — `aiosqlite` uses `BEGIN IMMEDIATE` to serialize writers, but concurrent READERS during a write can get `SQLITE_BUSY` if not handled. D30 notes `busy_timeout=5000` is inconsistent across L2/L3.

**Why it happens:**
- The existing L2 Pipeline is single-worker. Adding `asyncio.TaskGroup` or `multiprocessing` creates true concurrency on previously single-threaded code.
- SQLite supports concurrent reads + one writer, but Python's aiosqlite wraps sqlite3 in a thread pool — async creates the illusion of sequential execution while threads are actually racing.
- `HybridIndex` has FTS5 (SQLite-backed, protected by WAL) AND HNSW (in-memory, no lock). The HNSW path is the vulnerable one.
- L3's `created_at` is read-then-write (TOCTOU): `now = int(time.time())` → validation → `INSERT ... created_at = now`. Two concurrent deploy calls can get the same `now` value.

**How to avoid:**
1. **L2 Pipeline multi-worker:** Use `asyncio.Semaphore` to limit concurrent workers. Each worker must create its own `HybridIndex` instance (or read-only view). D79 should NOT share a single index across workers.
2. **L3 concurrent deploy:** Use `INSERT ... RETURNING version` in a single transaction — let SQLite's `AUTOINCREMENT` handle version ordering, not application-level `time.time()`. Fix D16 as a prerequisite for D25.
3. **D65 (MCP connection pool):** Use `anyio.create_task_group()` for pooled connections, with a per-connection lock. Stale connections must be detected via `ping()` before reuse — NOT via timeout-only (which leaves orphaned MCP subprocesses).
4. **Add `busy_timeout=5000` consistently** across ALL `aiosqlite.connect()` calls (D30). This is a one-line PRAGMA change with outsized impact on concurrent correctness.

**Warning signs:**
- D79 PR adds `concurrent.futures` or `asyncio.TaskGroup` but no new locks
- `time.sleep(1.1)` in tests (D26) → race condition hidden by timing
- `SQLITE_BUSY` errors in CI that are "flaky" (pass on retry)

**Phase to address:**
Phase 7.2 (L2 Pipeline carry-forward) for D79 + D65. Phase 8.x (L3 leftovers) for D25/D26. D16 is a prerequisite for D25.

---

### Pitfall 6: Cross-Module Refactoring (D20 _sanitize_errors, D14 private access) — Breaking the Pyramid

**What goes wrong:**
D20 extracts `_sanitize_errors()` from L3's `api.py` to a shared module. D14 refactors L2's `index._row_to_memory` to stop accessing private symbols. Both look trivial but:
1. **Shared utility moves break imports** — L4 already has its OWN copy of `_sanitize_errors()` (in `api.py:521-541`). L3 has its own copy (in `api.py:268-286`). They are identical in logic BUT L3's is used in `global_exception_handler` + `deploy_managed_hooks`. L4's is only used in `_run_create_session`. Moving to a shared location requires both consumers to update imports simultaneously. Keeping one on the old import = `ImportError` in production.
2. **L2 private symbol access (D14)** — `_row_to_memory` is `_`-prefixed (convention-private). Other modules in L2 may already depend on it despite the underscore. Removing it or changing signature without a deprecation cycle breaks those callers at runtime (Python doesn't enforce `_` visibility).
3. **Package boundary crossing** — L2, L3, L4 are separate packages (`eaasp-l2-memory-engine`, `eaasp-l3-governance`, `eaasp-l4-orchestration`). A shared utility needs a new shared package (e.g., `eaasp-shared` or `eaasp-commons`). Creating a new package means a new `pyproject.toml`, new `uv.lock`, new CI build step — for ONE function.

**How to avoid:**
1. **D20: Create `eaasp-shared` package with ONE function:** Don't over-extract. `_sanitize_errors` is 20 lines. Move it to a new `tools/eaasp-shared/` package with a single module `errors.py`. Both L3 and L4 add `eaasp-shared` as a dependency. Run `uv lock` in both packages.
2. **D20: Do BOTH moves in the SAME commit:** L3 import change + L4 import change + new shared package. Staggered commits break the import graph. Use `make dev-eaasp` as the integration test.
3. **D14: Add a public wrapper, deprecate the private one:** Don't delete `_row_to_memory`. Add `row_to_memory()` as the public method, make `_row_to_memory` a thin delegate with a deprecation warning. Remove in v3.5.
4. **Check for other `_`-prefixed imports:** `grep -r "from.*import.*_"` across L2/L3/L4 before touching D14. Other modules may silently depend on private symbols.

**Warning signs:**
- `from eaasp_shared.errors import _sanitize_errors` added to L3 but not L4 (or vice versa)
- `ImportError` in `make dev-eaasp` after D20 commit
- D14 PR deletes `_row_to_memory` and CI passes → hidden callers exist in non-CI paths

**Phase to address:**
Phase 8.x (L3 leftovers for D20, L2 leftovers for D14). D20 must ship as a single atomic commit touching 3 packages.

---

### Pitfall 7: P3 Over-Engineering — Gold-Plating Simple Fixes

**What goes wrong:**
Many v3.4 items are P3 ("should fix, not must fix"). The temptation is to turn a 20-minute fix into a 3-day refactor. Examples:
1. **D39 (Policy version hash):** "Replace `str(int)` with hash" → implement a full Merkle-tree manifest of policy versions with SHA-256 chain of custody. The actual fix: use `hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]` — 3 lines.
2. **D28 (L4 exception handler):** "Add global exception handler to L4" → build a custom middleware framework with error taxonomy, structured logging pipeline, and dead-letter queue. The actual fix: copy L3's `global_exception_handler` pattern (20 lines, already proven).
3. **D106 (MAX_TURNS hardcode):** "Promote to config field" → add a full YAML schema with per-skill overrides, hot-reload, and validation. The actual fix: add `AgentLoopConfig.task_budget_override: Option<u32>` — one field, one env var.
4. **D36 (event window cursor):** "Event window cursor for >10k events" → implement a Kafka-style offset manager with consumer groups. The actual fix: add pagination token to the existing `list_events(from=, limit=)` API — a `next_cursor` field in the response.

**Why it happens:**
- P3 items feel incomplete — engineers want to "do it right" instead of doing the minimum.
- Codebase has high architecture standards (15 ADRs, 226 test files) → creates psychological pressure to match that bar for every change.
- Many P3 items say "Phase 3+ NLU" or "Phase 6 multi-node" — these are forward-looking labels, NOT invitations to build Phase 6 now.

**How to avoid:**
1. **Budget constraint per D-item:** P3 items get ≤2 hours each. If the fix takes longer, it's a P2 scope expansion — flag it for milestone review.
2. **Pattern-matching over designing:** L4 exception handler (D28) → L3 already has one. Copy it. L4 loguru init (D31) → L3 already has it. Copy it. Don't re-invent.
3. **Env var, not config file:** D106 (MAX_TURNS) → `GRID_MAX_TURNS=500`. D105 (HookPoint alias) → no new config needed, just accept the old string.
4. **P3 closure criteria:** "The specific bug/behavior described in the INBOX row is fixed. No additional behavior changes." Write this in the PR description.

**Warning signs:**
- A P3 PR touches >5 files
- A P3 PR introduces a new dependency
- A P3 PR adds documentation beyond a CHANGELOG line
- Commit message says "feat:" instead of "fix:" for a P3 item

**Phase to address:**
All phases. Add "P3 budget enforcement" as a reviewer checklist item in Phase 8.0+.

---

### Pitfall 8: Breaking Contract Tests — v2-phase2-e2e / v2-phase3-e2e Regression

**What goes wrong:**
The EAASP contract verification suite (`make v2-phase2-e2e` with 112 pytest cases, `make v2-phase3-e2e-rust`) is the primary regression guard for the L0→L1→L2→L3→L4 integration chain. Changes in ANY layer can break it:
1. **Proto changes (D74 EmitEvent gRPC reverse):** Adding a new RPC method requires proto regeneration + all 7 runtimes to update stubs. If `scripts/gen_runtime_proto.py` isn't re-run, Python runtimes use stale stubs.
2. **Schema changes (D90 WS ToolResult schema):** Adding a field to a WebSocket message schema breaks the `ServerMessage` deserializer in the TS runtime AND the WS client in grid-server.
3. **Hook envelope changes (D48 ScopedHookBody matcher):** Adding fields to the hook body MUST pass `hook_envelope_parity_test.rs` (Rust↔Python cross-language parity). Missing parity test = silent drift.
4. **L4 handshake flow:** D34/D38/D41 change the three-way handshake → the E2E script's `curl` calls assume specific response shapes. Changing these without updating the E2E script causes CI failures that look like infrastructure problems.

**Why it happens:**
- Contract tests are "cross-cutting" — a change in L4 can break a test that exercises L1 gRPC → L4 event ingest → L2 memory search. The failure shows at L2 but the root cause is in L4.
- Proto regeneration is manual (`scripts/gen_runtime_proto.py`). Forgetting to run it produces stale code that compiles (proto stubs are backward-compatible) but misses new fields.
- The E2E scripts use bash + `curl` — no type checking, no compile-time safety. The contract is enforced at runtime.

**How to avoid:**
1. **Pre-commit checklist for every v3.4 PR:**
   - [ ] `make check` passes (cargo check + tsc)
   - [ ] `make verify` passes (static checks)
   - [ ] `make v2-phase2-e2e` passes (or `SKIP_RUNTIMES=true` if L1 unchanged)
   - [ ] `make v2-phase3-e2e-rust` passes (Rust-side regression)
2. **If proto/*.proto is touched:** Run `scripts/gen_runtime_proto.py` AND `make build-eaasp-all`. BOTH must succeed before commit.
3. **If hook envelope is touched:** Run `cargo test -p grid-engine hook_envelope_parity_test` AND `pytest lang/*/tests/ -k hook_envelope`.
4. **If L4 API shape changes:** Update `scripts/eaasp-e2e.sh` in the same commit. The E2E script is the living spec.

**Warning signs:**
- "Saw a test failure in L2 but my change was in L4" → contract drift
- `make v2-phase2-e2e` fails with "unexpected key in response" → schema mismatch
- Proto file changed but `git diff proto/` shows no generated-file changes

**Phase to address:**
All phases. The contract test suite is the final gate for every phase.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Copy `_sanitize_errors()` from L3 to L4 (skip D20) | Saves creating shared package | Double maintenance on every Pydantic upgrade; inconsistent error shapes | Never — D20 is P3 in THIS milestone |
| Skip NATS abstraction layer, replace SQLite directly | One less file | Can't fallback when NATS is down; tests all break; history lost | Never — D75 requires dual backend |
| Skip CI wiring for bats (D108) | Saves CI config | Tests exist but never run; hook scripts regress silently | Never — D108 is P2 (active priority) |
| Add `user_id` to `L2Client.search_memory()` without L2-side coordination | L4 unblocked | L2 may ignore the field or reject request with 422; silent failures | Only after L2 confirms it accepts the field |
| Use `time.sleep(1.1)` in concurrent tests (D26) | Test passes | Makes test suite 30s+ slower; flakes on slow CI; hides real races | Never — fix the race, don't sleep over it |
| Skip MCP transport test for L3 (D10, REST preserved) | One less test | MCP path untested; breaks on first real MCP consumer | Only if MCP is behind feature flag AND REST e2e is the gate |

## Integration Gotchas

Common mistakes when connecting to external services or cross-module boundaries.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| L4 → L2 `search_memory` with `user_id` (D38) | Adding `user_id` parameter to `handshake.py:L2Client.search_memory()` without checking L2 API accepts it | Verify L2's `SearchRequest` model has `user_id` field (it doesn't — check `api.py:19-23`). Add it to L2 FIRST, then pass from L4. Cross-service field MUST exist on the receiver before the sender. |
| L4 → L3 `validate_session` with new fields | Adding fields to `SessionValidateRequest` body in L4's `L3Client.validate_session()` without L3-side model update | L3's `SessionValidateRequest` model (in `api.py:37-40`) has `agent_id`, `skill_id`, `runtime_tier`. Adding `user_id` requires both sides updated in the same deploy batch. |
| NATS JetStream (D75) | Starting NATS server in the FastAPI lifespan (blocks startup if NATS is down) | Connect asynchronously on first use with a retry loop + health check endpoint that reports `nats: disconnected`. Startup must succeed even if NATS is unreachable (graceful degrade). |
| MCP connection pool (D65) | Reusing a stale MCP subprocess connection without health check | Add `ping` before every connection handoff from pool. MCP subprocesses can die silently (OOM, timeout). Pool must detect and recreate dead connections. |
| rmcp ServerHandler (D10) | Using Rust `rmcp` crate in Python L3 (wrong language) | Use Python `mcp` SDK. rmcp is a Rust crate already in Cargo workspace for grid-engine MCP clients. L3 is Python — use the Python MCP package. |
| Pipeline multi-worker (D79) | Sharing a single `HybridIndex` across workers with no read lock | Each worker gets its own `HybridIndex` instance. Read-only workers can share a single read-locked instance. Writer workers must have exclusive access. |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Polling-based `subscribe()` (D76) | `while True: await asyncio.sleep(0.5); events = await db.fetch(...)` burns CPU and misses events between polls | Switch to push-based via NATS JetStream (D75) or SQLite `update_hook` callback | >5 concurrent sessions; >100 events/sec |
| Event window no cursor (D36) | `list_events(from=1, limit=500)` repeatedly fetches first 500 events. >10k events → frontend freezes paginating through all of them | Add `next_cursor` token to response. Cursor = `max(seq) + 1` from last returned page. | >10k events per session |
| Single-event append per transaction (L4 event_stream.py) | Each `append()` calls `BEGIN IMMEDIATE` + `INSERT` + `COMMIT` — 3 SQLite round-trips per event. Burst of 1000 events = 3000 round-trips | Batch append: accept `list[Event]` and commit them in one transaction. Use for `SESSION_CREATED` + initial event burst (D33, D125) | >100 events/sec in burst |
| HybridIndex rebuild on search (D98) | `HybridIndex.search()` recreates HNSWVectorIndex from disk on every call → O(N) startup per search | Cache HNSWVectorIndex in memory. Rebuild only on `INSERT`/`DELETE`. D98 already filed → fix it. | >10 searches/sec |
| `embed_batch` sequential (D93) | Embeds one text at a time. 100 texts × 100ms each = 10 seconds | Batch embed: send all texts in one API call. Most embedding providers support batch endpoints. | >10 writes/sec |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| D38: Propagating `user_id` without L3 RBAC check | User A can read User B's memory by passing `user_id=B` in intent dispatch | L4 must validate `user_id` against the authenticated session's identity (from JWT or API key) BEFORE passing to L2. L2 must independently verify `user_id` matches its own auth context. |
| D41: Session list endpoint without access control | Listing all sessions leaks cross-tenant data | Add `?user_id=` filter to session list. Non-admin users can only list their own sessions. |
| D48: `ScopedHookBody` without `tool_filter` | A hook with `matcher: Prompt` triggers on ALL prompts, even those in unrelated skills | Add `tool_filter: ["tool_a", "tool_b"]` to scope hook execution to specific tool invocations. Without it, hooks fire globally. |
| D107: Stop hook jq fragment shared as file include | If the shared jq file is writable by the skill author, they can inject arbitrary jq that bypasses the three-way check | Shared jq fragments must be read-only from the hook executor's perspective. Store in a system directory (not skill directory) and load before passing to jq. |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **D34 (NLU Intent→Skill):** Implemented intent parser ✓. But: tested with 3 skills ✓, tested with 50 skills ✗ (no collision test), handles "unknown intent" ✗ (graceful fallback to error response vs 500 crash). Must test with the full skill registry fixture.
- [ ] **D38 (user_id propagation):** Passes `user_id` to L2Client ✓. But: L2's search_memory ignores the field ✗ (L2 API model has no `user_id`). L2 must add the field first.
- [ ] **D41 (session list endpoint):** Returns `GET /v1/sessions` with 200 ✓. But: missing pagination for >500 sessions ✗ (uses `limit=50` default, no `offset`/`cursor`), missing RBAC filter ✗, missing `?user_id=` query param ✗.
- [ ] **D75 (NATS JetStream):** Connects to NATS and publishes events ✓. But: No graceful disconnect ✗ (leaks NATS connections on FastAPI shutdown), no fallback to SQLite ✗ (single point of failure), no migration path for existing SQLite events ✗ (historical data lost).
- [ ] **D108 (bats/shellcheck):** .bats file written ✓. But: Not wired to CI ✗, not in `make verify` ✗, `bats` not installed on CI runners ✗. Test exists in repo but never executed.
- [ ] **D10 (rmcp ServerHandler):** MCP transport added ✓. But: REST endpoints broken ✗ (L4→L3 calls fail), `make dev-eaasp` fails ✗ (L3 doesn't start on expected REST port), E2E tests broken ✗ (scripts use curl to REST endpoints).
- [ ] **D79 (Pipeline multi-worker):** Workers created ✓. But: No semaphore limiting concurrency ✗, shared `HybridIndex` ✗, no error propagation from child workers to coordinator ✗ (one worker crashes silently).
- [ ] **D139 (Dual Terminate semantic):** Two terminate paths added ✓. But: gRPC contract updated ✗ (proto file not regenerated), comparison runtimes updated ✗ (6 runtimes need new Terminate handler), backward compat with old L4 clients ✗ (old client sends single terminate → crashes new runtime).
- [ ] **D130 (Cancel token dual-token):** ChildCancellationToken propagation added ✓. But: `cancel_session()` still sends redundant `AgentMessage::Cancel` ✗ (old path not removed), per-turn token reset races with parent cancel ✗ (child created after parent fires → never cancelled).

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| L4↔L2/L3 HTTP schema mismatch | MEDIUM | 1. Roll back the field addition. 2. Add respx test capturing real L2/L3 response shape. 3. Re-add field WITH test. 4. Deploy L2/L3 first, then L4. |
| NATS JetStream connection leak | MEDIUM | 1. Kill orphaned NATS consumers via `nats consumer rm`. 2. Add `drain()` in FastAPI shutdown handler. 3. Add health check for orphaned consumer count. |
| bats tests invisible in CI | LOW | 1. Install bats-core on CI runner. 2. Add `make hook-scripts-test` to CI workflow. 3. Run full hook test suite, fix any pre-existing failures. |
| rmcp ServerHandler breaks REST consumers | HIGH | 1. Revert L3 to dual-transport (REST + MCP). 2. Add feature flag `EAASP_L3_MCP_ENABLED=false` defaulting to off. 3. Only enable MCP after E2E passes with REST path. |
| Concurrent Pipeline corrupts HNSW index | HIGH | 1. Stop all L2 workers. 2. Delete and rebuild HNSW index from SQLite FTS data. 3. Add per-worker index isolation OR read-write lock. |
| Cross-module shared utility breaks imports | LOW | 1. Revert the shared module commit. 2. Do both L3+L4 import changes in one atomic commit. 3. Run `make dev-eaasp` as the gate. |
| P3 gold-plating consumes sprint budget | LOW | 1. Revert the over-engineered changes. 2. Re-implement the minimal fix (≤2 hours). 3. File a follow-up P3 for the "nice to have" parts. |
| Contract test regression | MEDIUM | 1. Identify the breaking change via `git bisect`. 2. Fix the code OR update the test expectation (if intentional). 3. Run full `make v2-phase3-e2e-rust` to confirm no cascading failures. |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| L4↔L2/L3 HTTP schema drift | Phase 8.0 (L4 P2: D34/D38/D41) | respx-mocked integration test per new call path; `make v2-phase2-e2e` passes |
| NATS JetStream stateful infra | Phase 8.x (L2 P3 leftovers: D75) | Dual backend with feature flag; testcontainer-based integration test; `make dev-eaasp` unchanged |
| bats invisible in CI | Phase 8.x (hooks P2: D108) | `make verify` includes hook-scripts-test; CI job runs bats with conditional skip |
| rmcp breaks REST consumers | Phase 8.x (L3 P3 leftovers: D10) | Dual transport preserved; `make dev-eaasp` passes; `make v2-phase2-e2e` passes |
| Concurrent race conditions | Phase 7.2 (L2 P2 carry-forward: D12/D94 + L2 P3: D65/D79) + Phase 8.x (L3 P3: D25/D26) | Semaphore/read-write lock added; D16 fixed before D25; `busy_timeout=5000` consistent |
| Cross-module import breakage | Phase 8.x (L3 P3: D20 + L2 P3: D14) | Atomic single-commit shared package creation; `make dev-eaasp` as gate |
| P3 over-engineering | All phases | P3 budget ≤2 hours; reviewer checklist "P3 scope enforcement" in each PR |
| Contract test regression | All phases | Pre-commit checklist: `make check` + `make verify` + `make v2-phase2-e2e` + `make v2-phase3-e2e-rust` |

## Sources

- **Codebase analysis** (2026-06-07): `crates/grid-engine/`, `tools/eaasp-l4-orchestration/`, `tools/eaasp-l3-governance/`, `tools/eaasp-l2-memory-engine/` — direct code inspection of current state
- **DEFERRED_LEDGER.md** (`docs/design/EAASP/DEFERRED_LEDGER.md`): All 85 D-row descriptions, classification, and status history
- **v3.3-INBOX.md** (`.planning/v3.3-INBOX.md`): Module-grouped debt catalog from Phase 6.2 triage
- **PROJECT.md** (`.planning/PROJECT.md`): Milestone scope, tech stack constraints, ADR governance rules
- **CLAUDE.md**: Authoritative source priority (ADR > EAASP/ > Grid/ > code), contract enforcement rules, cross-runtime parity requirements
- **`scripts/eaasp-e2e.sh`**: Living E2E contract specification (112 pytest cases)
- **`make dev-eaasp`** / **`make verify`**: Dev loop and static verification gate — any change breaking these is a regression
- **ADR-V2-006**: Hook envelope contract (Rust↔Python byte-parity, enforced by `hook_envelope_parity_test.rs`)
- **ADR-V2-020**: Tool namespace layering (L0/L1/L2 tools, enforced by `RequiredTool` parser)
- **ADR-V2-024**: Dual-axis model (engine vs data/integration), v3.4 all on engine side

---

*Pitfalls research for: Grid/EAASP v3.4 INBOX Drain (brownfield debt sweep)*
*Researched: 2026-06-07*
