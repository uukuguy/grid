# S8 — Risk-classified External Write

> **Scenario:** A grid agent asks the EAASP local stack to update a SCADA
> setpoint. The setpoint is `xfmr-042.temperature_limit_c`, the proposed
> value is `70.0` (canonical S8 demo), and the skill declares
> `risk_level: write_external`. The L3 governance gate pauses the call
> BEFORE the tool side effect executes; the CLI (or automation flag)
> resolves the gate synchronously; the deterministic mock-SCADA state
> changes from `65.0` to `70.0` only on approval.
>
> **Validation standard:** This is the only walkthrough scenario
> delivered by Phase 3.7.3. Per ROADMAP.md §3.7.3, "1 实战 enterprise
> scenario (e.g. agent writes to external system, governance gate triggers,
> user approves, action completes) runs end-to-end through EAASP local
> tools with observable governance behavior."

This walkthrough is intentionally written for a non-developer observer.
You should be able to run it after ~10 minutes of setup; nothing below
requires touching the L1 protocol, the L3 HTTP surface, or any grid-server
code.

## What you'll observe

1. The skill manifest declares a write-class risk; without that metadata
   the action would have been auto-allowed.
2. The L3 governance gate produces a `gate_request` audit row and a
   `governance.request` SSE event BEFORE the SCADA tool is invoked.
3. The CLI prints a `Approve? [y/N]` block with the proposed tool name,
   risk class, and a deterministic action preview.
4. Approval resolves the gate to `approve`, persists a separate
   `approve` audit row, emits a `governance.decision` SSE event, and
   only then invokes the tool.
5. The mock-SCADA setpoint transitions from `65.0` to `70.0`. On
   denial, the tool is never called and the state stays at `65.0`.

## Prerequisites

A clean checkout of the repository plus the following environment:

| Variable | Required | Purpose |
|----------|----------|---------|
| `EAASP_SKILL_URL` | optional | URL of the running skill-registry service (default `http://127.0.0.1:18081`). |
| `EAASP_L3_URL` | optional | URL of the running L3 governance service (default `http://127.0.0.1:18083`). |
| `EAASP_L4_URL` | optional | URL of the running L4 orchestration service (default `http://127.0.0.1:18084`). |
| `OPENAI_API_KEY` | optional | If unset, the live LLM path is unavailable; the hermetic CLI tests still run. |
| `ANTHROPIC_API_KEY` | optional | Same as above for Anthropic providers. |

No real customer endpoints, credentials, or production SCADA gateways
are touched. The fixture values are deterministic neutral values
(`xfmr-042`, `temperature_limit_c`, `65.0` → `70.0`).

## Phase 0 — Deploy the skill

The skill manifest lives at
`examples/skills/scada-set-setpoint/SKILL.md`. Deploy it via the EAASP
CLI exactly like any other skill:

```bash
eaasp skill submit examples/skills/scada-set-setpoint/
eaasp skill promote scada-set-setpoint 0.1.0 reviewed
```

The first command submits the draft. The second promotes it to
`reviewed` status so the runtime can resolve it during session creation.
The skill manifest declares:

- `risk_level: write_external`
- `workflow.required_tools: [l2:scada_set_setpoint]`
- A `PreToolUse` scoped hook that requires governance approval before
  the tool is invoked.

If the skill-registry service is not running locally, the CLI will
return exit code `3` (`service unavailable`) — start the registry
per the project's normal `make dev-eaasp` flow.

## Phase 1 — Deploy an enforce policy

Before the agent loop can trigger the gate, an enforce-mode hook must
be deployed to L3. A minimal policy looks like:

```json
{
  "version": "v3.7.3-s8",
  "hooks": [
    {
      "hook_id": "h_pre_set_setpoint",
      "phase": "PreToolUse",
      "mode": "enforce",
      "agent_id": "*",
      "skill_id": "scada-set-setpoint",
      "handler": "python:eaasp_l3_governance.gate:evaluate"
    }
  ]
}
```

