# TUI Key Handler Invariants

> **Phase 5.2 T-01.7 retroactive source-of-truth.**
>
> Phase 5.2 PLAN (`.planning/phases/05.2-cli-hardening/05.2-01-PLAN.md`)
> specified T-01.7 to capture the key→action mapping table **before** the
> `tui/key_handler.rs` split. The split landed first in commits `92b7710`
> (initial split) and `cfcffd6` (studio build follow-up). This file captures
> the post-refactor invariants from **all 10 source files** in the
> `tui/key_handlers/` directory; the bindings table below is the
> source-of-truth for T-01.13 (unit tests ≥ 21) and T-01.15 (completeness
> verification).
>
> **2026-05-16 revision:** First pass covered only 5 files (`mod.rs`,
> `normal.rs`, `slash_commands.rs`, `vim_normal.rs`, `vim_insert.rs`) under
> the wrong assumption that the other 5 (`approval.rs`, `overlay.rs`,
> `model_selector.rs`, `history_search.rs`, `common.rs`) were thin
> dispatcher delegates. They are not — 4 of the 5 own real key-binding
> logic for 20 additional bindings. Total now: **98 distinct bindings** in
> 10 files (`common.rs` is helpers only, no `KeyCode` matches).
>
> The state-invariants section (originally written 2026-05-04) is kept intact
> below — it documents cursor/mutex/mode-transition rules that complement
> the binding table.

## Files in scope (10 modules)

| File | LOC | Role | Tests |
|------|-----|------|-------|
| `mod.rs` | 568 | Dispatcher — priority routing + Global bindings | 46 |
| `normal.rs` | 776 | Default REPL editing + scroll + autocomplete + slash-trigger | 20 |
| `slash_commands.rs` | 290 | `/`-prefixed commands evaluated when Enter is pressed in slash-overlay | 9 |
| `vim_normal.rs` | 222 | Vim normal-mode navigation/edit | 14 |
| `vim_insert.rs` | 274 | Vim insert-mode editing | 10 |
| `approval.rs` | 172 | Tool-approval dialog (y/n/a) | 5 |
| `overlay.rs` | 135 | Generic overlay close + Ctrl+D/E/A toggle | 4 |
| `model_selector.rs` | 113 | Model picker popup (j/k + ↑/↓ + Enter/Esc) | 10 |
| `history_search.rs` | 138 | Reverse-incremental Ctrl+R search | 8 |
| `common.rs` | 145 | Helpers (`compute_scroll_amount`, `open_external_editor`, `is_ctrl_c`) — no `KeyCode` matches | 4 |

Total: **2833 LOC across 10 files, 98 distinct bindings + 4 delegated handler entries, 130 test functions.**

Note: the PLAN anticipated 7 files (`mod`/`normal`/`vim`/`search`/`selector`/`overlay`/`approval`/`common`).
Actual layout: `vim_normal.rs` + `vim_insert.rs` cover what the PLAN called `vim.rs`;
`search.rs` and `selector.rs` were not extracted (functionality landed under
`history_search.rs` and `model_selector.rs` respectively). All 10 files own
real key-handler logic except `common.rs` (pure helpers).

## Dispatcher priority (mod.rs)

Mode resolution order (first match wins):

```
Overlay  >  ApprovalMode  >  ModelSelector  >  VimNormal(ctrl-only)
        >  VimInsert  >  HistorySearch  >  Normal
```

`VimNormal` returns early on non-Ctrl keys; Ctrl shortcuts fall through to
`Normal` so the user keeps the same Ctrl-bindings in vim mode.

`Overlay` / `ApprovalMode` / `ModelSelector` / `HistorySearch` delegate to
handler functions in sibling modules; their per-key behavior is
intentionally summarized in the binding table rather than enumerated.

## Bindings table

