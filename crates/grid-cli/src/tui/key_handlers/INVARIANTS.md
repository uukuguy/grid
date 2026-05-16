# TUI Key Handler Invariants

> **Phase 5.2 T-01.7 retroactive source-of-truth.**
>
> Phase 5.2 PLAN (`.planning/phases/05.2-cli-hardening/05.2-01-PLAN.md`)
> specified T-01.7 to capture the key→action mapping table **before** the
> `tui/key_handler.rs` split. The split landed first in commits `92b7710`
> (initial split) and `cfcffd6` (studio build follow-up). This file captures
> the post-refactor invariants from the 5 source files; the bindings table
> below is the source-of-truth for T-01.13 (unit tests ≥ 21) and T-01.15
> (completeness verification).
>
> The state-invariants section (originally written 2026-05-04) is kept intact
> below — it documents cursor/mutex/mode-transition rules that complement
> the binding table.

## Files in scope

| File | LOC | Role |
|------|-----|------|
| `mod.rs` | 568 | Dispatcher — priority routing + Global bindings |
| `normal.rs` | 776 | Default REPL editing + scroll + autocomplete + slash-trigger |
| `slash_commands.rs` | 290 | `/`-prefixed commands evaluated when Enter is pressed in slash-overlay |
| `vim_normal.rs` | 222 | Vim normal-mode navigation/edit |
| `vim_insert.rs` | 274 | Vim insert-mode editing |

Total: **2130 LOC, 78 distinct bindings.**

Note: actual on-disk module is `tui/key_handlers/` (plural) and contains 5
files — the PLAN anticipated 7. `vim_normal.rs` + `vim_insert.rs` together
cover what the PLAN called `vim.rs`. `search.rs` / `selector.rs` /
`overlay.rs` / `approval.rs` / `common.rs` were not extracted; their
dispatch is still in `mod.rs` and delegates into other modules
(`tui/overlays/`, `tui/managers/`, `tui/widgets/`).

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
| 76 | Overlay | Esc | Close current overlay | Delegated to `overlay::handle_overlay_key()` |
| 77 | ApprovalMode | (depends on overlay type) | Tool approval dialog handling | Delegated to `approval::handle_approval_key()` |
| 78 | ModelSelector | (selector-state-specific) | Model selection navigation/confirm | Delegated to `model_selector::handle_model_selector_key()` |
| 79 | HistorySearch | (Ctrl+R active) | Navigate search results | Delegated to `history_search::handle_history_search_key()` |

Total: 78 distinct bindings + 4 delegated overlay/selector handlers (rows
76–79 each cover multiple sub-keys evaluated outside this module).

## Cross-mode asymmetries (lock-in regression targets)

1. **VimInsert supports Emacs line editing** (Ctrl+A/E/U/W); **VimNormal does not** (Ctrl falls through to `Normal`).
2. **VimNormal owns word navigation** (`w`/`b`) and **visual mode** (`v`); **VimInsert does not**.
3. **Normal mode Up/Down has 3-way branching** (autocomplete → history → scroll); **Vim modes do not check autocomplete on Up/Down** (Tab is the only autocomplete entry in VimInsert).
4. **Streaming-cancel Esc** has priority over input-clear Esc in Normal mode; the cascade order in row 34 is fixed.
5. **Slash overlay reuses overlay toggles**: `/debug` ≡ Ctrl+D (row 3), `/eval` ≡ Ctrl+E with empty input (row 4), `/sessions` ≡ Ctrl+A with empty input (row 5). A test breaking one must break both surfaces.
6. **Ctrl+Shift+O is an alias of Alt+O** for macOS terminals where Alt is intercepted (rows 9 + 10 must stay equivalent).
7. **Newline bindings are 4-way redundant** (rows 20–22 + Ctrl+J) to accommodate terminals that swallow Shift+Enter or Alt+Enter.

## Test-coverage targets

Per Phase 5.2 PLAN T-01.13 (unit tests ≥ 21) and T-01.15 (completeness
verification), each row above should map to at least one unit test in the
appropriate per-file test module:

- Rows 2–34 → `tui/key_handlers/normal.rs` tests
- Rows 35–49 → `tui/key_handlers/vim_normal.rs` tests
- Rows 50–64 → `tui/key_handlers/vim_insert.rs` tests
- Rows 65–75 → `tui/key_handlers/slash_commands.rs` tests
- Rows 76–79 → integration tests at `crates/grid-cli/tests/key_handler_integration.rs` (T-01.14 target)

Asymmetry items 1–7 should each be locked by at least one dedicated test so
future edits cannot silently break the contract.

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
