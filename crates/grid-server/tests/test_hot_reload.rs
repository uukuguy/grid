//! Phase 5.4 Plan 02 Task 06 — SERVER-05 hot-reload endpoint.
//!
//! 8 cases total:
//!   - 4 reloadable fields (hooks_file, policies_file, log_level, cors_origins)
//!     → 200 + state updated under `state.runtime_overrides`.
//!   - 4 restart-required fields (host, port, auth_mode, api_key per GA7)
//!     → 422 + `{"error":"FIELD_REQUIRES_RESTART","field":<name>, ...}`.
//!
//! Exercises the endpoint end-to-end through the production router
//! (`crate::router::build_router`) — auth defaults to None in `TestApp::new()`
//! so no header plumbing is needed.

mod common;

use common::TestApp;
use serde_json::json;

// ── reloadable cases ───────────────────────────────────────────────────────

#[tokio::test]
async fn test_reloadable_hooks_file() {
    let app = TestApp::new().await;
    let (status, body) = app
        .post_json("/api/v1/admin/reload", json!({"hooks_file": "/new/hooks.yaml"}))
        .await;
    assert_eq!(status, axum::http::StatusCode::OK);
    assert_eq!(body["reloaded"], true);
    let fields = body["fields_updated"]
        .as_array()
        .expect("fields_updated is array");
    assert!(
        fields.iter().any(|v| v == "hooks_file"),
        "expected hooks_file in fields_updated, got {:?}",
        fields
    );
    let o = app.state.runtime_overrides.read().await;
    assert_eq!(o.hooks_file.as_deref(), Some("/new/hooks.yaml"));
}

#[tokio::test]
async fn test_reloadable_policies_file() {
    let app = TestApp::new().await;
    let (status, body) = app
        .post_json(
            "/api/v1/admin/reload",
            json!({"policies_file": "/new/policy.json"}),
        )
        .await;
    assert_eq!(status, axum::http::StatusCode::OK);
    assert_eq!(body["reloaded"], true);
    let o = app.state.runtime_overrides.read().await;
    assert_eq!(o.policies_file.as_deref(), Some("/new/policy.json"));
}

#[tokio::test]
async fn test_reloadable_log_level() {
    let app = TestApp::new().await;
    let (status, body) = app
        .post_json("/api/v1/admin/reload", json!({"log_level": "debug"}))
        .await;
    assert_eq!(status, axum::http::StatusCode::OK);
    assert_eq!(body["reloaded"], true);
    let fields = body["fields_updated"]
        .as_array()
        .expect("fields_updated is array");
    assert!(
        fields.iter().any(|v| v == "log_level"),
        "log_level should appear in fields_updated even though the tracing reload \
         handle isn't yet wired (recorded in overrides for operator visibility)"
    );
    let o = app.state.runtime_overrides.read().await;
    assert_eq!(o.log_level.as_deref(), Some("debug"));
}

#[tokio::test]
async fn test_reloadable_cors_origins() {
    let app = TestApp::new().await;
    let new_origins = vec!["https://example.com".to_string(), "https://foo.invalid".to_string()];
    let (status, body) = app
        .post_json(
            "/api/v1/admin/reload",
            json!({"cors_origins": new_origins.clone()}),
        )
        .await;
    assert_eq!(status, axum::http::StatusCode::OK);
    assert_eq!(body["reloaded"], true);
    let o = app.state.runtime_overrides.read().await;
    assert_eq!(o.cors_origins.as_ref(), Some(&new_origins));
}

// ── restart-required cases (422) ───────────────────────────────────────────

async fn assert_restart_required(field: &str, body: serde_json::Value) {
    let app = TestApp::new().await;
    let (status, resp) = app.post_json("/api/v1/admin/reload", body).await;
    assert_eq!(
        status,
        axum::http::StatusCode::UNPROCESSABLE_ENTITY,
        "field {} should yield 422, got {} with body {:?}",
        field,
        status,
        resp
    );
    assert_eq!(resp["error"], "FIELD_REQUIRES_RESTART");
    assert_eq!(resp["field"], field);
    assert!(
        resp["message"]
            .as_str()
            .map(|m| m.contains("restart"))
            .unwrap_or(false),
        "message should mention restart, got {:?}",
        resp["message"]
    );
}

#[tokio::test]
async fn test_require_restart_host() {
    assert_restart_required("host", json!({"host": "0.0.0.0"})).await;
}

#[tokio::test]
async fn test_require_restart_port() {
    assert_restart_required("port", json!({"port": 3002})).await;
}

#[tokio::test]
async fn test_require_restart_auth_mode() {
    assert_restart_required("auth_mode", json!({"auth_mode": "none"})).await;
}

#[tokio::test]
async fn test_require_restart_api_key() {
    assert_restart_required("api_key", json!({"api_key": "xxx"})).await;
}
