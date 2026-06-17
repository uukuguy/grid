use axum::{
    body::Body,
    extract::Request,
    http::{Response, StatusCode},
    middleware::Next,
};
use std::sync::Arc;

use crate::AppState;

pub async fn quota_middleware(
    request: Request<Body>,
    next: Next,
) -> Response<Body> {
    let state = request.extensions().get::<Arc<AppState>>();

    if let Some(state) = state {
        // Extract tenant_id from JWT in Authorization header
        let tenant_id = request
            .headers()
            .get("Authorization")
            .and_then(|v| v.to_str().ok())
            .and_then(|v| v.strip_prefix("Bearer "))
            .and_then(|token| {
                state.jwt.verify_token(token).ok().map(|claims| claims.claims.tenant_id)
            });

        if let Some(tenant_id) = tenant_id {
            let runtime = state.tenant_manager.get_or_create_runtime(&tenant_id);
            if let Err(e) = runtime.quota_manager.consume_api_call() {
                let retry_after = 60;
                return Response::builder()
                    .status(StatusCode::TOO_MANY_REQUESTS)
                    .header("Retry-After", retry_after.to_string())
                    .body(Body::from(e.to_string()))
                    .unwrap();
            }
        }
    }

    next.run(request).await
}
