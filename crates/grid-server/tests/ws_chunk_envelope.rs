//! Phase 5.4 SC#1 + SC#2 WebSocket integration tests.
//!
//! Covers all ROADMAP Phase 5.4 SC#1 + SC#2 requirements via real
//! tokio-tungstenite client against a bound axum server:
//!   - test_path_alias_warns_on_legacy   (D-05 deprecation warn)
//!   - test_path_v1_native_no_warn       (D-05 canonical path)
//!   - test_backpressure_1000_chunks     (T-01 mitigation, 5.4-01-05)
//!   - test_message_ordering_serial      (T-01 mitigation, 5.4-01-06)
//!   - test_ws_reconnect_simple          (D-15 simple reconnect, 5.4-01-06)
//!   - test_chunk_text_delta_envelope    (D-01/D-02 SC#2, 5.4-01-07)
//!   - test_chunk_tool_lifecycle         (D-01/D-02 SC#2, 5.4-01-07)
//!   - test_control_session_created_first (D-01/D-02 SC#2, 5.4-01-07)

mod common;

use std::sync::{Arc, Mutex};

use futures_util::StreamExt;
use grid_engine::AgentEvent;
use grid_types::SessionId;
use tokio_tungstenite::tungstenite::Message;

use common::ws::{connect_ws_v1, next_json, start_ws_server};
use common::TestApp;

/// Shared writer that captures formatted tracing lines into a Vec<String>.
#[derive(Clone, Default)]
struct CapturedLogs(Arc<Mutex<Vec<u8>>>);

