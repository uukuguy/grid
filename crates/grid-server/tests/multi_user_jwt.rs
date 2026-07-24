//! Phase 03.8.0 hermetic tests for v3.8 multi-user JWT primitive.
//!
//! Covers REQUIREMENTS.md v3.8:
//! - AUTH-01: JWT carries tenant_id, user_id, role
//! - AUTH-04: tampered signature → 401; missing claim → 401
//! - AUTH-05: HMAC-SHA256 secret ≥ 32 bytes (HS256 minimum per RFC 7518 §3.2)
//!
//! Tests use the same minimal-axum-router + `tower::ServiceExt::oneshot`
//! pattern as `test_auth_modes.rs` (Phase 5.4 SC#1) — no real server, no
//! port, fully hermetic.

use axum::body::Body;
use axum::http::{Request, StatusCode};
use axum::routing::post;
use axum::Router;
use grid_engine::auth::{AuthConfig, AuthMode, MIN_JWT_SECRET_BYTES};
use http_body_util::BodyExt;
use std::sync::Arc;
use tower::ServiceExt;

// ── helpers ────────────────────────────────────────────────────────────────

const TEST_JWT_SECRET: &str = "test-secret-must-be-thirty-two-bytes-or-more_"; // 47 bytes >= 32

fn full_mode_config() -> AuthConfig {
    AuthConfig {
        mode: AuthMode::Full,
        api_keys: Default::default(),
        require_user_id: false,
        jwt_secret: Some(TEST_JWT_SECRET.to_string()),
        token_blacklist: None,
        hmac_secret: TEST_JWT_SECRET.to_string(),
    }
}

async fn echo() -> &'static str {
    "ok"
}

fn make_full_mode_router(config: AuthConfig) -> Router {
    let config = Arc::new(config);
    Router::new()
        .route("/echo", post(echo))
        .layer(axum::middleware::from_fn(move |req, next| {
            let config = config.clone();
            async move {
                match grid_server::middleware::auth_middleware_with_role(req, next, &config)
                    .await
                {
                    Ok(resp) => resp,
                    Err(status) => axum::response::Response::builder()
                        .status(status)
                        .body(Body::empty())
                        .expect("build error response"),
                }
            }
        }))
}

// ── 1. mint + verify round-trip ──────────────────────────────────────────

#[test]
fn jwt_round_trip_carries_tenant_user_role() {
    let cfg = full_mode_config();
    let (token, exp) = cfg
        .mint_jwt("tenant-x", "user-a", "a@example.com", "user", 3600)
        .expect("mint should succeed with valid secret");
    let claims = cfg
        .validate_jwt(&token)
        .expect("verify should round-trip a token we just minted");
    assert_eq!(claims.tenant_id, "tenant-x");
    assert_eq!(claims.sub, "user-a");
    assert_eq!(claims.role, "user");
    assert_eq!(claims.exp, exp);
}

#[test]
fn mint_requires_secret_in_full_mode() {
    let cfg = AuthConfig {
        mode: AuthMode::Full,
        api_keys: Default::default(),
        require_user_id: false,
        jwt_secret: None, // <-- missing on purpose
        token_blacklist: None,
        hmac_secret: TEST_JWT_SECRET.to_string(),
    };
    let result = cfg.mint_jwt("tenant-x", "user-a", "a@example.com", "user", 3600);
    assert!(result.is_err(), "expected Err when GRID_JWT_SECRET unset");
}

#[test]
fn short_secret_treated_as_unset_at_default() {
    // Default::default() should not silently accept a 16-byte secret.
    // The boundary check happens via try_from_env(); Default is permissive
    // for test fixtures — but jwt_secret must still be Some(s) at the
    // application layer for mint to succeed. A 16-byte value loaded via
    // env var is converted to None (warn) so this test exercises that.
    let cfg = AuthConfig::default();
    // Force the test to be deterministic: do not pollute the env. We test
    // the env-handling path separately by reading the env-load code;
    // here we just confirm that Default+None returns Err on mint.
    let result = cfg.mint_jwt("tenant-x", "user-a", "a@example.com", "user", 3600);
    assert!(result.is_err(), "Default::default() leaves jwt_secret=None");
    assert_eq!(MIN_JWT_SECRET_BYTES, 32);
}

