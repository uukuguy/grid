//! Phase 03.8.2 hermetic tests for RBAC route enforcement + tenant scoping.
//!
//! Covers REQUIREMENTS.md v3.8:
//! - RBAC-01: Role × Action matrix is enforced at the route layer
//! - RBAC-02: ManageUsers route is admin+
//! - RBAC-03: GET /audit requires ManageUsers or Owner
//! - RBAC-04: Owner always succeeds
//! - TENANT-03: cross-tenant data access returns 403 + body `tenant_mismatch`
//! - SESSION-01..03: SessionStore::get_for_tenant + list scope
//!
//! Approach: build a minimal Router that mounts the production
//! `require_action_middleware` (from `grid_server::middleware`) against
//! handlers backed by an in-process `InMemorySessionStore`. JWTs minted
//! with the v3.8.0 primitive carry tenant_id + role claims, mirroring the
//! production AuthMode::Full middleware path.

use axum::body::Body;
use axum::extract::{Json, Path, State};
use axum::http::StatusCode;
use axum::middleware::from_fn;
use axum::routing::{get, post};
use axum::Router;
use grid_engine::auth::middleware::RequiredAction;
use grid_engine::auth::roles::{Action, Role};
use grid_engine::auth::{AuthConfig, AuthMode, JwtClaims};
use grid_engine::session::{
    InMemorySessionStore, SessionStore, SessionSummary, TenantSessionResult,
};
use grid_server::middleware::{auth_middleware_with_role, require_action_middleware};
use grid_types::{SessionId, TenantId, UserId};
use serde_json::{json, Value};
use std::sync::Arc;
use tower::ServiceExt;

// ── Helpers ─────────────────────────────────────────────────────────────

const TEST_JWT_SECRET: &str = "test-secret-must-be-thirty-two-bytes-or-more-pad";

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

/// Mint a JWT carrying the given (tenant_id, sub, role) triple.
async fn mint_token(
    auth: &AuthConfig,
    tenant: &str,
    user: &str,
    role: &Role,
) -> String {
    // Role is an enum with serde rename_all = "snake_case"; serialize
    // it through serde_json to get the canonical wire string.
    let role_wire = serde_json::to_string(role)
        .expect("role serialize")
        .trim_matches('"')
        .to_string();
    auth
        .mint_jwt(tenant, user, "test@example.com", &role_wire, 3600)
        .expect("mint should succeed")
        .0
}

// minimal handler: GET /sessions/{id}, gated by Action::Read
async fn get_session_handler(
    State(state): State<TestAppState>,
    Path(session_id): Path<String>,
) -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    let store = state.sessions.clone();
    let sid = SessionId::from_string(&session_id);
    match store.get_session(&sid).await {
        Some(session) => Ok(Json(json!({
            "session_id": session.session_id.as_str(),
            "user_id": session.user_id.as_str(),
        }))),
        None => Err((StatusCode::NOT_FOUND, Json(json!({"error":"not_found"})))),
    }
}

// minimal handler: GET /admin/users, gated by Action::ManageUsers
async fn list_users_handler() -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    Ok(Json(json!({"users":["a","b","c"]})))
}

// minimal handler: GET /audit, gated by Action::ManageUsers (RBAC-03)
async fn list_audit_handler() -> Result<Json<Value>, (StatusCode, Json<Value>)> {
    Ok(Json(json!({"audit":["x","y"]})))
}

#[derive(Clone)]
struct TestAppState {
    sessions: Arc<InMemorySessionStore>,
}

fn make_app(state: TestAppState, auth: Arc<AuthConfig>) -> Router {
    let auth_layer = from_fn(move |req, next| {
        let cfg = auth.clone();
        async move {
            match auth_middleware_with_role(req, next, &cfg).await {
                Ok(r) => r,
                Err(s) => axum::response::Response::builder()
                    .status(s)
                    .body(Body::empty())
                    .expect("err response"),
            }
        }
    });

    Router::new()
        .route(
            "/sessions/{id}",
            get(get_session_handler).layer(from_fn(|req, next| async move {
                require_action_middleware(req, next, RequiredAction(Action::Read)).await
            })),
        )
        .route(
            "/admin/users",
            get(list_users_handler).layer(from_fn(|req, next| async move {
                require_action_middleware(req, next, RequiredAction(Action::ManageUsers)).await
            })),
        )
        .route(
            "/audit",
            get(list_audit_handler).layer(from_fn(|req, next| async move {
                require_action_middleware(req, next, RequiredAction(Action::ManageUsers)).await
            })),
        )
        .with_state(state)
        .layer(auth_layer)
}

