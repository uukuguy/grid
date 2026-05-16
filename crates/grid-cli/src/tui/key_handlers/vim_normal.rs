//! Vim normal mode key handling.
//!
//! In Vim normal mode, keys perform actions rather than inserting text.
//! This includes navigation, editing, and mode transitions.

use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};

use crate::tui::app_state::TuiState;

/// Handle keys in Vim normal mode.
///
/// In normal mode, keys perform actions:
/// - `i`, `a`, `A`, `I` → enter insert mode
/// - `h`, `l`, `w`, `b` → navigation
/// - `x` → delete character
/// - `v` → enter visual mode
/// - Ctrl shortcuts pass through to normal handler
pub fn handle_vim_normal_key(state: &mut TuiState, key: KeyEvent) {
    match (key.modifiers, key.code) {
        // ── Enter insert mode ──
        (KeyModifiers::NONE, KeyCode::Char('i')) => {
            state.vim.enter_insert();
            state.dirty = true;
        }
        (KeyModifiers::NONE, KeyCode::Char('a')) => {
            // Insert after cursor
            if state.input_cursor < state.input_buffer.len() {
                let next = state.input_buffer[state.input_cursor..]
                    .char_indices()
                    .nth(1)
                    .map(|(i, _)| state.input_cursor + i)
                    .unwrap_or(state.input_buffer.len());
                state.input_cursor = next;
            }
            state.vim.enter_insert();
            state.dirty = true;
        }
        (KeyModifiers::SHIFT, KeyCode::Char('A')) => {
            // Insert at end of line
            state.input_cursor = state.input_buffer.len();
            state.vim.enter_insert();
            state.dirty = true;
        }
        (KeyModifiers::SHIFT, KeyCode::Char('I')) => {
            // Insert at beginning
            state.input_cursor = 0;
            state.vim.enter_insert();
            state.dirty = true;
        }

        // ── Navigation ──
        (KeyModifiers::NONE, KeyCode::Char('h')) | (KeyModifiers::NONE, KeyCode::Left) => {
            if state.input_cursor > 0 {
                let prev = state.input_buffer[..state.input_cursor]
                    .char_indices()
                    .last()
                    .map(|(i, _)| i)
                    .unwrap_or(0);
                state.input_cursor = prev;
            }
        }
        (KeyModifiers::NONE, KeyCode::Char('l')) | (KeyModifiers::NONE, KeyCode::Right) => {
            if state.input_cursor < state.input_buffer.len() {
                let next = state.input_buffer[state.input_cursor..]
                    .char_indices()
                    .nth(1)
                    .map(|(i, _)| state.input_cursor + i)
                    .unwrap_or(state.input_buffer.len());
                state.input_cursor = next;
            }
        }
        (KeyModifiers::NONE, KeyCode::Char('0')) => {
            state.input_cursor = 0;
        }
        (KeyModifiers::SHIFT, KeyCode::Char('$')) => {
            state.input_cursor = state.input_buffer.len();
        }

        // ── Delete ──
        (KeyModifiers::NONE, KeyCode::Char('x')) => {
            if state.input_cursor < state.input_buffer.len() {
                state.input_buffer.remove(state.input_cursor);
                if state.input_cursor >= state.input_buffer.len() && state.input_cursor > 0 {
                    state.input_cursor -= 1;
                }
                state.dirty = true;
            }
        }

        // ── Word forward/back ──
        (KeyModifiers::NONE, KeyCode::Char('w')) => {
            // Move to next word start
            let text = &state.input_buffer[state.input_cursor..];
            let skip_word = text.chars().take_while(|c| !c.is_whitespace()).count();
            let skip_space = text.chars().skip(skip_word).take_while(|c| c.is_whitespace()).count();
            let advance: usize = text.chars().take(skip_word + skip_space).map(|c| c.len_utf8()).sum();
            state.input_cursor = (state.input_cursor + advance).min(state.input_buffer.len());
        }
        (KeyModifiers::NONE, KeyCode::Char('b')) => {
            // Move to previous word start
            let text = &state.input_buffer[..state.input_cursor];
            let skip_space = text.chars().rev().take_while(|c| c.is_whitespace()).count();
            let skip_word = text.chars().rev().skip(skip_space).take_while(|c| !c.is_whitespace()).count();
            let retreat: usize = text.chars().rev().take(skip_space + skip_word).map(|c| c.len_utf8()).sum();
            state.input_cursor = state.input_cursor.saturating_sub(retreat);
        }

        // ── Visual mode ──
        (KeyModifiers::NONE, KeyCode::Char('v')) => {
            state.vim.enter_visual(state.input_cursor);
            state.dirty = true;
        }

        // ── Ctrl shortcuts pass through to normal handler ──
        // These are handled by the main dispatcher

        _ => {
            // For unhandled keys, mark as dirty (handled) to prevent double-processing
            state.dirty = true;
        }
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
        // Vim is enabled by default, ensure we're in normal mode
        state.vim.enabled = true;
        state.vim.enter_normal();
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
    fn test_i_enters_insert_mode() {
        let mut state = make_test_state();
        assert_eq!(state.vim.mode, super::super::super::widgets::figures::VimMode::Normal);
        handle_vim_normal_key(&mut state, make_key(KeyCode::Char('i')));
        assert_eq!(state.vim.mode, super::super::super::widgets::figures::VimMode::Insert);
    }

    #[test]
    fn test_a_enters_insert_mode_after_cursor() {
        let mut state = make_test_state();
        state.input_buffer = "hello".to_string();
        state.input_cursor = 0;
        handle_vim_normal_key(&mut state, make_key(KeyCode::Char('a')));
        assert_eq!(state.input_cursor, 1);
        assert_eq!(state.vim.mode, super::super::super::widgets::figures::VimMode::Insert);
    }

    #[test]
    fn test_h_navigates_left() {
        let mut state = make_test_state();
        state.input_buffer = "hello".to_string();
        state.input_cursor = 3;
        handle_vim_normal_key(&mut state, make_key(KeyCode::Char('h')));
        assert_eq!(state.input_cursor, 2);
    }

    #[test]
    fn test_l_navigates_right() {
        let mut state = make_test_state();
        state.input_buffer = "hello".to_string();
        state.input_cursor = 2;
        handle_vim_normal_key(&mut state, make_key(KeyCode::Char('l')));
        assert_eq!(state.input_cursor, 3);
    }

    #[test]
    fn test_x_deletes_character() {
        let mut state = make_test_state();
        state.input_buffer = "hello".to_string();
        state.input_cursor = 2;
        handle_vim_normal_key(&mut state, make_key(KeyCode::Char('x')));
        assert_eq!(state.input_buffer, "helo");
        // After deletion at cursor 2, buffer is "helo" (len 4). Vim semantics:
        // cursor only retreats if it would land past end-of-buffer; here 2 < 4
        // so it stays. Matches INVARIANTS.md row 45 ("moves cursor back if at end").
        assert_eq!(state.input_cursor, 2);
    }

    #[test]
    fn test_0_goes_to_start() {
        let mut state = make_test_state();
        state.input_buffer = "hello".to_string();
        state.input_cursor = 3;
        handle_vim_normal_key(&mut state, make_key(KeyCode::Char('0')));
        assert_eq!(state.input_cursor, 0);
    }

    #[test]
    fn test_dollar_goes_to_end() {
        let mut state = make_test_state();
        state.input_buffer = "hello".to_string();
        state.input_cursor = 2;
        // `$` on US keyboards = Shift+4 — KeyEvent carries SHIFT modifier.
        // Handler at line 75 matches `KeyModifiers::SHIFT, KeyCode::Char('$')`.
        let evt = KeyEvent {
            code: KeyCode::Char('$'),
            modifiers: KeyModifiers::SHIFT,
            kind: KeyEventKind::Press,
            state: KeyEventState::NONE,
        };
        handle_vim_normal_key(&mut state, evt);
        assert_eq!(state.input_cursor, 5);
    }
}
