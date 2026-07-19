# S2: Memory-driven session

> **Scenario ID:** S2
> **Quickstart invocation:** `grid quickstart S2`
> **Acceptance marker (CONTEXT.md D-01):** Recall hit visible in output;
> `grid memory list` shows the written anchor.

## Prerequisites

- One of: `OPENAI_API_KEY=...` or `ANTHROPIC_API_KEY=...`
- (Optional) `OPENAI_NO_PROXY=1` if on macOS + Clash proxy

## CLI invocation

```bash
export OPENAI_API_KEY=sk-...
grid quickstart S2
```

## What happens

1. `execute_init` + `run_doctor` pre-flight.
2. `run_s2_memory_driven`:
   - **Step 1/2:** Writes a memory anchor — `"User prefers brief answers"`,
     tagged `preferences` — via `grid memory add`.
   - **Step 2/2:** Invokes `execute_ask` with the prompt
     `"Based on my preferences, what's the best way to summarize?"` —
     the agent should reference the stored preference in its answer.

## Expected output

```
grid quickstart: running scenario S2 (retry=false, json=false)
[doctor output]
=== S2: Memory-driven session ===
Step 1/2: grid memory add — write preference anchor
  Added memory: User prefers brief answers (id: <uuid>)
Step 2/2: grid ask — recall preference in same session
[Assistant] Based on your stored preference for brief answers, the best way
to summarize is: lead with the headline, then 1-2 sentences of supporting
context, then a bullet list of key points.
=== S2 complete (in-session; cross-session resume ships in Plan 02 Task 3) ===
```

After S2, `grid memory list` should show the anchor:

```bash
$ grid memory list
ID                                   | TAGS         | CONTENT
--------------------------------------+--------------+---------------------------------
<uuid>                                | preferences  | User prefers brief answers
```

## Acceptance verification

- **PASS** if `grid memory list` shows the anchor after S2 runs.
- **PASS** if the assistant's response references the stored preference
  ("brief", "short", "concise", etc.).
- **FAIL** if `grid memory add` silently fails (the new typed-error path via
  REQ-AUDIT-08 should surface a clear error if the write fails).

## Cross-session resume (Phase 3.7.1 Task 3)

After `grid quickstart S2` succeeds, the assistant response is anchored to
the current session. To exercise **cross-session recall** (i.e. recall after
process restart):

```bash
# Find the session ID
grid session list

# In a fresh shell:
grid session resume <session-id>
# → prints last assistant message + history count + suggests `grid ask --session <id>`
```

The session resume path is wired by `grid session resume <id>`
(`crates/grid-cli/src/commands/session.rs` `resume_session` function).

## Known gaps

- Per Phase 3.7.1 audit, S2 in `grid quickstart S2` runs in-session (write +
  read in same session). The cross-session resume subcommand ships in Plan 02
  Task 3 (REQ-AUDIT-01) — already implemented but the quickstart S2 doesn't
  trigger it automatically.

Generated-By: Claude (claude-opus-4-8) via Claude Code CLI