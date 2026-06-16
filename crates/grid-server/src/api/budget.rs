use std::sync::Arc;

use axum::extract::{Query, State};
use axum::Json;
use grid_types::SessionId;
use serde::Deserialize;

use crate::state::AppState;

#[derive(Deserialize, Default)]
pub struct BudgetQuery {
    pub session_id: Option<String>,
}

pub async fn get_budget(
    State(state): State<Arc<AppState>>,
    Query(params): Query<BudgetQuery>,
) -> Json<grid_types::TokenBudgetSnapshot> {
    let session_id = params
        .session_id
        .map(|s| SessionId::from_string(&s))
        .unwrap_or_else(|| state.agent_handle.session_id.clone());

    if let Some(snapshot) = state.budget_cache.get(&session_id) {
        Json(snapshot.clone())
    } else {
        Json(grid_types::TokenBudgetSnapshot {
            total: 200_000,
            system_prompt: 0,
            dynamic_context: 0,
            history: 0,
            free: 200_000,
            usage_percent: 0.0,
            degradation_level: 0,
        })
    }
}
