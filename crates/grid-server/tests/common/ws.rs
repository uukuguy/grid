//! tokio-tungstenite WebSocket client helper for Phase 5.4 WS tests.
//!
//! Binds a real TCP listener on 127.0.0.1:0 + serves the TestApp's router
//! via `axum::serve`. Provides convenience connect_ws_v1 / connect_ws_legacy.

use std::net::SocketAddr;
use std::sync::Arc;

use tokio::net::{TcpListener, TcpStream};
use tokio_tungstenite::{
    connect_async, tungstenite::Message, MaybeTlsStream, WebSocketStream,
};

use crate::common::TestApp;

pub type WsClient = WebSocketStream<MaybeTlsStream<TcpStream>>;

/// Start the TestApp's full router bound to 127.0.0.1:0.
/// Returns (bound addr, server JoinHandle, the Arc<AppState> shared with the
/// router — needed for test_inject_events backdoor calls).
pub async fn start_ws_server(
    app: Arc<TestApp>,
) -> (
    SocketAddr,
    tokio::task::JoinHandle<()>,
    Arc<grid_server::state::AppState>,
) {
    let listener = TcpListener::bind("127.0.0.1:0").await.expect("bind");
    let addr = listener.local_addr().expect("local_addr");
    let router = app.router.clone();
    let state = app.state.clone();
    let handle = tokio::spawn(async move {
        axum::serve(listener, router).await.ok();
    });
    // Give axum a moment to start accepting.
    tokio::time::sleep(std::time::Duration::from_millis(50)).await;
    (addr, handle, state)
}

/// Connect via the canonical path `ws://addr/v1/sessions/{session_id}/stream`.
pub async fn connect_ws_v1(addr: SocketAddr, session_id: &str) -> WsClient {
    let url = format!("ws://{}/v1/sessions/{}/stream", addr, session_id);
    let (ws, _resp) = connect_async(url).await.expect("ws connect_async v1");
    ws
}

/// Connect via the legacy path `ws://addr/ws?session_id=<id>`.
pub async fn connect_ws_legacy(addr: SocketAddr, session_id: &str) -> WsClient {
    let url = format!("ws://{}/ws?session_id={}", addr, session_id);
    let (ws, _resp) = connect_async(url).await.expect("ws connect_async legacy");
    ws
}

/// Receive next WS frame as JSON, panicking on any other variant.
pub async fn next_json(ws: &mut WsClient) -> serde_json::Value {
    use futures_util::StreamExt;
    let frame = ws
        .next()
        .await
        .expect("ws stream closed unexpectedly")
        .expect("ws frame error");
    match frame {
        Message::Text(t) => serde_json::from_str(&t).expect("frame is not valid json"),
        other => panic!("expected text frame, got {:?}", other),
    }
}
