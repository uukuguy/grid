# v3.16 OBSTACK 产品面收口实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development task-by-task. Every implementation task follows TDD, commits independently, then passes a task-scoped spec + quality review.

**Goal:** 完成 `web/ + L4 + eaasp-cli-v2` 的真实 OBSTACK 产品面缺口，并以证据否决无数据契约的旧 6d/6e 投影。

**Architecture:** L4 继续拥有六个 business-flow endpoint；`web/` 和 Python `ObstackClient` 是消费者。L4 session 读面暴露已持久化的 `business_key`。不新增 grid-server proxy/RBAC 假路由。

**Tech Stack:** React 19 + TypeScript + Vitest；Python 3.12 + FastAPI + Typer + pytest；shell/Python verification scripts。

**Design:** `docs/superpowers/specs/2026-08-24-v316-obstack-product-surface-design.md`

## Global Constraints

1. L4 owns `/v1/business-flows/*`; `web/` is the existing OBSTACK UI owner.
2. No new `/alerts`, `/stats`, or `/optimize` backend endpoint.
3. No `grid-server` RBAC entry without a real handler; expected catalog remains 134.
4. No changes to `grid-types`, `grid-engine`, `grid-sandbox`, or `grid-hook-bridge`.
5. Historical NULL `business_key` stays NULL; clients must not infer it.
6. Targeted tests only; no unsolicited workspace-wide/full suites.
7. Each task must record RED and GREEN evidence and use the required commit trailers.

## Task 1: Add the typed SSE contract and operator derivations

**Files:**
- Modify: `web/src/api/flows.ts`
- Modify: `web/src/api/obstack_types.ts`
- Create: `web/src/lib/obstack/operatorViews.ts`
- Create: `web/src/test/v316-obstack-contract.test.ts`

**Interfaces:**
- `ObstackClient.stream_business_flow(key, onEvent, signal): Promise<void>`
- `flowsApi.stream(key, onEvent, signal): Promise<void>`
- `deriveFlowStats(flows): FlowStats`
- `deriveFlowAlerts(flows, nowSeconds?): FlowAlert[]`
- `rankSlowFlows(flows, limit): BusinessFlowSummary[]`

- [ ] Write tests first for URL encoding, Bearer propagation, split/multiple SSE frames, abort, non-2xx, aggregate counts, failed alerts, stale-active alerts, and duration ranking.
- [ ] Run `cd web && npx vitest run src/test/v316-obstack-contract.test.ts` and capture expected RED.
- [ ] Implement the smallest typed fetch-stream parser and pure derivation module.
- [ ] Re-run the focused test and `npm run build`; both must pass.
- [ ] Commit and write `.superpowers/sdd/task-1-report.md` with RED/GREEN evidence.

## Task 2: Integrate live and derived operator views into the existing dashboard

**Files:**
- Modify: `web/src/pages/Flows.tsx`
- Modify: `web/src/components/dashboard/FlowsDetail.tsx`
- Create: `web/src/components/dashboard/FlowOperatorOverview.tsx`
- Create: `web/src/test/v316-obstack-surface.test.tsx`
- Modify: `scripts/v315-browser-e2e.mjs`

**Behavior:**
- List page renders stats and derived alerts from the current filtered flow rows.
- Detail labels evaluation hints as optimization guidance.
- Detail starts one SSE stream per selected key, aborts it on key change/unmount, deduplicates by `(ts, layer, component, event_type, stable-json(payload))`, and refreshes summary/timeline/evaluation after a live event.
- No requests target nonexistent operator endpoints.

- [ ] Write component tests first using mocked `flowsApi` and a controllable stream callback.
- [ ] Run `cd web && npx vitest run src/test/v316-obstack-surface.test.tsx` and capture expected RED.
- [ ] Implement the overview and live detail integration without changing app ownership or adding routes.
- [ ] First replace `scripts/v315-browser-e2e.mjs`'s main-worktree absolute Playwright import with worktree-relative module resolution, then extend smoke assertions for stats/optimization/live indicator.
- [ ] Run both v3.16 web tests and `npm run build`; commit and report.

## Task 3: Add the missing flow CLI commands

**Files:**
- Modify: `tools/eaasp-cli-v2/src/eaasp_cli_v2/cmd_flow.py`
- Create: `tools/eaasp-cli-v2/tests/test_v316_flow_commands.py`

**Behavior:**
- Add `list`, `top-failed`, and `top-slow` using `ObstackClient.list_business_flows` and `FlowListParams`.
- Validate limits are 1..200.
- `top-failed` always requests the maximum bounded candidate window (`limit=200,status=failed`), then ranks failed count/recency and applies the user display limit.
- `top-slow` always requests `limit=200`, then ranks non-null `last_duration_ms` descending and applies the user display limit.
- Empty results are successful and explicit.

- [ ] Write all command tests first, including the fixed 200-row candidate request, output-limit sorting, empty results, invalid limits, and shared-client errors.
- [ ] Run `cd tools/eaasp-cli-v2 && PYTHONPATH=../eaasp-common/src uv run --extra dev pytest -q tests/test_v316_flow_commands.py` and capture RED.
- [ ] Implement only the three commands and small local formatting helpers.
- [ ] Re-run the focused test and existing `tests/test_cmd_flow.py`; commit and report.

## Task 4: Surface persisted BusinessKey through L4 sessions and CLI

