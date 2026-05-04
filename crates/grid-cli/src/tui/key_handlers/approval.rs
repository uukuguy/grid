//! Approval dialog key handling.
//!
//! Handles keyboard input when the approval dialog is showing.
//! Users can approve or deny tool executions.

use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};

use super::app_state::TuiState;

/// Handle keys when the approval dialog is showing.
///
/// In approval mode:
/// - y/Y: approve the tool execution
/// - a/A: always approve (for this and future similar operations)
/// - n/N or Escape: deny the tool execution
/// - Ctrl+C: handle cancellation
pub async fn handle_approval_key(state: &mut TuiState, key: KeyEvent) {
    match (key.modifiers, key.code) {
        (KeyModifiers::NONE, KeyCode::Char('y') | KeyCode::Char('Y')) => {
            // Approve
            if let Some(ref approval) = state.pending_approval {
                if let Some(ref gate) = state.approval_gate {
                    gate.respond(&approval.tool_id, true).await;
                }
            }
            state.pending_approval = None;
        }
        (KeyModifiers::NONE, KeyCode::Char('a') | KeyCode::Char('A')) => {
            // Always approve (respond true; future: persist preference)
            if let Some(ref approval) = state.pending_approval {
                if let Some(ref gate) = state.approval_gate {
                    gate.respond(&approval.tool_id, true).await;
                }
            }
            state.pending_approval = None;
        }
        (KeyModifiers::NONE, KeyCode::Char('n') | KeyCode::Char('N'))
        | (KeyModifiers::NONE, KeyCode::Esc) => {
            // Deny
            if let Some(ref approval) = state.pending_approval {
                if let Some(ref gate) = state.approval_gate {
                    gate.respond(&approval.tool_id, false).await;
                }
            }
            state.pending_approval = None;
        }
        (KeyModifiers::CONTROL, KeyCode::Char('c')) => {
            if state.interrupt_manager.handle_ctrl_c().await {
                state.running = false;
            }
        }
        _ => {}
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tui::app_state::{PendingApproval, TuiState};
    use crossterm::event::{KeyCode, KeyEvent, KeyEventKind, KeyEventState, KeyModifiers};
    use grid_engine::tools::approval::ApprovalGate;
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

    #[tokio::test]
    async fn test_approval_y_with_gate_clears_pending() {
        let mut state = make_test_state();
        let gate = ApprovalGate::new();
        state.approval_gate = Some(gate.clone());
        // Register a pending approval in the gate and get the receiver
        let rx = gate.register("t1").await;
        state.pending_approval = Some(PendingApproval {
            tool_id: "t1".into(),
            tool_name: "bash".into(),
            risk_level: RiskLevel::HighRisk,
            args_preview: None,
        });
        handle_approval_key(&mut state, make_key(KeyCode::Char('y'))).await;
        assert!(state.pending_approval.is_none());
        // The receiver should get `true` (approved)
        assert_eq!(rx.await.unwrap(), true);
    }

    #[tokio::test]
    async fn test_approval_n_with_gate_denies() {
        let mut state = make_test_state();
        let gate = ApprovalGate::new();
        state.approval_gate = Some(gate.clone());
        let rx = gate.register("t2").await;
        state.pending_approval = Some(PendingApproval {
            tool_id: "t2".into(),
            tool_name: "bash".into(),
            risk_level: RiskLevel::HighRisk,
            args_preview: None,
        });
        handle_approval_key(&mut state, make_key(KeyCode::Char('n'))).await;
        assert!(state.pending_approval.is_none());
        assert_eq!(rx.await.unwrap(), false);
    }

    #[tokio::test]
    async fn test_approval_a_with_gate_approves() {
        let mut state = make_test_state();
        let gate = ApprovalGate::new();
        state.approval_gate = Some(gate.clone());
        let rx = gate.register("t3").await;
        state.pending_approval = Some(PendingApproval {
            tool_id: "t3".into(),
            tool_name: "bash".into(),
            risk_level: RiskLevel::HighRisk,
            args_preview: None,
        });
        handle_approval_key(&mut state, make_key(KeyCode::Char('a'))).await;
        assert!(state.pending_approval.is_none());
        assert_eq!(rx.await.unwrap(), true);
    }

    #[tokio::test]
    async fn test_approval_without_gate_still_clears() {
        let mut state = make_test_state();
        // No gate set — approval_gate is None
        state.pending_approval = Some(PendingApproval {
            tool_id: "t1".into(),
            tool_name: "bash".into(),
            risk_level: RiskLevel::HighRisk,
            args_preview: None,
        });
        handle_approval_key(&mut state, make_key(KeyCode::Char('y'))).await;
        assert!(state.pending_approval.is_none());
    }

    #[tokio::test]
    async fn test_approval_escape_denies() {
        let mut state = make_test_state();
        let gate = ApprovalGate::new();
        state.approval_gate = Some(gate.clone());
        let rx = gate.register("t4").await;
        state.pending_approval = Some(PendingApproval {
            tool_id: "t4".into(),
            tool_name: "bash".into(),
            risk_level: RiskLevel::HighRisk,
            args_preview: None,
        });
        handle_approval_key(&mut state, make_key(KeyCode::Esc)).await;
        assert!(state.pending_approval.is_none());
        assert_eq!(rx.await.unwrap(), false);
    }
}
