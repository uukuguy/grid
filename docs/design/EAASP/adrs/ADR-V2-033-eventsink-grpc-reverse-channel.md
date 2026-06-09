---
id: ADR-V2-033
title: "EventSink gRPC Reverse Channel — L1→L4 Event Push Service"
type: contract
status: Proposed
date: 2026-06-09
phase: "Phase 8.1 — Contract Proto + Grid-Engine/Server Cross-Cutting"
author: "Jiangwen Su"
supersedes: []
superseded_by: null
deprecated_at: null
deprecated_reason: null
enforcement:
  level: contract-test
  trace:
    - "proto/eaasp/runtime/v2/runtime.proto"
    - "crates/grid-runtime/src/service.rs"
    - "tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/"
    - "tests/contract/"
  review_checklist: "docs/design/EAASP/adrs/ADR-V2-033-eventsink-grpc-reverse-channel.md"
affected_modules:
  - "proto/eaasp/runtime/v2/"
  - "crates/grid-runtime/"
  - "tools/eaasp-l4-orchestration/"
related:
  - ADR-V2-001
  - ADR-V2-004
---

# ADR-V2-033 — EventSink gRPC Reverse Channel (L1→L4 Event Push)

**Status:** Proposed
**Date:** 2026-06-09
**Phase:** Phase 8.1 — Contract Proto + Grid-Engine/Server Cross-Cutting
**Author:** Jiangwen Su
**Related:** ADR-V2-001 (EmitEvent interface), ADR-V2-004 (L4→L1 gRPC binding)

---

## 背景 (Context)

### Current state

The existing `EmitEvent` RPC at `proto/eaasp/runtime/v2/runtime.proto:76` sits inside the `RuntimeService` and follows the **L4→L1 direction** — L4 calls `EmitEvent` on L1's gRPC server to inject events into the runtime. This is a standard RPC pattern where L1 is the server and L4 is the client.

```protobuf
// proto/eaasp/runtime/v2/runtime.proto:71-76
// EmitEvent exposes the session's emergent event stream to L4.
rpc EmitEvent(EventStreamEntry) returns (Empty);
```

Per ADR-V2-001, `EmitEvent` is **OPTIONAL** — T1 runtimes SHOULD implement it, but the default is no-op. Events emitted via this RPC cover enriched runtime-side events: `PRE_COMPACT`, `TOKEN_USAGE`, `THINKING_DELTA`, etc.

### The gap

The current architecture has a one-way event flow (L4→L1). There is **no mechanism for L1 runtimes to proactively push events back to L4** without L4 polling. Specifically:

1. **PRE_COMPACT** events fire inside `grid-engine` at `compaction_pipeline.rs:349` — these are currently written to a local file sink (`pre_compact_emitter.rs`) but not streamed to L4 in real-time.
2. **TOOL_RESULT** events would enable L4 observability dashboards without intercepting `POST_TOOL_USE` hooks.
3. **TOKEN_USAGE** events could feed real-time cost dashboards in L4's session monitoring.

D74 in the DEFERRED_LEDGER (L198) captures this gap as the "EmitEvent gRPC reverse channel" — L1 acts as a gRPC **client** pushing events to L4's gRPC **server**.

### Design constraint

gRPC does not allow a single process to be both server and client for the same RPC in a natural way. The existing `EmitEvent` on `RuntimeService` has L1 as the server. To reverse the direction, we need a **separate service** where L1 is the client and L4 is the server.

---

## 决策 (Decision)

### Introduce an `EventSink` gRPC service

A new `EventSink` gRPC service is defined adjacent to `RuntimeService` in `runtime.proto`. It has a single RPC that reuses the existing `EventStreamEntry` message:

```protobuf
// NEW service — L1 is the gRPC client, L4 is the gRPC server.
service EventSink {
  // Push a lifecycle event from L1 runtime to L4 orchestration.
  // Direction: L1 → L4 (reverse of RuntimeService.EmitEvent).
  rpc EmitEvent(EventStreamEntry) returns (Empty);
}
```

### Direction inversion

