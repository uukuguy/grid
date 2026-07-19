# S5: Parallel batch

> **Scenario ID:** S5
> **Quickstart invocation:** `grid quickstart S5`
> **Acceptance marker (CONTEXT.md D-01):** `grid run --parallel` (or
> equivalent) launches N agents; results aggregated.

## Prerequisites

- One of: `OPENAI_API_KEY=...` or `ANTHROPIC_API_KEY=...`
- (Optional) `OPENAI_NO_PROXY=1` if on macOS + Clash proxy

## CLI invocation

```bash
export OPENAI_API_KEY=sk-...

# Via quickstart (default N=3)
grid quickstart S5

# Or directly via grid run --parallel
grid run --parallel 3    # launches 3 parallel agents
```

## What happens

1. `execute_init` + `run_doctor` pre-flight.
2. `run_s5_parallel_batch` calls `execute_run(RunOptions { parallel: Some(3),
   .. })`.
3. `execute_run` (in `crates/grid-cli/src/commands/run.rs`) detects
   `parallel.is_some()` and dispatches to `run_parallel(n, opts, state)`.
4. `run_parallel` spawns N `tokio::spawn` tasks, each calling `execute_ask`
   with the prompt:
   > Summarize the README.md file (parallel agent #i/N)
5. Aggregates results: prints `Parallel summary: X succeeded, Y failed (total N)`.

## Expected output

```
grid quickstart: running scenario S5 (retry=false, json=false)
[doctor output]
=== S5: Parallel batch ===
Launching 3 parallel agents...
[Agent 1/3] <output of execute_ask run #1>
[Agent 2/3] <output of execute_ask run #2>
[Agent 3/3] <output of execute_ask run #3>

Parallel summary: 3 succeeded, 0 failed (total 3)
=== S5 complete ===
```

If any agent fails:

```
Parallel summary: 2 succeeded, 1 failed (total 3)
Error: 1 of 3 parallel agents failed
```

## Acceptance verification

- **PASS** if `grid run --help` mentions `--parallel` flag (REQ-AUDIT-02,
  verified by `tests/S5_parallel_batch.rs`).
- **PASS** if `grid run --parallel 3` launches 3 agents concurrently and prints
  `Parallel summary: 3 succeeded, 0 failed`.
- **PASS** if failure of one agent prints `X of N parallel agents failed` and
  exits non-zero (REQ-AUDIT-06 via run_parallel's `anyhow::bail`).
- **FAIL** if the agents run sequentially (no concurrency observable).

## Known gaps

- Results aggregation is currently a count summary. Detailed per-agent output
  (text + tool calls interleaved) is in scope for a follow-up phase if needed.
- The default batch size in `quickstart S5` is hard-coded to 3. To change,
  call `grid run --parallel <N>` directly.

## Per-agent isolation

Each parallel agent runs in its own `tokio::spawn` with a cloned `AppState`.
The shared DB connection (via `session_store.get_shared_connection`) is
thread-safe (Phase 7.2 Plan 01 verified). No cross-agent state corruption.

Generated-By: Claude (claude-opus-4-8) via Claude Code CLI