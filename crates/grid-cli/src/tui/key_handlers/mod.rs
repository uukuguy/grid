//! Keyboard event handlers for the conversation-centric TUI.
//!
//! This module is organized into mode-specific handlers:
//!
//! - [`common`] - Shared utilities (scroll acceleration, external editor)
//! - [`slash_commands`] - Execution of local `/` commands
//! - [`normal`] - Main chat/input mode handler
//! - [`vim_insert`] - Vim insert mode handler
//! - [`vim_normal`] - Vim normal mode handler
//! - [`history_search`] - Reverse incremental search (Ctrl+R)
//! - [`model_selector`] - Model selection popup
//! - [`overlay`] - Overlay panel key handling
//! - [`approval`] - Tool approval dialog handling
//!
//! The main entry point is [`handle_key`] which dispatches to the
//! appropriate mode handler based on current state.

pub mod approval;
pub mod common;
pub mod history_search;
pub mod model_selector;
pub mod normal;
pub mod overlay;
pub mod slash_commands;
pub mod vim_insert;
pub mod vim_normal;

// Re-export commonly used items
pub use common::{compute_scroll_amount, open_external_editor};
pub use slash_commands::execute_slash_command;

use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};

use crate::tui::app_state::TuiState;

/// Handle a keyboard event, mutating TuiState accordingly.
///
/// This is the main entry point that dispatches to the appropriate
/// mode handler based on current state.
pub async fn handle_key(state: &mut TuiState, key: KeyEvent) {
    // If an overlay is active, route to overlay key handler
    if state.overlay != super::app_state::OverlayMode::None {
        overlay::handle_overlay_key(state, key).await;
        return;
    }

    // If approval dialog is showing, route to approval handler
    if state.pending_approval.is_some() {
        approval::handle_approval_key(state, key).await;
        return;
    }

    // If model selector is visible, route to model selector handler
    if state.model_selector.visible {
        model_selector::handle_model_selector_key(state, key);
        return;
    }

    // If vim mode is enabled and in Normal mode, handle vim keybindings
    if state.vim.enabled && state.vim.mode == super::widgets::figures::VimMode::Normal {
        vim_normal::handle_vim_normal_key(state, key);

        // If we handled a vim key (non-Ctrl), return
        if !key.modifiers.contains(KeyModifiers::CONTROL) {
            return;
        }
        // Ctrl shortcuts fall through to normal handler
    }

    // If vim mode is enabled and in Insert mode
    if state.vim.enabled && state.vim.mode == super::widgets::figures::VimMode::Insert {
        vim_insert::handle_vim_insert_key(state, key);
        return;
    }

    // If history search is active, route to search handler
    if state.history_search.active {
        history_search::handle_history_search_key(state, key);
        return;
    }

    // Otherwise, handle in normal mode
    normal::handle_normal_key(state, key).await;
}

#[cfg(test)]
mod integration_tests {
    use super::*;
    use crate::tui::app_state::{PendingApproval, TuiState};
    use crossterm::event::{KeyCode, KeyEvent, KeyEventKind, KeyEventState, KeyModifiers};
    use grid_types::message::ContentBlock;
    use grid_types::tool::RiskLevel;
    use tokio::sync::{broadcast, mpsc};