| Service | RPC | Client | Server | Direction |
|---------|-----|--------|--------|-----------|
| `RuntimeService` | `EmitEvent` | L4 | L1 | L4→L1 (existing) |
| **`EventSink`** | **`EmitEvent`** | **L1** | **L4** | **L1→L4 (new)** |

The existing `RuntimeService.EmitEvent` is **NOT removed or changed**. The new `EventSink` service is additive.

### L4 gRPC server

L4's FastAPI lifespan starts a gRPC server on a configurable port:

- **Env var:** `GRID_EVENT_SINK_PORT` (default: `50056`)
- **Implementation:** `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/` adds an `EventSinkServicer` that receives `EventStreamEntry` messages and routes them into the existing L4 event pipeline (SQLite WAL backend per ADR-V2-002).

### L1 gRPC client

L1 runtime creates a gRPC client to the EventSink endpoint:

- **Port:** read from `GRID_EVENT_SINK_PORT` env var
- **Implementation:** `crates/grid-runtime/` adds an `EventSinkClient` that connects at startup and pushes events
- **Event types pushed (priority order):**
  1. `PRE_COMPACT` — highest observability value, already fires at `compaction_pipeline.rs:349`
  2. `TOOL_RESULT` — enables L4 dashboards
  3. `PRE_TOOL_USE` — enables tool-call tracing
  4. `POST_TOOL_USE` — enables tool-result tracing
  5. `THINKING_DELTA` — thinking trace visibility
  6. `TEXT_DELTA` — incremental response visibility
  7. `TOKEN_USAGE` — real-time cost monitoring

### OPTIONAL contract (per ADR-V2-001 lineage)

The `EventSink` service is **OPTIONAL** — same tier as `Health`, `PauseSession`, `DisconnectMCP`. Specifically:

1. L1's gRPC client MUST gracefully handle connection failure — fall back to no-op with a `warn!` log.
2. No event loss is acceptable because **primary persistence** remains the file sink (`pre_compact_emitter.rs`) and/or SQLite backend.
3. gRPC push is **best-effort augmentation** — it enhances observability but is not a correctness requirement.
4. If L4 does not start the EventSink gRPC server, L1 operates normally with zero degradation.

### Cross-runtime compatibility

| Runtime | Impact |
|---------|--------|
| `grid-runtime` | Adds EventSink client (primary implementor) |
| `claude-code-runtime-python` | No changes required — continues using `RuntimeService.EmitEvent` (L4→L1) |
| `goose-runtime` | No changes required |
| `nanobot-runtime-python` | No changes required |
| `pydantic-ai-runtime-python` | No changes required |
| `claw-code-runtime` | No changes required |
| `ccb-runtime-ts` | No changes required |
| `hermes-runtime-python` | Frozen per ADR-V2-017 — no changes |

The `EventSink` service is **purely additive**. No existing runtime adapter needs changes. The existing `RuntimeService.EmitEvent` (L4→L1 direction) remains unchanged. Contract-v1 certification is unaffected.

### EventStreamEntry reuse

The `EventStreamEntry` message at `runtime.proto:263-269` already defines the correct shape:

```protobuf
message EventStreamEntry {
  string session_id = 1;
  string event_id = 2;
  HookEventType event_type = 3;
  string payload_json = 4;
  string timestamp = 5;  // ISO 8601
}
```

Both `RuntimeService.EmitEvent` (L4→L1) and `EventSink.EmitEvent` (L1→L4) use the **same message type** — no new message definitions needed.

---

## 后果 (Consequences)

### Positive

- **Real-time L4 observability**: PRE_COMPACT and TOOL_RESULT events reach L4 dashboards without L4 polling, enabling session monitoring at scale.
- **Minimal proto surface**: One new service, one reused message, zero schema duplication.
- **OPTIONAL contract**: No runtime is forced to implement the reverse channel. Existing runtimes continue working unchanged.
- **No wire-breaking**: `RuntimeService.EmitEvent` (L4→L1) is untouched. Contract-v1 certification pass rates unaffected.

### Negative