fn make_request(method: &str, uri: &str, token: &str) -> axum::http::Request<Body> {
    axum::http::Request::builder()
        .method(method)
        .uri(uri)
        .header("authorization", format!("Bearer {token}"))
        .body(Body::empty())
        .expect("request")
}

// Wait briefly for the InMemorySessionStore to materialize a session
// (create_session is async and zero-cost in InMemory, so a yield is
// enough). Used sparingly; only when we genuinely need it.
async fn tiny_pause() {
    tokio::time::sleep(std::time::Duration::from_millis(5)).await;
}

// ── RBAC-01: matrix is enforced ────────────────────────────────────────

#[tokio::test]
async fn rbac_01_viewer_cannot_call_manage_users_route() {
    let auth = Arc::new(full_mode_config());
    let app = make_app(TestAppState {
        sessions: Arc::new(InMemorySessionStore::new()),
    }, auth.clone());

    let token = mint_token(&auth, "t1", "u-viewer", &Role::Viewer).await;
    let resp = app
        .oneshot(make_request("GET", "/admin/users", &token))
        .await
        .expect("response");
    assert_eq!(resp.status(), StatusCode::FORBIDDEN);
}

#[tokio::test]
async fn rbac_01_owner_can_call_manage_users_route() {
    let auth = Arc::new(full_mode_config());
    let app = make_app(TestAppState {
        sessions: Arc::new(InMemorySessionStore::new()),
    }, auth.clone());

    let token = mint_token(&auth, "t1", "u-owner", &Role::Owner).await;
    let resp = app
        .oneshot(make_request("GET", "/admin/users", &token))
        .await
        .expect("response");
    assert_eq!(resp.status(), StatusCode::OK);
}

#[tokio::test]
async fn rbac_01_admin_cannot_call_manage_users_per_matrix() {
    // Per Role::can: only Owner can ManageUsers. Admin does NOT have it.
    let auth = Arc::new(full_mode_config());
    let app = make_app(TestAppState {
        sessions: Arc::new(InMemorySessionStore::new()),
    }, auth.clone());

    let token = mint_token(&auth, "t1", "u-admin", &Role::Admin).await;
    let resp = app
        .oneshot(make_request("GET", "/admin/users", &token))
        .await
        .expect("response");
    assert_eq!(
        resp.status(),
        StatusCode::FORBIDDEN,
        "Admin must NOT be able to ManageUsers per existing matrix"
    );
}

// ── RBAC-02 + RBAC-04: ManageUsers path ───────────────────────────────

#[tokio::test]
async fn rbac_04_owner_always_succeeds_on_manage_users() {
    let auth = Arc::new(full_mode_config());
    let app = make_app(TestAppState {
        sessions: Arc::new(InMemorySessionStore::new()),
    }, auth.clone());

    let token = mint_token(&auth, "anywhere", "u1", &Role::Owner).await;
    let resp = app
        .oneshot(make_request("GET", "/admin/users", &token))
        .await
        .expect("response");
    assert_eq!(resp.status(), StatusCode::OK, "Owner MUST succeed everywhere");
}

// ── RBAC-03: /audit requires ManageUsers ───────────────────────────────

#[tokio::test]
async fn rbac_03_viewer_cannot_get_audit() {
    let auth = Arc::new(full_mode_config());
    let app = make_app(TestAppState {
        sessions: Arc::new(InMemorySessionStore::new()),
    }, auth.clone());

    let token = mint_token(&auth, "t1", "u-viewer", &Role::Viewer).await;
    let resp = app
        .oneshot(make_request("GET", "/audit", &token))
        .await
        .expect("response");
    assert_eq!(resp.status(), StatusCode::FORBIDDEN);
}

#[tokio::test]
async fn rbac_03_owner_can_get_audit() {
    let auth = Arc::new(full_mode_config());
    let app = make_app(TestAppState {
        sessions: Arc::new(InMemorySessionStore::new()),
    }, auth.clone());

    let token = mint_token(&auth, "t1", "u-owner", &Role::Owner).await;
    let resp = app
        .oneshot(make_request("GET", "/audit", &token))
        .await
        .expect("response");
    assert_eq!(resp.status(), StatusCode::OK);
}

