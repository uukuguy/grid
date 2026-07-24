use axum::{body::Body, extract::Request, http::StatusCode, middleware::Next, response::Response};
use grid_engine::auth::middleware::{RequiredAction, UserContext};
use grid_engine::auth::roles::Role;
use grid_engine::auth::{AuthConfig, AuthMode, JwtClaims, Permission};
use grid_types::{TenantId, UserId};

/// Maximum body size accepted while verifying an HMAC signature.
/// Larger payloads are rejected with 413; the limit lives here so callers
/// don't have to thread a config value through every middleware layer.
const HMAC_MAX_BODY_BYTES: usize = 10 * 1024 * 1024; // 10 MiB

/// HMAC request-signature replay window (±5 minutes per ADR-003).
const HMAC_REPLAY_WINDOW_SECS: i64 = 300;

/// 从请求中提取用户上下文
pub fn get_user_context<B>(req: &Request<B>) -> Option<UserContext> {
    req.extensions().get::<UserContext>().cloned()
}

/// Verify an HMAC-SHA256 request signature per ADR-003.
///
/// Format:
/// - `sig_hex`: lowercase hex of `HMAC-SHA256(secret, ts + "\n" + body)`
/// - `ts`: Unix timestamp (seconds) as ASCII decimal
/// - `body`: raw request body bytes
///
/// Mitigations:
/// - **Replay (T-05)**: rejects timestamps outside ±5min from server time.
/// - **Timing attack (ASVS V2.10)**: compares via
///   `subtle::ConstantTimeEq` rather than `==` on `&str`.
fn verify_hmac_signature(sig_hex: &str, ts: &str, body: &[u8], secret: &str) -> bool {
    use hmac::{Hmac, Mac};
    use sha2::Sha256;
    use subtle::ConstantTimeEq;
    type HmacSha256 = Hmac<Sha256>;

    // 1. Replay window — reject if ts is too far from server's view of now.
    let now = chrono::Utc::now().timestamp();
    let ts_parsed: i64 = match ts.parse() {
        Ok(n) => n,
        Err(_) => return false,
    };
    if (now - ts_parsed).abs() > HMAC_REPLAY_WINDOW_SECS {
        return false;
    }

    // 2. Compute expected = HMAC-SHA256(secret, ts + "\n" + body), hex-encoded.
    let mut mac = match HmacSha256::new_from_slice(secret.as_bytes()) {
        Ok(m) => m,
        Err(_) => return false,
    };
    mac.update(ts.as_bytes());
    mac.update(b"\n");
    mac.update(body);
    let expected = mac.finalize().into_bytes();
    let expected_hex = hex::encode(expected);

    // 3. Constant-time compare to defeat timing attacks (ASVS V2.10).
    sig_hex.as_bytes().ct_eq(expected_hex.as_bytes()).into()
}

