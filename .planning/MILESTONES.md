# Milestones

## v3.7 实战可用性补全 (Production-Usability Closure) (Shipped: 2026-07-23)

**Phases completed:** 3 phases (3.7.1 / 3.7.2 / 3.7.3) + 1 SKIPPED (3.7.4 deferred to v3.8), 7 plans, 18 tasks

**Git range:** `3a85a06c` (2026-07-19) → `dbb6588c` (2026-07-23) — 50 commits, 76 files changed, 17,095 insertions, 4 days

**Tests:** 175/175 PASS total across milestone
- Phase 3.7.1: 14/14 hermetic scenario integration tests + 7/7 unit tests + 9/9 doctor checks
- Phase 3.7.2: 26/26 vitest + 5/5 Playwright E1-E3 + auditor 8.83/10
- Phase 3.7.3: 136/136 (L3 76 + L4 events 11 + CLI 18 + mock-SCADA 19 + Rust skill-parser 12)

**Key accomplishments:**

1. **Phase 3.7.1 grid-cli 实战可用性** — `grid quickstart <scenario>` + `grid session resume` + `grid run --parallel` + error UX per D-05..D-07 + 12 doctor checks (incl. Hooks File + Eval Bridge); 8/9 REQ-AUDITs closed; 5 scenario walkthrough docs (S1-S5) + dated `PRODUCTION_USABILITY_2026-07-19.md`

2. **Phase 3.7.2 web/ dashboard 实战化** — WS auto-reconnect + SessionControls global + memory_added toast + seq field + Live badge; 9 REQ-WEB items closed; UI-SPEC 7/7 + auditor 8.83/10; S7 walkthrough doc

3. **Phase 3.7.3 EAASP 本地仿真补全 (Phase 3 governance hooks)** — Risk classification taxonomy (read/write_local/write_external) in Rust + Python; L3 `PolicyEngine.evaluate_gate()` decision matrix; append-only `governance_decisions` ledger; L4 `governance.request`/`governance.decision` SSE events; CLI `--yes`/`--no` + interactive `Approve? [y/N]`; deterministic `scada_set_setpoint` mock-SCADA S8 scenario + walkthrough doc; 8/8 REQ-EAASP-01..08 closed

**Locked decisions honored (D-01..D-10 from 03.7.3-CONTEXT.md):** Risk taxonomy (D-01) · L3 hook enforcement (D-02) · L3 audit extension (D-03) · CLI sync approval (D-04) · L4 SSE events (D-05) · No new HTTP endpoint (D-06) · Default mode preserved (D-07) · Existing tests unaffected (D-08) · Single S8 scenario (D-09) · Dated walkthrough record (D-10)

**Deferred to v3.8+:** Phase 3.7.4 grid-server multi-user (per user 2026-07-19 explicit deferral); full production OPA backend; multi-party approval; sandbox tier enforcement; L5 Cowork UI consumers; web-platform/ Quality 7.5→9.0; grid-desktop Quality 6.5→9.0

**Live walkthrough status:** Blocked on missing LLM API key (per CLAUDE.md §Runtime Verification Tasks). All scenarios verified hermetically via in-process S1-S8 walkthrough tests; CLI `eaasp session run --yes` / `--no` / interactive paths fully exercised.

---

## v3.5 Debt Finalization (Shipped: 2026-06-16)

**Phases completed:** 3 phases, 3 plans, 3 tasks

**Key accomplishments:**

- Phase 9.0: LEDGER audit — 56 D-rows standardized to `✅ CLOSED` format (17 notation fix + 30 newly closed + 9 genuine actives filed for later)
- Phase 9.1: Hooks/Pyright quick wins — D121 stop-hook dedup warning, D122 env-parity cross-runtime verify, D123 RAII `EnvGuard` replacing `set_var` + Mutex
- Phase 9.2: Final LEDGER close-out — main D-table 100% ✅ CLOSED with full format uniformity
- LEDGER end state: zero P1/P2/P3 active items, 17 genuinely ACTIVE items filed as 📦 long-term for Phase 4–6 concern

---

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