| # | Mode | Key | Action | Notes |
|---|------|-----|--------|-------|
| 1 | Global | Ctrl+C | Interrupt handler (double-press to exit) | Checked by `interrupt_manager`; resets on any text input |
| 2 | Normal | Ctrl+C | Exit app on second consecutive press | First press activates interrupt counter |
| 3 | Normal | Ctrl+D | Toggle AgentDebug overlay | Toggles `state.overlay` |
| 4 | Normal | Ctrl+E | Move cursor to line end (or toggle Eval overlay if input empty) | Emacs binding; context-dependent |
| 5 | Normal | Ctrl+A | Move cursor to line start (or toggle SessionPicker overlay if input empty) | Emacs binding; context-dependent |
| 6 | Normal | Ctrl+N | Move cursor down one line in multiline input | Emacs binding; no-op on single-line |
| 7 | Normal | Ctrl+P | Move cursor up one line in multiline input | Emacs binding; no-op on single-line |
| 8 | Normal | Ctrl+O | Cycle through tool results (expand one, collapse others, then close all) | `tool_toggle_cursor` tracks state; scroll to tool on expand |
| 9 | Normal | Alt+O | Toggle ALL tool results expand/collapse | Clears overrides; scrolls to bottom when collapsing |
| 10 | Normal | Ctrl+Shift+O | Same as Alt+O | macOS alt unreliable; Ctrl+Shift+O fallback |
| 11 | Normal | Ctrl+Y | Copy last assistant response to clipboard | No-op if no assistant message exists |
| 12 | Normal | Ctrl+K | Compact conversation context | Sends `AgentMessage::CompactHistory` |
| 13 | Normal | Ctrl+R | Enter/advance reverse incremental history search | Activates `state.history_search` |
| 14 | Normal | Shift+Tab | Cycle permission mode | Calls `state.permission_mode.next()` |
| 15 | Normal | Alt+T | Toggle extended thinking mode (E-11) | Pushes mode notification as assistant message |
| 16 | Normal | Alt+P | Toggle model selector popup | Toggles `state.model_selector` visibility |
| 17 | Normal | Ctrl+X | Open external editor for input buffer | Uses `$EDITOR` env var; only if input non-empty or streaming |
| 18 | Normal | Tab | Accept autocomplete suggestion | Replaces trigger+partial with completion |
| 19 | Normal | Enter | Accept autocomplete, execute slash command, or submit user message | 3-way branch based on context |
| 20 | Normal | Shift+Enter | Insert newline in input | Multiline input support |
| 21 | Normal | Alt+Enter | Insert newline in input | Multiline input support |
| 22 | Normal | Ctrl+J | Insert newline in input | Multiline input support |
| 23 | Normal | Up | Navigate history up, scroll conversation up, or cycle autocomplete prev | Priority: autocomplete > history > scroll |
| 24 | Normal | Down | Navigate history down, scroll conversation down, or cycle autocomplete next | Priority: autocomplete > history > scroll |
| 25 | Normal | Home | Scroll conversation to top | Sets `scroll_offset = u16::MAX`; marks `user_scrolled` |
| 26 | Normal | End | Scroll conversation to bottom | Sets `scroll_offset = 0`; clears `user_scrolled` |
| 27 | Normal | PageUp | Scroll conversation up by terminal height | Accumulates `scroll_offset` |
| 28 | Normal | PageDown | Scroll conversation down by terminal height | Subtracts from `scroll_offset` |
| 29 | Normal | Char (any printable) | Insert character into input buffer | Updates autocomplete; resets `interrupt_manager` |
| 30 | Normal | Backspace | Delete character before cursor | UTF-8 aware; updates autocomplete |
| 31 | Normal | Delete | Delete character at cursor | Updates autocomplete |
| 32 | Normal | Left | Move cursor left by one character | UTF-8 boundary aware |
| 33 | Normal | Right | Move cursor right by one character | UTF-8 boundary aware |
| 34 | Normal | Esc | Multi-stage: enter vim normal → dismiss autocomplete → cancel streaming → clear input → reset scroll | Vim-mode aware; highest priority is streaming cancel |
| 35 | VimNormal | i | Enter insert mode | Enters `VimMode::Insert` |
| 36 | VimNormal | a | Insert after cursor (move right first, then enter insert) | Moves cursor right, then enters insert |
| 37 | VimNormal | Shift+A | Insert at end of line | Moves to buffer end, then enters insert |
| 38 | VimNormal | Shift+I | Insert at beginning | Moves to buffer start, then enters insert |
| 39 | VimNormal | h | Move cursor left | Same as Left arrow |
| 40 | VimNormal | Left | Move cursor left | Same as h |
| 41 | VimNormal | l | Move cursor right | Same as Right arrow |
| 42 | VimNormal | Right | Move cursor right | Same as l |
| 43 | VimNormal | 0 | Jump to start of line | Cursor to position 0 |
| 44 | VimNormal | Shift+$ | Jump to end of line | Cursor to `buffer.len()` |
| 45 | VimNormal | x | Delete character at cursor | Moves cursor back if at end |
| 46 | VimNormal | w | Jump to next word start | Skips current word + whitespace |
| 47 | VimNormal | b | Jump to previous word start | Skips back over whitespace + word |
| 48 | VimNormal | v | Enter visual mode | Marks `visual_start` at current cursor |
| 49 | VimNormal | Ctrl+\* | Fall through to Normal handler | Ctrl shortcuts not intercepted by vim normal |
| 50 | VimInsert | Esc | Enter normal mode | Calls `state.vim.enter_normal()` |
| 51 | VimInsert | Backspace | Delete character before cursor | Updates autocomplete |
| 52 | VimInsert | Left | Move cursor left | UTF-8 aware |
| 53 | VimInsert | Right | Move cursor right | UTF-8 aware |
| 54 | VimInsert | Up | Move cursor up one line (multiline only) | No-op on single-line input |
| 55 | VimInsert | Down | Move cursor down one line (multiline only) | No-op on single-line input |
| 56 | VimInsert | Home | Jump to line start | Sets cursor to 0 |
| 57 | VimInsert | End | Jump to line end | Sets cursor to `buffer.len()` |
| 58 | VimInsert | Delete | Delete character at cursor | Updates autocomplete |
| 59 | VimInsert | Tab | Accept autocomplete suggestion | Same logic as Normal mode |
| 60 | VimInsert | Char (any printable) | Insert character into buffer | Updates autocomplete |
| 61 | VimInsert | Ctrl+A | Jump to line start | Emacs binding |
| 62 | VimInsert | Ctrl+E | Jump to line end | Emacs binding |
| 63 | VimInsert | Ctrl+U | Delete from cursor to line start | Emacs kill-line-backwards |
| 64 | VimInsert | Ctrl+W | Delete word before cursor | Emacs kill-word-backwards |
| 65 | SlashCommands | `/help`, `/h`, `/?` | Show help text (built-in + custom commands) | Async command execution |
| 66 | SlashCommands | `/clear` | Clear conversation history | Resets messages, tokens, tools, cache |
| 67 | SlashCommands | `/exit`, `/quit`, `/q` | Exit session | Sets `state.running = false` |
| 68 | SlashCommands | `/debug` | Toggle AgentDebug overlay | Same effect as Ctrl+D |
| 69 | SlashCommands | `/eval` | Toggle Eval overlay | Same effect as Ctrl+E (empty input) |
| 70 | SlashCommands | `/sessions` | Toggle SessionPicker overlay | Same effect as Ctrl+A (empty input) |
| 71 | SlashCommands | `/todo` | Show plan panel info message | Replaced old toggle-panel behavior |
| 72 | SlashCommands | `/mouse` | Toggle mouse capture | Emits crossterm `EnableMouseCapture`/`DisableMouseCapture` |
| 73 | SlashCommands | `/compact` | Compact conversation context | Sends `AgentMessage::CompactHistory` |
| 74 | SlashCommands | `/custom_*` | Execute custom command from `~/.grid/commands/` | Template expansion; sent to agent |
| 75 | SlashCommands | `/unknown` | Show error message | "Unknown command" response |
| 76 | Approval | y / Y | Approve tool execution | Clears `pending_approval`; calls `gate.respond(tool_id, true)` |
| 77 | Approval | a / A | Always approve (future: persist preference) | Clears `pending_approval`; calls `gate.respond(tool_id, true)` |
| 78 | Approval | n / N | Deny tool execution | Clears `pending_approval`; calls `gate.respond(tool_id, false)` |
| 79 | Approval | Esc | Deny (alias for n/N) | Clears `pending_approval`; calls `gate.respond(tool_id, false)` |
| 80 | Approval | Ctrl+C | Handle cancellation | Calls `interrupt_manager.handle_ctrl_c()`; sets `running = false` if handled |
| 81 | Overlay | Esc | Close overlay | Sets `state.overlay = OverlayMode::None` |
| 82 | Overlay | Ctrl+D | Toggle agent debug overlay | Toggles between `AgentDebug` and `None` |
| 83 | Overlay | Ctrl+E | Toggle eval overlay | Toggles between `Eval` and `None` |
| 84 | Overlay | Ctrl+A | Toggle session picker overlay | Toggles between `SessionPicker` and `None` |
| 85 | Overlay | Ctrl+C | Handle cancellation | Calls `interrupt_manager.handle_ctrl_c()`; comment notes "overlays handle own keys in T3" |
| 86 | ModelSelector | Up | Previous model in list | Calls `state.model_selector.prev()`; sets `dirty = true` |
| 87 | ModelSelector | k | Previous model (vim-style alias of Up) | Calls `state.model_selector.prev()`; sets `dirty = true` |
| 88 | ModelSelector | Down | Next model in list | Calls `state.model_selector.next()`; sets `dirty = true` |
| 89 | ModelSelector | j | Next model (vim-style alias of Down) | Calls `state.model_selector.next()`; sets `dirty = true` |
| 90 | ModelSelector | Enter | Confirm selection | Calls `state.model_selector.confirm()`; sets `state.model_name`; sets `dirty` |
| 91 | ModelSelector | Esc | Cancel selection (close selector) | Sets `state.model_selector.visible = false` |
| 92 | ModelSelector | Alt+P | Cancel selection (alias of Esc) | Sets `state.model_selector.visible = false` |
| 93 | HistorySearch | Char (printable) | Append char to search query | Pushes to query; resets `match_index`; searches entries |
| 94 | HistorySearch | Backspace | Remove last char from query | Pops from query; re-searches entries |
| 95 | HistorySearch | Ctrl+R | Advance to next match (cycle) | Calls `state.history_search.next_match()`; re-searches |
| 96 | HistorySearch | Esc | Cancel search | Calls `state.history_search.deactivate()` |
| 97 | HistorySearch | Enter | Accept matched text into input buffer | Copies `matched_text` to `input_buffer`; deactivates search |

