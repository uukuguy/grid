//! Phase 5.4 Plan 02 Task 04 — SERVER-04 auth modes integration tests.
//!
//! 3 modes × ≥1 case + HMAC signature path inline within ApiKey arm
//! (per Q3 correction: no `AuthMode::Hmac` / `AuthMode::Hybrid` variants).
//!
//! Tests build a minimal Axum router that wires only the auth middleware
//! around a single echo endpoint, then exercise the LIFO middleware via
//! `tower::ServiceExt::oneshot` for in-process verification.

use axum::body::Body;
use axum::http::{Method, Request, StatusCode};
use axum::routing::post;
use axum::Router;
use grid_engine::auth::{AuthConfig, AuthMode, Permission};
use grid_server::middleware::auth_middleware_with_role;
use http_body_util::BodyExt;
use std::sync::Arc;
use tower::ServiceExt;

// ── helpers ────────────────────────────────────────────────────────────────

/// Build an `AuthConfig` for `mode` with one known API key ("valid-key") +
/// optional HMAC secret. The secret is also used as the API-key hash secret
/// so test keys round-trip through `validate_key`.
fn auth_config(mode: AuthMode, hmac_secret: &str) -> AuthConfig {
    let mut cfg = AuthConfig {
        mode,
        api_keys: Default::default(),
        require_user_id: false,
        jwt_secret: None,
        token_blacklist: None,
        hmac_secret: hmac_secret.to_string(),
    };
    if mode == AuthMode::ApiKey {
        cfg.add_api_key(
            "valid-key",
            Some("test-user".to_string()),
            vec![Permission::Read, Permission::Write],
        );
    }
    cfg
}

/// Build a minimal router: auth middleware → echo handler.
fn make_router(config: AuthConfig) -> Router {
    let config = Arc::new(config);
    let auth_layer = axum::middleware::from_fn(move |req, next| {
        let config = config.clone();
        async move {
            match auth_middleware_with_role(req, next, &config).await {
                Ok(resp) => resp,
                Err(status) => axum::response::Response::builder()
                    .status(status)
                    .body(Body::empty())
                    .expect("build error response"),
            }
        }
    });

    Router::new()
        .route("/echo", post(echo))
        .layer(auth_layer)
}

async fn echo(body: Body) -> axum::response::Response {
    let bytes = axum::body::to_bytes(body, 10 * 1024 * 1024)
        .await
        .unwrap_or_default();
    axum::response::Response::builder()
        .status(StatusCode::OK)
        .body(Body::from(bytes))
        .expect("build echo response")
}

/// Compute the HMAC-SHA256 hex signature for (ts + "\n" + body) under
/// `secret`. Mirrors `verify_hmac_signature` in middleware/auth.rs.
fn compute_hmac_sig(ts: &str, body: &[u8], secret: &str) -> String {
    use hmac::{Hmac, Mac};
    use sha2::Sha256;
    type HmacSha256 = Hmac<Sha256>;
    let mut mac = HmacSha256::new_from_slice(secret.as_bytes()).expect("hmac key");
    mac.update(ts.as_bytes());
    mac.update(b"\n");
    mac.update(body);
    hex::encode(mac.finalize().into_bytes())
}

async fn send(
    router: Router,
    body: &[u8],
    headers: &[(&str, String)],
) -> (StatusCode, Vec<u8>) {
    let mut req = Request::builder()
        .method(Method::POST)
        .uri("/echo")
        .header("content-type", "application/json");
    for (k, v) in headers {
        req = req.header(*k, v);
    }
    let req = req.body(Body::from(body.to_vec())).expect("build request");
    let resp = router.oneshot(req).await.expect("router oneshot");
    let status = resp.status();
    let bytes = resp
        .into_body()
        .collect()
        .await
        .expect("read body")
        .to_bytes()
        .to_vec();
    (status, bytes)
}

// ── AuthMode::None ─────────────────────────────────────────────────────────

#[tokio::test]
async fn test_mode_none_no_header_200() {
    let router = make_router(auth_config(AuthMode::None, "secret-not-used"));
    let (status, body) = send(router, b"{\"ping\":true}", &[]).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body, b"{\"ping\":true}");
}

