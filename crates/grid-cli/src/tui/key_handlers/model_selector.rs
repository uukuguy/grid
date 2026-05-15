//! Model selector key handling.
//!
//! Handles keyboard input when the model selector popup is visible.

use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};

use crate::tui::app_state::TuiState;

/// Handle keys when model selector is visible.
///
/// In this mode:
/// - Up/Down (or j/k) navigates model list
/// - Enter confirms selection
/// - Escape cancels selection
/// - Alt+P also closes the selector
pub fn handle_model_selector_key(state: &mut TuiState, key: KeyEvent) {
    match (key.modifiers, key.code) {
        (KeyModifiers::NONE, KeyCode::Esc) | (KeyModifiers::ALT, KeyCode::Char('p')) => {
            state.model_selector.visible = false;
            state.dirty = true;
        }
        (KeyModifiers::NONE, KeyCode::Up) | (KeyModifiers::NONE, KeyCode::Char('k')) => {
            state.model_selector.prev();
            state.dirty = true;
        }
        (KeyModifiers::NONE, KeyCode::Down) | (KeyModifiers::NONE, KeyCode::Char('j')) => {
            state.model_selector.next();
            state.dirty = true;
        }
        (KeyModifiers::NONE, KeyCode::Enter) => {
            if let Some(model) = state.model_selector.confirm() {
                state.model_name = model;
                state.dirty = true;
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
        let mut state = TuiState::new_for_test(
            grid_types::SessionId::from_string("test"),
            handle,
            "test-model".to_string(),
        );
        // Show model selector
        state.model_selector.visible = true;
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

    #[test]
    fn test_escape_closes_selector() {
        let mut state = make_test_state();
        assert!(state.model_selector.visible);
        handle_model_selector_key(&mut state, make_key(KeyCode::Esc));
        assert!(!state.model_selector.visible);
    }

    #[test]
    fn test_up_navigates() {
        let mut state = make_test_state();
        let initial = state.model_selector.selected;
        handle_model_selector_key(&mut state, make_key(KeyCode::Up));
        // Should move to previous (may wrap)
        assert!(state.dirty);
    }

    #[test]
    fn test_down_navigates() {
        let mut state = make_test_state();
        handle_model_selector_key(&mut state, make_key(KeyCode::Down));
        assert!(state.dirty);
    }

    #[test]
    fn test_enter_confirms() {
        let mut state = make_test_state();
        handle_model_selector_key(&mut state, make_key(KeyCode::Enter));
        assert!(!state.model_selector.visible);
    }

    #[test]
    fn test_jk_navigation() {
        let mut state = make_test_state();
        handle_model_selector_key(&mut state, make_key(KeyCode::Char('j')));
        assert!(state.dirty);
        handle_model_selector_key(&mut state, make_key(KeyCode::Char('k')));
        assert!(state.dirty);
    }
}