Total: **98 distinct bindings across 10 files** (`common.rs` contributes 0
key bindings — pure helpers). 2 bindings (rows 84 + 5) share a key (`Ctrl+A`)
across `Overlay` and `Normal` modes — the dispatcher priority resolves this.

## `common.rs` helpers (no `KeyCode` matches)

- `compute_scroll_amount(state, direction_up) → u16` — 3/6/12-line scroll
  acceleration with 200ms window; resets on direction change. Called from
  `normal.rs` Up/Down (rows 23-24) and PageUp/PageDown (rows 27-28).
- `open_external_editor(text) → Result<String, io::Error>` — launches
  `$EDITOR` (fallback `vi`) on temp file; exits raw/alt-screen, edits,
  re-enters; returns trimmed result. Called from `normal.rs` Ctrl+X (row 17).
- `is_ctrl_c(key: &KeyEvent) → bool` — Ctrl+C detector. Called by
  `mod.rs` dispatcher before mode-specific handlers (row 1 — Global).

## Cross-mode asymmetries (lock-in regression targets)

1. **VimInsert supports Emacs line editing** (Ctrl+A/E/U/W); **VimNormal does not** (Ctrl falls through to `Normal`).
2. **VimNormal owns word navigation** (`w`/`b`) and **visual mode** (`v`); **VimInsert does not**.
3. **Normal mode Up/Down has 3-way branching** (autocomplete → history → scroll); **Vim modes do not check autocomplete on Up/Down** (Tab is the only autocomplete entry in VimInsert).
4. **Streaming-cancel Esc** has priority over input-clear Esc in Normal mode; the cascade order in row 34 is fixed.
5. **Slash overlay reuses overlay toggles**: `/debug` ≡ Ctrl+D (rows 3 + 82), `/eval` ≡ Ctrl+E with empty input (rows 4 + 83), `/sessions` ≡ Ctrl+A with empty input (rows 5 + 84). A test breaking one must break both surfaces.
6. **Ctrl+Shift+O is an alias of Alt+O** for macOS terminals where Alt is intercepted (rows 9 + 10 must stay equivalent).
7. **Newline bindings are 4-way redundant** (rows 20–22 + Ctrl+J) to accommodate terminals that swallow Shift+Enter or Alt+Enter.
8. **ModelSelector dual navigation** (rows 86-89): `↑/k` AND `↓/j` are explicit aliases — both vim and arrow-key users must work. Tests must lock both paths.
9. **Approval mode is the most aggressive Esc handler** (row 79): Esc = deny (not cancel). This is intentional fail-safe behavior; do not unify with Overlay/HistorySearch Esc semantics.
10. **Overlay Ctrl+D/E/A toggles are stateful** (rows 82-84): each binding toggles its mode against `None`, so pressing twice round-trips. Do not change to one-way "open" semantics.

