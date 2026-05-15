//! Common utilities for keyboard handlers.
//!
//! Shared functions used across multiple handler modules.

use std::time::Instant;

use crossterm::event::{KeyCode, KeyModifiers};

use crate::tui::app_state::TuiState;

const SCROLL_AMOUNTS: [u16; 3] = [3, 6, 12];
const SCROLL_ACCEL_WINDOW_MS: u128 = 200;

/// Compute the scroll amount with 3-level acceleration.
///
/// Rapidly scrolling in the same direction within 200ms accelerates:
/// level 0 = 3 lines, level 1 = 6 lines, level 2 = 12 lines.
/// Changing direction or pausing resets to level 0.
pub fn compute_scroll_amount(state: &mut TuiState, direction_up: bool) -> u16 {
    let now = Instant::now();
    let same_dir = state.scroll_last_dir == Some(direction_up);
    let within_window = state
        .scroll_last_time
        .map(|t| now.duration_since(t).as_millis() < SCROLL_ACCEL_WINDOW_MS)
        .unwrap_or(false);

    if same_dir && within_window {
        state.scroll_accel = (state.scroll_accel + 1).min(2);
    } else {
        state.scroll_accel = 0;
    }

    state.scroll_last_dir = Some(direction_up);
    state.scroll_last_time = Some(now);
    SCROLL_AMOUNTS[state.scroll_accel as usize]
}

/// Open an external editor ($EDITOR or vi) with the given text content.
///
/// Writes text to a temp file, opens the editor, waits for it to close,
/// then reads back the edited content.
pub fn open_external_editor(text: &str) -> Result<String, std::io::Error> {
    use std::io::Write;

    let editor = std::env::var("EDITOR").unwrap_or_else(|_| "vi".to_string());
    let tmp_dir = std::env::temp_dir();
    let tmp_path = tmp_dir.join("grid_input.tmp");

    // Write current text to temp file
    {
        let mut file = std::fs::File::create(&tmp_path)?;
        file.write_all(text.as_bytes())?;
    }

    // Leave alternate screen and raw mode for the editor
    let _ = crossterm::terminal::disable_raw_mode();
    let _ = crossterm::execute!(
        std::io::stdout(),
        crossterm::terminal::LeaveAlternateScreen
    );

    // Open editor
    let status = std::process::Command::new(&editor)
        .arg(&tmp_path)
        .status()?;

    // Re-enter alternate screen and raw mode
    let _ = crossterm::terminal::enable_raw_mode();
    let _ = crossterm::execute!(
        std::io::stdout(),
        crossterm::terminal::EnterAlternateScreen
    );

    if !status.success() {
        let _ = std::fs::remove_file(&tmp_path);
        return Err(std::io::Error::new(
            std::io::ErrorKind::Other,
            "Editor exited with non-zero status",
        ));
    }

    // Read back edited content
    let result = std::fs::read_to_string(&tmp_path)?;
    let _ = std::fs::remove_file(&tmp_path);
    Ok(result.trim_end().to_string())
}

/// Helper to check if a key event represents Ctrl+C.
pub fn is_ctrl_c(key: &crossterm::event::KeyEvent) -> bool {
    matches!(
        (key.modifiers, key.code),
        (KeyModifiers::CONTROL, KeyCode::Char('c'))
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_scroll_acceleration_levels() {
        let mut state = TuiState::new_for_test(
            grid_types::SessionId::from_string("test"),
            create_test_handle(),
            "test-model".to_string(),
        );
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
        let mut state = TuiState::new_for_test(
            grid_types::SessionId::from_string("test"),
            create_test_handle(),
            "test-model".to_string(),
        );
        compute_scroll_amount(&mut state, true);  // level 0
        compute_scroll_amount(&mut state, true);  // level 1
        // Direction change → reset to level 0
        let amount = compute_scroll_amount(&mut state, false);
        assert_eq!(amount, 3);
    }

    fn create_test_handle() -> grid_engine::agent::AgentExecutorHandle {
        use tokio::sync::{broadcast, mpsc};
        let (tx, _rx) = mpsc::channel(16);
        let (broadcast_tx, _) = broadcast::channel(16);
        grid_engine::agent::AgentExecutorHandle {
            tx,
            broadcast_tx,
            session_id: grid_types::SessionId::from_string("test"),
        }
    }
}
