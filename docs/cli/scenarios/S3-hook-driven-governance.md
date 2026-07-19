# S3: Hook-driven governance

> **Scenario ID:** S3
> **Quickstart invocation:** `grid quickstart S3`
> **Acceptance marker (CONTEXT.md D-01):** Hook decision prompt visible;
> approve path works without manual config tweaking.

## Prerequisites

- One of: `OPENAI_API_KEY=...` or `ANTHROPIC_API_KEY=...`
- **REQUIRED:** `GRID_HOOKS_FILE` env var pointing to a valid hooks config file
- A hooks config that defines a `PreToolUse` rule that pauses for approval

## CLI invocation

```bash
export OPENAI_API_KEY=sk-...
export GRID_HOOKS_FILE=./hooks.yaml

# Minimal hooks.yaml for S3:
cat > hooks.yaml <<EOF
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: prompt
          prompt: "Approve this destructive command? (y/n)"
EOF

grid quickstart S3
```

## What happens

1. `execute_init` + `run_doctor` pre-flight. **doctor now validates
   `GRID_HOOKS_FILE`** (REQ-AUDIT-07) — check 11 reports Pass/Warn/Fail
   depending on file existence and readability.
2. `run_s3_hook_governance`:
   - If `GRID_HOOKS_FILE` is not set → prints actionable error and exits 1.
   - Otherwise invokes `execute_ask` with a prompt that triggers a PreToolUse
     hook: `"Delete /tmp/test_quickstart_s3.txt using rm — but pause for
     approval first."` The agent attempts the `rm` action, the hook fires,
     the user sees an approval prompt in stderr, and decides y/n.

## Expected output

```
grid quickstart: running scenario S3 (retry=false, json=false)
[doctor output — should include Hooks File check]
=== S3: Hook-driven governance ===
GRID_HOOKS_FILE detected. Invoking execute_ask with PreToolUse-triggering prompt.
[ToolCall] Bash(command="rm /tmp/test_quickstart_s3.txt")
[Hook: PreToolUse] Approve this destructive command? (y/n)
> y
[ToolResult] Bash: <output of rm>
[Assistant] <acknowledgment of action>
=== S3 complete ===
```

## Acceptance verification

- **PASS** if the user sees `[Hook: PreToolUse]` prompt in stderr WITHOUT
  needing to manually edit any config file beyond `hooks.yaml`.
- **PASS** if `grid doctor` reports `Hooks File: ./hooks.yaml (N bytes)` as
  Pass — confirming check 11 (REQ-AUDIT-07) is wired.
- **FAIL** if `GRID_HOOKS_FILE` is unset and `quickstart S3` exits with a
  generic error (instead of the actionable "GRID_HOOKS_FILE not set" message).
- **FAIL** if the agent runs the rm command without pausing (no hook
  integration).

## Known gaps

- The hooks.yaml format is custom — the file is loaded by `grid-server` /
  `grid-runtime` and parsed by the hook execution layer. See
  `crates/grid-engine/src/hooks/` for parser details.
- The PreToolUse matcher syntax follows the existing `grid-runtime` hook
  envelope (ADR-V2-006). For S3, only `Bash` matcher with `prompt` type
  hooks is tested; other matchers (`Write`, `Edit`, etc.) may require
  additional hooks.yaml tuning.

Generated-By: Claude (claude-opus-4-8) via Claude Code CLI