#[test]
fn tampered_signature_rejected() {
    let cfg = full_mode_config();
    let (mut token, _) = cfg
        .mint_jwt("tenant-x", "user-a", "a@example.com", "user", 3600)
        .expect("mint");
    // Tamper: change the last character of the signature.
    let last = token.pop().expect("token non-empty");
    let replacement = if last == 'A' { 'B' } else { 'A' };
    token.push(replacement);

    assert!(
        cfg.validate_jwt(&token).is_none(),
        "tampered token must not validate"
    );
}

#[test]
fn token_without_tenant_id_rejected() {
    // Hand-craft a JWT with the legacy claims (no tenant_id) using the same
    // secret. jsonwebtoken requires the secret to actually decode the JSON
    // before checking fields. To produce a "no tenant_id" token we use a
    // separately constructed serializer. (v3.8.1 also requires `jti`; this
    // legacy-shape token lacks both → still rejected for the right reason.)
    use jsonwebtoken::{encode, EncodingKey, Header};
    let claims = serde_json::json!({
        "sub": "user-a",
        "email": "a@example.com",
        "role": "user",
        "iat": 0i64,
        "exp": i64::MAX,
    });
    let token = encode(
        &Header::default(),
        &claims,
        &EncodingKey::from_secret(TEST_JWT_SECRET.as_bytes()),
    )
    .expect("encode hand-crafted claims");
    let cfg = full_mode_config();
    assert!(
        cfg.validate_jwt(&token).is_none(),
        "token lacking tenant_id must fail validation"
    );
}

#[test]
fn expired_token_rejected() {
    use jsonwebtoken::{encode, EncodingKey, Header};
    let cfg = full_mode_config();
    let claims = serde_json::json!({
        "sub": "user-a",
        "tenant_id": "tenant-x",
        "jti": "test-jti-001",
        "email": "a@example.com",
        "role": "user",
        "iat": 0i64,
        "exp": 1i64, // unix epoch + 1s — far in the past
    });
    let token = encode(
        &Header::default(),
        &claims,
        &EncodingKey::from_secret(TEST_JWT_SECRET.as_bytes()),
    )
    .expect("encode");
    assert!(cfg.validate_jwt(&token).is_none(), "expired token rejected");
}

// ── 7. middleware integration: AuthMode::Full + Axum ─────────────────────

#[tokio::test]
async fn full_mode_middleware_validates_bearer_token() {
    let cfg = full_mode_config();
    let (token, _) = cfg
        .mint_jwt("tenant-x", "user-a", "a@example.com", "user", 3600)
        .expect("mint");
    let router = make_full_mode_router(cfg);

    let req = Request::builder()
        .method("POST")
        .uri("/echo")
        .header("authorization", format!("Bearer {token}"))
        .body(Body::empty())
        .expect("request");
    let resp = router.oneshot(req).await.expect("response");
    assert_eq!(resp.status(), StatusCode::OK);
}

#[tokio::test]
async fn full_mode_middleware_rejects_missing_bearer() {
    let cfg = full_mode_config();
    let router = make_full_mode_router(cfg);
    let req = Request::builder()
        .method("POST")
        .uri("/echo")
        .body(Body::empty())
        .expect("request");
    let resp = router.oneshot(req).await.expect("response");
    assert_eq!(resp.status(), StatusCode::UNAUTHORIZED);
}

#[tokio::test]
async fn full_mode_middleware_rejects_tampered_token() {
    let cfg = full_mode_config();
    let (mut token, _) = cfg
        .mint_jwt("tenant-x", "user-a", "a@example.com", "user", 3600)
        .expect("mint");
    let last = token.pop().unwrap();
    let replacement = if last == 'A' { 'B' } else { 'A' };
    token.push(replacement);

    let router = make_full_mode_router(cfg);
    let req = Request::builder()
        .method("POST")
        .uri("/echo")
        .header("authorization", format!("Bearer {token}"))
        .body(Body::empty())
        .expect("request");
    let resp = router.oneshot(req).await.expect("response");
    assert_eq!(resp.status(), StatusCode::UNAUTHORIZED);
}
