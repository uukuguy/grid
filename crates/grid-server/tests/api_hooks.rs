//! E2E tests for Hooks API endpoints (AO-T3)

mod common;

use axum::http::StatusCode;

#[tokio::test]
async fn hooks_list_returns_ok() {
    let app = common::TestApp::new().await;
    let (status, body) = app.get("/api/v1/hooks").await;
    assert_eq!(status, StatusCode::OK);
    assert!(body.is_array());
}

#[tokio::test]
async fn hooks_points_returns_enum_values() {
    let app = common::TestApp::new().await;
    let (status, body) = app.get("/api/v1/hooks/points").await;
    assert_eq!(status, StatusCode::OK);
    assert!(body["points"].is_array());
    let points = body["points"].as_array().unwrap();
    assert!(!points.is_empty());
    // Verify some known hook points exist
    let point_strs: Vec<&str> = points.iter().filter_map(|v| v.as_str()).collect();
    assert!(point_strs.contains(&"PreToolUse"));
    assert!(point_strs.contains(&"PostToolUse"));
    assert!(point_strs.contains(&"SessionStart"));
    assert!(point_strs.contains(&"SessionEnd"));
    assert!(point_strs.contains(&"Stop"));
}

#[tokio::test]
async fn hooks_reload_returns_ok() {
    let app = common::TestApp::new().await;
    let (status, body) = app.post_json("/api/v1/hooks/reload", serde_json::json!({})).await;
    assert_eq!(status, StatusCode::OK);
    // Should have reloaded field
    assert!(body["reloaded"].is_boolean());
    assert!(body["message"].is_string());
}

#[tokio::test]
async fn hooks_wasm_list_returns_ok() {
    let app = common::TestApp::new().await;
    let (status, body) = app.get("/api/v1/hooks/wasm").await;
    assert_eq!(status, StatusCode::OK);
    assert!(body.is_array());
    // Field-shape invariant: every entry must have a `name` (string) and
    // `status` (string) field. Guards against the DiscoveredPlugin -> WasmPluginInfo
    // mapping regressing (e.g. accessing `p.name` instead of `p.manifest.name`).
    for entry in body.as_array().unwrap() {
        assert!(
            entry.get("name").and_then(|v| v.as_str()).is_some(),
            "wasm plugin entry missing `name` string field: {entry}"
        );
        assert!(
            entry.get("status").and_then(|v| v.as_str()).is_some(),
            "wasm plugin entry missing `status` string field: {entry}"
        );
    }
}
