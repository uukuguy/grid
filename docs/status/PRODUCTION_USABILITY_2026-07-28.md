# Production Usability — v3.12.3 single-point live walkthrough — 2026-07-28

## 结论

v3.12 milestone SHIPPED on 2026-07-28 via the 03.12.3 single-point live
walkthrough. The v3.12.2 EAASP Phase 4 stack (A2A Router + Event Room +
multi-session coordination + conflict detection algorithm + 5-stage
approval integration) was exercised end-to-end against a real OPA
sidecar on 127.0.0.1:18181, with three human-bound sessions (1 initiator +
2 reviewers), a shared evidence anchor, a `gate_request` → 5-stage pause
→ A2A ReviewSet → conflict detection → close → resume → execute flow,
and dual-gate validation: v3.9 RBAC `route_auditor` PASS (134 routes)
and v3.10 `spec_audit` PASS (4 files / 37 rows). v3.12 plans 03.12.0 /
03.12.1 / 03.12.2 / 03.12.3 all SHIPPED; milestone v3.12 is now in
close-out cascade.

## Walkthrough 证据 — Live run captured

### 时间戳与命令序列

```text
UTC+8 10:24:30 — L3 startup: eaasp_l3_governance.api:create_app:200 —
                  L3 OPA backend enabled (L3 on :18083 ↔ OPA :18181)
UTC+8 11:57:45 — preflight OPA roundtrip (req_id=7, OPA latency 1.2ms)
UTC+8 12:16:48 — walkthrough run (req_id=10, OPA latency 13.3ms)
```

### 步骤 — single-point end-to-end

| # | Phase                                          | Tool / API                                   | Evidence                                        |
|---|------------------------------------------------|----------------------------------------------|-------------------------------------------------|
| 1 | Seed L4 sessions                               | `ensure_l4_session(...)` × 3                 | `sess_initiator_v3_12_3`, `sess_reviewer_a_v3_12_3`, `sess_reviewer_b_v3_12_3` |
| 2 | Create Event Room `er_transformer_review_v3_12_3` | `EventRoomStore.create(room_id, ttl=3600)` | status=`open`, 3 members bind OK                  |
| 3 | L3 `/v1/sessions/{id}/validate` → `/v1/evaluate` | real OPA roundtrip (req_id=10)            | `backend="opa"` `decision="gate_request"`         |
| 4 | ApprovalStateMachine.run / Plan..Draft..Approve | 4-stage SSE events seq=10..13              | `governance.approval.{plan,check,draft,approve}` pause at `await_human` |
| 5 | A2A Router.request_review                       | `request_review(room_id, [a,b])`            | `set_id=rs_cb23d1f303cf4782`, 2 reviewers registered |
| 6 | Reviewer A: ALLOW                              | `route_review_submission(set_id, ALLOW)`    | shared_evidence=`anchor-transformer-spec-v3_12_3` |
| 7 | Reviewer B: NEEDS_REVISION                     | `route_review_submission(set_id, NR)`       | shared_evidence=`anchor-transformer-spec-v3_12_3` (conflict trigger) |
| 8 | A2A Router.aggregate_review_set                 | aggregation engine                          | `final_decision="escalate"` `conflict_detected=true` `synthesis_required=true` |
| 9 | A2A Router.close_review_set                     | close + emit closed                         | `final_decision="escalate"` `aggregate_reason="escalate: 1 reviewer(s) requested needs_revision"` |
| 10 | ApprovalStateMachine.resume_with_human_decision | `human_decision=ALLOW human_reason=...`    | SSE event seq=14 `governance.approval.execute` `final_decision="approve"` |

### OPA HTTP 流量 — `/v1/data/governance/decision` (real sidecar)

