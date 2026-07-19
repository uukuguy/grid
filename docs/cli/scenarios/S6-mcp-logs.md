# S6: MCP live log streaming

> **Phase:** 3.7.1 grid-cli Plan 03 (REQ-AUDIT-04)
> **Date:** 2026-07-20
> **Status:** Implemented

## Prerequisites

- `grid` binary built (Phase 3.7.1 Plan 02 baseline).
- At least one MCP server registered via `grid mcp add <name> <command> [...]`.
- No API key required (logs are captured from the server's stderr, not from an LLM).

## Quickstart

```bash
# 1. Register a fake MCP server (writes 3 lines + 1 late line to stderr)
grid mcp add fake-s6 sh -c \
  'echo "INFO: hello" 1>&2; echo "ERROR: bad" 1>&2; echo "WARN: careful" 1>&2; sleep 1; echo "INFO: late" 1>&2'

# 2. Trigger a tool call so the server actually starts
grid tool list --server fake-s6   # or any other call that exercises the server

# 3. Tail the last 10 lines
grid mcp logs fake-s6 --lines 10

# 4. Stream new lines live
grid mcp logs fake-s6 --follow
# (Ctrl-C to exit; exit code 0)
```

## Manual steps

| Step | Command | What it does |
|------|---------|--------------|
| 1 | `grid mcp add fake-s6 sh -c '...'` | Register a fake server |
| 2 | `grid mcp status` | Confirm server is Running |
| 3 | `grid mcp logs fake-s6 --lines 5` | Static tail of recent entries |
| 4 | `grid mcp logs fake-s6 --level error` | Filter to only Error-level lines |
| 5 | `grid mcp logs fake-s6 --output json` | Machine-parseable per-line JSON |
| 6 | `grid mcp logs fake-s6 --follow` | Live stream; Ctrl-C to exit |

## Expected output

Text mode (default on TTY):

```
2026-07-20T10:23:45.123Z [INFO ] INFO: hello
2026-07-20T10:23:45.124Z [ERROR] ERROR: bad
2026-07-20T10:23:45.125Z [WARN ] WARN: careful
2026-07-20T10:23:46.428Z [INFO ] INFO: late
```

JSON mode (or non-TTY stdout):

```
{"timestamp":"2026-07-20T10:23:45.123Z","level":"info","message":"INFO: hello"}
{"timestamp":"2026-07-20T10:23:45.124Z","level":"error","message":"ERROR: bad"}
{"timestamp":"2026-07-20T10:23:45.125Z","level":"warn","message":"WARN: careful"}
{"timestamp":"2026-07-20T10:23:46.428Z","level":"info","message":"INFO: late"}
```

`--level error` filter (text mode):

```
2026-07-20T10:23:45.124Z [ERROR] ERROR: bad
```

## Known limits

- **Buffer cap = 1000 entries/server** (D-11). Older entries drop on overflow.
- **Level inference is heuristic** (D-12). Recognises `ERROR:`/`[error]`/`ERR:`/`FATAL:`/`WARN:`/`[warn]`/`WARNING:`. Anything else is `Info`. False negatives (unrecognised Error-level lines) are acceptable; false positives are not.
- **No on-disk persistence** — buffer is in-memory only. Restarting the server clears the buffer.
- **No `--since TIMESTAMP` or `--grep PATTERN`** — out of scope for Plan 03 (`3.7.1-03-CONTEXT.md` D-09 deferred ideas).

## Acceptance

Per Phase 3.7.1 Plan 03 acceptance standard:

- `grid mcp logs <name> --lines 10` returns up to 10 recent log lines.
- `grid mcp logs <name> --follow` streams new lines; Ctrl-C exits with code 0.
- `grid mcp logs <name> --level error` filters out INFO/WARN.
- `grid mcp logs <name> --output json` (or non-TTY stdout) emits one JSON object per line.
- Buffer cap (1000/server) enforced.

Generated-By: Claude (claude-opus-4-8) via Claude Code CLI
Co-Authored-By: claude-flow <ruv@ruv.net>
