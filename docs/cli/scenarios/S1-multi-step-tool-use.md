# S1: Multi-step tool use

> **Scenario ID:** S1
> **Quickstart invocation:** `grid quickstart S1` (default scenario)
> **Acceptance marker (CONTEXT.md D-01):** Each tool call observable in CLI
> output without `--debug`.

## Prerequisites

- One of: `OPENAI_API_KEY=...` or `ANTHROPIC_API_KEY=...`
- (Optional) `OPENAI_NO_PROXY=1` if on macOS + Clash proxy

## CLI invocation

```bash
export OPENAI_API_KEY=sk-...
grid quickstart S1
# or equivalently:
grid quickstart   # S1 is the default
```

## What happens

1. `execute_init` — creates `.grid/` dirs and config files in cwd.
2. `run_doctor` — runs 12 health checks (LLM key, db, hooks file, eval bridge, etc).
3. `run_s1_multi_step_tool_use` — invokes `execute_ask` with the prompt:
   > Read the file README.md, summarize the first 5 lines, then list the files in
   > docs/cli/. Use tools.

The agent uses **2 tool calls** (file_read on README.md, glob_list on docs/cli/)
to gather information, then synthesizes a summary in its final response.

## Expected output

```
grid quickstart: running scenario S1 (retry=false, json=false)
Initializing Grid project...
  Created /Users/.../grid-sandbox/.grid
  Exists  /Users/.../grid-sandbox/config.yaml
  ...
Project initialized successfully!
[doctor output — 12 checks, all PASS or WARN except Eval Bridge]
=== S1: Multi-step tool use ===
Prompt: Read README.md, summarize the first 5 lines, then list the files in docs/cli/.
Tools expected: file_read, glob_list
[ToolCall] file_read(path="README.md")
[ToolResult] file_read: <contents of README.md>
[ToolCall] glob_list(pattern="docs/cli/**")
[ToolResult] glob_list: ["docs/cli/QUICKSTART.md", "docs/cli/scenarios/S1-..."]
[Assistant] <final summary based on tool results>
=== S1 complete ===
```

## Acceptance verification

- **PASS** if `[ToolCall]` lines for file_read and glob_list are visible WITHOUT
  `--debug`.
- **PASS** if the final `[Assistant]` line contains a coherent summary that
  references both the README content and the docs/cli/ file list.
- **FAIL** if doctor pre-flight reports any Fails (e.g. missing API key).
- **FAIL** if tool calls are hidden behind a flag like `--verbose`.

## Known gaps

- None specific to S1 — covered by `grid ask` + `execute_ask` paths which stream
  tool events to stderr (per `crates/grid-cli/src/commands/ask.rs:117-141`).
- Audit row: S1 Multi-step tool use → `grid ask "<prompt>"` = PASS
  (`crates/grid-cli/src/commands/ask.rs:117-141`).

Generated-By: Claude (claude-opus-4-8) via Claude Code CLI