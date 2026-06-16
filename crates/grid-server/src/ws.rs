use std::sync::Arc;

use axum::extract::ws::{Message, WebSocket};
use axum::extract::{Path, Query, Request, State, WebSocketUpgrade};
use axum::response::IntoResponse;
use futures_util::{SinkExt, StreamExt};
use grid_types::SessionId;
use serde::Deserialize;
use tokio::sync::broadcast;
use tracing::{debug, info, warn};

use grid_engine::{AgentExecutorHandle, AgentMessage};

use crate::state::AppState;
use crate::ws_chunk;

// --- Client -> Server messages ---

#[derive(Debug, Deserialize)]
#[serde(tag = "type")]
enum ClientMessage {
    #[serde(rename = "send_message")]
    SendMessage { content: String },
    #[serde(rename = "cancel")]
    Cancel,
    #[serde(rename = "approval_response")]
    ApprovalResponse {
        tool_id: String,
        approved: bool,
    },
    /// Phase AS: User's response to an agent interaction request (ask_user tool)
    #[serde(rename = "interaction_response")]
    InteractionResponse {
        request_id: String,
        response: grid_engine::tools::interaction::InteractionResponse,
    },
}

// --- Server -> Client messages ---
//
// As of Phase 5.4 D-03/D-04, server→client wire is split:
// - model output → ChunkType envelope (handled by ws_chunk::map_event)
// - lifecycle / control → ws_chunk::ControlMessage variants
//
// The historic 14-variant `enum ServerMessage` has been retired; the two
// standalone control sends below (session_created + error) construct
// `ws_chunk::ControlMessage` directly.

/// Extract a named parameter from a query string.
fn extract_query_param(query: &str, name: &str) -> Option<String> {
    query.split('&').find_map(|pair| {
        let (k, v) = pair.split_once('=')?;
        if k == name { Some(v.to_string()) } else { None }
    })
}

#[derive(Debug, Deserialize)]
pub struct WsQueryParams {
    pub session_id: Option<String>,
    pub token: Option<String>,
}

/// Legacy WebSocket handler — removed.
/// Mounted at `/ws?session_id=...` until Phase A.1 when the deprecated
/// path was removed. The canonical path `/v1/sessions/:id/stream` remains.
#[allow(dead_code)]
pub async fn ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<Arc<AppState>>,
    req: Request,
) -> impl IntoResponse {
    warn!(
        "'/ws' WebSocket path is deprecated; use '/v1/sessions/{{id}}/stream' instead. \
         This alias will be removed when no in-tree consumer references remain \
         (grep -r '/ws?' returns 0)."
    );

    // Auth check: if auth is enabled, verify user context exists.
    // Browser WebSocket API cannot send custom HTTP headers, so we also
    // accept the token as a query parameter: /ws?token=xxx
    if state.auth_config.mode != grid_engine::auth::AuthMode::None
        && req
            .extensions()
            .get::<grid_engine::auth::UserContext>()
            .is_none()
    {
        let query_token = req
            .uri()
            .query()
            .and_then(|q| extract_query_param(q, "token"));

        match query_token {
            Some(ref token) if state.auth_config.validate_key(token) => {
                debug!("WebSocket authenticated via query token");
            }
            Some(_) => {
                warn!("WebSocket query token validation failed");
                return axum::response::Response::builder()
                    .status(axum::http::StatusCode::UNAUTHORIZED)
                    .body(axum::body::Body::from(
                        "WebSocket authentication failed: invalid token",
                    ))
                    .unwrap_or_else(|_| {
                        axum::response::Response::new(axum::body::Body::from("Unauthorized"))
                    })
                    .into_response();
            }
            None => {
                return axum::response::Response::builder()
                    .status(axum::http::StatusCode::UNAUTHORIZED)
                    .body(axum::body::Body::from("WebSocket authentication required"))
                    .unwrap_or_else(|_| {
                        axum::response::Response::new(axum::body::Body::from("Unauthorized"))
                    })
                    .into_response();
            }
        }
    }

    let requested_sid = req
        .uri()
        .query()
        .and_then(|q| extract_query_param(q, "session_id"));

    let handle = resolve_session_handle(&state, requested_sid.as_deref());

    ws.on_upgrade(move |socket| handle_socket(socket, state, handle))
        .into_response()
}

