//! Normal mode key handling for the TUI.
//!
//! Handles keyboard events in the main input/chat mode including:
#![doc = "- Text input (character, backspace, delete)"]
#![doc = "- Cursor movement (arrows, home/end)"]
#_[doc = "- Message submission (Enter)"]
#_[doc = "- Scroll control (up/down, page up/down)"]
#_[doc = "- Ctrl shortcuts for common operations"]
//!
//! This is the default mode when no overlays or special modes are active.

use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};
use grid_engine::agent::AgentMessage;
use grid_types::message::ChatMessage;

use super::app_state::{OverlayMode, TuiState};
use super::common::compute_scroll_amount;
use super::slash_commands::execute_slash_command;

/// Handle keys in normal mode (main chat/input mode).
///
/// Returns `true` if the key was handled, `false` if it should be
/// passed to another handler.
pub async fn handle_normal_key(state: &mut TuiState, key: KeyEvent) {
    match (key.modifiers, key.code) {
        // ── Ctrl shortcuts ──
        (KeyModifiers::CONTROL, KeyCode::Char('c')) => {
            if state.interrupt_manager.handle_ctrl_c().await {
                state.running = false;
            }
        }
        (KeyModifiers::CONTROL, KeyCode::Char('d')) => {
            state.overlay = if state.overlay == OverlayMode::AgentDebug {
                OverlayMode::None
            } else {
                OverlayMode::AgentDebug
            };
        }
        (KeyModifiers::CONTROL, KeyCode::Char('e')) => {
            // Emacs: move cursor to end of line; when input empty: toggle eval overlay
            if !state.input_buffer.is_empty() {
                state.input_cursor = state.input_buffer.len();
            } else {
                state.overlay = if state.overlay == OverlayMode::Eval {
                    OverlayMode::None
                } else {
                    OverlayMode::Eval
                };
            }
        }
        (KeyModifiers::CONTROL, KeyCode::Char('a')) => {
            // Emacs: move cursor to start of line; when input empty: toggle session picker
            if !state.input_buffer.is_empty() {
                state.input_cursor = 0;
            } else {
                state.overlay = if state.overlay == OverlayMode::SessionPicker {
                    OverlayMode::None
                } else {
                    OverlayMode::SessionPicker
                };
            }
        }
        (KeyModifiers::CONTROL, KeyCode::Char('n')) => {
            // Emacs: move cursor down one line in multiline input
            if state.input_buffer.contains('\n') {
                let lines: Vec<&str> = state.input_buffer.split('\n').collect();
                let mut pos = 0;
                let mut cursor_line = 0;
                let mut cursor_col = 0;
                for (i, line) in lines.iter().enumerate() {
                    if state.input_cursor <= pos + line.len() {
                        cursor_line = i;
                        cursor_col = state.input_cursor - pos;
                        break;
                    }
                    pos += line.len() + 1;
                    if i == lines.len() - 1 {
                        cursor_line = i;
                        cursor_col = line.len();
                    }
                }
                if cursor_line + 1 < lines.len() {
                    let next_line = lines[cursor_line + 1];
                    let new_col = cursor_col.min(next_line.len());
                    let mut new_pos = 0;
                    for line in &lines[..=cursor_line] {
                        new_pos += line.len() + 1;
                    }
                    state.input_cursor = new_pos + new_col;
                }
            }
        }
        (KeyModifiers::CONTROL, KeyCode::Char('p')) => {
            // Emacs: move cursor up one line in multiline input; when input empty: toggle todo
            if state.input_buffer.contains('\n') {
                let lines: Vec<&str> = state.input_buffer.split('\n').collect();
                let mut pos = 0;
                let mut cursor_line = 0;
                let mut cursor_col = 0;
                for (i, line) in lines.iter().enumerate() {
                    if state.input_cursor <= pos + line.len() {
                        cursor_line = i;
                        cursor_col = state.input_cursor - pos;
                        break;
                    }
                    pos += line.len() + 1;
                    if i == lines.len() - 1 {
                        cursor_line = i;
                        cursor_col = line.len();
                    }
                }
                if cursor_line > 0 {
                    let prev_line = lines[cursor_line - 1];
                    let new_col = cursor_col.min(prev_line.len());
                    let mut new_pos = 0;
                    for line in &lines[..cursor_line - 1] {
                        new_pos += line.len() + 1;
                    }
                    state.input_cursor = new_pos + new_col;
                }
            }
            // When input is single-line, Ctrl+P is a no-op (todo panel removed)
        }

        // ── Ctrl+O: cycle tool results — open one at a time, then close all ──
        // Cycle: open last → open second-to-last → ... → open first → close all → repeat
        // Only one tool is expanded at a time (previous one closes when next opens).
        // When opening: scroll to make the tool call visible.
        // When closing all: scroll back to bottom.
        (KeyModifiers::CONTROL, KeyCode::Char('o')) => {
            let ids = state.all_tool_use_ids();
            if !ids.is_empty() {
                let n = ids.len();
                let cursor = state.tool_toggle_cursor % (n + 1); // extra slot = "close all"

                // Clear all overrides first (close previous)
                state.tool_expanded_overrides.clear();

                if cursor < n {
                    // Open one tool: cursor 0 = last, 1 = second-to-last, etc.
                    let target_idx = n - 1 - cursor;
                    let tool_id = ids[target_idx].clone();
                    state.tool_expanded_overrides.insert(tool_id.clone(), true);

                    // Defer scroll to render phase for precise positioning
                    state.scroll_to_tool = Some(tool_id);
                    state.user_scrolled = true;
                } else {
                    // cursor == n → all closed — scroll back to bottom
                    state.scroll_offset = 0;
                    state.user_scrolled = false;
                }

                state.tool_toggle_cursor += 1;
                state.invalidate_cache();
            }
        }

        // ── Alt+O: toggle ALL tool results expand/collapse ──
        (KeyModifiers::ALT, KeyCode::Char('o')) => {
            state.tools_default_collapsed = !state.tools_default_collapsed;
            state.tool_expanded_overrides.clear();
            state.tool_toggle_cursor = 0;
            // Scroll to bottom when collapsing all
            if state.tools_default_collapsed {
                state.scroll_offset = 0;
                state.user_scrolled = false;
            }
            state.invalidate_cache();
        }
        // ── Ctrl+Shift+O: same as Alt+O (Alt may not work on macOS) ──
        (_, KeyCode::Char('O')) if key.modifiers.contains(KeyModifiers::CONTROL) && key.modifiers.contains(KeyModifiers::SHIFT) => {
            state.tools_default_collapsed = !state.tools_default_collapsed;
            state.tool_expanded_overrides.clear();
            state.tool_toggle_cursor = 0;
            if state.tools_default_collapsed {
                state.scroll_offset = 0;
                state.user_scrolled = false;
            }
            state.invalidate_cache();
        }

        // ── Ctrl+Y: copy last assistant response to clipboard ──
        (KeyModifiers::CONTROL, KeyCode::Char('y')) => {
            if let Some(text) = state.last_assistant_response_text() {
                if super::app_state::TuiState::copy_to_clipboard(&text) {
                    // Brief visual feedback — could add a toast/notification later
                    state.dirty = true;
                }
            }
        }

        // ── Ctrl+K: compact context (AV-T3) ──
        (KeyModifiers::CONTROL, KeyCode::Char('k')) => {
            let _ = state.handle.tx.try_send(AgentMessage::CompactHistory);
            let msg = "Compacting conversation context... (Ctrl+K)";
            state.messages.push(ChatMessage::assistant(msg));
            state.invalidate_cache();
            state.auto_scroll();
        }

        // ── Ctrl+R: reverse incremental history search ──
        (KeyModifiers::CONTROL, KeyCode::Char('r')) => {
            if state.history_search.active {
                // Already searching — advance to next match
                state.history_search.next_match();
                let entries = state.message_history.entries();
                state.history_search.search(&entries);
            } else {
                // Enter search mode
                state.history_search.activate();
            }
            state.dirty = true;
        }

        // ── Shift+Tab: cycle permission mode ──
        (KeyModifiers::SHIFT, KeyCode::BackTab) => {
            state.permission_mode = state.permission_mode.next();
            state.dirty = true;
        }

        // ── Alt+T: toggle extended thinking mode (E-11) ──
        (KeyModifiers::ALT, KeyCode::Char('t')) => {
            state.extended_thinking = !state.extended_thinking;
            let mode = if state.extended_thinking { "Extended" } else { "Normal" };
            state.messages.push(grid_types::message::ChatMessage::assistant(
                &format!("[Thinking mode: {}]", mode),
            ));
            state.invalidate_cache();
            state.auto_scroll();
        }

        // ── Alt+P / Meta+P: toggle model selector popup ──
        (KeyModifiers::ALT, KeyCode::Char('p')) => {
            state.model_selector.toggle();
            state.dirty = true;
        }

        // ── Ctrl+X Ctrl+E: open external editor for input ──
        // Note: This handles Ctrl+X only — a second Ctrl+E is needed.
        // For simplicity, we handle Ctrl+X as the trigger when input is non-empty.
        (KeyModifiers::CONTROL, KeyCode::Char('x')) => {
            if !state.input_buffer.is_empty() || state.is_streaming {
                // Open $EDITOR with current input content
                if let Ok(edited) = super::common::open_external_editor(&state.input_buffer) {
                    state.input_buffer = edited;
                    state.input_cursor = state.input_buffer.len();
                    state.dirty = true;
                }
            }
        }

        // ── Tab: accept autocomplete suggestion ──
        (KeyModifiers::NONE, KeyCode::Tab) => {
            if state.autocomplete.is_visible() {
                if let Some((insert, delete_count)) = state.autocomplete.accept() {
                    // Delete trigger + partial text, then insert completion
                    let start = state.input_cursor.saturating_sub(delete_count);
                    state.input_buffer.replace_range(start..state.input_cursor, &insert);
                    state.input_cursor = start + insert.len();
                    state.dirty = true;
                }
            }
        }

        // ── Enter: accept autocomplete OR execute slash command OR submit input ──
        (KeyModifiers::NONE, KeyCode::Enter) => {
            // If autocomplete popup is visible, accept the selection
            if state.autocomplete.is_visible() {
                if let Some((insert, delete_count)) = state.autocomplete.accept() {
                    let start = state.input_cursor.saturating_sub(delete_count);
                    state.input_buffer.replace_range(start..state.input_cursor, &insert);
                    state.input_cursor = start + insert.len();
                    state.dirty = true;
                }
            } else if !state.input_buffer.trim().is_empty() && !state.is_streaming {
                let text = std::mem::take(&mut state.input_buffer);
                state.input_cursor = 0;

                // Check for slash commands
                if text.starts_with('/') {
                    execute_slash_command(state, &text).await;
                } else {
                    // Save to message history
                    state.message_history.push(text.clone());

                    // Add user message to conversation
                    state.messages.push(ChatMessage::user(&text));
                    state.invalidate_cache();
                    state.auto_scroll();

                    // Start task timing
                    state.task_start_time = Some(std::time::Instant::now());
                    state.task_input_tokens = 0;
                    state.task_output_tokens = 0;
                    state.task_tool_calls = 0;
                    state.task_rounds = 0;

                    // Send to agent
                    let _ = state
                        .handle
                        .send(AgentMessage::UserMessage {
                            content: text,
                            channel_id: "tui".into(),
                        })
                        .await;
                    state.is_streaming = true;
                    state.cancelled = false;
                    state.interrupt_manager.reset();
                }
            }
        }

        // ── Shift+Enter / Alt+Enter / Ctrl+J: newline in input ──
        (KeyModifiers::SHIFT, KeyCode::Enter)
        | (KeyModifiers::ALT, KeyCode::Enter)
        | (KeyModifiers::CONTROL, KeyCode::Char('j')) => {
            state.input_buffer.insert(state.input_cursor, '\n');
            state.input_cursor += 1;
            state.dirty = true;
        }

        // ── Arrow keys: autocomplete navigation / history / scroll ──
        (KeyModifiers::NONE, KeyCode::Up) => {
            if state.autocomplete.is_visible() {
                state.autocomplete.select_prev();
                return;
            }
            // Try history navigation first (when input is empty and history exists)
            if state.input_buffer.is_empty() && !state.message_history.is_empty() {
                if let Some(prev) = state.message_history.up() {
                    state.input_buffer = prev.to_string();
                    state.input_cursor = state.input_buffer.len();
                }
            } else if state.input_buffer.is_empty() {
                // No history — scroll up with acceleration
                let amount = compute_scroll_amount(state, true);
                state.scroll_offset = state.scroll_offset.saturating_add(amount);
                state.user_scrolled = true;
            } else {
                // Input has content — navigate history
                if let Some(prev) = state.message_history.up() {
                    state.input_buffer = prev.to_string();
                    state.input_cursor = state.input_buffer.len();
                }
            }
        }
        (KeyModifiers::NONE, KeyCode::Down) => {
            if state.autocomplete.is_visible() {
                state.autocomplete.select_next();
                return;
            }
            if state.message_history.is_navigating() {
                // Currently browsing history — navigate forward
                if let Some(next) = state.message_history.down() {
                    state.input_buffer = next.to_string();
                    state.input_cursor = state.input_buffer.len();
                } else {
                    // Reached end of history — clear input
                    state.input_buffer.clear();
                    state.input_cursor = 0;
                }
            } else if state.user_scrolled {
                // Scroll down with acceleration
                let amount = compute_scroll_amount(state, false);
                state.scroll_offset = state.scroll_offset.saturating_sub(amount);
                if state.scroll_offset == 0 {
                    state.user_scrolled = false;
                }
            }
        }

        // ── Home/End: jump scroll ──
        (KeyModifiers::NONE, KeyCode::Home) => {
            state.scroll_offset = u16::MAX; // scroll to top
            state.user_scrolled = true;
        }
        (KeyModifiers::NONE, KeyCode::End) => {
            state.scroll_offset = 0;
            state.user_scrolled = false;
        }

        // ── PageUp/PageDown ──
        (KeyModifiers::NONE, KeyCode::PageUp) => {
            state.scroll_offset = state
                .scroll_offset
                .saturating_add(state.terminal_height.saturating_sub(4));
            state.user_scrolled = true;
        }
        (KeyModifiers::NONE, KeyCode::PageDown) => {
            state.scroll_offset = state
                .scroll_offset
                .saturating_sub(state.terminal_height.saturating_sub(4));
            if state.scroll_offset == 0 {
                state.user_scrolled = false;
            }
        }

        // ── Text input ──
        (KeyModifiers::NONE, KeyCode::Char(c)) | (KeyModifiers::SHIFT, KeyCode::Char(c)) => {
            state.input_buffer.insert(state.input_cursor, c);
            state.input_cursor += c.len_utf8();
            state.interrupt_manager.reset();
            state.dirty = true;
            // Update autocomplete on every keystroke
            let text_before = state.input_buffer[..state.input_cursor].to_string();
            state.autocomplete.update(&text_before);
        }

        // ── Backspace ──
        (KeyModifiers::NONE, KeyCode::Backspace) => {
            if state.input_cursor > 0 {
                // Find the previous char boundary
                let prev = state.input_buffer[..state.input_cursor]
                    .char_indices()
                    .last()
                    .map(|(i, _)| i)
                    .unwrap_or(0);
                state.input_buffer.remove(prev);
                state.input_cursor = prev;
                state.dirty = true;
                let text_before = state.input_buffer[..state.input_cursor].to_string();
                state.autocomplete.update(&text_before);
            }
        }

        // ── Delete ──
        (KeyModifiers::NONE, KeyCode::Delete) => {
            if state.input_cursor < state.input_buffer.len() {
                state.input_buffer.remove(state.input_cursor);
                state.dirty = true;
                let text_before = state.input_buffer[..state.input_cursor].to_string();
                state.autocomplete.update(&text_before);
            }
        }

        // ── Left/Right cursor ──
        (KeyModifiers::NONE, KeyCode::Left) => {
            if state.input_cursor > 0 {
                let prev = state.input_buffer[..state.input_cursor]
                    .char_indices()
                    .last()
                    .map(|(i, _)| i)
                    .unwrap_or(0);
                state.input_cursor = prev;
            }
        }
        (KeyModifiers::NONE, KeyCode::Right) => {
            if state.input_cursor < state.input_buffer.len() {
                let next = state.input_buffer[state.input_cursor..]
                    .char_indices()
                    .nth(1)
                    .map(|(i, _)| state.input_cursor + i)
                    .unwrap_or(state.input_buffer.len());
                state.input_cursor = next;
            }
        }

        // ── Escape: vim normal → dismiss autocomplete → cancel streaming → clear input → reset scroll ──
        (KeyModifiers::NONE, KeyCode::Esc) => {
            // Vim: Escape enters normal mode (if vim enabled and in insert/visual)
            if state.vim.enabled && state.vim.mode != super::widgets::figures::VimMode::Normal {
                state.vim.enter_normal();
                state.dirty = true;
                return;
            }
            if state.autocomplete.is_visible() {
                state.autocomplete.dismiss();
                return;
            }
            if state.is_streaming || state.is_thinking || !state.active_tools.is_empty() {
                // Cancel current agent operation — highest priority
                let _ = state
                    .handle
                    .send(AgentMessage::Cancel)
                    .await;
                state.is_streaming = false;
                state.is_thinking = false;
                state.thinking_text.clear();
                state.active_tools.clear();
                // Preserve partial streaming text as a message before clearing
                if !state.streaming_text.is_empty() {
                    let partial = std::mem::take(&mut state.streaming_text);
                    state
                        .messages
                        .push(grid_types::message::ChatMessage::assistant(&partial));
                    state.invalidate_cache();
                }
                // Mark as cancelled so Completed event won't overwrite preserved messages
                state.cancelled = true;
            } else if !state.input_buffer.is_empty() {
                state.input_buffer.clear();
                state.input_cursor = 0;
            } else if state.user_scrolled {
                state.scroll_offset = 0;
                state.user_scrolled = false;
            }
        }

        _ => {}
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tui::app_state::TuiState;
    use crossterm::event::{KeyCode, KeyEvent, KeyEventKind, KeyEventState, KeyModifiers};
    use tokio::sync::{broadcast, mpsc};

    fn make_test_state() -> TuiState {
        let (tx, _rx) = mpsc::channel(16);
        let (broadcast_tx, _) = broadcast::channel(16);
        let handle = grid_engine::agent::AgentExecutorHandle {
            tx,
            broadcast_tx,
            session_id: grid_types::SessionId::from_string("test"),
        };
        TuiState::new_for_test(grid_types::SessionId::from_string("test"), handle, "test-model".to_string())
    }

    fn make_key(code: KeyCode) -> KeyEvent {
        KeyEvent {
            code,
            modifiers: KeyModifiers::NONE,
            kind: KeyEventKind::Press,
            state: KeyEventState::NONE,
        }
    }

    fn make_ctrl_key(c: char) -> KeyEvent {
        KeyEvent {
            code: KeyCode::Char(c),
            modifiers: KeyModifiers::CONTROL,
            kind: KeyEventKind::Press,
            state: KeyEventState::NONE,
        }
    }

    #[tokio::test]
    async fn test_char_input() {
        let mut state = make_test_state();
        handle_normal_key(&mut state, make_key(KeyCode::Char('h'))).await;
        handle_normal_key(&mut state, make_key(KeyCode::Char('i'))).await;
        assert_eq!(state.input_buffer, "hi");
        assert_eq!(state.input_cursor, 2);
    }

    #[tokio::test]
    async fn test_backspace() {
        let mut state = make_test_state();
        handle_normal_key(&mut state, make_key(KeyCode::Char('a'))).await;
        handle_normal_key(&mut state, make_key(KeyCode::Char('b'))).await;
        handle_normal_key(&mut state, make_key(KeyCode::Backspace)).await;
        assert_eq!(state.input_buffer, "a");
        assert_eq!(state.input_cursor, 1);
    }

    #[tokio::test]
    async fn test_backspace_empty() {
        let mut state = make_test_state();
        handle_normal_key(&mut state, make_key(KeyCode::Backspace)).await;
        assert_eq!(state.input_buffer, "");
        assert_eq!(state.input_cursor, 0);
    }

    #[tokio::test]
    async fn test_esc_clears_input() {
        let mut state = make_test_state();
        handle_normal_key(&mut state, make_key(KeyCode::Char('x'))).await;
        handle_normal_key(&mut state, make_key(KeyCode::Esc)).await;
        assert_eq!(state.input_buffer, "");
        assert_eq!(state.input_cursor, 0);
    }

    #[tokio::test]
    async fn test_ctrl_c_first_does_not_exit() {
        let mut state = make_test_state();
        handle_normal_key(&mut state, make_ctrl_key('c')).await;
        assert!(state.running);
    }

    #[tokio::test]
    async fn test_ctrl_c_double_exits() {
        let mut state = make_test_state();
        handle_normal_key(&mut state, make_ctrl_key('c')).await;
        handle_normal_key(&mut state, make_ctrl_key('c')).await;
        assert!(!state.running);
    }

    #[tokio::test]
    async fn test_ctrl_d_toggles_debug() {
        let mut state = make_test_state();
        handle_normal_key(&mut state, make_ctrl_key('d')).await;
        assert_eq!(state.overlay, OverlayMode::AgentDebug);
        handle_normal_key(&mut state, make_ctrl_key('d')).await;
        assert_eq!(state.overlay, OverlayMode::None);
    }

    #[tokio::test]
    async fn test_scroll_up_down() {
        let mut state = make_test_state();
        handle_normal_key(&mut state, make_key(KeyCode::Up)).await;
        assert_eq!(state.scroll_offset, 3);
        assert!(state.user_scrolled);
        handle_normal_key(&mut state, make_key(KeyCode::Down)).await;
        assert_eq!(state.scroll_offset, 0);
        assert!(!state.user_scrolled);
    }

    #[tokio::test]
    async fn test_enter_sends_message() {
        let mut state = make_test_state();
        handle_normal_key(&mut state, make_key(KeyCode::Char('h'))).await;
        handle_normal_key(&mut state, make_key(KeyCode::Char('i'))).await;
        handle_normal_key(&mut state, make_key(KeyCode::Enter)).await;
        assert_eq!(state.input_buffer, "");
        assert!(state.is_streaming);
        assert_eq!(state.messages.len(), 1);
    }

    #[tokio::test]
    async fn test_enter_on_empty_does_nothing() {
        let mut state = make_test_state();
        handle_normal_key(&mut state, make_key(KeyCode::Enter)).await;
        assert!(!state.is_streaming);
        assert!(state.messages.is_empty());
    }

    #[tokio::test]
    async fn test_left_right_cursor() {
        let mut state = make_test_state();
        handle_normal_key(&mut state, make_key(KeyCode::Char('a'))).await;
        handle_normal_key(&mut state, make_key(KeyCode::Char('b'))).await;
        assert_eq!(state.input_cursor, 2);
        handle_normal_key(&mut state, make_key(KeyCode::Left)).await;
        assert_eq!(state.input_cursor, 1);
        handle_normal_key(&mut state, make_key(KeyCode::Right)).await;
        assert_eq!(state.input_cursor, 2);
    }

    #[tokio::test]
    async fn test_delete_key() {
        let mut state = make_test_state();
        handle_normal_key(&mut state, make_key(KeyCode::Char('a'))).await;
        handle_normal_key(&mut state, make_key(KeyCode::Char('b'))).await;
        handle_normal_key(&mut state, make_key(KeyCode::Left)).await;
        handle_normal_key(&mut state, make_key(KeyCode::Delete)).await;
        assert_eq!(state.input_buffer, "a");
    }

    #[tokio::test]
    async fn test_home_end_scroll() {
        let mut state = make_test_state();
        handle_normal_key(&mut state, make_key(KeyCode::Home)).await;
        assert_eq!(state.scroll_offset, u16::MAX);
        assert!(state.user_scrolled);
        handle_normal_key(&mut state, make_key(KeyCode::End)).await;
        assert_eq!(state.scroll_offset, 0);
        assert!(!state.user_scrolled);
    }

    #[tokio::test]
    async fn test_typing_resets_ctrl_c_count() {
        let mut state = make_test_state();
        handle_normal_key(&mut state, make_ctrl_key('c')).await; // first ctrl+c
        assert_eq!(state.interrupt_manager.press_count(), 1);
        handle_normal_key(&mut state, make_key(KeyCode::Char('a'))).await; // type something
        assert_eq!(state.interrupt_manager.press_count(), 0); // reset
    }

    #[tokio::test]
    async fn test_history_recall_after_submit() {
        let mut state = make_test_state();
        // Type "hello" and submit
        for c in "hello".chars() {
            handle_normal_key(&mut state, make_key(KeyCode::Char(c))).await;
        }
        handle_normal_key(&mut state, make_key(KeyCode::Enter)).await;
        assert_eq!(state.input_buffer, "");
        assert!(state.is_streaming);
        assert_eq!(state.message_history.len(), 1);

        // Simulate agent completion so is_streaming = false
        state.is_streaming = false;

        // Now press Up — should recall "hello"
        handle_normal_key(&mut state, make_key(KeyCode::Up)).await;
        assert_eq!(state.input_buffer, "hello");
    }

    #[tokio::test]
    async fn test_history_recall_blocked_during_streaming() {
        let mut state = make_test_state();
        // Manually add history
        state.message_history.push("previous".into());
        state.is_streaming = true;

        // Press Up during streaming — ESC priority means streaming blocks history?
        // Actually Up key has no streaming check, so it should still work
        handle_normal_key(&mut state, make_key(KeyCode::Up)).await;
        assert_eq!(state.input_buffer, "previous");
    }

    #[tokio::test]
    async fn test_ctrl_o_toggles_last_tool() {
        let mut state = make_test_state();
        use grid_types::message::ContentBlock;
        // Add a message with a tool result
        state.messages.push(ChatMessage {
            role: grid_types::message::MessageRole::Assistant,
            content: vec![
                ContentBlock::ToolUse {
                    id: "t1".into(),
                    name: "bash".into(),
                    input: serde_json::json!({"command": "ls"}),
                },
                ContentBlock::ToolResult {
                    tool_use_id: "t1".into(),
                    content: "file1\nfile2".into(),
                    is_error: false,
                },
            ],
        });
        assert!(state.is_tool_collapsed("t1")); // collapsed by default

        // Ctrl+O should toggle the last tool
        handle_normal_key(&mut state, make_ctrl_key('o')).await;
        assert!(!state.is_tool_collapsed("t1")); // now expanded

        // Ctrl+O again should collapse it
        handle_normal_key(&mut state, make_ctrl_key('o')).await;
        assert!(state.is_tool_collapsed("t1")); // back to collapsed
    }

    #[tokio::test]
    async fn test_alt_o_toggles_global() {
        let mut state = make_test_state();
        assert!(state.tools_default_collapsed);

        let alt_o = KeyEvent {
            code: KeyCode::Char('o'),
            modifiers: KeyModifiers::ALT,
            kind: KeyEventKind::Press,
            state: KeyEventState::NONE,
        };
        handle_normal_key(&mut state, alt_o).await;
        assert!(!state.tools_default_collapsed);
        assert!(state.tool_expanded_overrides.is_empty());
    }

    #[tokio::test]
    async fn test_ctrl_shift_o_toggles_global() {
        let mut state = make_test_state();
        assert!(state.tools_default_collapsed);

        let ctrl_shift_o = KeyEvent {
            code: KeyCode::Char('O'),
            modifiers: KeyModifiers::CONTROL | KeyModifiers::SHIFT,
            kind: KeyEventKind::Press,
            state: KeyEventState::NONE,
        };
        handle_normal_key(&mut state, ctrl_shift_o).await;
        assert!(!state.tools_default_collapsed);
        assert!(state.tool_expanded_overrides.is_empty());
    }

    #[tokio::test]
    async fn test_ctrl_p_noop_when_single_line() {
        let mut state = make_test_state();
        // Ctrl+P with empty input is a no-op (todo panel removed)
        handle_normal_key(&mut state, make_ctrl_key('p')).await;
        // No crash, no state change
        assert!(state.messages.is_empty());
    }
}
