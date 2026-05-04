# Key Handler Invariants

This document captures the critical invariants that must hold across all
mode-specific keyboard handlers in the `key_handlers` module.

## State Invariants

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
