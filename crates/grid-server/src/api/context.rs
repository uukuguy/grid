use std::sync::Arc;

use axum::{extract::{Query, State}, routing::get, Json, Router};
use grid_types::SessionId;
use serde::{Deserialize, Serialize};

use crate::state::AppState;

#[derive(Deserialize, Default)]
pub struct ContextQuery {
    pub session_id: Option<String>,
}

/// Context budget snapshot response (AO-T10).
#[derive(Serialize)]
pub struct ContextSnapshotResponse {
    pub total_budget: usize,
    pub system_tokens: usize,
    pub message_tokens: usize,
    pub tool_tokens: usize,
    pub remaining: usize,
    pub usage_pct: f32,
    pub needs_pruning: bool,
    pub degradation_level: String,
}

/// Zone information in context breakdown.
#[derive(Serialize)]
pub struct ZoneInfo {
    pub name: String,
    pub tokens: usize,
    pub description: String,
}

/// Context zones breakdown response.
#[derive(Serialize)]
pub struct ContextZonesResponse {
    pub zone_a: ZoneInfo,
    pub zone_b: ZoneInfo,
    pub zone_c: ZoneInfo,
    pub zone_d: ZoneInfo,
}

fn degradation_label(pct: f32) -> &'static str {
    if pct < 0.60 {
        "none"
    } else if pct < 0.70 {
        "soft_trim"
    } else if pct < 0.90 {
        "auto_compaction"
    } else if pct < 0.95 {
        "overflow_compaction"
    } else if pct < 0.99 {
        "tool_result_truncation"
    } else {
        "final_error"
    }
}

/// GET /context/snapshot — current context budget snapshot
pub async fn context_snapshot(
    State(state): State<Arc<AppState>>,
    Query(params): Query<ContextQuery>,
) -> Json<ContextSnapshotResponse> {
    let session_id = params
        .session_id
        .map(|s| SessionId::from_string(&s))
        .unwrap_or_else(|| state.agent_handle.session_id.clone());

    if let Some(budget) = state.budget_cache.get(&session_id) {
        return Json(ContextSnapshotResponse {
            total_budget: budget.total,
            system_tokens: budget.system_prompt,
            message_tokens: budget.history,
            tool_tokens: 0,
            remaining: budget.free,
            usage_pct: budget.usage_percent,
            needs_pruning: budget.usage_percent > 60.0,
            degradation_level: degradation_label(budget.usage_percent).to_string(),
        });
    }

    let cm = grid_engine::context::ContextManager::with_default_counter(200_000);
    let snapshot = cm.budget_snapshot("", &[]);
    let needs_pruning = cm.needs_pruning(&snapshot);

    Json(ContextSnapshotResponse {
        total_budget: snapshot.total_budget,
        system_tokens: snapshot.system_tokens,
        message_tokens: snapshot.message_tokens,
        tool_tokens: snapshot.tool_tokens,
        remaining: snapshot.remaining,
        usage_pct: snapshot.usage_pct,
        needs_pruning,
        degradation_level: degradation_label(snapshot.usage_pct).to_string(),
    })
}

/// GET /context/zones — zone breakdown
pub async fn context_zones(
    State(state): State<Arc<AppState>>,
    Query(params): Query<ContextQuery>,
) -> Json<ContextZonesResponse> {
    let session_id = params
        .session_id
        .map(|s| SessionId::from_string(&s))
        .unwrap_or_else(|| state.agent_handle.session_id.clone());

    let system_tokens;
    let message_tokens;

    if let Some(budget) = state.budget_cache.get(&session_id) {
        system_tokens = budget.system_prompt;
        message_tokens = budget.history;
    } else {
        let cm = grid_engine::context::ContextManager::with_default_counter(200_000);
        let snapshot = cm.budget_snapshot("", &[]);
        system_tokens = snapshot.system_tokens;
        message_tokens = snapshot.message_tokens;
    }

    Json(ContextZonesResponse {
        zone_a: ZoneInfo {
            name: "System Prompt".to_string(),
            tokens: system_tokens,
            description: "Static system prompt (cacheable)".to_string(),
        },
        zone_b: ZoneInfo {
            name: "Dynamic Context".to_string(),
            tokens: 0,
            description: "Date, MCP status, session state, user context".to_string(),
        },
        zone_c: ZoneInfo {
            name: "Conversation History".to_string(),
            tokens: message_tokens,
            description: "Active conversation messages".to_string(),
        },
        zone_d: ZoneInfo {
            name: "Tool Definitions".to_string(),
            tokens: 0,
            description: "Tool schemas and specifications (reserved)".to_string(),
        },
    })
}

pub fn router() -> Router<Arc<AppState>> {
    Router::new()
        .route("/context/snapshot", get(context_snapshot))
        .route("/context/zones", get(context_zones))
}
