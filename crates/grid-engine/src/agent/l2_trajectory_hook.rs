//! L2 Trajectory Stop hook — fires at session termination and writes
//! a session_trajectory anchor + file to the L2 Memory Engine.
//!
//! Per Phase 5.4 D-09: Stop hook that writes session trajectory to L2 memory engine.
//! Fire-and-forget: errors are logged at warn level; agent termination is never blocked.
//!
//! See ADR-V2-006 §2 (hook envelope) + ADR-V2-015 (L2 hybrid retrieval).
//! See PATTERNS.md §B9 / LC-5 (warn-on-error convention).

use anyhow::Result;
use async_trait::async_trait;
use tracing::warn;

use crate::agent::stop_hooks::{StopHook, StopHookDecision};
use crate::hooks::HookContext;
use crate::l2::{L2MemoryClient, WriteAnchorRequest, WriteFileRequest};

/// L2 trajectory hook — observability-only Stop hook that writes
/// a session trajectory record to L2. Never injects (always returns Noop).
pub struct L2TrajectoryStopHook {
    client: L2MemoryClient,
    session_id: String,
}

impl L2TrajectoryStopHook {
    pub fn new(client: L2MemoryClient, session_id: String) -> Self {
        Self { client, session_id }
    }
}

#[async_trait]
impl StopHook for L2TrajectoryStopHook {
    fn name(&self) -> &str {
        "l2-trajectory"
    }

    async fn execute(&self, ctx: &HookContext) -> Result<StopHookDecision> {
        let anchor_req = WriteAnchorRequest {
            event_id: format!(
                "stop-{}-{}",
                self.session_id,
                chrono::Utc::now().timestamp_millis()
            ),
            session_id: self.session_id.clone(),
            anchor_type: "session_trajectory".into(),
            data_ref: ctx.tool_result.as_ref().map(|v| v.to_string()),
            snapshot_hash: None,
            source_system: Some("grid-server".into()),
        };
        if let Err(e) = self.client.write_anchor(&anchor_req).await {
            warn!(error = %e, "L2 trajectory anchor write failed (non-fatal)");
        }
        let file_req = WriteFileRequest {
            memory_id: None,
            scope: format!("session:{}", self.session_id),
            category: "session_trajectory".into(),
            content: format!("Session {} terminated at stop hook", self.session_id),
            evidence_refs: None,
            status: Some("agent_suggested".into()),
        };
        if let Err(e) = self.client.write_file(&file_req).await {
            warn!(error = %e, "L2 trajectory file write failed (non-fatal)");
        }
        // Per LC-5: pure observability hook never injects.
        Ok(StopHookDecision::Noop)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn name_is_l2_trajectory() {
        let client = L2MemoryClient::new("http://127.0.0.1:9999");
        let hook = L2TrajectoryStopHook::new(client, "test-sess".into());
        assert_eq!(hook.name(), "l2-trajectory");
    }

    #[tokio::test]
    async fn execute_on_l2_down_returns_noop_not_err() {
        // Bind a port that nothing listens on (a closed socket). Hook MUST log
        // warn! and still return Ok(Noop) — never propagate error.
        let client = L2MemoryClient::new("http://127.0.0.1:1");
        let hook = L2TrajectoryStopHook::new(client, "down-sess".into());
        let ctx = HookContext::new().with_session("down-sess");
        let result = hook.execute(&ctx).await;
        assert!(result.is_ok(), "Stop hook must NOT propagate L2 errors");
        match result.unwrap() {
            StopHookDecision::Noop => {}
            other => panic!("Expected Noop, got {:?}", other),
        }
    }
}
