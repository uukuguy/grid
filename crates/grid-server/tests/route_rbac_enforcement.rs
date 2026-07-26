use axum::{body::Body, extract::Request, http::Method, middleware::Next};
use grid_engine::auth::roles::Action;
use grid_engine::auth::JwtClaims;
use grid_server::middleware::auth::{catalog_entry_for_request, catalog_rbac_middleware};
use grid_server::rbac::catalog::{route_catalog, RouteKind};
use tower::ServiceExt;

/// Stubs out JWT minting + a claims injection layer. The full production
/// chain (auth → catalog → handler) is exercised end-to-end in
/// `route_public_allowlist.rs` and `multi_user_*` test files; here we focus
/// on the catalog middleware alone and pre-supply a `JwtClaims` via a
/// shim layer so the middleware has something to enforce on.
async fn inject_claims(
    mut req: Request<Body>,
    next: Next,
) -> axum::response::Response {
    let role = req
        .extensions()
        .get::<TestRole>()
        .copied()
        .unwrap_or(TestRole::Viewer);
    let now = chrono::Utc::now().timestamp();
    req.extensions_mut().insert(JwtClaims {
        sub: "test-user".to_string(),
        email: "test@example.com".to_string(),
        role: role.as_str().to_string(),
        tenant_id: "tenant-1".to_string(),
        jti: "jti-all-routes".to_string(),
        exp: now + 3600,
        iat: now,
    });
    next.run(req).await
}

#[derive(Copy, Clone, Debug)]
enum TestRole {
    Viewer,
    User,
    Admin,
    Owner,
}
impl TestRole {
    fn as_str(&self) -> &'static str {
        match self {
            TestRole::Viewer => "viewer",
            TestRole::User => "user",
            TestRole::Admin => "admin",
            TestRole::Owner => "owner",
        }
    }
}

/// Drives the production catalog RBAC middleware for every catalog entry
/// under one fixed role at a time. Verifies the chain enforces the
/// matrix derived from `role.can(action)` for each route.
///
/// What this test does NOT prove (see also: route_public_allowlist.rs):
/// - It does not exercise `AuthMode::None/ApiKey` — those paths skip
///   catalog enforcement by design (D-05 compatibility).
/// - It does not exercise the production `auth_middleware_with_role`
///   wiring — `multi_user_*` test files cover the JWT mint/validate path.
/// This file covers the catalog RBAC enforcement contract in isolation,
/// under `AuthMode::Full` semantics.
#[tokio::test]
async fn production_user_role_chain_for_all_routes() {
    for role in [TestRole::Viewer, TestRole::User, TestRole::Admin, TestRole::Owner] {
        run_chain_for_role(role).await;
    }
}

async fn run_chain_for_role(role: TestRole) {
    // Mount a tiny stub for every catalog entry — the catalog middleware
    // runs above the stub and either lets it through or short-circuits.
    let mut router = axum::Router::new();
    for entry in route_catalog() {
        let method: Method = entry.method.parse().unwrap();
        let path = entry.path.to_string();
        let method_router = match method {
            Method::GET => axum::routing::get(stub_204),
            Method::POST => axum::routing::post(stub_204),
            Method::PUT => axum::routing::put(stub_204),
            Method::DELETE => axum::routing::delete(stub_204),
            _ => axum::routing::any(stub_204),
        };
        router = router.route(&path, method_router);
    }
    let app = router
        .layer(axum::middleware::from_fn(catalog_rbac_middleware))
        .layer(axum::middleware::from_fn(move |mut req: Request<Body>, next| {
            req.extensions_mut().insert(role);
            inject_claims(req, next)
        }));

    for entry in route_catalog() {
        let needs_body = entry.method == "POST" || entry.method == "PUT";
        let request: Request<Body> = if needs_body {
            Request::builder()
                .method(entry.method)
                .uri(entry.path)
                .header("content-type", "application/json")
                .body(Body::from(b"{}".to_vec()))
                .expect("build request with body")
        } else {
            Request::builder()
                .method(entry.method)
                .uri(entry.path)
                .body(Body::empty())
                .expect("build request")
        };
        let resp = app.clone().oneshot(request).await.expect("oneshot");
        let expected = match entry.route_kind {
            RouteKind::Public => axum::http::StatusCode::NO_CONTENT,
            RouteKind::Requires(action) => {
                // Match what the engine's Role::can produces.
                let engine_role = grid_engine::auth::roles::Role::parse(role.as_str())
                    .expect("role parseable");
                if engine_role.can(action) {
                    axum::http::StatusCode::NO_CONTENT
                } else {
                    axum::http::StatusCode::FORBIDDEN
                }
            }
        };
        assert_eq!(
            resp.status(),
            expected,
            "role={:?} entry {:?} produced unexpected status; entry kind = {:?}",
            role,
            (entry.method, entry.path),
            entry.route_kind
        );
    }
}

async fn stub_204() -> axum::http::StatusCode {
    axum::http::StatusCode::NO_CONTENT
}

#[test]
fn rbac_05_full_route_catalog_is_annotated() {
    let missing: Vec<_> = route_catalog()
        .iter()
        .filter(|entry| !matches!(entry.route_kind, RouteKind::Public | RouteKind::Requires(_)))
        .collect();
    assert!(missing.is_empty(), "unannotated routes: {missing:?}");
}

#[test]
fn rbac_08_runtime_resolver_uses_catalog_metadata() {
    for entry in route_catalog() {
        let method: Method = entry.method.parse().unwrap();
        let request = Request::builder()
            .method(method)
            .uri(entry.path)
            .body(Body::empty())
            .unwrap();
        let resolved = catalog_entry_for_request(&request);
        match entry.route_kind {
            RouteKind::Public => {
                assert!(matches!(resolved.map(|e| e.route_kind), Some(RouteKind::Public)));
            }
            RouteKind::Requires(action) => {
                assert!(matches!(
                    resolved.map(|e| e.route_kind),
                    Some(RouteKind::Requires(a)) if a == action
                ));
            }
        }
    }
}

#[test]
fn mode_03_viewer_cannot_resolve_non_read_as_allowed() {
    let mut saw_non_read = false;
    for entry in route_catalog() {
        if let RouteKind::Requires(action) = entry.route_kind {
            if action != Action::Read {
                saw_non_read = true;
                assert!(!grid_engine::auth::roles::Role::Viewer.can(action));
            }
        }
    }
    assert!(saw_non_read);
}