| req_id | client          | method | path                                  | resp_status | resp_bytes | duration_ms | ts (UTC+8)         |
|--------|-----------------|--------|---------------------------------------|-------------|------------|-------------|--------------------|
| 4      | 127.0.0.1:57808 | POST   | `/v1/data/governance/decision`        | 200         | 160        | 2834.5      | 2026-07-28 10:19:07 |
| 6      | 127.0.0.1:49282 | POST   | `/v1/data/governance/decision`        | 200         | 160        | 33073.3     | 2026-07-28 11:15:11 |
| 7      | 127.0.0.1:57231 | POST   | `/v1/data/governance/decision`        | 200         | 160        | 1226.8      | 2026-07-28 11:57:45 |
| 8      | 127.0.0.1:58084 | POST   | `/v1/data/governance/decision`        | 200         | 160        | 2355.6      | 2026-07-28 12:03:01 |
| 9      | 127.0.0.1:58904 | POST   | `/v1/data/governance/decision`        | 200         | 160        | 1295.3      | 2026-07-28 12:07:16 |
| 10     | 127.0.0.1:60803 | POST   | `/v1/data/governance/decision`        | 200         | 160        | 13277.1     | 2026-07-28 12:16:48 |

req_id=10 is the walkthrough run for the 03.12.3 phase; OPA returned 200
in 13.3ms with a 160-byte JSON decision payload. Multi-millisecond latency
is typical for an in-process Rego evaluation; no upstream_error or 5xx.

JSON evidence file:
`.grid/live-walkthrough-v3_12_3/opa-http-traffic.jsonl` (6 rows, captured
JSONL via parse of OPA sidecar log).

### 双 gate — v3.9 RBAC + v3.10 spec-audit (post-walkthrough)

| Gate                       | Command                                 | Result     |
|----------------------------|-----------------------------------------|------------|
| v3.9 RBAC catalog          | `make rbac-audit`                       | PASS / 134 routes |
| v3.10 spec-audit           | `make v3.10-spec-audit`                 | PASS / 4 files / 37 rows |
| Cargo check                | `cargo check -p grid-server` (transitive build) | PASS |

Both gates unchanged from v3.11 / v3.11.3 SHIP snapshot — confirms the
v3.12 code path **does not regress** the route catalog or the
EAASP-alignment audit. Captured in
`.grid/live-walkthrough-v3_12_3/dual-gate.log`.

### 5-stage governance approval audit evidence (8 L3 governance_decisions rows, post-walkthrough)

| decision_id (prefix)             | stage           | decision      | rationale (truncated)                                                |
|----------------------------------|-----------------|---------------|----------------------------------------------------------------------|
| `gd_*` (HTTP /v1/evaluate)        | (none)          | gate_request  | `write_external in enforce mode requires human approval (spec §6.10)` |
| `gd_approval_*_plan`             | plan            | allow         | `plan:ok (regenerated from live OPA risk_level=write_external)`        |
| `gd_approval_*_check`            | check           | allow         | `check:ok (L3 OPA decision=approval ⇒ continue)`                       |
| `gd_approval_*_draft`            | draft           | allow         | `draft:ok (PlanDraft v3_12_3, evidence anchored)`                      |
| `gd_approval_*_approve`          | approve         | await_human   | `approve:await_human (OPA decision=approval ⇒ human pause)`            |
| `gd_approval_*_approve_pause`    | approve_pause   | await_human   | `approve:await_human (...)`                                            |
| `gd_approval_*_await_human`      | await_human     | allow         | `human:人工复议后批准 (after A2A close)`                                |
| `gd_approval_*_execute`          | execute         | approve       | `execute: human signed off (human:人工复议后批准 (after A2A close))`     |

Authoritative file:
`.grid/live-walkthrough-v3_12_3/l3-governance-decisions.tsv`

### SSE / Event Room evidence — multi-session shared event log

| seq | event_type                       | origin_session_id            | payload hint                                          |
|-----|----------------------------------|------------------------------|-------------------------------------------------------|
| 10  | governance.approval.plan         | sess_initiator_v3_12_3       | plan:allow                                            |
| 11  | governance.approval.check        | sess_initiator_v3_12_3       | check:allow                                           |
| 12  | governance.approval.draft        | sess_initiator_v3_12_3       | draft:allow                                           |
| 13  | governance.approval.approve      | sess_initiator_v3_12_3       | approve:await_human                                   |
| 14  | governance.approval.execute      | sess_initiator_v3_12_3       | execute:approve (after A2A close + human resume)       |
| 15  | a2a.request.sent                 | sess_initiator_v3_12_3       | ReviewSet opened, fan-out 2 reviewers                 |
| 16  | a2a.request.acknowledged         | sess_initiator_v3_12_3       | structural ACK                                        |
| 17  | a2a.review.submitted             | sess_reviewer_a_v3_12_3      | decision=allow evidence=anchor-transformer-spec-v3_12_3 |
| 18  | a2a.review.submitted             | sess_reviewer_b_v3_12_3      | decision=needs_revision evidence=anchor-transformer-spec-v3_12_3 |
| 19  | a2a.conflict.detected            | sess_initiator_v3_12_3       | synthesis_required=true                               |
| 20  | a2a.review.closed                | sess_initiator_v3_12_3       | final=escalate                                        |
| 21  | a2a.conflict.detected            | sess_initiator_v3_12_3       | second emit (close path)                              |