Deploy via the CLI:

```bash
eaasp policy deploy /path/to/s8-policy.json
```

The policy registers an enforce hook that targets the
`scada-set-setpoint` skill. The L3 policy engine will require a
`gate_request` audit row and a synchronous CLI approval for every
`scada_set_setpoint` invocation.

## Phase 2 — Run the scenario

The exact CLI invocation (single command, single session):

```bash
eaasp session run \
  -s scada-set-setpoint \
  -r grid-runtime \
  "Update xfmr-042 temperature_limit_c to 70.0"
```

You should see output similar to:

```
session created: sess_…  (dim)
[governance] Risk-classified action requested:
  tool:   scada_set_setpoint
  risk:   write_external
  effect: will write to deterministic mock-SCADA (xfmr-042/temperature_limit_c=70.0)
Approve? [y/N]:
```

If the prompt is missing, you are running in a non-interactive
environment and need to pass `--yes` or `--no` explicitly (see below).

### Approving the action

Press `y` and `Enter`. The CLI resolves the gate to `approve`, the
final audit row is persisted, and the SSE stream emits a
`governance.decision` event. The mock-SCADA state transitions from
`65.0` to `70.0`.

### Denying the action

Press `Enter` (or `n`) — the safe default is No. The CLI exits with
code `4` and prints a denial summary. The mock-SCADA state stays at
`65.0` and no tool call is made.

### Non-interactive automation

For batch or automation use:

```bash
# Auto-approve
eaasp session run --yes -s scada-set-setpoint -r grid-runtime \
  "Update xfmr-042 temperature_limit_c to 70.0"

# Auto-deny
eaasp session run --no -s scada-set-setpoint -r grid-runtime \
  "Update xfmr-042 temperature_limit_c to 70.0"
```

Both flags produce the same observable evidence as the interactive
prompt — the only difference is the `approver` field in the final
audit row:

| Path | approver string |
|------|-----------------|
| `--yes` | `cli:--yes` |
| `--no` | `cli:--no` |
| Interactive `y` | `cli:interactive` |
| Interactive Enter / `n` | `cli:interactive` (deny) |

### Flag conflicts

If both `--yes` and `--no` are passed, the CLI exits with code `2`
BEFORE creating a session:

```
$ eaasp session run --yes --no -s scada-set-setpoint -r grid-runtime "..."
Error: --yes and --no are mutually exclusive
exit=2
```

## Phase 3 — Inspect the audit ledger

After a successful run, the L3 SQLite database contains two rows for
the gate_request and one for the final approve decision:

```sql
SELECT decision_id, session_id, hook_id, tool_name, risk_level,
       decision, approver, rationale, ts
FROM governance_decisions
WHERE session_id = 'sess_…'
ORDER BY ts DESC;
```

Expected output (shape):

| decision_id | risk_level | decision | approver | rationale |
|-------------|------------|----------|----------|-----------|
| `gd_<uuid>_final` | write_external | approve | cli:--yes | resolved request gd_<uuid>: cli --yes |
| `gd_<uuid>` | write_external | gate_request | NULL | approval required |

The two rows have distinct `decision_id` values — final decisions
**never** overwrite request rows (per audit §6.3).

## Phase 4 — Observe the L4 events

The SSE event stream exposes the same lifecycle:

```bash
eaasp session show sess_…
```

Look for two events with `event_type` exactly `governance.request`
and `governance.decision`:

```
[hh:mm:ss] governance.request      decision_id=gd_xxx hook_id=h_pre_… tool_name=scada_set_setpoint risk_level=write_external
[hh:mm:ss] governance.decision     decision_id=gd_xxx_final decision=approve approver=cli:--yes
```

Both events are best-effort (audit §7.1); if the event append fails
the gate decision still stands and the L3 audit ledger remains
authoritative.

