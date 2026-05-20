use std::path::PathBuf;
use std::sync::Arc;

use grid_engine::{
    auth::AuthConfig, mcp::McpStorage, metrics::MetricsRegistry, scheduler::Scheduler,
    tools::approval::ApprovalGate, tools::interaction::InteractionGate,
    AgentExecutorHandle, AgentRuntime,
};
use grid_types::SessionId;
use tokio::sync::RwLock;

use crate::config::Config;

/// Runtime-updatable configuration overrides (AO-T8 + Phase 5.4 SERVER-05).
/// Fields set to `Some(...)` override the corresponding value in `Config`.
///
/// Phase 5.4 Task 5.4-02-06 added `hooks_file` and `policies_file` —
/// reloadable via `POST /api/v1/admin/reload` (T-06 mitigation).
#[derive(Debug, Clone, Default, serde::Serialize, serde::Deserialize)]
pub struct RuntimeConfigOverrides {
    pub logging_format: Option<String>,
    pub cors_strict: Option<bool>,
    pub cors_origins: Option<Vec<String>>,
    pub provider_name: Option<String>,
    pub provider_model: Option<String>,
    pub autonomy_level: Option<String>,
    pub require_approval_for_medium_risk: Option<bool>,
    pub block_high_risk_commands: Option<bool>,
    /// Phase 5.4 SERVER-05: hooks definition file path; reloadable.
    pub hooks_file: Option<String>,
    /// Phase 5.4 SERVER-05: policy DSL file path; reloadable.
    pub policies_file: Option<String>,
    /// Phase 5.4 SERVER-05: tracing log filter (e.g. "grid_server=debug").
    /// Reloadable when `log_reload_handle` is wired (W0-03 spike: viable).
    pub log_level: Option<String>,
}

pub struct AppState {
    pub db_path: PathBuf,
    /// Scheduler for periodic tasks (optional)
    pub scheduler: Option<Arc<Scheduler>>,
    /// Server configuration for frontend
    pub config: Config,
    /// Runtime-updatable overrides (AO-T8)
    pub runtime_overrides: RwLock<RuntimeConfigOverrides>,
    /// Auth configuration for request authentication
    pub auth_config: AuthConfig,
    /// Metrics registry for collecting application metrics
    pub metrics_registry: Arc<RwLock<MetricsRegistry>>,
    /// Runtime supervisor: owns all agent dependencies and manages AgentExecutor lifecycle
    pub agent_supervisor: Arc<AgentRuntime>,
    /// 主 AgentExecutor 的通信句柄（channels 唯一的 Agent 接入点）
    pub agent_handle: AgentExecutorHandle,
    /// Optional L2 memory engine base URL override (Phase 5.4 D-07/D-08).
    /// `None` → `L2MemoryClient::from_env()`; `Some(url)` → `L2MemoryClient::new(url)`.
    pub l2_client_base_url: Option<String>,
    /// Server start time for uptime calculation
    pub start_time: std::time::Instant,
    /// Shared approval gate for pending human approval requests (T3).
    pub approval_gate: Option<ApprovalGate>,
    /// Shared interaction gate for agent-to-user communication (Phase AS).
    pub interaction_gate: Arc<InteractionGate>,
}

impl AppState {
    pub fn new(
        db_path: PathBuf,
        scheduler: Option<Arc<Scheduler>>,
        config: Config,
        agent_supervisor: Arc<AgentRuntime>,
        agent_handle: AgentExecutorHandle,
    ) -> Self {
        // Convert YAML config to runtime AuthConfig
        let auth_config = config.auth.to_auth_config();

        // Initialize metrics registry
        let metrics_registry = Arc::new(RwLock::new(MetricsRegistry::new()));

        // Create shared ApprovalGate — same instance shared between WS handler and AgentRuntime
        let approval_gate = agent_supervisor.approval_gate().cloned();

        // Shared InteractionGate for agent-to-user communication (Phase AS)
        let interaction_gate = agent_supervisor.interaction_gate().clone();

        Self {
            db_path,
            scheduler,
            config,
            runtime_overrides: RwLock::new(RuntimeConfigOverrides::default()),
            auth_config,
            metrics_registry,
            agent_supervisor,
            agent_handle,
            l2_client_base_url: None,
            start_time: std::time::Instant::now(),
            approval_gate,
            interaction_gate,
        }
    }

