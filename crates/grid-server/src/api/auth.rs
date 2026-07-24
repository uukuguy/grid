//! v3.8.1 HTTP auth endpoints — login / refresh / logout.
//!
//! Three handlers that surface the JWT primitive from `grid-engine::auth`
//! (03.8.0) + UserStore/TokenBlacklist (03.8.1):
//!
//! - `POST /api/v1/auth/login` — verify email+password against UserStore,
//!   mint a JWT, return `{ access_token, token_type, expires_at }`. On
//!   any failure returns the same 401 body (AUTH-04 / D-09: never
//!   reveal whether the user exists).
//! - `POST /api/v1/auth/refresh` — re-mints a fresh JWT with new exp
//!   using the bearer token from `Authorization` header. Old token
//!   remains valid until its own exp (no rotation in v3.8.1 per D-04).
//! - `POST /api/v1/auth/logout` — blacklists the bearer token until
//!   its natural exp. Returns 204 No Content.
//!
//! All endpoints read AppState (Arc-wrapped) for auth config, user store,
//! token blacklist, and TTL. They DO NOT participate in AuthMode::Full
//! middleware (login refreshes use the `Authorization` header inline,
//! bypassing the middleware's own validation; logout similarly reads
//! the token directly).

use axum::extract::{Request, State};
use axum::http::{header, StatusCode};
use axum::response::IntoResponse;
use axum::Json;
use grid_engine::auth::JwtClaims;
use serde::{Deserialize, Serialize};
use std::sync::Arc;

use crate::state::AppState;

// ── wire types ──────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct LoginRequest {
    pub email: String,
    pub password: String,
}

#[derive(Debug, Serialize)]
pub struct LoginResponse {
    pub access_token: String,
    pub token_type: &'static str,
    pub expires_at: i64,
}

#[derive(Debug, Serialize)]
pub struct ErrorResponse {
    pub error: &'static str,
    pub message: String,
}

fn err(status: StatusCode, code: &'static str, msg: String) -> (StatusCode, Json<ErrorResponse>) {
    (
        status,
        Json(ErrorResponse {
            error: code,
            message: msg,
        }),
    )
}

fn ttl_for(_state: &AppState) -> i64 {
    // Per v3.8.1 plan §Task 4 D-09: token_ttl_secs is fixed at startup;
    // the refresh handler can re-read on each request if we want to
    // honor mid-run changes (not implemented in v3.8.1).
    // We pass state in rather than reading it again so the test helper
    // can pin a different TTL.
    _state.token_ttl_secs
}

// ── handlers ───────────────────────────────────────────────────────────

/// `POST /api/v1/auth/login`
pub async fn login_handler(
    State(state): State<Arc<AppState>>,
    Json(req): Json<LoginRequest>,
) -> Result<Json<LoginResponse>, (StatusCode, Json<ErrorResponse>)> {
    let Some(record) = state.users.verify_credentials(&req.email, &req.password) else {
        // AUTH-04 / D-09: same body regardless of which side failed.
        return Err(err(
            StatusCode::UNAUTHORIZED,
            "auth_failed",
            "invalid credentials".into(),
        ));
    };
    let ttl = ttl_for(&state);
    // Role is an enum with serde rename_all = "snake_case"; serialize it
    // through serde_json to get the canonical wire string (e.g. "admin",
    // "owner") without needing Role::Display. Trim the wrapping quotes.
    let role_wire = serde_json::to_string(&record.role)
        .map_err(|e| err(
            StatusCode::INTERNAL_SERVER_ERROR,
            "mint_failed",
            format!("role serialization: {e}"),
        ))?
        .trim_matches('"')
        .to_string();
    let (token, exp) = state
        .auth_config
        .mint_jwt(
            &record.tenant_id,
            &record.user_id,
            &record.email,
            &role_wire,
            ttl,
        )
        .map_err(|e| {
            err(
                StatusCode::INTERNAL_SERVER_ERROR,
                "mint_failed",
                format!("server misconfigured: {e}"),
            )
        })?;
    Ok(Json(LoginResponse {
        access_token: token,
        token_type: "Bearer",
        expires_at: exp,
    }))
}

/// `POST /api/v1/auth/refresh`
///
/// Re-mints a fresh JWT (new `jti`, new `exp`) using the bearer token
/// presented in the `Authorization` header. The old token is NOT revoked
/// — D-04: single-token sliding expiration, no rotation in v3.8.1.
pub async fn refresh_handler(
    State(state): State<Arc<AppState>>,
    req: Request,
) -> Result<Json<LoginResponse>, (StatusCode, Json<ErrorResponse>)> {
    let bearer = extract_bearer(&req).ok_or_else(|| {
        err(
            StatusCode::UNAUTHORIZED,
            "auth_failed",
            "missing or malformed bearer token".into(),
        )
    })?;
    let claims = state.auth_config.validate_jwt(bearer).ok_or_else(|| {
        err(
            StatusCode::UNAUTHORIZED,
            "auth_failed",
            "token rejected".into(),
        )
    })?;
    if state.token_blacklist.is_blacklisted(&claims.jti) {
        return Err(err(
            StatusCode::UNAUTHORIZED,
            "auth_failed",
            "token rejected".into(),
        ));
    }
    let ttl = ttl_for(&state);
    let (token, exp) = state
        .auth_config
        .mint_jwt(
            &claims.tenant_id,
            &claims.sub,
            &claims.email,
            &claims.role,
            ttl,
        )
        .map_err(|e| {
            err(
                StatusCode::INTERNAL_SERVER_ERROR,
                "mint_failed",
                format!("server misconfigured: {e}"),
            )
        })?;
    Ok(Json(LoginResponse {
        access_token: token,
        token_type: "Bearer",
        expires_at: exp,
    }))
}

/// `POST /api/v1/auth/logout`
///
/// Blacklists the bearer token until its natural exp. After this returns,
/// the same `Authorization: Bearer <token>` (with this exact jti) will be
/// rejected by all handlers that consult `Extension<JwtClaims>` post-blacklist
/// (the server-side token blacklist lives behind the JWT validation path).
pub async fn logout_handler(
    State(state): State<Arc<AppState>>,
    req: Request,
) -> Result<StatusCode, (StatusCode, Json<ErrorResponse>)> {
    let bearer = extract_bearer(&req).ok_or_else(|| {
        err(
            StatusCode::UNAUTHORIZED,
            "auth_failed",
            "missing or malformed bearer token".into(),
        )
    })?;
    let claims: JwtClaims = state.auth_config.validate_jwt(bearer).ok_or_else(|| {
        err(
            StatusCode::UNAUTHORIZED,
            "auth_failed",
            "token rejected".into(),
        )
    })?;
    state
        .token_blacklist
        .blacklist(&claims.jti, claims.exp);
    Ok(StatusCode::NO_CONTENT)
}

/// Pull `Authorization: Bearer <token>` out of the request. Used by
/// refresh + logout (login doesn't need it).
fn extract_bearer(req: &Request) -> Option<&str> {
    req.headers()
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
}

// Make `IntoResponse` available for the tuple-returning handlers above.
#[allow(dead_code)]
fn _unused_into_response() -> impl IntoResponse { () }
