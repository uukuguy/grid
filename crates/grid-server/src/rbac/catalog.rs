//! Canonical authorization metadata for every `grid-server` HTTP route.
//!
//! The catalog is deliberately plain typed data. Router assembly remains in
//! `api` and `router`; the authorization auditor compares that surface with
//! this source of truth and rejects drift.

use grid_engine::auth::roles::Action;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RouteKind {
    Public,
    Requires(Action),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RouteCatalogEntry {
    pub method: &'static str,
    pub path: &'static str,
    pub route_kind: RouteKind,
}

impl RouteCatalogEntry {
    const fn public(method: &'static str, path: &'static str) -> Self {
        Self {
            method,
            path,
            route_kind: RouteKind::Public,
        }
    }

    const fn requires(method: &'static str, path: &'static str, action: Action) -> Self {
        Self {
            method,
            path,
            route_kind: RouteKind::Requires(action),
        }
    }
}

pub const PUBLIC_ROUTE_ALLOWLIST: [(&str, &str); 3] = [
    ("GET", "/api/health"),
    ("GET", "/api/health/live"),
    ("POST", "/api/v1/auth/login"),
];

macro_rules! route {
    (public, $method:literal, $path:literal) => {
        RouteCatalogEntry::public($method, $path)
    };
    ($action:ident, $method:literal, $path:literal) => {
        RouteCatalogEntry::requires($method, $path, Action::$action)
    };
}

pub static ROUTE_CATALOG: &[RouteCatalogEntry] = &[
    route!(public, "GET", "/api/health"),
    route!(public, "GET", "/api/health/live"),
    route!(Read, "GET", "/v1/sessions/{id}/stream"),
    route!(public, "POST", "/api/v1/auth/login"),
    route!(Read, "POST", "/api/v1/auth/refresh"),
    route!(Read, "POST", "/api/v1/auth/logout"),
    route!(CreateSession, "POST", "/api/v1/sessions/start"),
    route!(Read, "GET", "/api/v1/sessions/active"),
    route!(Read, "GET", "/api/v1/sessions/metrics"),
    route!(RunAgent, "DELETE", "/api/v1/sessions/{id}/stop"),
    route!(Read, "GET", "/api/v1/sessions/{id}/status"),
    route!(Read, "GET", "/api/v1/sessions/{id}/executions"),
    route!(Read, "GET", "/api/v1/sessions/{id}"),
    route!(CreateSession, "POST", "/api/v1/sessions/{id}/rewind"),
    route!(CreateSession, "POST", "/api/v1/sessions/{id}/fork"),
    route!(RunAgent, "POST", "/api/v1/sessions/{id}/pause"),
    route!(RunAgent, "POST", "/api/v1/sessions/{id}/resume"),
    route!(Read, "GET", "/api/v1/sessions"),
    route!(Read, "GET", "/api/v1/executions"),
    route!(Read, "GET", "/api/v1/executions/{id}"),
    route!(Read, "GET", "/api/v1/tools"),
    route!(Read, "GET", "/api/v1/config"),
    route!(ManageConfig, "PUT", "/api/v1/config"),
    route!(Read, "GET", "/api/v1/memories"),
    route!(RunAgent, "POST", "/api/v1/memories"),
    route!(RunAgent, "DELETE", "/api/v1/memories"),
    route!(Read, "GET", "/api/v1/memories/working"),
    route!(Read, "GET", "/api/v1/memories/{id}"),
    route!(RunAgent, "DELETE", "/api/v1/memories/{id}"),
    route!(Read, "GET", "/api/v1/budget"),
    route!(Read, "GET", "/api/v1/metrics"),
    route!(Read, "GET", "/api/v1/metrics/prometheus"),
    route!(Read, "GET", "/api/v1/metering/snapshot"),
    route!(Read, "GET", "/api/v1/metering/summary"),
    route!(Read, "GET", "/api/v1/metering/by-session"),
    route!(ManageConfig, "POST", "/api/v1/metering/reset"),
    route!(Read, "GET", "/api/v1/audit"),
    route!(ManageConfig, "DELETE", "/api/v1/audit"),
    route!(Read, "GET", "/api/v1/audit/export"),
    route!(Read, "GET", "/api/v1/audit/stats"),
    route!(Read, "GET", "/api/v1/events"),
    route!(Read, "GET", "/api/v1/events/stream"),
    route!(Read, "GET", "/api/v1/events/session/{session_id}"),
    route!(Read, "GET", "/api/v1/events/stats"),
    route!(Read, "GET", "/api/v1/mcp/servers"),
    route!(ManageMcp, "POST", "/api/v1/mcp/servers"),
    route!(Read, "GET", "/api/v1/mcp/servers/{id}"),
    route!(ManageMcp, "PUT", "/api/v1/mcp/servers/{id}"),
    route!(ManageMcp, "DELETE", "/api/v1/mcp/servers/{id}"),
    route!(ManageMcp, "POST", "/api/v1/mcp/servers/{id}/start"),
    route!(ManageMcp, "POST", "/api/v1/mcp/servers/{id}/stop"),
    route!(Read, "GET", "/api/v1/mcp/servers/{id}/status"),
    route!(Read, "GET", "/api/v1/mcp/servers/{server_id}/tools"),
    route!(RunAgent, "POST", "/api/v1/mcp/servers/{server_id}/call"),
    route!(Read, "GET", "/api/v1/mcp/servers/{server_id}/executions"),
    route!(Read, "GET", "/api/v1/mcp/servers/{server_id}/logs"),
    route!(ManageMcp, "DELETE", "/api/v1/mcp/servers/{server_id}/logs"),
    route!(Read, "GET", "/api/v1/mcp/servers/{server_id}/logs/export"),
    route!(Read, "GET", "/api/v1/scheduler/tasks"),
    route!(RunAgent, "POST", "/api/v1/scheduler/tasks"),
    route!(Read, "GET", "/api/v1/scheduler/tasks/{id}"),
    route!(RunAgent, "PUT", "/api/v1/scheduler/tasks/{id}"),
    route!(RunAgent, "DELETE", "/api/v1/scheduler/tasks/{id}"),
    route!(RunAgent, "POST", "/api/v1/scheduler/tasks/{id}/run"),
    route!(Read, "GET", "/api/v1/scheduler/tasks/{id}/executions"),
    route!(RunAgent, "POST", "/api/v1/tasks"),
    route!(Read, "GET", "/api/v1/tasks"),
    route!(Read, "GET", "/api/v1/tasks/{id}"),
    route!(RunAgent, "DELETE", "/api/v1/tasks/{id}"),
    route!(Read, "GET", "/api/v1/providers"),
    route!(ManageConfig, "POST", "/api/v1/providers"),
    route!(Read, "GET", "/api/v1/providers/status"),
    route!(ManageConfig, "DELETE", "/api/v1/providers/{id}"),
    route!(ManageConfig, "POST", "/api/v1/providers/{id}/select"),
    route!(ManageConfig, "POST", "/api/v1/providers/{id}/reset"),
    route!(ManageConfig, "DELETE", "/api/v1/providers/selection"),
    route!(Read, "GET", "/api/v1/agents"),
    route!(RunAgent, "POST", "/api/v1/agents"),
    route!(Read, "GET", "/api/v1/agents/{id}"),
    route!(RunAgent, "DELETE", "/api/v1/agents/{id}"),
    route!(RunAgent, "POST", "/api/v1/agents/{id}/start"),
    route!(RunAgent, "POST", "/api/v1/agents/{id}/stop"),
    route!(RunAgent, "POST", "/api/v1/agents/{id}/pause"),
    route!(RunAgent, "POST", "/api/v1/agents/{id}/resume"),
    route!(Read, "GET", "/api/v1/skills"),
    route!(Read, "GET", "/api/v1/skills/{name}"),
    route!(ManageSkills, "DELETE", "/api/v1/skills/{name}"),
    route!(RunAgent, "POST", "/api/v1/skills/{name}/execute"),
    route!(Read, "GET", "/api/v1/collaboration/status"),
    route!(Read, "GET", "/api/v1/collaboration/agents"),
    route!(Read, "GET", "/api/v1/collaboration/events"),
    route!(Read, "GET", "/api/v1/collaboration/proposals"),
    route!(RunAgent, "POST", "/api/v1/collaboration/proposals"),
    route!(
        RunAgent,
        "POST",
        "/api/v1/collaboration/proposals/{id}/vote"
    ),
    route!(Read, "GET", "/api/v1/collaboration/shared-state"),
    route!(Read, "GET", "/api/v1/sync/status"),
    route!(RunAgent, "POST", "/api/v1/sync/pull"),
    route!(RunAgent, "POST", "/api/v1/sync/push"),
    route!(RunAgent, "POST", "/api/v1/eval/sessions"),
    route!(RunAgent, "POST", "/api/v1/eval/sessions/{id}/messages"),
    route!(RunAgent, "DELETE", "/api/v1/eval/sessions/{id}"),
    route!(Read, "GET", "/api/v1/knowledge-graph/entities"),
    route!(RunAgent, "POST", "/api/v1/knowledge-graph/entities"),
    route!(Read, "GET", "/api/v1/knowledge-graph/entities/{id}"),
    route!(RunAgent, "DELETE", "/api/v1/knowledge-graph/entities/{id}"),
    route!(
        Read,
        "GET",
        "/api/v1/knowledge-graph/entities/{id}/relations"
    ),
    route!(RunAgent, "POST", "/api/v1/knowledge-graph/relations"),
    route!(Read, "GET", "/api/v1/knowledge-graph/stats"),
    route!(Read, "GET", "/api/v1/knowledge-graph/traverse"),
    route!(Read, "GET", "/api/v1/knowledge-graph/path"),
    route!(Read, "GET", "/api/v1/hooks"),
    route!(Read, "GET", "/api/v1/hooks/points"),
    route!(ManageConfig, "POST", "/api/v1/hooks/reload"),
    route!(Read, "GET", "/api/v1/hooks/wasm"),
    route!(ManageConfig, "POST", "/api/v1/hooks/wasm/{name}/reload"),
    route!(ManageConfig, "POST", "/api/v1/secrets/verify"),
    route!(Read, "GET", "/api/v1/secrets"),
    route!(ManageConfig, "POST", "/api/v1/secrets"),
    route!(ManageConfig, "DELETE", "/api/v1/secrets/{name}"),
    route!(Read, "GET", "/api/v1/sandbox/status"),
    route!(Read, "GET", "/api/v1/sandbox/sessions"),
    route!(ManageConfig, "POST", "/api/v1/sandbox/cleanup"),
    route!(ManageConfig, "POST", "/api/v1/sandbox/{session_id}/release"),
    route!(Read, "GET", "/api/v1/security/policy"),
    route!(ManageConfig, "PUT", "/api/v1/security/policy"),
    route!(Read, "GET", "/api/v1/security/tracker"),
    route!(RunAgent, "POST", "/api/v1/security/check-command"),
    route!(RunAgent, "POST", "/api/v1/security/scan"),
    route!(RunAgent, "POST", "/api/v1/security/pii/redact"),
    route!(Read, "GET", "/api/v1/security/defence/status"),
    route!(Read, "GET", "/api/v1/context/snapshot"),
    route!(Read, "GET", "/api/v1/context/zones"),
    route!(RunAgent, "POST", "/api/v1/autonomous/trigger"),
    route!(ManageConfig, "POST", "/api/v1/admin/reload"),
];

pub fn route_catalog() -> &'static [RouteCatalogEntry] {
    ROUTE_CATALOG
}

pub fn build_catalog() -> Vec<RouteCatalogEntry> {
    ROUTE_CATALOG.to_vec()
}