## Test-coverage targets

Per Phase 5.2 PLAN T-01.13 (unit tests ≥ 21) and T-01.15 (completeness
verification), each row above should map to at least one unit test in the
appropriate per-file test module:

- Row 1 (Global Ctrl+C) → `tui/key_handlers/mod.rs` tests (dispatcher-level)
- Rows 2–34 → `tui/key_handlers/normal.rs` tests
- Rows 35–49 → `tui/key_handlers/vim_normal.rs` tests
- Rows 50–64 → `tui/key_handlers/vim_insert.rs` tests
- Rows 65–75 → `tui/key_handlers/slash_commands.rs` tests
- Rows 76–80 → `tui/key_handlers/approval.rs` tests
- Rows 81–85 → `tui/key_handlers/overlay.rs` tests
- Rows 86–92 → `tui/key_handlers/model_selector.rs` tests
- Rows 93–97 → `tui/key_handlers/history_search.rs` tests

Cross-mode transitions (e.g. Normal → VimNormal via Esc, slash overlay
dismissal, Approval auto-close on respond) → `crates/grid-cli/tests/key_handler_integration.rs`
(T-01.14 target — file does not exist yet).

Asymmetry items 1–10 should each be locked by at least one dedicated test so
future edits cannot silently break the contract.

**Current test inventory** (130 tests across the 10 files; rough mapping to
binding rows, not 1:1):