- **Proto regeneration needed**: All 7 runtime stubs must be regenerated after `runtime.proto` is updated (adds the `EventSink` service definition). Estimated ~30 min for codegen + verification.
- **New port**: L4 must bind an additional port (50056) for the EventSink gRPC server.
- **Two event channels**: L4 now receives events from TWO gRPC services (the existing `RuntimeService.EmitEvent` for L4-initiated injection, and `EventSink.EmitEvent` for L1-initiated push). L4's event ingestion pipeline must route both to the same backend.

### Risks

- **L4 gRPC server reliability**: If the L4 EventSink gRPC server crashes or is unreachable, L1's best-effort client must not propagate errors to the agent loop. Mitigation: the L1 client wraps all calls in `tokio::time::timeout` with a short deadline (1s) and logs failures at `warn!` level.
- **Port collision**: The default `50056` may conflict with other services. Mitigation: `GRID_EVENT_SINK_PORT` env var allows per-deployment override.

---

## 影响范围 (Affected Modules)

| Module | Impact |
|--------|--------|
| `proto/eaasp/runtime/v2/runtime.proto` | Add `EventSink` service definition (1 RPC, reuses `EventStreamEntry`) |
| `crates/grid-runtime/` | Add `EventSinkClient` (gRPC client), wire into event emission hot paths |
| `tools/eaasp-l4-orchestration/` | Add `EventSinkServicer` (gRPC server), integrate with lifespan |
| `tests/contract/` | Add optional EventSink contract test (smoke: L1→L4 push + L4 receive) |
| All 7 runtimes | Proto regeneration only — no functional changes |

---

## 候选方案 (Alternatives Considered)

### Option A: Extend existing `RuntimeService.EmitEvent` to be bidirectional

Use the same `EmitEvent` RPC with L1 as client and L4 as server by flipping which side binds.

**Pros:** No new service definition.
**Cons:** gRPC service definitions are inherently asymmetric — a service's RPCs are implemented by the server. Making `RuntimeService.EmitEvent` bidirectional would require L4 to implement the `RuntimeService` server interface partially, creating confusion about who "owns" the service. Rejected.

### Option B: REST endpoint instead of gRPC service

L1 pushes events to L4 via HTTP POST to `/v1/events/ingest` (already defined in ADR-V2-002).

**Pros:** No new proto definitions; simpler to implement.
**Cons:** Inconsistent with the rest of the L1/L4 contract (which is gRPC-native). Creates a second transport mechanism for the same data. Rejected in favor of gRPC uniformity.

### Option C: Separate proto file

Define `EventSink` in a new `proto/eaasp/runtime/v2/eventsink.proto` file.

**Pros:** Cleaner separation of concerns.
**Cons:** Yet another proto file to manage. `EventStreamEntry` lives in `runtime.proto` so the new file would need to import it anyway. Rejected — adding to the existing file is simpler.

### Option D: Adopt this ADR (EventSink service in `runtime.proto` ← SELECTED)

Add a new `EventSink` service to the existing `proto/eaasp/runtime/v2/runtime.proto`, reusing `EventStreamEntry`, with OPTIONAL contract per ADR-V2-001 lineage.

**Pros:** Minimal proto surface; reuses existing types; OPTIONAL = zero pressure on comparison runtimes; additive = no breaking changes.
**Cons:** Two gRPC event channels in L4; new port to manage.
**Adopted.**

---

## References

- [ADR-V2-001](./ADR-V2-001-emit-event-interface.md) — EmitEvent OPTIONAL contract
- [ADR-V2-004](./ADR-V2-004-l4-to-l1-real-grpc-binding.md) — L4→L1 gRPC binding
- DEFERRED_LEDGER.md L198 — D74: EmitEvent gRPC reverse channel
- `proto/eaasp/runtime/v2/runtime.proto:71-76` — current EmitEvent RPC
- `proto/eaasp/runtime/v2/runtime.proto:258-269` — EventStreamEntry message
- `crates/grid-runtime/src/service.rs:597-613` — current EmitEvent handler (L4→L1)
- `crates/grid-runtime/src/contract.rs:110-121` — RuntimeContract::emit_event (no-op default)
- `crates/grid-runtime/src/pre_compact_emitter.rs` — event emission to file (reference pattern)
