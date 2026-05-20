//! SC#3 (Phase 5.4) — Stop hook → L2 trajectory write integration tests.
//!
//! Tests:
//! 1. test_stop_hook_writes_anchor_to_l2 — Stop hook fires, mock L2 receives
//!    POST /tools/memory_write_anchor/invoke with session_trajectory anchor_type.
//! 2. test_stop_hook_writes_file_to_l2  — Stop hook fires, mock L2 receives
//!    POST /tools/memory_write_file/invoke with scope=session:<sid> +
//!    category=session_trajectory.
//! 3. test_schema_coverage_session_and_turn_tables (W4 plan-checker) —
//!    Open temp SQLite, run grid_engine::db::migrate, dump schema, assert
//!    both `sessions` AND `turns` tables present (SC#3 schema-coverage proof).
//!
//! These DO NOT spin a real LLM — they directly call dispatch_stop_hooks
//! per stop_hooks.rs:111-118.

use std::sync::{Arc, Mutex};

use axum::{
    extract::State,
    routing::post,
    Json, Router,
};
use grid_engine::agent::{dispatch_stop_hooks, L2TrajectoryStopHook, StopHook};
use grid_engine::hooks::HookContext;
use grid_engine::l2::L2MemoryClient;
use serde_json::Value;
use tokio::net::TcpListener;

/// Recorded request: (path, body-json).
type CapturedReqs = Arc<Mutex<Vec<(String, Value)>>>;

/// Mock L2 endpoint handler — captures path + body, returns 200 with stub.
async fn mock_anchor_handler(
    State(captured): State<CapturedReqs>,
    Json(body): Json<Value>,
) -> Json<Value> {
    captured
        .lock()
        .unwrap()
        .push(("/tools/memory_write_anchor/invoke".to_string(), body));
    Json(serde_json::json!({"anchor_id": "mock-anchor-1"}))
}

async fn mock_file_handler(
    State(captured): State<CapturedReqs>,
    Json(body): Json<Value>,
) -> Json<Value> {
    captured
        .lock()
        .unwrap()
        .push(("/tools/memory_write_file/invoke".to_string(), body));
    Json(serde_json::json!({"memory_id": "mock-memory-1", "version": 1}))
}

/// Start a hand-rolled mock L2 HTTP server bound to 127.0.0.1:0.
/// Returns the bound URL + a captured-requests handle.
async fn start_mock_l2() -> (String, CapturedReqs, tokio::task::JoinHandle<()>) {
    let captured: CapturedReqs = Arc::new(Mutex::new(Vec::new()));
    let captured_for_router = captured.clone();

    let router = Router::new()
        .route(
            "/tools/memory_write_anchor/invoke",
            post(mock_anchor_handler),
        )
        .route(
            "/tools/memory_write_file/invoke",
            post(mock_file_handler),
        )
        .with_state(captured_for_router);

    let listener = TcpListener::bind("127.0.0.1:0").await.expect("bind");
    let addr = listener.local_addr().expect("local_addr");
    let handle = tokio::spawn(async move {
        axum::serve(listener, router).await.ok();
    });

    // Give axum a moment to start accepting.
    tokio::time::sleep(std::time::Duration::from_millis(50)).await;

    (format!("http://{}", addr), captured, handle)
}

#[tokio::test]
async fn test_stop_hook_writes_anchor_to_l2() {
    let (base_url, captured, _server_handle) = start_mock_l2().await;

    let client = L2MemoryClient::new(&base_url);
    let session_id = "sess-anchor-test".to_string();
    let hook: Arc<dyn StopHook> = Arc::new(L2TrajectoryStopHook::new(client, session_id.clone()));

    let ctx = HookContext::new().with_session(&session_id);
    let _decision = dispatch_stop_hooks(&[hook], &ctx).await;

    // Give the HTTP server a tick to record the requests
    tokio::time::sleep(std::time::Duration::from_millis(50)).await;

    let recorded = captured.lock().unwrap().clone();
    let anchor_calls: Vec<_> = recorded
        .iter()
        .filter(|(p, _)| p == "/tools/memory_write_anchor/invoke")
        .collect();
    assert_eq!(
        anchor_calls.len(),
        1,
        "expected exactly 1 POST to memory_write_anchor/invoke, got {}: {:?}",
        anchor_calls.len(),
        recorded
    );

    let (_, body) = anchor_calls[0];
    let args = &body["args"];
    assert_eq!(args["session_id"], session_id);
    // The L2 client serializes #[serde(rename = "type")] anchor_type → "type" key.
    assert_eq!(
        args["type"], "session_trajectory",
        "anchor type must be session_trajectory per D-09"
    );
    assert_eq!(args["source_system"], "grid-server");
}

#[tokio::test]
async fn test_stop_hook_writes_file_to_l2() {
    let (base_url, captured, _server_handle) = start_mock_l2().await;

    let client = L2MemoryClient::new(&base_url);
    let session_id = "sess-file-test".to_string();
    let hook: Arc<dyn StopHook> = Arc::new(L2TrajectoryStopHook::new(client, session_id.clone()));

    let ctx = HookContext::new().with_session(&session_id);
    let _decision = dispatch_stop_hooks(&[hook], &ctx).await;

    tokio::time::sleep(std::time::Duration::from_millis(50)).await;

    let recorded = captured.lock().unwrap().clone();
    let file_calls: Vec<_> = recorded
        .iter()
        .filter(|(p, _)| p == "/tools/memory_write_file/invoke")
        .collect();
    assert_eq!(
        file_calls.len(),
        1,
        "expected exactly 1 POST to memory_write_file/invoke, got {}: {:?}",
        file_calls.len(),
        recorded
    );

    let (_, body) = file_calls[0];
    let args = &body["args"];
    assert_eq!(args["scope"], format!("session:{}", session_id));
    assert_eq!(
        args["category"], "session_trajectory",
        "file category must be session_trajectory per D-09"
    );
    assert_eq!(args["status"], "agent_suggested");
}

/// W4 plan-checker SC#3 schema-coverage proof:
/// Migrate a fresh temp SQLite db and assert both `sessions` and `turns`
/// table-creation SQL are present. Independent of mock L2.
#[test]
fn test_schema_coverage_session_and_turn_tables() {
    let tmp = tempfile::tempdir().expect("tempdir");
    let db_path = tmp.path().join("schema-cov.db");
    let conn = rusqlite::Connection::open(&db_path).expect("open conn");

    grid_engine::db::migrate(&conn).expect("migrate");

    // Dump schema for all user tables
    let mut stmt = conn
        .prepare("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")
        .expect("prepare");
    let rows: Vec<String> = stmt
        .query_map([], |row| row.get::<_, String>(0))
        .expect("query_map")
        .filter_map(Result::ok)
        .collect();
    let schema_dump = rows.join("\n");

    // SC#3: "schema 新增/演进 covering session record + turn record"
    assert!(
        schema_dump.contains("CREATE TABLE") && schema_dump.contains("sessions"),
        "schema must contain CREATE TABLE ... sessions (got: {})",
        &schema_dump[..schema_dump.len().min(500)]
    );
    assert!(
        schema_dump.contains("CREATE TABLE") && schema_dump.contains("turns"),
        "schema must contain CREATE TABLE ... turns (got: {})",
        &schema_dump[..schema_dump.len().min(500)]
    );
}
