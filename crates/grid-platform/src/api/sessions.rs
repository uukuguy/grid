//! Session API handlers

use axum::{
    extract::{Path, State},
    Json,
};
use serde::{Deserialize, Serialize};

use crate::user_runtime::{Session, SessionStatus};
use crate::{ArcAppState, AuthExtractor, ErrorResponse, ErrorCode};

/// Custom error type for handlers that need specific status codes
type ApiError = (axum::http::StatusCode, Json<ErrorResponse>);

fn with_status(code: ErrorCode, status: axum::http::StatusCode, message: &str) -> ApiError {
    (status, Json(ErrorResponse::new(code, message)))
}

/// Request to create a session
#[derive(Debug, Deserialize)]
pub struct CreateSessionRequest {
    pub name: Option<String>,
}

/// Response for a session
#[derive(Debug, Serialize)]
pub struct SessionResponse {
    pub id: String,
    pub user_id: String,
    pub name: Option<String>,
    pub status: String,
    pub created_at: String,
    pub updated_at: String,
}

impl From<Session> for SessionResponse {
    fn from(s: Session) -> Self {
        Self {
            id: s.id,
            user_id: s.user_id,
            name: s.name,
            status: match s.status {
                SessionStatus::Active => "active".to_string(),
                SessionStatus::Paused => "paused".to_string(),
                SessionStatus::Completed => "completed".to_string(),
            },
            created_at: s.created_at.to_rfc3339(),
            updated_at: s.updated_at.to_rfc3339(),
        }
    }
}

/// List all sessions for current user
pub async fn list_sessions(
    State(state): State<ArcAppState>,
    auth: AuthExtractor,
) -> Result<Json<Vec<SessionResponse>>, ErrorResponse> {
    let user_runtime = state
        .get_or_create_user_runtime(&auth.user_id)
        .map_err(|_| ErrorResponse::internal("Failed to access user runtime"))?;

    let sessions = user_runtime.list_sessions(&auth.user_id);
    Ok(Json(sessions.into_iter().map(|s| s.into()).collect()))
}

/// Create a new session
pub async fn create_session(
    State(state): State<ArcAppState>,
    auth: AuthExtractor,
    Json(req): Json<CreateSessionRequest>,
) -> Result<Json<SessionResponse>, ErrorResponse> {
    let user_runtime = state
        .get_or_create_user_runtime(&auth.user_id)
        .map_err(|_| ErrorResponse::internal("Failed to access user runtime"))?;

    let session = user_runtime
        .create_session(req.name)
        .map_err(|_| ErrorResponse::internal("Failed to create session"))?;

    Ok(Json(session.into()))
}

/// Get a specific session
pub async fn get_session(
    State(state): State<ArcAppState>,
    auth: AuthExtractor,
    Path(session_id): Path<String>,
) -> Result<Json<SessionResponse>, ApiError> {
    let user_runtime = state
        .get_or_create_user_runtime(&auth.user_id)
        .map_err(|_| {
            with_status(ErrorCode::Internal, axum::http::StatusCode::INTERNAL_SERVER_ERROR, "Failed to access user runtime")
        })?;

    let session = user_runtime
        .get_session(&auth.user_id, &session_id)
        .ok_or_else(|| {
            with_status(ErrorCode::NotFound, axum::http::StatusCode::NOT_FOUND, "Session not found")
        })?;

    Ok(Json(session.into()))
}

/// Delete a session
pub async fn delete_session(
    State(state): State<ArcAppState>,
    auth: AuthExtractor,
    Path(session_id): Path<String>,
) -> Result<axum::http::StatusCode, ApiError> {
    let user_runtime = state
        .get_or_create_user_runtime(&auth.user_id)
        .map_err(|_| {
            with_status(ErrorCode::Internal, axum::http::StatusCode::INTERNAL_SERVER_ERROR, "Failed to access user runtime")
        })?;

    let deleted = user_runtime.delete_session(&auth.user_id, &session_id);
    if !deleted {
        return Err(with_status(ErrorCode::NotFound, axum::http::StatusCode::NOT_FOUND, "Session not found"));
    }

    Ok(axum::http::StatusCode::NO_CONTENT)
}
