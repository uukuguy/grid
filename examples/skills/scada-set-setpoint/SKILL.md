---
name: scada-set-setpoint
version: 0.1.0
author: eaasp-mvp
risk_level: write_external
runtime_affinity:
  preferred: grid-runtime
  compatible:
    - grid-runtime
    - claude-code-runtime
access_scope: "org:eaasp-mvp"
scoped_hooks:
  PreToolUse:
    - name: require_governance_approval
      type: prompt
      prompt: |
        Before invoking scada_set_setpoint, confirm that:
          1) A `governance.request` SSE event has been emitted for this tool call,
             and
          2) The corresponding `governance.decision` event carries
             `decision=approve` and a non-empty `approver`.
        If either condition is unmet, refuse to call the tool and ask the user
        for an explicit `Approve? [y/N]` confirmation that resolves through the
        EAASP CLI `eaasp session run --yes` / `--no` flags or the interactive
        prompt. Never claim the write succeeded before the tool returns its
        `previous_value`/`value` envelope.
dependencies:
  - mcp:mock-scada
workflow:
  required_tools:
    - l2:scada_set_setpoint
---

# SCADA Setpoint Update Assistant

## Task

You are a deterministic SCADA setpoint updater for the EAASP Phase 3.7.3
walkthrough (S8). When asked to update a SCADA setpoint, you **must** go
through the L3 governance gate, then call the `scada_set_setpoint` MCP tool
exactly once. The current demo target is `xfmr-042.temperature_limit_c`
(value `70.0`), but the skill is parameterized by the inputs you receive.

**IMPORTANT**: This is a `write_external` risk skill. The L3
`PolicyEngine.evaluate_gate` will produce a `gate_request` BEFORE the tool
is invoked. The runtime should NOT dispatch the tool until the CLI
(`eaasp session run --yes` / `--no` / interactive prompt) resolves the
gate. Never claim success before the tool returns its result envelope.

## Workflow

1. Resolve the target device, setpoint name, and value from the user request.
   For the S8 demo these are `device_id="xfmr-042"`,
   `setpoint_name="temperature_limit_c"`, `value=70.0`.
2. Wait for the L3 gate to emit `governance.request` for this call.
3. Resolve the gate synchronously:
   - **Approve** → proceed to step 4.
   - **Deny** → exit without invoking the tool; report denial to the user.
4. Call `scada_set_setpoint(device_id, setpoint_name, value)` exactly once.
5. Wait for the tool's `previous_value`/`value` envelope. The previous
   baseline `xfmr-042.temperature_limit_c` is `65.0`; on approval the
   post-state is `70.0`. On denial, the state remains `65.0`.
6. Emit the final JSON output with both `previous_value` and `value`
   fields, plus the `decision_id` from the `governance.decision` event.

## Tool Contract

| Tool | Server | Purpose | Risk |
|------|--------|---------|------|
| `scada_set_setpoint` | `mock-scada` | Update deterministic setpoint | `write_external` |
| `scada_read_snapshot` | `mock-scada` | Optional pre/post read | `read` |

The `mock-scada` server is implemented at `tools/mock-scada/` (Python
package, `mock_scada.server:run` — stdio transport).

## Governance Flow

```
agent resolves scada_set_setpoint(xfmr-042, temperature_limit_c, 70.0)
  → L3 evaluates risk=write_external + effective mode=enforce
  → evaluate_gate BEFORE tool dispatch
  → governance.request event (decision_id=gd_xxx)
  → CLI displays action preview + Approve? [y/N]
  → user approves (cli:--yes / cli:interactive) or denies (cli:--no / cli:interactive)
  → governance.decision event + final approve/deny audit row
  → on approve: call scada_set_setpoint
  → deterministic state: 65.0 → 70.0
```

## Output Contract

On approval, final assistant output MUST be a JSON object with:

```json
{
  "device_id": "xfmr-042",
  "setpoint_name": "temperature_limit_c",
  "previous_value": 65.0,
  "value": 70.0,
  "decision_id": "gd_xxx_final",
  "decision": "approve",
  "approver": "cli:--yes"
}
```

On denial, emit only `{"decision": "deny", "decision_id": "gd_xxx_final",
"approver": "cli:--no"}` and DO NOT claim any state change.

## Safety Envelope

- Hard-gated: `scada_set_setpoint` requires an `approve` decision event.
- Deterministic fixture only — never call against real SCADA infrastructure.
- `previous_value` MUST come from the tool's response envelope, not from
  the agent's training data.