/// Canonical WebSocket handler — mounted at `/v1/sessions/:id/stream`.
/// No deprecation warn; this is the path going forward (D-05).
pub async fn ws_handler_with_path(
    ws: WebSocketUpgrade,
    State(state): State<Arc<AppState>>,
    Path(session_id): Path<String>,
    Query(params): Query<WsQueryParams>,
) -> impl IntoResponse {
    // Auth check (same logic as legacy handler).
    if state.auth_config.mode != grid_engine::auth::AuthMode::None {
        let token = params.token.as_deref();
        match token {
            Some(t) if state.auth_config.validate_key(t) => {
                debug!("WebSocket authenticated via query token");
            }
            Some(_) => {
                warn!("WebSocket query token validation failed");
                return axum::response::Response::builder()
                    .status(axum::http::StatusCode::UNAUTHORIZED)
                    .body(axum::body::Body::from(
                        "WebSocket authentication failed: invalid token",
                    ))
                    .unwrap_or_else(|_| {
                        axum::response::Response::new(axum::body::Body::from("Unauthorized"))
                    })
                    .into_response();
            }
            None => {
                return axum::response::Response::builder()
                    .status(axum::http::StatusCode::UNAUTHORIZED)
                    .body(axum::body::Body::from("WebSocket authentication required"))
                    .unwrap_or_else(|_| {
                        axum::response::Response::new(axum::body::Body::from("Unauthorized"))
                    })
                    .into_response();
            }
        }
    }

    let handle = resolve_session_handle(&state, Some(session_id.as_str()));
    ws.on_upgrade(move |socket| handle_socket(socket, state, handle))
        .into_response()
}

/// Shared session-handle resolution: if `session_id` is given and matches an
/// existing session, return that handle; otherwise fall back to the primary
/// agent_handle.
fn resolve_session_handle(state: &Arc<AppState>, session_id: Option<&str>) -> AgentExecutorHandle {
    if let Some(sid) = session_id {
        let session_id = SessionId::from_string(sid);
        match state.agent_supervisor.get_session_handle(&session_id) {
            Some(h) => {
                info!(session_id = %sid, "WebSocket routed to existing session");
                h
            }
            None => {
                debug!(session_id = %sid, "Session not found, using primary session");
                state.agent_handle.clone()
            }
        }
    } else {
        state.agent_handle.clone()
    }
}