/// 认证中间件 - 验证 API Key 并提取角色信息
pub async fn auth_middleware_with_role(
    req: Request<Body>,
    next: Next,
    config: &AuthConfig,
) -> Result<Response, StatusCode> {
    // Health check is always public regardless of auth mode
    if req.uri().path() == "/api/health" {
        let mut req = req;
        req.extensions_mut().insert(UserContext::anonymous());
        return Ok(next.run(req).await);
    }

    match config.mode {
        AuthMode::None => {
            let mut req = req;
            req.extensions_mut().insert(UserContext::anonymous());
            Ok(next.run(req).await)
        }
        AuthMode::ApiKey => {
            // 1. Validate X-API-Key (existing path)
            let key_owned = req
                .headers()
                .get("x-api-key")
                .and_then(|v| v.to_str().ok())
                .map(str::to_owned);

            let key = match &key_owned {
                Some(k) if config.validate_key(k) => k,
                _ => return Err(StatusCode::UNAUTHORIZED),
            };

            let user_id = config.get_user_id(key);
            let permissions = config.get_permissions(key);
            let role = config.get_role(key);

            // 2. HMAC signature — Phase 5.4 SERVER-04 / T-05 mitigation per
            //    ADR-003. Additive: if `x-grid-signature` is present, the
            //    request MUST also include `x-grid-timestamp` and the
            //    signature MUST validate against the request body.
            //    Per Q3 correction this lives INSIDE the ApiKey arm — there
            //    is NO `AuthMode::Hmac` / `AuthMode::Hybrid` variant.
            let has_signature_header = req.headers().contains_key("x-grid-signature");

            if has_signature_header {
                let sig_owned = req
                    .headers()
                    .get("x-grid-signature")
                    .and_then(|v| v.to_str().ok())
                    .map(str::to_owned)
                    .ok_or(StatusCode::UNAUTHORIZED)?;
                let ts_owned = req
                    .headers()
                    .get("x-grid-timestamp")
                    .and_then(|v| v.to_str().ok())
                    .map(str::to_owned)
                    .ok_or(StatusCode::UNAUTHORIZED)?;

                // Drain body so we can hash it, then rebuild the request
                // with the same bytes so downstream handlers still see the
                // full payload.
                let (parts, body) = req.into_parts();
                let body_bytes = axum::body::to_bytes(body, HMAC_MAX_BODY_BYTES)
                    .await
                    .map_err(|_| StatusCode::PAYLOAD_TOO_LARGE)?;

                if !verify_hmac_signature(
                    &sig_owned,
                    &ts_owned,
                    &body_bytes,
                    &config.hmac_secret,
                ) {
                    return Err(StatusCode::UNAUTHORIZED);
                }

                let mut req = Request::from_parts(parts, Body::from(body_bytes));
                req.extensions_mut()
                    .insert(UserContext::new(user_id, permissions, role));
                Ok(next.run(req).await)
            } else {
                // Vanilla ApiKey path — no signature requested.
                let mut req = req;
                req.extensions_mut()
                    .insert(UserContext::new(user_id, permissions, role));
                Ok(next.run(req).await)
            }
        }
        AuthMode::Full => {
            let auth_header = req.headers().get("authorization");
            let token = auth_header
                .and_then(|v| v.to_str().ok())
                .and_then(|v| v.strip_prefix("Bearer "));

            match token {
                Some(t) => {
                    if let Some(claims) = config.validate_jwt(t) {
                        // v3.8.1 hotfix (security review): consult the token
                        // blacklist AFTER successful validate_jwt. A blacklisted
                        // jti must be rejected even though the signature is
                        // valid — that's the whole point of logout.
                        //
                        // `None` blacklist (default in non-multi-user modes,
                        // and during tests that don't care) skips the check
                        // rather than failing closed — preserves existing behavior
                        // for callers that haven't wired a TokenBlacklist.
                        if let Some(ref bl) = config.token_blacklist {
                            if bl.is_blacklisted(&claims.jti) {
                                return Err(StatusCode::UNAUTHORIZED);
                            }
                        }

                        let (permissions, role) = match claims.role.as_str() {
                            "admin" => (vec![Permission::Admin], Some(Role::Admin)),
                            "member" => {
                                (vec![Permission::Read, Permission::Write], Some(Role::User))
                            }
                            "viewer" => (vec![Permission::Read], Some(Role::Viewer)),
                            "owner" => (vec![Permission::Admin], Some(Role::Owner)),
                            _ => (vec![], None),
                        };

                        let mut req = req;
                        // Existing UserContext continues to flatten claims for the
                        // existing API surface (no regression).
                        req.extensions_mut().insert(UserContext {
                            user_id: Some(claims.sub.clone()),
                            permissions,
                            role,
                        });
                        // v3.8: also expose full claims so handlers in 03.8.2 can
                        // read tenant_id for cross-tenant scoping. Handlers that
                        // don't need it simply don't extract this extension.
                        req.extensions_mut().insert(claims);
                        Ok(next.run(req).await)
                    } else {
                        Err(StatusCode::UNAUTHORIZED)
                    }
                }
                _ => Err(StatusCode::UNAUTHORIZED),
            }
        }
    }
}

