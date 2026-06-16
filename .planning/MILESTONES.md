# Milestones

## v3.4 Full INBOX Drain (Shipped: 2026-06-16)

**Phases completed:** 11 phases, 21 plans, 39 tasks

**Key accomplishments:**

- One-liner:
- One-liner:
- Re-verified all 8 L2 carry-forward D-items as ✅ CLOSED with correct commit hashes and full test suite passing — zero regressions since June 2 close, 8/8 commit hashes confirmed in git log, 134+5 L2 tests PASS, no implementation changes needed.
- Created eaasp_common shared Python package with sanitize_errors() utility, then migrated L3 governance from local _sanitize_errors to shared import — first inter-tool Python dependency in the EAASP ecosystem.
- Before:
- MCP server with 4 policy tools wired to PolicyEngine, SSE transport mounted in FastAPI lifespan with all 8 REST endpoints preserved
- ADR-V2-033 EventSink gRPC reverse channel + ADR-V2-017 §2 double-Terminate NO-OP contract revision
- Configurable task budget multiplier (D106) + live-connected cancel token eliminating per-turn snapshot staleness (D130)
- Confirmed D90 already resolved — tool_name present in AgentEvent::ToolResult (D83/S1.T4) and serialized to WS wire at ws_chunk.rs:173-182; LEDGER closed with zero code changes
- L4 Foundation P2 differentiators delivered:
- One-liner:
- L4_ALLOW_TRIM_P4 env-gated budget flag, >500/s event burst WARNING, {name, kind} dependency dicts, and reference-mode SESSION_CREATED events — 4 mechanical items copying established L3 Phase 7.3 patterns
- 5 mechanical P3 items: 5xx test coverage, unused dep removal, --limit flag, response shape guards, and dynamic version parsing — ~129 LOC across 4 files.
- One-liner:
- One-liner:
- One-liner:
- One-liner:
- Six standalone mechanical fixes to eval/verify scripts and IDE config — ~41 LOC total pylint-free polish for milestone v3.4 final sign-off.

---

## v3.3 Engine + Platform Debt Sweep (Shipped: 2026-06-07)

**Phases completed:** 3 phases, 3 plans, 4 tasks

**Key accomplishments:**

- 1. [Rule 3 - Blocking] Plan verify command for pytest (Task 3)
- One-liner:
- 93 open main-namespace D-rows triaged (P1=0 / P2=15 / P3=70 / DEAD=8), 8 DEAD rows migrated to closed-text archive, v3.3-INBOX.md generated with 12-module taxonomy — milestone v3.2 CLOSED

---