async fn handle_socket(socket: WebSocket, state: Arc<AppState>, handle: AgentExecutorHandle) {
    let (mut sender, mut receiver) = socket.split();

    let sid_str = handle.session_id.as_str().to_string();
    info!(session_id = %sid_str, "WebSocket connected");

    // Phase 5.4 D-04: emit session_created control envelope on connect (before
    // any client message). This lets reconnect / new-connection tests assert
    // the lifecycle handshake immediately.
    let initial_msg = ws_chunk::WsServerMessage::Control(ws_chunk::ControlMessage::SessionCreated {
        session_id: sid_str.clone(),
    });
    if let Ok(text) = serde_json::to_string(&initial_msg) {
        let _ = sender.send(Message::Text(text.into())).await;
    }

    // Subscribe to the broadcast channel so async injections (test backdoor +
    // future server-side push) reach this socket even before a user message.
    let mut bg_rx = handle.subscribe();
    loop {
        tokio::select! {
            // Branch A: background events from the broadcast channel (test
            // injection or out-of-band agent events). Forward whatever
            // ws_chunk::map_event returns.
            ev = bg_rx.recv() => {
                match ev {
                    Ok(event) => {
                        if let Some(msg) = ws_chunk::map_event(&sid_str, event) {
                            let is_done = matches!(
                                &msg,
                                ws_chunk::WsServerMessage::Control(ws_chunk::ControlMessage::Done { .. })
                            );
                            if let Ok(text) = serde_json::to_string(&msg) {
                                if sender.send(Message::Text(text.into())).await.is_err() {
                                    break;
                                }
                            }
                            if is_done {
                                // Stay open; another user message may arrive.
                                // (The legacy code broke the inner loop; the
                                // outer loop here continues until the client
                                // closes the socket.)
                            }
                        }
                    }
                    Err(broadcast::error::RecvError::Closed) => break,
                    Err(broadcast::error::RecvError::Lagged(n)) => {
                        warn!(session_id = %sid_str, lagged = n, "broadcast channel lagged");
                    }
                }
            }
            // Branch B: client → server messages.
            msg = receiver.next() => {
                let Some(msg) = msg else { break };
                let txt = match msg {
                    Ok(Message::Text(t)) => t,
                    Ok(Message::Close(_)) => {
                        info!(session_id = %sid_str, "WebSocket closed by client");
                        break;
                    }
                    Err(e) => {
                        warn!(session_id = %sid_str, "WebSocket error: {e}");
                        break;
                    }
                    _ => continue,
                };

                state.agent_supervisor.touch_session(&handle.session_id);

                let client_msg: ClientMessage = match serde_json::from_str(&txt) {
                    Ok(m) => m,
                    Err(e) => {
                        let err = ws_chunk::WsServerMessage::Control(ws_chunk::ControlMessage::Error {
                            session_id: sid_str.clone(),
                            message: format!("Invalid message: {e}"),
                        });
                        if let Ok(text) = serde_json::to_string(&err) {
                            let _ = sender.send(Message::Text(text.into())).await;
                        }
                        continue;
                    }
                };

                match client_msg {
                    ClientMessage::SendMessage { content } => {
                        // Subscribe a per-turn rx (avoid races on first chunk)
                        let mut rx = handle.subscribe();

                        let _ = handle
                            .send(AgentMessage::UserMessage {
                                content: content.clone(),
                                channel_id: "websocket".to_string(),
                            })
                            .await;

                        // Drain per-turn rx until Done, then return to outer select.
                        loop {
                            match rx.recv().await {
                                Ok(event) => {
                                    if let Some(server_msg) = ws_chunk::map_event(&sid_str, event) {
                                        let is_done = matches!(
                                            &server_msg,
                                            ws_chunk::WsServerMessage::Control(
                                                ws_chunk::ControlMessage::Done { .. }
                                            )
                                        );
                                        if let Ok(text) = serde_json::to_string(&server_msg) {
                                            if sender.send(Message::Text(text.into())).await.is_err() {
                                                return;
                                            }
                                        }
                                        if is_done {
                                            break;
                                        }
                                    }
                                }
                                Err(broadcast::error::RecvError::Closed) => return,
                                Err(broadcast::error::RecvError::Lagged(n)) => {
                                    warn!("Broadcast lagged by {n} messages");
                                }
                            }
                        }
                    }
                    ClientMessage::Cancel => {
                        let _ = handle.send(AgentMessage::Cancel).await;
                        info!(session_id = %sid_str, "Agent cancellation requested");
                    }
                    ClientMessage::ApprovalResponse { tool_id, approved } => {
                        if let Some(ref gate) = state.approval_gate {
                            let found = gate.respond(&tool_id, approved).await;
                            if found {
                                info!(tool_id = %tool_id, approved, "Approval response forwarded");
                            } else {
                                warn!(tool_id = %tool_id, "No pending approval for tool_id");
                            }
                        } else {
                            warn!("ApprovalResponse received but no ApprovalGate configured");
                        }
                    }
                    ClientMessage::InteractionResponse { request_id, response } => {
                        let found = state.interaction_gate.respond(&request_id, response).await;
                        if found {
                            info!(request_id = %request_id, "Interaction response forwarded");
                        } else {
                            warn!(request_id = %request_id, "No pending interaction request");
                        }
                    }
                }
            }
        }
    }

    info!(session_id = %sid_str, "WebSocket disconnected");
}
