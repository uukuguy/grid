# Grid CLI Quickstart

> **Audience:** CTOs, leads, evaluators — non-developer observers who want to
> drive an agent end-to-end in under 5 minutes without touching the codebase.
>
> **Prerequisites:** Rust 1.75+, an LLM API key in env (see [Scenarios](#scenarios)
> for per-scenario env requirements), ~2 minutes.

This doc mirrors what `grid quickstart` does programmatically. Use whichever
interface fits your workflow:

- **CLI path:** `grid quickstart <scenario>` — pre-flight + run.
- **Doc path:** this file + the per-scenario walkthrough docs under
  `docs/cli/scenarios/S{1..5}-*.md`.

---

## Scenarios

| ID | Scenario | CLI invocation | Walkthrough doc |
|----|----------|----------------|-----------------|
| S1 | Multi-step tool use | `grid quickstart S1` (default) | [S1-multi-step-tool-use.md](scenarios/S1-multi-step-tool-use.md) |
| S2 | Memory-driven session | `grid quickstart S2` | [S2-memory-driven-session.md](scenarios/S2-memory-driven-session.md) |
| S3 | Hook-driven governance | `grid quickstart S3` | [S3-hook-driven-governance.md](scenarios/S3-hook-driven-governance.md) |
| S4 | Streaming stop/resume | `grid quickstart S4` | [S4-streaming-stop-resume.md](scenarios/S4-streaming-stop-resume.md) |
| S5 | Parallel batch | `grid quickstart S5` | [S5-parallel-batch.md](scenarios/S5-parallel-batch.md) |
| S6 | MCP live log streaming | `grid mcp logs <name> [--follow] [--level error] [--output json]` | [S6-mcp-logs.md](scenarios/S6-mcp-logs.md) |
| S7 | Web dashboard production usability | (browser + `npm run dev` + grid-server) | [S7-web-dashboard.md](scenarios/S7-web-dashboard.md) |

---

## Prerequisites

### Required env vars (one of the LLM provider pair)

```bash
# Option A: OpenAI / OpenRouter
export OPENAI_API_KEY=sk-...
export LLM_PROVIDER=openai    # default; can be omitted

# Option B: Anthropic
export ANTHROPIC_API_KEY=sk-ant-...
export LLM_PROVIDER=anthropic
```

### Optional env vars

```bash
# macOS Clash proxy workaround (only if you're behind a Clash proxy on
# localhost — disable for other networks)
export OPENAI_NO_PROXY=1
export ANTHROPIC_NO_PROXY=1
export GRID_LLM_NO_PROXY=1

# S3 (hook-driven governance) requires this:
export GRID_HOOKS_FILE=./hooks.yaml
```

### Build

```bash
cd /path/to/grid-sandbox
cargo build -p grid-cli --release
# binary lands at target/release/grid
```

---

## Quick start (S1)

The fastest path: S1 (multi-step tool use) — no special env, just an API key.

```bash
export OPENAI_API_KEY=sk-...
./target/release/grid quickstart
# → runs pre-flight + multi-step tool use against README.md + docs/cli/
# expected output: tool calls observed, final assistant summary visible
```

If anything fails, the error output format is:

```
error: <human-readable cause>
fix:   grid doctor --repair
hint:  transient, retry with --retry    # only for retryable errors
```

In CI / scripts (non-TTY stderr), the same error renders as JSON:

```json
{"class":"retryable","message":"...","fix":"grid doctor --repair","code":5}
```

---

## Other scenarios

For S2-S5, see the per-scenario walkthrough docs linked above. Each has:
- Prerequisites (which env vars + config files)
- Exact CLI invocation
- Expected output sketch
- Known gaps at audit time (per Phase 3.7.1 audit @ `docs/audit/3.7.1-GAP-AUDIT.md`)

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Authentication failed: bad key` | Wrong/missing API key | `grid auth login` (sets OPENAI_API_KEY) |
| `Session not found: <id>` | Resume used wrong session ID | `grid session list` (then use a valid id) |
| `GRID_HOOKS_FILE not set` | S3 needs hooks config | `export GRID_HOOKS_FILE=./hooks.yaml` |
| `grid eval run` prints cargo instructions | REQ-AUDIT-03 stub | Use `cargo run -p octo-eval -- run --suite <name>` instead (until REQ-AUDIT-03 ships) |
| `grid mcp logs` says "live log streaming not yet available" | REQ-AUDIT-04 stub | No fix yet (track REQ-AUDIT-04) |
| `error: ... fix: grid doctor --repair` | Generic failure | Run `grid doctor --repair` for actionable next step |
| macOS + port 502 on localhost | Clash proxy intercepting | `export OPENAI_NO_PROXY=1` |

For deeper diagnostics, run `grid doctor` (12 checks; see
`docs/audit/3.7.1-GAP-AUDIT.md` REQ-AUDIT-07 for the Hooks File + Eval Bridge
checks).

---

## Production-usability score

Per Phase 3.7.1 acceptance standard: all 5 scenarios should PASS end-to-end on a
clean checkout with documented env vars. The dated audit record at
`docs/status/PRODUCTION_USABILITY_<date>.md` captures the live walkthrough
results for each Phase 3.7.1 release.

Generated-By: Claude (claude-opus-4-8) via Claude Code CLI