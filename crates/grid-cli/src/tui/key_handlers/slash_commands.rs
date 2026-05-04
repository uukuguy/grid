//! Slash command execution for the TUI.
//!
//! Handles local commands prefixed with `/` that execute within the TUI
//! without sending messages to the agent.

use grid_engine::agent::AgentMessage;
use grid_types::message::ChatMessage;

use super::app_state::{OverlayMode, TuiState};

/// Execute a TUI-local slash command. Returns `true` if handled locally.
pub async fn execute_slash_command(state: &mut TuiState, input: &str) {
    let parts: Vec<&str> = input.trim().splitn(2, ' ').collect();
    let cmd = parts[0];
    let _args = parts.get(1).copied().unwrap_or("");

    match cmd {
        "/help" | "/h" | "/?" => {
            let mut help_text = String::from(concat!(
                "Available commands:\n",
                "  /help       — Show this help\n",
                "  /clear      — Clear conversation history\n",
                "  /exit /quit — Exit the session\n",
                "  /mouse      — Toggle mouse capture (off = select text to copy)\n",
                "  /debug      — Toggle debug panel\n",
                "  /eval       — Toggle eval panel\n",
                "  /sessions   — Toggle session picker\n",
                "  /todo       — Toggle todo/plan panel\n",
                "  /compact    — Compact conversation context\n",
                "  /cost       — Show token usage and costs\n",
                "  /model      — Switch the LLM model\n",
                "  /mode       — Switch between plan/normal mode\n",
                "  /theme      — Change color theme\n",
            ));
            // Append custom commands if any are loaded
            if !state.custom_commands.is_empty() {
                help_text.push_str("\nCustom commands:\n");
                for c in &state.custom_commands {
                    let args_hint = if c.has_arguments { " <args>" } else { "" };
                    help_text.push_str(&format!(
                        "  /{}{} — {}\n",
                        c.name, args_hint, c.description
                    ));
                }
            }
            help_text.push_str(concat!(
                "\nKeyboard shortcuts:\n",
                "  Ctrl+Y      — Copy last response to clipboard\n",
                "  Ctrl+O      — Cycle through tool results (expand/collapse one by one)\n",
                "  Ctrl+Shift+O — Toggle ALL tool results expand/collapse\n",
                "\nText selection:\n",
                "  Most terminals (iTerm2, etc.) support native text selection & copy.\n",
                "  /mouse      — Toggle mouse capture off if native selection doesn't work.\n",
            ));
            state
                .messages
                .push(ChatMessage::assistant(&help_text));
            state.invalidate_cache();
            state.auto_scroll();
        }
        "/clear" => {
            state.messages.clear();
            state.streaming_text.clear();
            state.thinking_text.clear();
            state.per_message_cache.clear();
            state.active_tools.clear();
            state.plan_steps.clear();
            // Reset context and token counters
            state.context_usage_pct = 0.0;
            state.total_input_tokens = 0;
            state.total_output_tokens = 0;
            state.task_input_tokens = 0;
            state.task_output_tokens = 0;
            state.tool_expanded_overrides.clear();
            state.tool_toggle_cursor = 0;
            state.invalidate_cache();
            // Notify backend to clear conversation history
            let _ = state.handle.tx.try_send(AgentMessage::ClearHistory);
        }
        "/exit" | "/quit" | "/q" => {
            state.running = false;
        }
        "/debug" => {
            state.overlay = if state.overlay == OverlayMode::AgentDebug {
                OverlayMode::None
            } else {
                OverlayMode::AgentDebug
            };
        }
        "/eval" => {
            state.overlay = if state.overlay == OverlayMode::Eval {
                OverlayMode::None
            } else {
                OverlayMode::Eval
            };
        }
        "/sessions" => {
            state.overlay = if state.overlay == OverlayMode::SessionPicker {
                OverlayMode::None
            } else {
                OverlayMode::SessionPicker
            };
        }
        "/todo" => {
            // Plan steps are now shown inline in conversation — no separate panel
            let msg = "Plan steps are shown inline in the conversation area.";
            state.messages.push(ChatMessage::assistant(msg));
            state.invalidate_cache();
            state.auto_scroll();
        }
        "/mouse" => {
            state.mouse_captured = !state.mouse_captured;
            if state.mouse_captured {
                let _ = crossterm::execute!(
                    std::io::stdout(),
                    crossterm::event::EnableMouseCapture
                );
                let msg = "Mouse capture ON — scroll with mouse, Shift+drag to select text.";
                state.messages.push(ChatMessage::assistant(msg));
            } else {
                let _ = crossterm::execute!(
                    std::io::stdout(),
                    crossterm::event::DisableMouseCapture
                );
                let msg = "Mouse capture OFF — select text with mouse to copy. Use keyboard (↑↓/PgUp/PgDn) to scroll. /mouse to re-enable.";
                state.messages.push(ChatMessage::assistant(msg));
            }
            state.invalidate_cache();
            state.auto_scroll();
        }
        "/compact" => {
            let msg = "Compacting conversation context...";
            state.messages.push(ChatMessage::assistant(msg));
            state.invalidate_cache();
            state.auto_scroll();
            let _ = state.handle.tx.try_send(AgentMessage::CompactHistory);
        }
        _ => {
            // Check custom commands from ~/.grid/commands/
            let cmd_name = cmd.strip_prefix('/').unwrap_or(cmd);
            if let Some(custom) = state
                .custom_commands
                .iter()
                .find(|c| c.name == cmd_name)
                .cloned()
            {
                // Expand template with arguments
                let expanded = custom.expand(_args);

                // Show a concise command summary (not the full expanded prompt)
                let display = if _args.is_empty() {
                    format!("/{}", custom.name)
                } else {
                    format!("/{} {}", custom.name, _args)
                };
                state.messages.push(ChatMessage::user(&display));
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
                        content: expanded,
                        channel_id: "tui".into(),
                    })
                    .await;
                state.is_streaming = true;
                state.cancelled = false;
                state.interrupt_manager.reset();
            } else {
                // Unknown slash command — show error message locally
                let msg =
                    format!("Unknown command: {}. Type /help for available commands.", cmd);
                state.messages.push(ChatMessage::assistant(&msg));
                state.invalidate_cache();
                state.auto_scroll();
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tui::app_state::TuiState;
    use grid_types::message::ContentBlock;
    use tokio::sync::{broadcast, mpsc};

    fn create_test_state() -> TuiState {
        let (tx, _rx) = mpsc::channel(16);
        let (broadcast_tx, _) = broadcast::channel(16);
        let handle = grid_engine::agent::AgentExecutorHandle {
            tx,
            broadcast_tx,
            session_id: grid_types::SessionId::from_string("test"),
        };
        TuiState::new_for_test(grid_types::SessionId::from_string("test"), handle, "test-model".to_string())
    }

    #[tokio::test]
    async fn test_slash_command_help() {
        let mut state = create_test_state();
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
        let mut state = create_test_state();
        state.messages.push(ChatMessage::user("hello"));
        state.messages.push(ChatMessage::assistant("hi"));
        execute_slash_command(&mut state, "/clear").await;
        assert!(state.messages.is_empty());
    }

    #[tokio::test]
    async fn test_slash_command_exit() {
        let mut state = create_test_state();
        assert!(state.running);
        execute_slash_command(&mut state, "/exit").await;
        assert!(!state.running);
    }

    #[tokio::test]
    async fn test_slash_command_quit() {
        let mut state = create_test_state();
        execute_slash_command(&mut state, "/quit").await;
        assert!(!state.running);
    }

    #[tokio::test]
    async fn test_slash_command_debug_toggle() {
        let mut state = create_test_state();
        assert_eq!(state.overlay, OverlayMode::None);
        execute_slash_command(&mut state, "/debug").await;
        assert_eq!(state.overlay, OverlayMode::AgentDebug);
        execute_slash_command(&mut state, "/debug").await;
        assert_eq!(state.overlay, OverlayMode::None);
    }

    #[tokio::test]
    async fn test_slash_command_eval_toggle() {
        let mut state = create_test_state();
        execute_slash_command(&mut state, "/eval").await;
        assert_eq!(state.overlay, OverlayMode::Eval);
        execute_slash_command(&mut state, "/eval").await;
        assert_eq!(state.overlay, OverlayMode::None);
    }

    #[tokio::test]
    async fn test_slash_command_sessions_toggle() {
        let mut state = create_test_state();
        execute_slash_command(&mut state, "/sessions").await;
        assert_eq!(state.overlay, OverlayMode::SessionPicker);
    }

    #[tokio::test]
    async fn test_slash_command_todo_shows_message() {
        let mut state = create_test_state();
        execute_slash_command(&mut state, "/todo").await;
        // /todo now shows an informational message instead of toggling a panel
        assert_eq!(state.messages.len(), 1);
    }

    #[tokio::test]
    async fn test_slash_command_unknown() {
        let mut state = create_test_state();
        execute_slash_command(&mut state, "/foobar").await;
        assert_eq!(state.messages.len(), 1);
        let text = match &state.messages[0].content[0] {
            ContentBlock::Text { text } => text.clone(),
            _ => String::new(),
        };
        assert!(text.contains("Unknown command"));
    }
}