    /// Get MCP storage on-demand (creates new connection each time)
    pub fn mcp_storage(&self) -> Option<grid_engine::mcp::storage::McpStorage> {
        McpStorage::new(&self.db_path).ok()
    }

    /// Get audit storage on-demand (creates new connection each time)
    pub fn audit_storage(&self) -> Option<grid_engine::audit::AuditStorage> {
        grid_engine::audit::AuditStorage::new(&self.db_path).ok()
    }

    /// Get metering storage on-demand (creates new async DB connection each time)
    pub async fn metering_storage(&self) -> Option<grid_engine::metering::storage::MeteringStorage> {
        let db = grid_engine::Database::open(self.db_path.to_str()?).await.ok()?;
        Some(grid_engine::metering::storage::MeteringStorage::new(db))
    }

    /// Get L2 memory engine client on-demand (Phase 5.4 D-08).
    ///
    /// Mirrors `mcp_storage` / `audit_storage` on-demand pattern: every call
    /// constructs a new `L2MemoryClient` (reqwest has its own connection pool,
    /// no need to long-hold). If `l2_client_base_url` is set on `AppState`
    /// (typically by tests), uses it; otherwise falls back to
    /// `L2MemoryClient::from_env()` which reads `EAASP_L2_HOST` / `EAASP_L2_PORT`.
    pub fn l2_storage(&self) -> grid_engine::l2::L2MemoryClient {
        match &self.l2_client_base_url {
            Some(url) => grid_engine::l2::L2MemoryClient::new(url),
            None => grid_engine::l2::L2MemoryClient::from_env(),
        }
    }

    /// Test backdoor — inject `AgentEvent`s directly into the primary
    /// session's broadcast channel. Used by WS load / ordering / reconnect
    /// tests (Tasks 5.4-01-05, 5.4-01-06, 5.4-01-07) to avoid spinning a real
    /// LLM. **NOT** exposed in production builds.
    ///
    /// Per W3 (plan-checker 2026-05-21): cfg-gated; `pub(crate)` visibility
    /// keeps it out of the binary surface entirely.
    #[cfg(any(test, feature = "testing"))]
    pub async fn test_inject_events(
        &self,
        session_id: &SessionId,
        events: Vec<grid_engine::AgentEvent>,
    ) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        // Resolve the handle (or fall back to primary if no match).
        let handle = match self.agent_supervisor.get_session_handle(session_id) {
            Some(h) => h,
            None => self.agent_handle.clone(),
        };
        for ev in events {
            // Pace via yield_now so the broadcast channel drains between
            // sends — backpressure test (5.4-01-05) relies on this to keep
            // the default-capacity broadcast channel from lagging.
            tokio::task::yield_now().await;
            // Ignore "no receivers" errors — tests may inject before a WS
            // subscriber is connected, in which case the value is simply
            // discarded. Realistic tests subscribe first.
            let _ = handle.broadcast_tx.send(ev);
        }
        Ok(())
    }

    /// Resolve a session handle: if session_id is given, look up in agent_supervisor;
    /// otherwise return the primary agent_handle.
    #[allow(dead_code)]
    pub fn resolve_session_handle(&self, session_id: Option<&str>) -> Option<AgentExecutorHandle> {
        match session_id {
            Some(id) => {
                let sid = SessionId::from_string(id);
                self.agent_supervisor.get_session_handle(&sid)
            }
            None => Some(self.agent_handle.clone()),
        }
    }
}