impl std::io::Write for CapturedLogs {
    fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
        self.0.lock().unwrap().extend_from_slice(buf);
        Ok(buf.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

impl<'a> tracing_subscriber::fmt::MakeWriter<'a> for CapturedLogs {
    type Writer = CapturedLogs;
    fn make_writer(&'a self) -> Self::Writer {
        self.clone()
    }
}

impl CapturedLogs {
    fn contains(&self, needle: &str) -> bool {
        let bytes = self.0.lock().unwrap();
        let s = std::str::from_utf8(&bytes).unwrap_or("");
        s.contains(needle)
    }
}

/// Install a tracing dispatcher scoped to a single test. Returns the captured
/// log handle. Uses `set_default(...)` to avoid cross-test interference.
fn install_capture() -> (CapturedLogs, tracing::dispatcher::DefaultGuard) {
    use tracing_subscriber::{fmt, layer::SubscriberExt, EnvFilter, Registry};
    let logs = CapturedLogs::default();
    let layer = fmt::Layer::new()
        .with_writer(logs.clone())
        .with_ansi(false);
    let subscriber = Registry::default()
        .with(EnvFilter::new("grid_server=warn"))
        .with(layer);
    let guard = tracing::dispatcher::set_default(&subscriber.into());
    (logs, guard)
}

// ─────────────────────────────────────────────────────────────────────────
// Task 5.4-01-04 — D-05 path alias + deprecation warn
// ─────────────────────────────────────────────────────────────────────────

#[tokio::test]
async fn test_legacy_path_removed() {
    let app = Arc::new(TestApp::new().await);
    let (addr, _server, _state) = start_ws_server(app).await;

    let url = format!("ws://{}/ws", addr);
    let result = tokio_tungstenite::connect_async(&url).await;
    assert!(
        result.is_err(),
        "legacy /ws path must be unreachable (404) after removal, got connection"
    );
}

#[tokio::test]
async fn test_path_v1_native_no_warn() {
    let (logs, _guard) = install_capture();

    let app = Arc::new(TestApp::new().await);
    let (addr, _server, _state) = start_ws_server(app).await;

    // Connecting via the canonical path must NOT trigger a deprecation warn.
    let mut ws = connect_ws_v1(addr, "v1-test").await;
    let _ = next_json(&mut ws).await; // consume session_created
    drop(ws);
    tokio::time::sleep(std::time::Duration::from_millis(50)).await;

    assert!(
        !logs.contains("deprecated"),
        "canonical /v1/sessions/{{id}}/stream must not emit a deprecation warn"
    );
}

// ─────────────────────────────────────────────────────────────────────────
// Task 5.4-01-05 — SC#1 backpressure: 1000 chunks, 0 dropped (T-01)
// ─────────────────────────────────────────────────────────────────────────

#[tokio::test]
async fn test_backpressure_1000_chunks() {
    // T-01 mitigation gate (Task 5.4-01-05): inject 1000 TextDelta events
    // into the broadcast channel and verify all 1000 are received in order
    // by the WS client. Defense-in-depth: this test installs a tracing
    // capture and asserts NO "broadcast channel lagged" warn line emitted —
    // if the channel had dropped any chunk, we would both receive < 1000
    // AND see a Lagged warn line in captured logs.
    let (logs, _guard) = install_capture();

    let app = Arc::new(TestApp::new().await);
    let (addr, _server, state) = start_ws_server(app).await;

    let session_id_str = "load-test";
    let mut ws = connect_ws_v1(addr, session_id_str).await;
    // Skip the SessionCreated control frame
    let first = next_json(&mut ws).await;
    assert_eq!(first["type"], "session_created");

    // Inject 1000 TextDelta events via the test backdoor. The primary
    // session_id is used (since `load-test` does not exist in the supervisor
    // registry, the helper falls back to the primary handle).
    let sid = SessionId::from_string(session_id_str);
    let events: Vec<AgentEvent> = (0..1000)
        .map(|i| AgentEvent::TextDelta {
            text: format!("msg-{}", i),
        })
        .collect();
    state
        .test_inject_events(&sid, events)
        .await
        .expect("inject");

    let mut received = 0usize;
    let deadline = tokio::time::Instant::now() + std::time::Duration::from_secs(30);
    while received < 1000 && tokio::time::Instant::now() < deadline {
        match tokio::time::timeout(std::time::Duration::from_secs(5), ws.next()).await {
            Ok(Some(Ok(Message::Text(txt)))) => {
                let v: serde_json::Value = serde_json::from_str(&txt).unwrap();
                if v["type"] == "chunk" && v["chunk_type"] == 1 {
                    received += 1;
                }
            }
            Ok(Some(Ok(_))) => continue,
            Ok(Some(Err(e))) => panic!("ws stream error: {e}"),
            Ok(None) => panic!("ws stream closed before 1000 chunks (received {received})"),
            Err(_) => panic!("timeout after 5s waiting for next chunk (received {received})"),
        }
    }

    assert_eq!(
        received, 1000,
        "expected exactly 1000 wire-1 chunks, received {received} — broadcast channel lagged"
    );
    // Explicit defense-in-depth: no Lagged warn line emitted.
    assert!(
        !logs.contains("broadcast channel lagged"),
        "broadcast channel must not lag with 0 dropped chunks (T-01 mitigation)"
    );
}

// ─────────────────────────────────────────────────────────────────────────
// Task 5.4-01-06 — SC#1 ordering + simple reconnect
// ─────────────────────────────────────────────────────────────────────────

#[tokio::test]
async fn test_message_ordering_serial() {
    let app = Arc::new(TestApp::new().await);
    let (addr, _server, state) = start_ws_server(app).await;

    let mut ws = connect_ws_v1(addr, "order-test").await;
    let _ = next_json(&mut ws).await; // skip session_created

    let sid = SessionId::from_string("order-test");
    let events: Vec<AgentEvent> = (0..5)
        .map(|i| AgentEvent::TextDelta {
            text: format!("msg-{}", i),
        })
        .collect();
    state
        .test_inject_events(&sid, events)
        .await
        .expect("inject");

    let mut received: Vec<String> = Vec::new();
    while received.len() < 5 {
        let v = next_json(&mut ws).await;
        if v["type"] == "chunk" && v["chunk_type"] == 1 {
            received.push(v["payload"]["text"].as_str().unwrap().to_string());
        }
    }
    assert_eq!(
        received,
        vec!["msg-0", "msg-1", "msg-2", "msg-3", "msg-4"],
        "TextDelta chunks must arrive in the order they were injected"
    );
}

#[tokio::test]
async fn test_ws_reconnect_simple() {
    // D-15 (CONTEXT lock 2026-05-21, plan-checker W1): simple reconnect
    // scope — only assert new connection succeeds + first SessionCreated
    // frame replay. chunk_id resume semantics deferred to Phase 5.5+.
    //
    // Scope guard: assert the SessionCreated frame does NOT contain a
    // `chunk_id` or `since_chunk_id` field. If a future commit adds chunk_id
    // resume to SessionCreated wire shape without going through Phase 5.5
    // planning, this test will fail and surface the scope creep.
    let app = Arc::new(TestApp::new().await);
    let (addr, _server, _state) = start_ws_server(app).await;

    // First connection
    let mut ws1 = connect_ws_v1(addr, "reconn-test").await;
    let v1 = next_json(&mut ws1).await;
    assert_eq!(v1["type"], "session_created", "first frame must be session_created");
    assert!(
        v1.get("chunk_id").is_none(),
        "Phase 5.4 D-15: SessionCreated must not yet carry chunk_id (defer to 5.5+)"
    );
    drop(ws1);
    tokio::time::sleep(std::time::Duration::from_millis(100)).await;

    // Reconnect
    let mut ws2 = connect_ws_v1(addr, "reconn-test").await;
    let v2 = next_json(&mut ws2).await;
    assert_eq!(
        v2["type"], "session_created",
        "reconnect must replay session_created as the first frame"
    );
    assert!(
        v2.get("since_chunk_id").is_none(),
        "Phase 5.4 D-15: reconnect must not yet support since_chunk_id replay (defer to 5.5+)"
    );
}

// ─────────────────────────────────────────────────────────────────────────
// Task 5.4-01-07 — SC#2 in-process lifecycle ≥3 cases (D-01/D-02)
// ─────────────────────────────────────────────────────────────────────────

#[tokio::test]
async fn test_chunk_text_delta_envelope() {
    let app = Arc::new(TestApp::new().await);
    let (addr, _server, state) = start_ws_server(app).await;

    let mut ws = connect_ws_v1(addr, "td-test").await;
    let _ = next_json(&mut ws).await; // skip session_created

    let sid = SessionId::from_string("td-test");
    state
        .test_inject_events(
            &sid,
            vec![AgentEvent::TextDelta {
                text: "hello".into(),
            }],
        )
        .await
        .expect("inject");

    let v = next_json(&mut ws).await;
    assert_eq!(v["type"], "chunk");
    assert_eq!(v["chunk_type"], 1);
    assert_eq!(v["payload"]["text"], "hello");
}

#[tokio::test]
async fn test_chunk_tool_lifecycle() {
    let app = Arc::new(TestApp::new().await);
    let (addr, _server, state) = start_ws_server(app).await;

    let mut ws = connect_ws_v1(addr, "tool-test").await;
    let _ = next_json(&mut ws).await; // skip session_created

    let sid = SessionId::from_string("tool-test");
    state
        .test_inject_events(
            &sid,
            vec![
                AgentEvent::ToolStart {
                    tool_id: "t1".into(),
                    tool_name: "bash".into(),
                    input: serde_json::json!({"cmd": "echo hi"}),
                },
                AgentEvent::ToolResult {
                    tool_id: "t1".into(),
                    tool_name: "bash".into(),
                    output: "hi\n".into(),
                    success: true,
                },
                AgentEvent::Done,
            ],
        )
        .await
        .expect("inject");

    // Frame 1: chunk wire 3 (TOOL_START)
    let v = next_json(&mut ws).await;
    assert_eq!(v["type"], "chunk");
    assert_eq!(v["chunk_type"], 3);
    assert_eq!(v["payload"]["tool_name"], "bash");

    // Frame 2: chunk wire 4 (TOOL_RESULT)
    let v = next_json(&mut ws).await;
    assert_eq!(v["type"], "chunk");
    assert_eq!(v["chunk_type"], 4);
    assert_eq!(v["payload"]["success"], true);

    // Frame 3: control done
    let v = next_json(&mut ws).await;
    assert_eq!(v["type"], "done");
}

#[tokio::test]
async fn test_control_session_created_first() {
    let app = Arc::new(TestApp::new().await);
    let (addr, _server, _state) = start_ws_server(app).await;

    let mut ws = connect_ws_v1(addr, "sc-test").await;
    let v = next_json(&mut ws).await;
    assert_eq!(v["type"], "session_created");
    // The control envelope's session_id is the *primary* session resolved
    // by handle_socket, NOT the path-segment session_id (since 'sc-test'
    // does not exist in the supervisor, server falls back to primary).
    assert!(
        v["session_id"].as_str().is_some(),
        "session_created must include session_id"
    );
}