| File | Test count | Approx. row coverage |
|------|-----------|----------------------|
| `mod.rs` | 46 | dispatch priority + Global Ctrl+C (row 1) |
| `normal.rs` | 20 | rows 2-34 (33 bindings, ~60% direct coverage) |
| `vim_normal.rs` | 14 | rows 35-49 (15 bindings, ~93% direct coverage) |
| `vim_insert.rs` | 10 | rows 50-64 (15 bindings, ~67% direct coverage) |
| `slash_commands.rs` | 9 | rows 65-75 (11 bindings, ~82% direct coverage) |
| `approval.rs` | 5 | rows 76-80 (5 bindings, 100% direct coverage) |
| `overlay.rs` | 4 | rows 81-85 (5 bindings, ~80%) |
| `model_selector.rs` | 10 | rows 86-92 (7 bindings, ~143% — multiple aliases tested) |
| `history_search.rs` | 8 | rows 93-97 (5 bindings, ~160%) |
| `common.rs` | 4 | 3 helpers (rows are footnotes, not bindings) |

PLAN T-01.13 target (≥ 21 unit tests) is **far exceeded** — the audit pivot
for Phase 5.2 closure is T-01.15 (verify every binding row has a test) and
T-01.14 (write integration tests for cross-mode transitions).

---