## Phase 5 — Verify the state change

The mock-SCADA service exposes the post-state via the deterministic
snapshot helper:

```bash
python -c "from mock_scada.snapshots import get_setpoint; print(get_setpoint('xfmr-042', 'temperature_limit_c'))"
```

Expected output: `70.0` after approval, `65.0` after denial.

## Failure indicators

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Approve? [y/N]` does not appear | Skill manifest is missing `risk_level: write_external` | Re-deploy the skill with the frontmatter field set |
| `[error] runtime error: governance_decisions: no such table` | L3 database was created before Phase 3.7.3 | Re-run `init_db` so the new DDL is applied |
| Tool was called without a prompt | Effective L3 mode is `shadow` | Flip the hook back to `enforce` via `eaasp policy mode <hook_id> enforce` |
| `--yes` flag returns exit 4 | A previous `gate_request` row was deleted manually | Restore from backup; the ledger is append-only |
| Event stream missing `governance.request` | L4 session ID mismatch | Verify `sess_…` matches the SSE tail |

## Cleanup

The hermetic test fixture is process-local. To reset the in-memory
SCADA setpoint back to `65.0`:

```bash
python -c "from mock_scada.snapshots import reset_setpoints_for_tests; reset_setpoints_for_tests()"
```

Restart the L3 service to wipe the audit ledger, or back up
`data/eaasp-l3.db` first if you want to preserve the trail.

## What this walkthrough does NOT demonstrate

This is the minimum credible Phase 3 governance gate. The following
capabilities remain deferred (per `docs/design/EAASP/EAASP_v2_0_EVOLUTION_PATH.md` §3.1
and Phase 3.7.3 CONTEXT.md §Out-of-scope):

- Full production OPA approval chain — Phase 3 ⏸
- Multi-party approval flows — v3.8+ candidate
- HTTP approval endpoints in L3 — D-06 forbids; CLI is the gate client
- L5 Cowork UI consumer of `governance.request` events — Phase 5 ⏸
- Sandbox tier enforcement — Phase 3 ⏸

The walkthrough is observable end-to-end and persists durable audit
evidence, but the gate itself runs in-process inside the EAASP CLI.
For production, swap the in-process `evaluate_gate` call for an HTTP
call to the OPA backend (or whatever future authority replaces it).

## Hermetic regression

A hermetic cross-component test exercises the same code paths without
needing a live LLM:

```bash
cd tools/eaasp-l3-governance
uv run pytest tests/test_gate_engine.py -k "s8" -x --tb=short
```

Two cases run: approve (state 65.0 → 70.0, two audit rows) and deny
(state stays 65.0, two audit rows, no tool call). Both must pass.

## Related files

| Path | Role |
|------|------|
| `examples/skills/scada-set-setpoint/SKILL.md` | Deployable S8 skill manifest |
| `tools/eaasp-l3-governance/src/eaasp_l3_governance/policy_engine.py` | `PolicyEngine.evaluate_gate` |
| `tools/eaasp-l3-governance/src/eaasp_l3_governance/managed_settings.py` | `RiskLevel` taxonomy + `ManagedHook.risk_level` |
| `tools/eaasp-l3-governance/src/eaasp_l3_governance/audit.py` | `AuditStore.record_governance_decision` |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/event_stream.py` | `emit_governance_request` / `emit_governance_decision` |
| `tools/eaasp-cli-v2/src/eaasp_cli_v2/cmd_session.py` | `_resolve_gate_request` + `--yes`/`--no` flags |
| `tools/mock-scada/src/mock_scada/server.py` | `scada_set_setpoint` MCP tool |
| `tools/eaasp-skill-registry/src/skill_parser.rs` | Rust `RiskLevel` enum + `V2Frontmatter.risk_level` |
| `docs/audit/3.7.3-GAP-AUDIT.md` | Frozen contracts this scenario implements |
