# S4: Streaming stop/resume

> **Scenario ID:** S4
> **Quickstart invocation:** `grid quickstart S4`
> **Acceptance marker (CONTEXT.md D-01):** `grid session run` streams chunks;
> Ctrl-C + `grid session resume <id>` recovers state.

## Prerequisites

- One of: `OPENAI_API_KEY=...` or `ANTHROPIC_API_KEY=...`
- A previously-created session (S4 creates one for you; the resume step is
  manual via `grid session resume <id>`)

## CLI invocation

```bash
export OPENAI_API_KEY=sk-...

# Step 1: create a session + see the ID
grid quickstart S4
# → "Session: <id>" printed at the end

# Step 2: in a fresh shell, exercise resume
grid session resume <id>
```

Or, for the full streaming + stop + resume cycle (more advanced, requires
`grid run` REPL mode):

```bash
# Start streaming REPL with a session
grid run --session <id>

# The agent streams tool calls + assistant chunks to stderr
# Press Ctrl-C to interrupt

# Resume in a new shell
grid session resume <id>
```

## What happens

1. `execute_init` + `run_doctor` pre-flight.
2. `run_s4_streaming_stop_resume`:
   - Calls `handle_session(SessionCommands::Create { name: "quickstart-s4" })`
   - Prints `Session: see `grid session list` for the new ID.`
   - Prints `To exercise resume, run: grid session resume <id>`
3. After S4 completes, the user runs `grid session resume <id>` manually.
4. `resume_session` (in `crates/grid-cli/src/commands/session.rs`):
   - Loads the session from `session_store.get_session(&sid)`
   - Loads message history via `session_store.get_messages(&sid)`
   - Prints `Resuming session: <id> (N messages)`
   - Prints the last assistant message from history
   - Suggests `grid ask --session <id>` to continue

## Expected output (S4 step)

```
grid quickstart: running scenario S4 (retry=false, json=false)
[doctor output]
=== S4: Streaming stop/resume ===
Creating session 'quickstart-s4' ...
Session: see `grid session list` for the new ID.
To exercise resume, run: grid session resume <id>
=== S4 scaffolding complete (full resume wires in Plan 02 Task 3) ===
```

## Expected output (resume step)

```
$ grid session resume <id>
Resuming session: <id> (3 messages)
Last assistant message:
  <last assistant text from the session>

To continue, run: grid ask --session <id>
```

## Acceptance verification

- **PASS** if `grid session resume <id>` prints `Resuming session: <id> (N
  messages)` (REQ-AUDIT-01).
- **PASS** if the last assistant message is shown without error.
- **PASS** if `grid session resume nonexistent-id` exits with code 4 (typed
  `GridError::session_not_found` from Task 2's error UX) and prints:
  ```
  error: Session not found: nonexistent-id
  fix:   grid session list (then resume a valid session id)
  ```
- **FAIL** if `grid session resume` returns silently or with exit 0 on a
  missing session ID (REQ-AUDIT-09 silent-error parity bug).

## Known gaps

- The full streaming REPL cycle (`grid run` → Ctrl-C → `grid session resume`)
  is not auto-walked through by `grid quickstart S4` because Ctrl-C handling
  requires an interactive TTY. The scaffolding creates the session; manual
  resume via `grid session resume <id>` exercises the core functionality.
- Per audit, REQ-AUDIT-09 (silent `show_agent_info` bug) is fixed in
  Plan 02 Task 4 — `agent` ops now return typed `GridError::agent_not_found`.

Generated-By: Claude (claude-opus-4-8) via Claude Code CLI