## State Invariants

> *Original section (2026-05-04). These rules complement the bindings table —
> they describe **how** handlers must behave, not **which** keys map to
> which action.*

### Cursor Bounds
- `state.input_cursor` must always satisfy: `0 <= state.input_cursor <= state.input_buffer.len()`
- The cursor marks the insertion point; characters are inserted BEFORE the cursor position
- Cursor movement handlers must clamp to these bounds

### Mutex Safety
- `state.pending_approval` must only be accessed after acquiring `approval_mutex.lock()`
- Lock must be released before any `.await` points to prevent deadlocks

### Mode Transitions
- Vim insert mode (`vim_insert`) can only transition to vim_normal via Escape
- Vim normal mode can only transition to vim_insert via 'i' or 'a'
- History search exits to normal mode on Enter/Escape
- Model selector closes on Enter/Escape
- Overlay modes exit to normal mode on Escape or after action completion

## Permission Mode Invariants

### Cycle Ordering
Permission mode cycles in this order:
1. `Ask` (default) - user prompted before any action
2. `AutoApprove` - all actions approved automatically
3. `Bypass` - security checks disabled (use with caution)
4. (cycles back to `Ask`)

### Shift+Tab Behavior
- Each Shift+Tab press cycles to the next permission mode
- The cycle is immediate (no confirmation required)
- Permission mode affects tool execution, not message sending

## Input Buffer Invariants

### Empty Submit Prevention
- Enter must NOT send empty messages (only valid when `!state.input_buffer.is_empty()`)
- Autocomplete commits do not trigger this check

### Scroll State Coordination
- When `state.input_buffer.is_empty()`, the view should auto-scroll to bottom
- After sending a message, input_buffer should be cleared

## Tool Collapse Invariants

### Per-Tool Collapse State
- `is_tool_collapsed(tool_id)` returns the per-tool state if set, otherwise follows global `is_collapsed`
- Individual collapse takes precedence over global collapse
- Clearing individual collapse reverts to global behavior

## History Search Invariants

### Match Navigation
- `match_index` is 0-based, pointing into `matches` vector
- Pressing Up decreases `match_index` (if > 0)
- Pressing Down increases `match_index` (if < matches.len() - 1)
- Enter/Escape exits history search and restores last input

### Empty Query
- If query is empty, matches contains all history
- Navigation wraps around (last -> first, first -> last)

## Approval Dialog Invariants

### Exclusive State
- While `pending_approval` is `Some(...)`, no other overlays or inputs are active
- Approval response must be sent via channel before clearing `pending_approval`

### Timeout Behavior
- Approval timeout is tracked via `Instant::now()` comparison
- Expired approvals auto-deny after configured duration

## Concurrency Invariants

### No Async in Locks
- Never `.await` while holding a mutex lock
- Always release locks before await points

### Stream State
- `state.is_streaming` must be `false` when entering normal input mode
- Ctrl+C sets `is_streaming = false` and clears partial response state

## Test Invariants

### Mock State
- All test functions must create fresh `AppState` instances
- State modifications in tests do not persist between tests
- Handler functions are async but tests can run sequentially

## Cross-Cutting Concerns

### Overlay Priority
1. Approval dialog (highest priority - blocks all other input)
2. Model selector
3. History search
4. Overlay panels (debug, context)
5. Normal mode (lowest priority)

### Escape Key Behavior
- In ANY mode, Escape cancels current action and returns to normal mode
- Approval dialog Escape = deny
- History search Escape = cancel and restore input
- Model selector Escape = close without selection
- Overlay Escape = close overlay
