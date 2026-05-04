//! Vim insert mode key handling.
//!
//! In Vim insert mode, keys are inserted into the input buffer.
//! Escape enters normal mode.

use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};

use super::app_state::TuiState;

/// Handle keys in Vim insert mode.
///
/// In insert mode, text is inserted at the cursor position.
/// Escape transitions to normal mode.
pub fn handle_vim_insert_key(state: &mut TuiState, key: KeyEvent) {
    match (key.modifiers, key.code) {
        // Escape → enter normal mode
        (KeyModifiers::NONE, KeyCode::Esc) => {
            state.vim.enter_normal();
            state.dirty = true;
        }
        // Backspace
        (KeyModifiers::NONE, KeyCode::Backspace) => {
            if state.input_cursor > 0 {
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
        // Left arrow
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
        // Right arrow
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
        // Up/Down arrows for multiline navigation
        (KeyModifiers::NONE, KeyCode::Up) => {
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
        }
        (KeyModifiers::NONE, KeyCode::Down) => {
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
        // Home/End
        (KeyModifiers::NONE, KeyCode::Home) => {
            state.input_cursor = 0;
        }
        (KeyModifiers::NONE, KeyCode::End) => {
            state.input_cursor = state.input_buffer.len();
        }
        // Delete
        (KeyModifiers::NONE, KeyCode::Delete) => {
            if state.input_cursor < state.input_buffer.len() {
                state.input_buffer.remove(state.input_cursor);
                state.dirty = true;
                let text_before = state.input_buffer[..state.input_cursor].to_string();
                state.autocomplete.update(&text_before);
            }
        }
        // Tab
        (KeyModifiers::NONE, KeyCode::Tab) => {
            if state.autocomplete.is_visible() {
                if let Some((insert, delete_count)) = state.autocomplete.accept() {
                    let start = state.input_cursor.saturating_sub(delete_count);
                    state.input_buffer.replace_range(start..state.input_cursor, &insert);
                    state.input_cursor = start + insert.len();
                    state.dirty = true;
                }
            }
        }
        // Text input
        (KeyModifiers::NONE, KeyCode::Char(c)) | (KeyModifiers::SHIFT, KeyCode::Char(c)) => {
            state.input_buffer.insert(state.input_cursor, c);
            state.input_cursor += c.len_utf8();
            state.dirty = true;
            let text_before = state.input_buffer[..state.input_cursor].to_string();
            state.autocomplete.update(&text_before);
        }
        // Ctrl shortcuts that work in insert mode
        (KeyModifiers::CONTROL, KeyCode::Char('c')) => {
            // Pass through to normal handler via special handling
            state.vim.ctrl_c_pending = true;
        }
        (KeyModifiers::CONTROL, KeyCode::Char('a')) => {
            state.input_cursor = 0;
        }
        (KeyModifiers::CONTROL, KeyCode::Char('e')) => {
            state.input_cursor = state.input_buffer.len();
        }
        (KeyModifiers::CONTROL, KeyCode::Char('u')) => {
            state.input_buffer = state.input_buffer[state.input_cursor..].to_string();
            state.input_cursor = 0;
            state.dirty = true;
        }
        (KeyModifiers::CONTROL, KeyCode::Char('w')) => {
            // Delete word before cursor
            let mut start = state.input_cursor;
            while start > 0 && state.input_buffer[..start].ends_with(' ') {
                start -= 1;
            }
            while start > 0 && !state.input_buffer[..start].ends_with(' ') {
                start -= 1;
            }
            state.input_buffer.drain(start..state.input_cursor);
            state.input_cursor = start;
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
        // Enter insert mode
        state.vim.enter_insert();
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
    fn test_char_input() {
        let mut state = make_test_state();
        handle_vim_insert_key(&mut state, make_key(KeyCode::Char('h')));
        handle_vim_insert_key(&mut state, make_key(KeyCode::Char('i')));
        assert_eq!(state.input_buffer, "hi");
        assert_eq!(state.input_cursor, 2);
    }

    #[test]
    fn test_backspace() {
        let mut state = make_test_state();
        handle_vim_insert_key(&mut state, make_key(KeyCode::Char('a')));
        handle_vim_insert_key(&mut state, make_key(KeyCode::Char('b')));
        handle_vim_insert_key(&mut state, make_key(KeyCode::Backspace));
        assert_eq!(state.input_buffer, "a");
        assert_eq!(state.input_cursor, 1);
    }

    #[test]
    fn test_escape_enters_normal_mode() {
        let mut state = make_test_state();
        assert_eq!(state.vim.mode, super::super::widgets::figures::VimMode::Insert);
        handle_vim_insert_key(&mut state, make_key(KeyCode::Esc));
        assert_eq!(state.vim.mode, super::super::widgets::figures::VimMode::Normal);
    }

    #[test]
    fn test_ctrl_a_goes_to_start() {
        let mut state = make_test_state();
        handle_vim_insert_key(&mut state, make_key(KeyCode::Char('a')));
        handle_vim_insert_key(&mut state, make_key(KeyCode::Char('b')));
        assert_eq!(state.input_cursor, 2);
        let ctrl_a = KeyEvent {
            code: KeyCode::Char('a'),
            modifiers: KeyModifiers::CONTROL,
            kind: KeyEventKind::Press,
            state: KeyEventState::NONE,
        };
        handle_vim_insert_key(&mut state, ctrl_a);
        assert_eq!(state.input_cursor, 0);
    }

    #[test]
    fn test_ctrl_e_goes_to_end() {
        let mut state = make_test_state();
        handle_vim_insert_key(&mut state, make_key(KeyCode::Char('a')));
        handle_vim_insert_key(&mut state, make_key(KeyCode::Char('b')));
        assert_eq!(state.input_cursor, 2);
        let ctrl_e = KeyEvent {
            code: KeyCode::Char('e'),
            modifiers: KeyModifiers::CONTROL,
            kind: KeyEventKind::Press,
            state: KeyEventState::NONE,
        };
        handle_vim_insert_key(&mut state, ctrl_e);
        assert_eq!(state.input_cursor, 2);
    }
}