/// RBAC 中间件: 检查是否具有执行特定动作的权限
///
/// Two enforcement paths coexist (D-08: AuthMode::None/ApiKey path is
/// preserved unchanged; only AuthMode::Full gets the new RBAC-01 path):
///
/// - **JWT path (AuthMode::Full)**: reads `Extension<JwtClaims>` (set by
///   `auth_middleware_with_role`), constructs a `TenantContext::for_multi_user`,
///   and checks `Role::can(required_action)` directly. This is the
///   canonical v3.8.2 multi-user enforcement.
///
/// - **Legacy path (AuthMode::None / ApiKey)**: falls back to
///   `UserContext::has_permission` for backward compatibility.
pub async fn require_action_middleware(
    req: Request<Body>,
    next: Next,
    required_action: RequiredAction,
) -> Result<Response, StatusCode> {
    // JWT path — preferred for AuthMode::Full.
    if let Some(claims) = req.extensions().get::<JwtClaims>().cloned() {
        let role = grid_engine::auth::roles::Role::parse(&claims.role)
            .ok_or(StatusCode::FORBIDDEN)?;
        let ctx = grid_engine::agent::TenantContext::for_multi_user(
            TenantId::from_string(claims.tenant_id),
            UserId::from_string(claims.sub),
            role,
        );
        return if ctx.can(required_action.0) {
            Ok(next.run(req).await)
        } else {
            Err(StatusCode::FORBIDDEN)
        };
    }

    // Legacy path — preserved for AuthMode::None / ApiKey (RBAC-04 unchanged).
    let user_ctx = get_user_context(&req).ok_or(StatusCode::UNAUTHORIZED)?;

    let required_permission = match required_action.0 {
        grid_engine::auth::roles::Action::Read => Some(Permission::Read),
        grid_engine::auth::roles::Action::CreateSession => Some(Permission::Write),
        grid_engine::auth::roles::Action::RunAgent => Some(Permission::Write),
        grid_engine::auth::roles::Action::ManageMcp => Some(Permission::Admin),
        grid_engine::auth::roles::Action::ManageSkills => Some(Permission::Admin),
        grid_engine::auth::roles::Action::ManageUsers => Some(Permission::Admin),
        grid_engine::auth::roles::Action::ManageConfig => Some(Permission::Admin),
    };

    if let Some(permission) = required_permission {
        if user_ctx.has_permission(&permission) {
            Ok(next.run(req).await)
        } else {
            Err(StatusCode::FORBIDDEN)
        }
    } else {
        Err(StatusCode::FORBIDDEN)
    }
}

/// RBAC 中间件: 检查是否具有最低角色权限
pub async fn require_role_middleware(
    req: Request<Body>,
    next: Next,
    required_role: grid_engine::auth::middleware::RequiredRole,
) -> Result<Response, StatusCode> {
    let user_ctx = get_user_context(&req).ok_or(StatusCode::UNAUTHORIZED)?;

    if user_ctx.has_role(required_role.0) {
        Ok(next.run(req).await)
    } else {
        Err(StatusCode::FORBIDDEN)
    }
}

/// Middleware wrapper: requires Admin role. Use with `from_fn(require_admin)`.
/// Skips check when user is anonymous (AuthMode::None).
pub async fn require_admin(
    req: Request<Body>,
    next: Next,
) -> Result<Response, StatusCode> {
    let user_ctx = req.extensions().get::<UserContext>().cloned().ok_or(StatusCode::UNAUTHORIZED)?;
    if user_ctx.user_id.is_none() && user_ctx.role.is_none() {
        return Ok(next.run(req).await);
    }
    if user_ctx.has_role(Role::Admin) || user_ctx.has_role(Role::Owner) {
        Ok(next.run(req).await)
    } else {
        Err(StatusCode::FORBIDDEN)
    }
}

/// Middleware wrapper: requires Write permission. Use with `from_fn(require_write)`.
pub async fn require_write(
    req: Request<Body>,
    next: Next,
) -> Result<Response, StatusCode> {
    let user_ctx = req.extensions().get::<UserContext>().cloned().ok_or(StatusCode::UNAUTHORIZED)?;
    if user_ctx.has_permission(&Permission::Write) || user_ctx.has_permission(&Permission::Admin) {
        Ok(next.run(req).await)
    } else {
        Err(StatusCode::FORBIDDEN)
    }
}
