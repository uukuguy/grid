//! Phase 5.4 Plan 02 Task 05 — SERVER-04 audit log columns + per-key rate limit.
//!
//! Two integration tests:
//! - `test_audit_log_columns`: audit middleware writes user_id + request_id
//!   columns; verified by reading back via `AuditStorage::query`.
//! - `test_rate_limit_per_key`: burst 100 requests with the same X-API-Key
//!   against a small per-key limit, expect ≥1 429; a different key still
//!   returns 200 (per-key isolation).

use axum::body::Body;
use axum::http::{Method, Request, StatusCode};
use axum::routing::get;
use axum::Router;
use grid_engine::audit::AuditStorage;
use grid_engine::auth::middleware::UserContext;
use grid_engine::auth::{AuthConfig, AuthMode, Permission};
use grid_server::middleware::{
    audit_middleware, auth_middleware_with_role, AuditMiddlewareState, RateLimiter,
};
use std::sync::Arc;
use tower::ServiceExt;

// ── audit middleware test ──────────────────────────────────────────────────

#[tokio::test]
async fn test_audit_log_columns() {
    // 1. Set up a temp SQLite that the audit middleware will write into.
    let tmp = tempfile::tempdir().expect("create tempdir");
    let db_path = tmp.path().join("audit.db");

    // Initialise the audit_logs schema by running the full migration pipeline
    // — the audit_logs table is created at migration v6, so we need migrate()
    // rather than just `AuditStorage::new` (which only opens the connection).
    {
        let conn = rusqlite::Connection::open(&db_path).expect("open db for migrate");
        grid_engine::db::migrate(&conn).expect("run migrations");
    }

    let audit_state = AuditMiddlewareState::new(db_path.clone());

    // 2. Build an Axum router: auth middleware → audit middleware → ping.
    let auth_config = Arc::new({
        let mut c = AuthConfig {
            mode: AuthMode::ApiKey,
            api_keys: Default::default(),
            require_user_id: false,
            jwt_secret: None,
            token_blacklist: None,
            hmac_secret: "audit-test-secret".to_string(),
        };
        c.add_api_key(
            "valid-key",
            Some("audit-user".to_string()),
            vec![Permission::Read],
        );
        c
    });

    let auth_layer = {
        let cfg = auth_config.clone();
        axum::middleware::from_fn(move |req, next| {
            let cfg = cfg.clone();
            async move {
                match auth_middleware_with_role(req, next, &cfg).await {
                    Ok(resp) => resp,
                    Err(s) => axum::response::Response::builder()
                        .status(s)
                        .body(Body::empty())
                        .expect("build error resp"),
                }
            }
        })
    };

    let router: Router = Router::new()
        .route("/ping", get(|| async { "pong" }))
        .layer(axum::middleware::from_fn_with_state(
            audit_state,
            audit_middleware,
        ))
        .layer(auth_layer);

    // 3. Send an authenticated request with an explicit X-Request-Id so the
    //    audit row has a known value to assert against.
    let req = Request::builder()
        .method(Method::GET)
        .uri("/ping")
        .header("x-api-key", "valid-key")
        .header("x-request-id", "test-req-abc")
        .body(Body::empty())
        .expect("build request");

    let resp = router.oneshot(req).await.expect("oneshot");
    assert_eq!(resp.status(), StatusCode::OK);

    // 4. The audit write is spawned on tokio — give it a brief moment to land.
    for _ in 0..50 {
        let storage = AuditStorage::new(&db_path).expect("open storage");
        let rows = storage.query(None, None, 10, 0).expect("query rows");
        if rows
            .iter()
            .any(|r| r.user_id.as_deref() == Some("audit-user"))
        {
            // Assert per-row contract: user_id populated, metadata JSON
            // contains request_id == "test-req-abc".
            let r = rows
                .iter()
                .find(|r| r.user_id.as_deref() == Some("audit-user"))
                .unwrap();
            assert_eq!(r.user_id.as_deref(), Some("audit-user"));
            let metadata_str = r
                .metadata
                .as_deref()
                .expect("metadata column populated");
            let metadata: serde_json::Value =
                serde_json::from_str(metadata_str).expect("metadata is valid JSON");
            assert_eq!(metadata["request_id"], "test-req-abc");
            return;
        }
        tokio::time::sleep(std::time::Duration::from_millis(20)).await;
    }
    panic!("audit row with user_id=audit-user was never written");
}

// ── per-key rate limit test ────────────────────────────────────────────────

/// Build a router that wires only the rate-limit middleware around a single
/// endpoint, keyed off the `X-API-Key` header (falling back to the literal
/// "anonymous" — distinct from the IP fallback in production because tests
/// don't set ConnectInfo).
fn rate_limited_router(limiter: RateLimiter) -> Router {
    use axum::response::IntoResponse;
    let rl_layer = axum::middleware::from_fn(move |req: Request<Body>, next: axum::middleware::Next| {
        let limiter = limiter.clone();
        async move {
            let key = req
                .headers()
                .get("x-api-key")
                .and_then(|v| v.to_str().ok())
                .map(str::to_owned)
                .unwrap_or_else(|| "anonymous".to_string());
            if !limiter.check(&key).await {
                return (
                    StatusCode::TOO_MANY_REQUESTS,
                    [("retry-after", "1")],
                    "Rate limit exceeded.",
                )
                    .into_response();
            }
            next.run(req).await
        }
    });

    Router::new()
        .route("/ping", get(|| async { "pong" }))
        .layer(rl_layer)
}

#[tokio::test]
async fn test_rate_limit_per_key() {
    // 50 requests per 1-second window — burst of 100 should overshoot.
    let limiter = RateLimiter::new(50, 1);
    let router = rate_limited_router(limiter);

    let mut saw_429 = false;
    for _ in 0..100 {
        let req = Request::builder()
            .method(Method::GET)
            .uri("/ping")
            .header("x-api-key", "client-A")
            .body(Body::empty())
            .expect("build req");
        let resp = router.clone().oneshot(req).await.expect("oneshot");
        if resp.status() == StatusCode::TOO_MANY_REQUESTS {
            saw_429 = true;
            break;
        }
    }
    assert!(saw_429, "rate limit never triggered after 100 same-key bursts");

    // Different key — uses a fresh per-key counter, must NOT be limited.
    let req = Request::builder()
        .method(Method::GET)
        .uri("/ping")
        .header("x-api-key", "client-B")
        .body(Body::empty())
        .expect("build req");
    let resp = router.oneshot(req).await.expect("oneshot");
    assert_eq!(
        resp.status(),
        StatusCode::OK,
        "different X-API-Key should NOT inherit client-A's saturation"
    );
}

/// Unused import guard so the dev-deps stay tidy if a CI tool prunes.
#[allow(dead_code)]
fn _ensure_uc_link() -> UserContext {
    UserContext::anonymous()
}