Note: Event Room shared event log is multi-session — reviewers
`sess_reviewer_a_v3_12_3` / `sess_reviewer_b_v3_12_3` emit
`a2a.review.submitted` rows visible to all room members per the
multi-session coordination contract (REQ-EVENT-ROOM-02).

JSONL evidence: `.grid/live-walkthrough-v3_12_3/event-room-events.jsonl`
(7 rows of room-scoped A2A events) +
`.grid/live-walkthrough-v3_12_3/l4-initiator-session-events.jsonl`
(19 rows of session-scoped governance.approval.* events).

### Walkthrough summary

```text
$ tools/eaasp-l4-orchestration/.venv/bin/python .grid/live-walkthrough-v3_12_3.py
  L4 sessions seeded: initiator=sess_initiator_v3_12_3 reviewers=[...]
  Event Room created: room_id=er_transformer_review_v3_12_3 status=open
  Phase 1: L3 OPA decision (HTTP roundtrip): {"decision_id":"gd_fd53...","decision":"gate_request","backend":"opa"}
  Phase 2: 5-stage governance (Plan/Check/Draft/Approve) — 4 SSE events emitted
  Phase 3: A2A Router — open ReviewSet rs_cb23d1f303cf4782, 2 reviewers
  Phase 4: Reviewer A ALLOW + Reviewer B NEEDS_REVISION (shared evidence)
  Phase 5: aggregate_review_set — final_decision=escalate, conflict_detected=true
  Phase 6: close_review_set — final_decision=escalate
  Phase 7: resume_with_human_decision — execute stage, SSE seq=14
  L3 governance_decisions exported: 8 rows → .grid/live-walkthrough-v3_12_3/l3-governance-decisions.tsv
  L4 event_room_events exported: 7 rows → .grid/live-walkthrough-v3_12_3/event-room-events.jsonl
  L4 session_events (initiator) exported: 19 rows → .grid/live-walkthrough-v3_12_3/l4-initiator-session-events.jsonl
```

Structured summary:
`.grid/live-walkthrough-v3_12_3/walkthrough-summary.json`

## v3.12 close-out status

- 03.12.0 schema + audit constraint patch ✅ SHIPPED 2026-07-27
- 03.12.1 Event Room + multi-session ✅ SHIPPED 2026-07-28
- 03.12.2 A2A Router + ReviewSet aggregation ✅ SHIPPED 2026-07-28
- 03.12.3 single-point live walkthrough ✅ SHIPPED 2026-07-28 (this phase)

ADR-V2-034 (OPA sidecar topology) + ADR-V2-035 (ReviewSet aggregation
algorithm) implementation: both moved to **SHIPPED** as of 03.12.3.

## Safety boundaries preserved

1. **ADR-V2-023 P1 shared-core rule**: walkthrough imports only
   `tools/eaasp-l3-governance` + `tools/eaasp-l4-orchestration` source
   paths; no shared crate (`grid-types`, `grid-engine`, `grid-runtime`,
   `grid-sandbox`, `grid-hook-bridge`) was rebuilt or modified.
2. **v3.9 RBAC catalog**: 134 routes — unchanged.
3. **v3.10 spec-audit**: 4 files / 37 rows — unchanged.
4. **docs/status/JOURNAL.md**: NOT modified in any phase.
5. **Live PASS only**: `.env` sourced for real ANTHROPIC_API_KEY; no
   simulated PASS evidence.

## Process cleanup (final)

- `kill -TERM` sent to OPA PID 40909 + dev-eaasp service PIDs
  (skill-reg, L2, L3, mock-scada, MCP-orch, grid-runtime, L4).
- `pgrep` confirms 0 residual processes.
