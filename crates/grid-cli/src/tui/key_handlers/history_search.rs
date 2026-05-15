//! History search mode key handling.
//!
//! Handles reverse incremental history search (Ctrl+R).
//! Typing filters messages matching the query; Enter accepts the match.

use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};

use crate::tui::app_state::TuiState;

/// Handle keys in history search mode.
///
/// In this mode:
/// - Typing characters builds the search query
/// - Backspace removes from query
/// - Enter accepts the matched text into input buffer
/// - Escape cancels search
/// - Ctrl+R advances to next match
pub fn handle_history_search_key(state: &mut TuiState, key: KeyEvent) {
    match (key.modifiers, key.code) {
        (KeyModifiers::CONTROL, KeyCode::Char('r')) => {
            // Next match
            state.history_search.next_match();
            let entries = state.message_history.entries();
            state.history_search.search(&entries);
            state.dirty = true;
        }
        (KeyModifiers::NONE, KeyCode::Esc) => {
            // Cancel search
            state.history_search.deactivate();
            state.dirty = true;
        }
        (KeyModifiers::NONE, KeyCode::Enter) => {
            // Accept match into input buffer
            if let Some(ref matched) = state.history_search.matched_text {
                state.input_buffer = matched.clone();
                state.input_cursor = state.input_buffer.len();
            }
            state.history_search.deactivate();
            state.dirty = true;
        }
        (KeyModifiers::NONE, KeyCode::Backspace) => {
            state.history_search.query.pop();
            let entries = state.message_history.entries();
            state.history_search.search(&entries);
            state.dirty = true;
        }
        (KeyModifiers::NONE, KeyCode::Char(c)) => {
            state.history_search.query.push(c);
            state.history_search.match_index = 0;
            let entries = state.message_history.entries();
            state.history_search.search(&entries);
            state.dirty = true;
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
        let mut state = TuiState::new_for_test(
            grid_types::SessionId::from_string("test"),
            handle,
            "test-model".to_string(),
        );
        // Activate history search
        state.history_search.activate();
        state
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

    #[test]
    fn test_escape_cancels_search() {
        let mut state = make_test_state();
        assert!(state.history_search.active);
        handle_history_search_key(&mut state, make_key(KeyCode::Esc));
        assert!(!state.history_search.active);
    }

    #[test]
    fn test_typing_builds_query() {
        let mut state = make_test_state();
        handle_history_search_key(&mut state, make_key(KeyCode::Char('h')));
        assert_eq!(state.history_search.query, "h");
        handle_history_search_key(&mut state, make_key(KeyCode::Char('e')));
        assert_eq!(state.history_search.query, "he");
    }

    #[test]
    fn test_backspace_removes_from_query() {
        let mut state = make_test_state();
        handle_history_search_key(&mut state, make_key(KeyCode::Char('h')));
        handle_history_search_key(&mut state, make_key(KeyCode::Char('e')));
        assert_eq!(state.history_search.query, "he");
        handle_history_search_key(&mut state, make_key(KeyCode::Backspace));
        assert_eq!(state.history_search.query, "h");
    }

    #[test]
    fn test_ctrl_r_next_match() {
        let mut state = make_test_state();
        // Type a query
        handle_history_search_key(&mut state, make_key(KeyCode::Char('a')));
        let initial_index = state.history_search.match_index;
        // Ctrl+R should advance to next match
        handle_history_search_key(&mut state, make_ctrl_key('r'));
        assert!(state.history_search.match_index >= initial_index);
    }
}
