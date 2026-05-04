//! Overlay mode key handling.
//!
//! Handles keyboard input when an overlay panel is active.

use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};

use super::app_state::{OverlayMode, TuiState};

/// Handle keys when an overlay is active.
///
/// Overlays include:
/// - AgentDebug: Shows agent debugging information
/// - Eval: Shows token/cost evaluation
/// - SessionPicker: Shows session selection list
///
/// In overlay mode:
/// - Escape closes the overlay
/// - Ctrl+D toggles agent debug
/// - Ctrl+E toggles eval
/// - Ctrl+A toggles session picker
/// - Ctrl+C handles cancellation
pub async fn handle_overlay_key(state: &mut TuiState, key: KeyEvent) {
    match (key.modifiers, key.code) {
        (KeyModifiers::NONE, KeyCode::Esc) => {
            state.overlay = OverlayMode::None;
        }
        (KeyModifiers::CONTROL, KeyCode::Char('d')) => {
            state.overlay = if state.overlay == OverlayMode::AgentDebug {
                OverlayMode::None
            } else {
                OverlayMode::AgentDebug
            };
        }
        (KeyModifiers::CONTROL, KeyCode::Char('e')) => {
            state.overlay = if state.overlay == OverlayMode::Eval {
                OverlayMode::None
            } else {
                OverlayMode::Eval
            };
        }
        (KeyModifiers::CONTROL, KeyCode::Char('a')) => {
            state.overlay = if state.overlay == OverlayMode::SessionPicker {
                OverlayMode::None
            } else {
                OverlayMode::SessionPicker
            };
        }
        (KeyModifiers::CONTROL, KeyCode::Char('c')) => {
            if state.interrupt_manager.handle_ctrl_c().await {
                state.running = false;
            }
        }
        _ => {} // Overlays handle their own keys in T3
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
        // Show overlay
        state.overlay = OverlayMode::AgentDebug;
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

    #[tokio::test]
    async fn test_esc_closes_overlay() {
        let mut state = make_test_state();
        assert_eq!(state.overlay, OverlayMode::AgentDebug);
        handle_overlay_key(&mut state, make_key(KeyCode::Esc)).await;
        assert_eq!(state.overlay, OverlayMode::None);
    }

    #[tokio::test]
    async fn test_ctrl_d_toggles_debug() {
        let mut state = make_test_state();
        assert_eq!(state.overlay, OverlayMode::AgentDebug);
        handle_overlay_key(&mut state, make_ctrl_key('d')).await;
        assert_eq!(state.overlay, OverlayMode::None);
        handle_overlay_key(&mut state, make_ctrl_key('d')).await;
        assert_eq!(state.overlay, OverlayMode::AgentDebug);
    }

    #[tokio::test]
    async fn test_ctrl_e_toggles_eval() {
        let mut state = make_test_state();
        state.overlay = OverlayMode::Eval;
        assert_eq!(state.overlay, OverlayMode::Eval);
        handle_overlay_key(&mut state, make_ctrl_key('e')).await;
        assert_eq!(state.overlay, OverlayMode::None);
    }

    #[tokio::test]
    async fn test_ctrl_a_toggles_session_picker() {
        let mut state = make_test_state();
        state.overlay = OverlayMode::SessionPicker;
        assert_eq!(state.overlay, OverlayMode::SessionPicker);
        handle_overlay_key(&mut state, make_ctrl_key('a')).await;
        assert_eq!(state.overlay, OverlayMode::None);
    }
}