// ── AuthMode::ApiKey vanilla (no signature) ────────────────────────────────

#[tokio::test]
async fn test_mode_apikey_valid_200() {
    let router = make_router(auth_config(AuthMode::ApiKey, "test-secret"));
    let (status, _) = send(
        router,
        b"{}",
        &[("x-api-key", "valid-key".to_string())],
    )
    .await;
    assert_eq!(status, StatusCode::OK);
}

#[tokio::test]
async fn test_mode_apikey_invalid_401() {
    let router = make_router(auth_config(AuthMode::ApiKey, "test-secret"));
    let (status, _) = send(
        router,
        b"{}",
        &[("x-api-key", "wrong-key".to_string())],
    )
    .await;
    assert_eq!(status, StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn test_mode_apikey_missing_header_401() {
    let router = make_router(auth_config(AuthMode::ApiKey, "test-secret"));
    let (status, _) = send(router, b"{}", &[]).await;
    assert_eq!(status, StatusCode::UNAUTHORIZED);
}

// ── AuthMode::ApiKey + HMAC signature inline path ──────────────────────────

#[tokio::test]
async fn test_mode_apikey_hmac_signature_valid_200() {
    let secret = "shared-hmac-secret";
    let router = make_router(auth_config(AuthMode::ApiKey, secret));
    let body = br#"{"foo":"bar"}"#.to_vec();
    let ts = chrono::Utc::now().timestamp().to_string();
    let sig = compute_hmac_sig(&ts, &body, secret);

    let (status, echoed) = send(
        router,
        &body,
        &[
            ("x-api-key", "valid-key".to_string()),
            ("x-grid-signature", sig),
            ("x-grid-timestamp", ts),
        ],
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    // Critical: body must be intact after the to_bytes() drain + rebuild.
    assert_eq!(echoed, body);
}

#[tokio::test]
async fn test_mode_apikey_hmac_signature_replay_window_old_401() {
    let secret = "shared-hmac-secret";
    let router = make_router(auth_config(AuthMode::ApiKey, secret));
    let body = br#"{"foo":"bar"}"#.to_vec();
    // 10 minutes ago — outside the ±5min replay window.
    let ts = (chrono::Utc::now().timestamp() - 600).to_string();
    let sig = compute_hmac_sig(&ts, &body, secret);

    let (status, _) = send(
        router,
        &body,
        &[
            ("x-api-key", "valid-key".to_string()),
            ("x-grid-signature", sig),
            ("x-grid-timestamp", ts),
        ],
    )
    .await;
    assert_eq!(status, StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn test_mode_apikey_hmac_signature_tampered_body_401() {
    let secret = "shared-hmac-secret";
    let router = make_router(auth_config(AuthMode::ApiKey, secret));
    let signed_body = br#"{"foo":"bar"}"#.to_vec();
    let sent_body = br#"{"foo":"evil"}"#.to_vec();
    let ts = chrono::Utc::now().timestamp().to_string();
    // Signature is over the original body, but the request sends a tampered one.
    let sig = compute_hmac_sig(&ts, &signed_body, secret);

    let (status, _) = send(
        router,
        &sent_body,
        &[
            ("x-api-key", "valid-key".to_string()),
            ("x-grid-signature", sig),
            ("x-grid-timestamp", ts),
        ],
    )
    .await;
    assert_eq!(status, StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn test_mode_apikey_hmac_signature_missing_timestamp_401() {
    let secret = "shared-hmac-secret";
    let router = make_router(auth_config(AuthMode::ApiKey, secret));
    let body = br#"{}"#.to_vec();
    let ts = chrono::Utc::now().timestamp().to_string();
    let sig = compute_hmac_sig(&ts, &body, secret);

    // x-grid-signature present but x-grid-timestamp absent → 401.
    let (status, _) = send(
        router,
        &body,
        &[
            ("x-api-key", "valid-key".to_string()),
            ("x-grid-signature", sig),
        ],
    )
    .await;
    assert_eq!(status, StatusCode::UNAUTHORIZED);
}