**Files:**
- Modify: `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/session_orchestrator.py`
- Create: `tools/eaasp-l4-orchestration/tests/test_v316_business_key_surface.py`
- Modify: `tools/eaasp-cli-v2/src/eaasp_cli_v2/cmd_session.py`
- Create: `tools/eaasp-cli-v2/tests/test_v316_session_business_key.py`

**Behavior:**
- `get_session` and both `list_sessions` query branches (unfiltered and `?status=...`) return `business_key`.
- Historical rows return `None`/JSON null.
- CLI `session list` and the metadata table in `session show` include `business_key` verbatim.

- [ ] Write L4 and CLI tests first for populated and NULL keys; the L4 test must exercise get, unfiltered list, and status-filtered list. Capture RED separately.
- [ ] Add only SELECT/result fields and CLI columns; do not change schema or infer keys.
- [ ] Run the two new test files plus existing targeted session API/CLI tests relevant to list/show.
- [ ] Commit and report.

## Task 5: Encode the truthful scope boundary and deferred contracts

**Files:**
- Modify: `docs/design/EAASP/DEFERRED_LEDGER.md`
- Modify: `docs/superpowers/plans/2026-08-09-obstack-v3-15-6-completion.md`
- Modify: `docs/status/climb/adjudicator-log.md`
- Modify: `tools/eaasp-common/src/eaasp_common/obstack_models.py`
- Create: `scripts/check-v316-obstack-boundaries.py`
- Create: `scripts/tests/test_check_v316_obstack_boundaries.py`

**Behavior:**
- Register `V316-MULTITENANT-OBSTACK-01`, `V316-EVAL-OBSTACK-01`, and `V316-ECOSYSTEM-HEALTH-01` with triggers and owners.
- Mark old 6d/6e execution text superseded by this plan; retain it as history.
- Correct the shared model docstring: L4 Python is the server owner and `web/src/api/obstack_types.ts` is the TypeScript mirror.
- Boundary audit proves all six L4 routes exist, grid-server has no fake business-flow RBAC entry, the three deferred IDs exist, and this plan is the active replacement.
- Negative fixtures in the audit test must prove the checker fails when a route or deferred ID is absent.

- [ ] Write checker tests first and capture RED.
- [ ] Implement the checker and documentation/state updates.
- [ ] Run `python3 -m unittest scripts.tests.test_check_v316_obstack_boundaries`; commit and report.

## Task 6: Connect persisted L4 events to the live business-flow SSE bus

**Files:**
- Modify: `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/event_engine.py`
- Modify: `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/api.py`
- Modify: `tools/eaasp-l4-orchestration/tests/test_event_engine.py`
- Create: `tools/eaasp-l4-orchestration/tests/test_v316_live_flow_publish.py`

**Behavior:**
- `EventEngine` invokes an optional async observer only after durable append succeeds.
- Observer failures are warning-only and do not turn a successful ingest into failure.
- App wiring resolves the persisted session `business_key`, skips NULL/malformed values, converts valid events to `BusinessFlowEvent`, and publishes them to the existing singleton bus.
- Both internal EventEngine traffic and `/v1/events/ingest` therefore drive the real SSE channel; no test-only route is added.

- [ ] Write observer ordering/failure tests and app-wiring publish/filter tests first; capture RED.
- [ ] Implement the smallest observer hook and app wiring.
- [ ] Run focused Event Engine and live-publish tests; commit and report.

## Task 7: Run integrated closeout and update durable state

**Files:**
- Create: `scripts/v316-obstack-surface-verify.sh`
- Modify: `docs/status/climb/session-state.json`
- Modify: `.planning/STATE.md`
- Modify: `docs/status/JOURNAL.md`

**Verification script:**
- Runs the two focused web test files and web build.
- Runs new CLI flow and session tests.
- Runs new L4 BusinessKey tests plus focused `test_flow_api.py` SSE/malformed-key controls.
- Runs boundary audit, `make rbac-audit`, and `make v3.10-spec-audit`.
- Starts or reuses a seeded L4 and hard-fails unless malformed key returns 400 and a live SSE subscription receives at least one `data:` frame.
- Prints each gate and exits nonzero on the first failure.

- [ ] Write shell-level tests or a dry-run command manifest first; prove a forced failing command stops the script.
- [ ] Implement the executable aggregate script with `set -euo pipefail`, explicit malformed-key/SSE probes, and no full-suite target.
- [ ] Run `bash -n scripts/v316-obstack-surface-verify.sh` then the real script.
- [ ] Run `make grid-web-e2e` as a supplementary browser smoke. The new verifier—not this legacy target—owns the non-skippable malformed-key and SSE probes. If an environmental prerequisite is missing, fix it and rerun rather than weakening the gate.
- [ ] Run `tools/climb/cycle.sh H-005`; target must report 100/100 and hard-pause.
- [ ] Update STATE/JOURNAL with exact test counts, catalog count, spec rows, and commit hashes; commit and report.

## Completion Review

After all seven tasks have clean task reviews:

1. Generate a whole-branch review package from `5e9d49b8` to HEAD.
2. Dispatch one final code reviewer for cross-task integration, scope, security, and test adequacy.
3. Fix and re-review every Critical/Important finding.
4. Run the final verification script once more.
5. Use the finishing-development-branch workflow; do not merge or tag without explicit user authorization.
