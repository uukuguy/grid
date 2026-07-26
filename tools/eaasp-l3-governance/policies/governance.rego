# Package: governance
# Owner: EAASP L3 governance
# Status: SHIPPED 2026-07-26 (v3.11.1)
#
# v2.0 spec reference:
#   - §6.1   Risk classification (read / write_local / write_external)
#   - §6.9   Three-state decision (allow / approval / deny)
#   - §6.10  Allow-auto for read; require approval for write in enforce mode
#   - §15.9  Deny-always-wins (any "deny" rule wins over an "allow" rule)
#
# Topology reference: ADR-V2-034 (Accepted 2026-07-26) — sidecar OPA on
# 127.0.0.1:18181; this bundle is loaded by `opa run -s -b policies/`
# (or by the v3.11.3 make dev-eaasp orchestration) and queried via
# POST /v1/data/governance/decision.
#
# Compatibility: the response envelope
#   { allow: bool, decision: "allow"|"approval"|"deny",
#     reason: string, obligations: [string] }
# matches the OPABackend._parse_opa_response contract in
# tools/eaasp-l3-governance/src/eaasp_l3_governance/opa_backend.py.
# DO NOT change the field names or the decision enum without bumping
# the adapter — see ADR-V2-034 §Decision item 4.
package governance

import rego.v1

# ─── Risk classification helpers ──────────────────────────────────────────

# read: passive observation (no side effect). Always allowed; no approval.
is_read if input.risk_level == "read"

# write_local: file/process state change in the agent's own context.
# May be allowed in shadow mode, requires approval in enforce mode.
is_write_local if input.risk_level == "write_local"

# write_external: any side effect that escapes the agent's own context
# (SCADA, external API, outbound network). Always requires approval in
# enforce mode; never auto-allowed.
is_write_external if input.risk_level == "write_external"

# Mode is declared in the managed-hook; shadow mode records decisions but
# does not block (per audit §5.2).
is_shadow if input.mode == "shadow"

# ─── Decision: single chained rule ─────────────────────────────────────────
#
# Each `else` branch only fires if the previous branch's body did not
# match. This produces exactly one ``decision`` value per input — the
# rego.v1 requirement for complete rules.
#
# Order encodes the precedence:
#   1. Deny-list (tools + patterns) — wins always (spec §15.9)
#   2. Read risk — auto-allow (spec §6.10)
#   3. Write in shadow — allow + audit obligation (audit §5.2)
#   4. Write in enforce — approval (spec §6.10)
#   5. Default — deny
default decision := {"allow": false, "decision": "deny", "reason": "default deny (no rule matched)", "obligations": []}

decision := result if {
    input.tool_name in {"rm_rf", "format_disk", "drop_table", "shutdown_host", "kill_all_sessions"}
    result := {
        "allow": false,
        "decision": "deny",
        "reason": sprintf("tool %v is on the deny-list (spec §15.9)", [input.tool_name]),
        "obligations": ["log:incident", "alert:security"],
    }
} else := result if {
    contains(input.action_preview, "rm -rf /")
    result := {
        "allow": false,
        "decision": "deny",
        "reason": "action_preview matches a destructive pattern (spec §15.9)",
        "obligations": ["log:incident", "alert:security"],
    }
} else := result if {
    contains(input.action_preview, "DROP TABLE")
    result := {
        "allow": false,
        "decision": "deny",
        "reason": "action_preview matches a destructive pattern (spec §15.9)",
        "obligations": ["log:incident", "alert:security"],
    }
} else := result if {
    is_read
    result := {
        "allow": true,
        "decision": "allow",
        "reason": "read risk auto-allowed (spec §6.10)",
        "obligations": [],
    }
} else := result if {
    not is_read
    is_shadow
    result := {
        "allow": true,
        "decision": "allow",
        "reason": sprintf("shadow mode permits %v (audit §5.2)", [input.risk_level]),
        "obligations": ["log:shadow"],
    }
} else := result if {
    not is_read
    not is_shadow
    input.mode == "enforce"
    result := {
        "allow": false,
        "decision": "approval",
        "reason": sprintf("%v in enforce mode requires human approval (spec §6.10)", [input.risk_level]),
        "obligations": ["notify:admin"],
    }
}

# ─── Internal: convenience rule for tests / audit trail ────────────────────

# Read-only summary used by the audit ledger and the certifier harness.
# Each rule is a complete rule (rego.v1) so the head binds a single value
# derived from input; the rules are evaluated independently and the
# rego.v1 grounding is satisfied because input is referenced inside the
# body of every rule.
risk_class := "passive" if is_read
risk_class := "local_side_effect" if is_write_local
risk_class := "external_side_effect" if is_write_external
