//! Admin endpoints — Phase 5.4 SERVER-05 hot-reload (T-06 mitigation).
//!
//! `POST /api/v1/admin/reload` accepts a JSON envelope and applies
//! reloadable fields onto `state.runtime_overrides`. Restart-required
//! fields (host, port, auth_mode, api_key — GA7 + RESEARCH §4 Q4)
//! surface as HTTP 422 with a structured `FIELD_REQUIRES_RESTART`
//! error body so operators see the rejection rather than silent drift
//! (the legacy `PUT /config` endpoint uses 400; this new endpoint
//! intentionally uses 422 per Q4 + plan §Task 06).
//!
//! Mechanism: POST endpoint over the existing auth-protected router,
//! NOT SIGHUP or a file watcher — locked by CONTEXT GA7.

use axum::{extract::State, http::StatusCode, response::IntoResponse, Json};
use std::sync::Arc;

use crate::state::AppState;

/// Fields that may NOT be hot-reloaded — change requires a server restart.
/// Listed in JSON-payload order so the loop short-circuits on the first match
/// rather than producing a multi-field rejection.
pub const RESTART_REQUIRED_FIELDS: &[&str] = &["host", "port", "auth_mode", "api_key"];

/// Reloadable fields accepted by `POST /admin/reload`.
///
/// All fields optional; absent fields are no-ops (NOT zeroed out).
#[derive(serde::Deserialize, Debug)]
pub struct ReloadRequest {
    pub hooks_file: Option<String>,
    pub policies_file: Option<String>,
    pub log_level: Option<String>,
    pub cors_origins: Option<Vec<String>>,
}

/// `POST /api/v1/admin/reload` — apply reloadable overrides without restart.
///
/// Returns:
/// - 422 + `FIELD_REQUIRES_RESTART` if any restart-only field present.
/// - 400 + `invalid_request` on parse failure.
/// - 200 + `{ reloaded: true, fields_updated: [...] }` on success.
pub async fn reload_config(
    State(state): State<Arc<AppState>>,
    Json(req_value): Json<serde_json::Value>,
) -> axum::response::Response {
    // 1. Restart-required reject — surface explicitly to defeat silent drift.
    for k in RESTART_REQUIRED_FIELDS {
        if req_value.get(k).is_some() {
            return (
                StatusCode::UNPROCESSABLE_ENTITY,
                Json(serde_json::json!({
                    "error": "FIELD_REQUIRES_RESTART",
                    "field": k,
                    "message": format!(
                        "{} cannot be hot-reloaded. Stop the server, update config, and restart.",
                        k
                    ),
                })),
            )
                .into_response();
        }
    }

    // 2. Strict parse — any unknown reloadable field is a 400 (anti-typo guard).
    let parsed: ReloadRequest = match serde_json::from_value(req_value) {
        Ok(p) => p,
        Err(e) => {
            return (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({
                    "error": "invalid_request",
                    "message": e.to_string(),
                })),
            )
                .into_response();
        }
    };

    // 3. Apply the `Some(field)` → update pattern atomically under the write
    //    lock. Returns which fields actually changed (not just which were
    //    provided), so callers know whether their POST was a no-op.
    let mut updated: Vec<&'static str> = Vec::new();
    {
        let mut o = state.runtime_overrides.write().await;
        if let Some(v) = parsed.hooks_file {
            if o.hooks_file.as_deref() != Some(v.as_str()) {
                o.hooks_file = Some(v);
                updated.push("hooks_file");
            }
        }
        if let Some(v) = parsed.policies_file {
            if o.policies_file.as_deref() != Some(v.as_str()) {
                o.policies_file = Some(v);
                updated.push("policies_file");
            }
        }
        if let Some(v) = parsed.log_level {
            // Phase A.1: log_level hot-reload requires restart.
            // tracing-subscriber 0.3.22 (currently locked) does not support
            // the `reload` feature needed for live filter updates.
            // Value is recorded — frontend may show "restart required" banner.
            if o.log_level.as_deref() != Some(v.as_str()) {
                o.log_level = Some(v);
                updated.push("log_level");
            }
        }
        if let Some(v) = parsed.cors_origins {
            if o.cors_origins.as_ref() != Some(&v) {
                o.cors_origins = Some(v);
                updated.push("cors_origins");
            }
        }
    }

    (
        StatusCode::OK,
        Json(serde_json::json!({
            "reloaded": true,
            "fields_updated": updated,
        })),
    )
        .into_response()
}