    fn make_test_state() -> TuiState {
        let (tx, _rx) = mpsc::channel(16);
        let (broadcast_tx, _) = broadcast::channel(16);
        let handle = grid_engine::agent::AgentExecutorHandle {
            tx,
            broadcast_tx,
            session_id: grid_types::SessionId::from_string("test"),
        };
        TuiState::new_for_test(
            grid_types::SessionId::from_string("test"),
            handle,
            "test-model".to_string(),
        )
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

    // Tests from original key_handler.rs

    #[tokio::test]
    async fn test_char_input() {
        let mut state = make_test_state();
        handle_key(&mut state, make_key(KeyCode::Char('h'))).await;
        handle_key(&mut state, make_key(KeyCode::Char('i'))).await;
        assert_eq!(state.input_buffer, "hi");
        assert_eq!(state.input_cursor, 2);
    }

    #[tokio::test]
    async fn test_backspace() {
        let mut state = make_test_state();
        handle_key(&mut state, make_key(KeyCode::Char('a'))).await;
        handle_key(&mut state, make_key(KeyCode::Char('b'))).await;
        handle_key(&mut state, make_key(KeyCode::Backspace)).await;
        assert_eq!(state.input_buffer, "a");
        assert_eq!(state.input_cursor, 1);
    }

    #[tokio::test]
    async fn test_backspace_empty() {
        let mut state = make_test_state();
        handle_key(&mut state, make_key(KeyCode::Backspace)).await;
        assert_eq!(state.input_buffer, "");
        assert_eq!(state.input_cursor, 0);
    }

    #[tokio::test]
    async fn test_esc_clears_input() {
        let mut state = make_test_state();
        handle_key(&mut state, make_key(KeyCode::Char('x'))).await;
        handle_key(&mut state, make_key(KeyCode::Esc)).await;
        assert_eq!(state.input_buffer, "");
        assert_eq!(state.input_cursor, 0);
    }

    #[tokio::test]
    async fn test_ctrl_c_first_does_not_exit() {
        let mut state = make_test_state();
        handle_key(&mut state, make_ctrl_key('c')).await;
        assert!(state.running);
    }

    #[tokio::test]
    async fn test_ctrl_c_double_exits() {
        let mut state = make_test_state();
        handle_key(&mut state, make_ctrl_key('c')).await;
        handle_key(&mut state, make_ctrl_key('c')).await;
        assert!(!state.running);
    }

    #[tokio::test]
    async fn test_ctrl_d_toggles_debug() {
        let mut state = make_test_state();
        handle_key(&mut state, make_ctrl_key('d')).await;
        assert_eq!(state.overlay, super::super::app_state::OverlayMode::AgentDebug);
        handle_key(&mut state, make_ctrl_key('d')).await;
        assert_eq!(state.overlay, super::super::app_state::OverlayMode::None);
    }

    #[tokio::test]
    async fn test_scroll_up_down() {
        let mut state = make_test_state();
        handle_key(&mut state, make_key(KeyCode::Up)).await;
        assert_eq!(state.scroll_offset, 3);
        assert!(state.user_scrolled);
        handle_key(&mut state, make_key(KeyCode::Down)).await;
        assert_eq!(state.scroll_offset, 0);
        assert!(!state.user_scrolled);
    }

    #[tokio::test]
    async fn test_enter_sends_message() {
        let mut state = make_test_state();
        handle_key(&mut state, make_key(KeyCode::Char('h'))).await;
        handle_key(&mut state, make_key(KeyCode::Char('i'))).await;
        handle_key(&mut state, make_key(KeyCode::Enter)).await;
        assert_eq!(state.input_buffer, "");
        assert!(state.is_streaming);
        assert_eq!(state.messages.len(), 1);
    }

    #[tokio::test]
    async fn test_enter_on_empty_does_nothing() {
        let mut state = make_test_state();
        handle_key(&mut state, make_key(KeyCode::Enter)).await;
        assert!(!state.is_streaming);
        assert!(state.messages.is_empty());
    }

    #[tokio::test]
    async fn test_left_right_cursor() {
        let mut state = make_test_state();
        handle_key(&mut state, make_key(KeyCode::Char('a'))).await;
        handle_key(&mut state, make_key(KeyCode::Char('b'))).await;
        assert_eq!(state.input_cursor, 2);
        handle_key(&mut state, make_key(KeyCode::Left)).await;
        assert_eq!(state.input_cursor, 1);
        handle_key(&mut state, make_key(KeyCode::Right)).await;
        assert_eq!(state.input_cursor, 2);
    }

    #[tokio::test]
    async fn test_overlay_esc_closes() {
        let mut state = make_test_state();
        state.overlay = super::super::app_state::OverlayMode::AgentDebug;
        handle_key(&mut state, make_key(KeyCode::Esc)).await;
        assert_eq!(state.overlay, super::super::app_state::OverlayMode::None);
    }

    #[tokio::test]
    async fn test_delete_key() {
        let mut state = make_test_state();
        handle_key(&mut state, make_key(KeyCode::Char('a'))).await;
        handle_key(&mut state, make_key(KeyCode::Char('b'))).await;
        handle_key(&mut state, make_key(KeyCode::Left)).await;
        handle_key(&mut state, make_key(KeyCode::Delete)).await;
        assert_eq!(state.input_buffer, "a");
    }

    #[tokio::test]
    async fn test_home_end_scroll() {
        let mut state = make_test_state();
        handle_key(&mut state, make_key(KeyCode::Home)).await;
        assert_eq!(state.scroll_offset, u16::MAX);
        assert!(state.user_scrolled);
        handle_key(&mut state, make_key(KeyCode::End)).await;
        assert_eq!(state.scroll_offset, 0);
        assert!(!state.user_scrolled);
    }

    #[tokio::test]
    async fn test_typing_resets_ctrl_c_count() {
        let mut state = make_test_state();
        handle_key(&mut state, make_ctrl_key('c')).await; // first ctrl+c
        assert_eq!(state.interrupt_manager.press_count(), 1);
        handle_key(&mut state, make_key(KeyCode::Char('a'))).await; // type something
        assert_eq!(state.interrupt_manager.press_count(), 0); // reset
    }

    #[tokio::test]
    async fn test_history_recall_after_submit() {
        let mut state = make_test_state();
        // Type "hello" and submit
        for c in "hello".chars() {
            handle_key(&mut state, make_key(KeyCode::Char(c))).await;
        }
        handle_key(&mut state, make_key(KeyCode::Enter)).await;
        assert_eq!(state.input_buffer, "");
        assert!(state.is_streaming);
        assert_eq!(state.message_history.len(), 1);

        // Simulate agent completion so is_streaming = false
        state.is_streaming = false;

        // Now press Up — should recall "hello"
        handle_key(&mut state, make_key(KeyCode::Up)).await;
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
        handle_key(&mut state, make_key(KeyCode::Up)).await;
        assert_eq!(state.input_buffer, "previous");
    }

    #[tokio::test]
    async fn test_ctrl_o_toggles_last_tool() {
        let mut state = make_test_state();
        // Add a message with a tool result
        state.messages.push(grid_types::message::ChatMessage {
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
        handle_key(&mut state, make_ctrl_key('o')).await;
        assert!(!state.is_tool_collapsed("t1")); // now expanded

        // Ctrl+O again should collapse it
        handle_key(&mut state, make_ctrl_key('o')).await;
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
        handle_key(&mut state, alt_o).await;
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
        handle_key(&mut state, ctrl_shift_o).await;
        assert!(!state.tools_default_collapsed);
        assert!(state.tool_expanded_overrides.is_empty());
    }

    #[test]
    fn test_scroll_acceleration_levels() {
        let mut state = make_test_state();
        // First scroll: level 0 = 3 lines
        let amount = compute_scroll_amount(&mut state, true);
        assert_eq!(amount, 3);
        // Immediately again (same direction): level 1 = 6 lines
        let amount = compute_scroll_amount(&mut state, true);
        assert_eq!(amount, 6);
        // Again: level 2 = 12 lines
        let amount = compute_scroll_amount(&mut state, true);
        assert_eq!(amount, 12);
        // Caps at 12
        let amount = compute_scroll_amount(&mut state, true);
        assert_eq!(amount, 12);
    }

    #[test]
    fn test_scroll_direction_change_resets() {
        let mut state = make_test_state();
        compute_scroll_amount(&mut state, true);  // level 0
        compute_scroll_amount(&mut state, true);  // level 1
        // Direction change → reset to level 0
        let amount = compute_scroll_amount(&mut state, false);
        assert_eq!(amount, 3);
    }

    #[tokio::test]
    async fn test_ctrl_p_noop_when_single_line() {
        let mut state = make_test_state();
        // Ctrl+P with empty input is a no-op (todo panel removed)
        handle_key(&mut state, make_ctrl_key('p')).await;
        // No crash, no state change
        assert!(state.messages.is_empty());
    }

    #[test]
    fn test_scroll_accel_state_fields() {
        let state = make_test_state();
        assert!(state.scroll_last_dir.is_none());
        assert!(state.scroll_last_time.is_none());
        assert_eq!(state.scroll_accel, 0);
    }

    #[tokio::test]
    async fn test_slash_command_help() {
        let mut state = make_test_state();
        execute_slash_command(&mut state, "/help").await;
        assert_eq!(state.messages.len(), 1);
        let text = match &state.messages[0].content[0] {
            ContentBlock::Text { text } => text.clone(),
            _ => String::new(),
        };
        assert!(text.contains("/help"), "Help output should list /help command");
        assert!(text.contains("/debug"), "Help output should list /debug command");
    }

    #[tokio::test]
    async fn test_slash_command_clear() {
        let mut state = make_test_state();
        state.messages.push(grid_types::message::ChatMessage::user("hello"));
        state.messages.push(grid_types::message::ChatMessage::assistant("hi"));
        execute_slash_command(&mut state, "/clear").await;
        assert!(state.messages.is_empty());
    }

    #[tokio::test]
    async fn test_slash_command_exit() {
        let mut state = make_test_state();
        assert!(state.running);
        execute_slash_command(&mut state, "/exit").await;
        assert!(!state.running);
    }

    #[tokio::test]
    async fn test_slash_command_quit() {
        let mut state = make_test_state();
        execute_slash_command(&mut state, "/quit").await;
        assert!(!state.running);
    }

    #[tokio::test]
    async fn test_slash_command_debug_toggle() {
        let mut state = make_test_state();
        assert_eq!(state.overlay, super::super::app_state::OverlayMode::None);
        execute_slash_command(&mut state, "/debug").await;
        assert_eq!(state.overlay, super::super::app_state::OverlayMode::AgentDebug);
        execute_slash_command(&mut state, "/debug").await;
        assert_eq!(state.overlay, super::super::app_state::OverlayMode::None);
    }

    #[tokio::test]
    async fn test_slash_command_eval_toggle() {
        let mut state = make_test_state();
        execute_slash_command(&mut state, "/eval").await;
        assert_eq!(state.overlay, super::super::app_state::OverlayMode::Eval);
        execute_slash_command(&mut state, "/eval").await;
        assert_eq!(state.overlay, super::super::app_state::OverlayMode::None);
    }

    #[tokio::test]
    async fn test_slash_command_sessions_toggle() {
        let mut state = make_test_state();
        execute_slash_command(&mut state, "/sessions").await;
        assert_eq!(state.overlay, super::super::app_state::OverlayMode::SessionPicker);
    }

    #[tokio::test]
    async fn test_slash_command_todo_shows_message() {
        let mut state = make_test_state();
        execute_slash_command(&mut state, "/todo").await;
        // /todo now shows an informational message instead of toggling a panel
        assert_eq!(state.messages.len(), 1);
    }

    #[tokio::test]
    async fn test_slash_command_unknown() {
        let mut state = make_test_state();
        execute_slash_command(&mut state, "/foobar").await;
        assert_eq!(state.messages.len(), 1);
        let text = match &state.messages[0].content[0] {
            ContentBlock::Text { text } => text.clone(),
            _ => String::new(),
        };
        assert!(text.contains("Unknown command"));
    }

    #[tokio::test]
    async fn test_slash_command_via_enter() {
        let mut state = make_test_state();
        // Type "/help" — autocomplete will show
        for c in "/help".chars() {
            handle_key(&mut state, make_key(KeyCode::Char(c))).await;
        }
        // First Enter: accepts autocomplete (inserts "/help")
        handle_key(&mut state, make_key(KeyCode::Enter)).await;
        assert_eq!(state.input_buffer, "/help");
        // Second Enter: executes the slash command
        handle_key(&mut state, make_key(KeyCode::Enter)).await;
        // Should NOT be streaming (local command, not sent to agent)
        assert!(!state.is_streaming);
        // Should have help message
        assert_eq!(state.messages.len(), 1);
    }

    #[tokio::test]
    async fn test_autocomplete_triggers_on_slash() {
        let mut state = make_test_state();
        handle_key(&mut state, make_key(KeyCode::Char('/'))).await;
        // Autocomplete should be visible with all slash commands
        assert!(state.autocomplete.is_visible());
        assert!(!state.autocomplete.items().is_empty());
    }

    #[tokio::test]
    async fn test_autocomplete_dismiss_on_esc() {
        let mut state = make_test_state();
        handle_key(&mut state, make_key(KeyCode::Char('/'))).await;
        assert!(state.autocomplete.is_visible());
        handle_key(&mut state, make_key(KeyCode::Esc)).await;
        assert!(!state.autocomplete.is_visible());
    }

    #[tokio::test]
    async fn test_autocomplete_accept_on_tab() {
        let mut state = make_test_state();
        // Type "/hel" to trigger autocomplete
        for c in "/hel".chars() {
            handle_key(&mut state, make_key(KeyCode::Char(c))).await;
        }
        assert!(state.autocomplete.is_visible());
        // Tab to accept
        handle_key(&mut state, make_key(KeyCode::Tab)).await;
        assert!(!state.autocomplete.is_visible());
        assert_eq!(state.input_buffer, "/help");
    }

    // Tool expansion tests

    #[test]
    fn test_tool_collapsed_by_default() {
        let state = make_test_state();
        assert!(state.is_tool_collapsed("any-tool-id"));
        assert!(state.tools_default_collapsed);
    }

    #[test]
    fn test_tool_expand_override() {
        let mut state = make_test_state();
        state.tool_expanded_overrides.insert("t1".into(), true);
        assert!(!state.is_tool_collapsed("t1")); // expanded
        assert!(state.is_tool_collapsed("t2")); // others still collapsed
    }

    #[test]
    fn test_global_toggle_clears_overrides() {
        let mut state = make_test_state();
        state.tool_expanded_overrides.insert("t1".into(), true);
        // Simulate Alt+O: toggle global + clear overrides
        state.tools_default_collapsed = !state.tools_default_collapsed;
        state.tool_expanded_overrides.clear();
        assert!(!state.is_tool_collapsed("t1")); // follows global (now false)
    }
}
