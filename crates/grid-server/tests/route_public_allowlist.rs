//! v3.9 H1 regressions: every `PUBLIC_ROUTE_ALLOWLIST` route is reachable
//! without credentials regardless of `AuthMode::None/ApiKey/Full`.
//!
//! These tests guard against the regression where the auth middleware
//! hardcoded only `/api/health` as a bypass — leaving `/api/health/live`
//! and `POST /api/v1/auth/login` blocked in `AuthMode::ApiKey`. The
//! production fix unifies the bypass with the static catalog's
//! `PUBLIC_ROUTE_ALLOWLIST` so the runtime and the static auditor
//! share a single source of truth for "this route is public".

use axum::body::Body;
use axum::http::{Request, StatusCode};
use axum::routing::post;
use axum::Router;
use grid_engine::auth::{AuthConfig, AuthMode};
use grid_server::middleware::auth_middleware_with_role;
use grid_server::rbac::catalog::PUBLIC_ROUTE_ALLOWLIST;
use http_body_util::BodyExt;
use std::sync::Arc;
use tower::ServiceExt;

const TEST_JWT_SECRET: &str = "test-secret-must-be-thirty-two-bytes-or-more_";
const API_KEY_VALUE: &str = "valid-key";

/// Build an `AuthConfig` for `mode`. For `ApiKey` and `Full`, seed a key or
/// JWT secret so the not-public routes have a meaningful error, but the
/// public allowlist endpoints should still bypass regardless.
fn auth_config_for(mode: AuthMode) -> AuthConfig {
    let mut cfg = AuthConfig {
        mode,
        api_keys: Default::default(),
        require_user_id: false,
        jwt_secret: None,
        token_blacklist: None,
        hmac_secret: TEST_JWT_SECRET.to_string(),
    };
    match mode {
        AuthMode::ApiKey => {
            cfg.add_api_key(
                API_KEY_VALUE,
                Some("test-user".to_string()),
                vec![grid_engine::auth::Permission::Read],
            );
        }
        AuthMode::Full => {
            cfg.jwt_secret = Some(TEST_JWT_SECRET.to_string());
        }
        AuthMode::None => {}
    }
    cfg
}

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

    // Public allowlist paths
    Router::new()
        .route("/api/health", axum::routing::get(echo_ok))
        .route("/api/health/live", axum::routing::get(echo_ok))
        .route("/api/v1/auth/login", post(echo_ok))
        // A non-public route, used to prove the public bypass isn't
        // over-broad: this route MUST require credentials.
        .route("/api/v1/private", axum::routing::get(echo_ok))
        .layer(auth_layer)
}

async fn echo_ok() -> &'static str {
    "ok"
}

async fn send(router: Router, request: Request<Body>) -> (StatusCode, Vec<u8>) {
    let resp = router.oneshot(request).await.expect("router oneshot");
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

/// Drive every public allowlist entry through every `AuthMode` and verify
/// the request returns 200 without credentials. This is the regression
/// guard for H1 (public-bypass unification).
#[tokio::test]
async fn public_allowlist_bypasses_auth_in_every_mode() {
    let catalog = grid_server::rbac::catalog::route_catalog();
    for (method, path) in PUBLIC_ROUTE_ALLOWLIST.iter() {
        for mode in [AuthMode::None, AuthMode::ApiKey, AuthMode::Full] {
            let router = make_router(auth_config_for(mode));
            let request: Request<Body> = if *method == "POST" {
                Request::builder()
                    .method(*method)
                    .uri(*path)
                    .header("content-type", "application/json")
                    .body(Body::from(b"{}".to_vec()))
                    .expect("build request with body")
            } else {
                Request::builder()
                    .method(*method)
                    .uri(*path)
                    .body(Body::empty())
                    .expect("build request")
            };
            let (status, body) = send(router, request).await;
            assert_eq!(
                status,
                StatusCode::OK,
                "public route {method} {path} unexpectedly returned {status} in {mode:?}; body: {:?}",
                String::from_utf8_lossy(&body)
            );
            // Sanity: the entry is also present in the catalog as Public.
            assert!(
                catalog.iter().any(|entry| entry.method == *method
                    && entry.path == *path
                    && matches!(entry.route_kind, grid_server::rbac::catalog::RouteKind::Public)),
                "allowlist entry missing from catalog: {method} {path}"
            );
        }
    }
}

/// Negative companion: a non-public route is NOT bypassing auth — without
/// credentials in `AuthMode::ApiKey` it must be 401. This guards against an
/// over-eager bypass that treats every None as Public.
#[tokio::test]
async fn non_public_route_still_requires_credentials_in_apikey() {
    let router = make_router(auth_config_for(AuthMode::ApiKey));
    let request = Request::builder()
        .method("GET")
        .uri("/api/v1/private")
        .body(Body::empty())
        .expect("build request");
    let (status, _body) = send(router, request).await;
    assert_eq!(
        status,
        StatusCode::UNAUTHORIZED,
        "non-public route must require API key in AuthMode::ApiKey"
    );
}

/// Negative companion: `AuthMode::Full` with a missing JWT must still be
/// 401 on a non-public route — even though the allowlist routes are open.
#[tokio::test]
async fn non_public_route_still_requires_credentials_in_full() {
    let router = make_router(auth_config_for(AuthMode::Full));
    let request = Request::builder()
        .method("GET")
        .uri("/api/v1/private")
        .body(Body::empty())
        .expect("build request");
    let (status, _body) = send(router, request).await;
    assert_eq!(
        status,
        StatusCode::UNAUTHORIZED,
        "non-public route must require a JWT in AuthMode::Full"
    );
}

/// Regression: the production JWT "member" string (pre-v3.9 vestige) used
/// to map to `Role::User` because of a legacy alias. v3.9 canonical role
/// strings are `"viewer"|"user"|"admin"|"owner"`; `UserStore` mints
/// `"user"`. A JWT carrying `role=user` must map to `Role::User`.
#[test]
fn jwt_role_user_string_maps_to_role_user() {
    use grid_engine::auth::{AuthConfig, AuthMode};
    let cfg = AuthConfig {
        mode: AuthMode::Full,
        api_keys: Default::default(),
        require_user_id: false,
        jwt_secret: Some(TEST_JWT_SECRET.to_string()),
        token_blacklist: None,
        hmac_secret: TEST_JWT_SECRET.to_string(),
    };
    let (token, _exp) = cfg
        .mint_jwt("tenant-1", "user-1", "u@example.com", "user", 3600)
        .expect("mint user JWT");
    let claims = cfg.validate_jwt(&token).expect("validate_jwt");
    assert_eq!(claims.role, "user");
    assert!(grid_engine::auth::roles::Role::parse(&claims.role)
        == Some(grid_engine::auth::roles::Role::User));
}
