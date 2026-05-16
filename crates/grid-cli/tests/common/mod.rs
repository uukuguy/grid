//! Shared test scaffolding for grid-cli integration tests (Phase 5.2 T-01.14, T-01.19).
//!
//! Only compiled when the `studio` feature is enabled, because the TUI
//! tests pull in `grid_cli::tui` (which is itself `cfg(feature = "studio")`).

#![cfg(feature = "studio")]

use crossterm::event::{KeyCode, KeyEvent, KeyEventKind, KeyEventState, KeyModifiers};
use grid_cli::tui::app_state::TuiState;
use grid_engine::agent::AgentExecutorHandle;
use grid_types::SessionId;
use tokio::sync::{broadcast, mpsc};

/// Build a fresh in-memory `TuiState` suitable for cross-mode integration tests.
///
/// Skips file-backed history (no `~/.grid/.../tui_history.txt` writes) and any
/// git probing. Matches the `make_test_state` helper used inside
/// `tui/key_handlers/mod.rs#integration_tests`, but lives outside `cfg(test)`
/// so external integration tests can use it too.
pub fn fresh_state() -> TuiState {
    let (tx, _rx) = mpsc::channel(16);
    let (broadcast_tx, _) = broadcast::channel(16);
    let handle = AgentExecutorHandle {
        tx,
        broadcast_tx,
        session_id: SessionId::from_string("test"),
    };
    TuiState::new_for_test(
        SessionId::from_string("test"),
        handle,
        "test-model".to_string(),
    )
}

pub fn key(code: KeyCode) -> KeyEvent {
    KeyEvent {
        code,
        modifiers: KeyModifiers::NONE,
        kind: KeyEventKind::Press,
        state: KeyEventState::NONE,
    }
}

pub fn ctrl(c: char) -> KeyEvent {
    KeyEvent {
        code: KeyCode::Char(c),
        modifiers: KeyModifiers::CONTROL,
        kind: KeyEventKind::Press,
        state: KeyEventState::NONE,
    }
}