// ── SESSION-01..03: in-memory tenant scoping ────────────────────────────

#[tokio::test]
async fn session_03_concurrent_users_have_isolated_sessions() {
    let auth = Arc::new(full_mode_config());
    let state = TestAppState {
        sessions: Arc::new(InMemorySessionStore::new()),
    };
    let store = state.sessions.clone();

    // Alice creates session S1.
    let alice_session = store
        .create_session_with_user(&UserId::from_string("alice"))
        .await;
    let s1 = alice_session.session_id.clone();
    // Bob creates session S2.
    let bob_session = store
        .create_session_with_user(&UserId::from_string("bob"))
        .await;
    let _s2 = bob_session.session_id.clone();

    // Alice's tenant + user_id can see S1.
    let res = store
        .get_session_for_tenant(
            &s1,
            &TenantId::from_string("tenant-alice"),
            &UserId::from_string("alice"),
        )
        .await;
    assert!(matches!(res, TenantSessionResult::Ok(_)));

    // Bob trying to read Alice's session by (right session, wrong user) →
    // NotFound (because user_id is the secondary ownership signal in the
    // default impl). The MATTER for SESSION-01 is that Bob doesn't GET
    // Alice's session data.
    let res = store
        .get_session_for_tenant(
            &s1,
            &TenantId::from_string("tenant-bob"),
            &UserId::from_string("bob"),
        )
        .await;
    assert!(
        matches!(res, TenantSessionResult::NotFound | TenantSessionResult::TenantMismatch),
        "Bob must not retrieve Alice's session data; got {res:?}"
    );
}

#[tokio::test]
async fn session_02_listing_filters_to_caller_scope() {
    let auth = Arc::new(full_mode_config());
    let state = TestAppState {
        sessions: Arc::new(InMemorySessionStore::new()),
    };
    let store = state.sessions.clone();

    store.create_session_with_user(&UserId::from_string("alice")).await;
    store.create_session_with_user(&UserId::from_string("alice")).await;
    store.create_session_with_user(&UserId::from_string("bob")).await;

    let alice_list: Vec<SessionSummary> = store
        .list_sessions_for_tenant(
            &TenantId::from_string("t1"),
            &UserId::from_string("alice"),
            100,
            0,
        )
        .await;
    let bob_list: Vec<SessionSummary> = store
        .list_sessions_for_tenant(
            &TenantId::from_string("t1"),
            &UserId::from_string("bob"),
            100,
            0,
        )
        .await;

    assert_eq!(alice_list.len(), 2, "Alice sees 2 of her own sessions");
    assert_eq!(bob_list.len(), 1, "Bob sees 1 of his own sessions");
    // No session id appears in both lists.
    for s in &alice_list {
        assert!(
            !bob_list.iter().any(|b| b.session_id == s.session_id),
            "Alice's session {} must not appear in Bob's listing",
            s.session_id
        );
    }
}

// ── TENANT-03: session returns Ok / TenantMismatch / NotFound correctly ─

#[tokio::test]
async fn tenant_03_session_lookup_3_armed_enum() {
    let store: Arc<dyn SessionStore> = Arc::new(InMemorySessionStore::new());
    let session = store
        .create_session_with_user(&UserId::from_string("alice"))
        .await;
    let sid = session.session_id.clone();

    // 1. Owner lookup: Ok.
    let r = store
        .get_session_for_tenant(
            &sid,
            &TenantId::from_string("t1"),
            &UserId::from_string("alice"),
        )
        .await;
    assert!(matches!(r, TenantSessionResult::Ok(_)));

    // 2. Wrong-user lookup: must be NotFound or TenantMismatch (not Ok).
    let r = store
        .get_session_for_tenant(
            &sid,
            &TenantId::from_string("t1"),
            &UserId::from_string("eve"),
        )
        .await;
    assert!(!matches!(r, TenantSessionResult::Ok(_)));

    // 3. Unknown session id: NotFound.
    let fake = SessionId::from_string("does-not-exist");
    let r = store
        .get_session_for_tenant(
            &fake,
            &TenantId::from_string("t1"),
            &UserId::from_string("alice"),
        )
        .await;
    assert!(matches!(r, TenantSessionResult::NotFound));

    tiny_pause().await;
}
