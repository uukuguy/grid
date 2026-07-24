use std::sync::Arc;

use axum::{
    extract::{Extension, Query, State},
    http::StatusCode,
    routing::get,
    Json, Router,
};
use grid_engine::auth::JwtClaims;
use serde::{Deserialize, Serialize};
use serde_json::json;

use crate::state::AppState;

#[derive(Deserialize)]
pub struct AuditQuery {
    pub event_type: Option<String>,
    pub user_id: Option<String>,
    pub limit: Option<u32>,
    pub offset: Option<u32>,
    /// v3.8.2 (AUDIT-02): when `Some(true)`, the caller asserts they have
    /// Owner privilege to query across tenants. Non-Owner callers hitting
    /// this flag receive 403, and the request itself is recorded as a
    /// SECURITY event.
    pub cross_tenant: Option<bool>,
}

#[derive(Serialize)]
pub struct AuditResponse {
    pub logs: Vec<AuditRecordResponse>,
    pub total: i64,
}

#[derive(serde::Serialize)]
pub struct AuditRecordResponse {
    pub id: i64,
    pub timestamp: String,
    pub event_type: String,
    pub user_id: Option<String>,
    pub session_id: Option<String>,
    pub resource_id: Option<String>,
    pub action: String,
    pub result: String,
    pub metadata: Option<String>,
    pub ip_address: Option<String>,
}

impl From<grid_engine::audit::AuditRecord> for AuditRecordResponse {
    fn from(record: grid_engine::audit::AuditRecord) -> Self {
        Self {
            id: record.id,
            timestamp: record.timestamp,
            event_type: record.event_type,
            user_id: record.user_id,
            session_id: record.session_id,
            resource_id: record.resource_id,
            action: record.action,
            result: record.result,
            metadata: record.metadata,
            ip_address: record.ip_address,
        }
    }
}

pub async fn list_audit(
    State(state): State<Arc<AppState>>,
    Extension(claims): Extension<Option<JwtClaims>>,
    Query(query): Query<AuditQuery>,
) -> Result<Json<AuditResponse>, (StatusCode, Json<serde_json::Value>)> {
    let limit = query.limit.unwrap_or(50).min(100);
    let offset = query.offset.unwrap_or(0);

    // v3.8.2 AUDIT-02: when cross_tenant=true, write a SECURITY audit row
    // AND require Owner privilege. Non-Owner callers receive 403; we
    // record the attempt either way.
    if query.cross_tenant.unwrap_or(false) {
        let role = claims.as_ref().map(|c| c.role.clone());
        let tenant = claims.as_ref().map(|c| c.tenant_id.clone());

        if let Some(audit_storage) = state.audit_storage() {
            use grid_engine::audit::AuditEvent;
            let _ = audit_storage.log(AuditEvent {
                event_type: "security".to_string(),
                user_id: claims.as_ref().map(|c| c.sub.clone()),
                tenant_id: tenant.clone(),
                role: role.clone(),
                session_id: None,
                resource_id: None,
                action: "audit.cross_tenant_query".to_string(),
                result: match role.as_deref() {
                    Some("owner") => "authorized",
                    _ => "rejected",
                }
                .to_string(),
                metadata: Some(json!({"event_type": "audit.cross_tenant_query"})),
                ip_address: None,
            });
        }
        if role.as_deref() != Some("owner") {
            return Err((
                StatusCode::FORBIDDEN,
                Json(json!({"error":"forbidden","message":"cross_tenant requires owner"})),
            ));
        }
    }

    // Get audit storage on-demand
    let Some(audit_storage) = state.audit_storage() else {
        tracing::error!("Failed to create audit storage");
        return Ok(Json(AuditResponse {
            logs: vec![],
            total: 0,
        }));
    };

    // Get total count first
    let total = audit_storage
        .count(query.event_type.as_deref(), query.user_id.as_deref())
        .unwrap_or(0);

    let logs_result = audit_storage.query(
        query.event_type.as_deref(),
        query.user_id.as_deref(),
        limit,
        offset,
    );

    let logs: Vec<AuditRecordResponse> = logs_result
        .map(|records| records.into_iter().map(AuditRecordResponse::from).collect())
        .unwrap_or_default();

    Ok(Json(AuditResponse { logs, total }))
}

// ── AO-T9: Audit Enhancement ─────────────────────────────────────────

/// Query params for audit export
#[derive(Deserialize)]
pub struct AuditExportQuery {
    pub since: Option<String>,
    pub until: Option<String>,
    #[serde(default = "default_export_limit")]
    pub limit: u32,
}

fn default_export_limit() -> u32 {
    10000
}

/// GET /audit/export — export audit records with date range filtering
pub async fn export_audit(
    State(state): State<Arc<AppState>>,
    Query(query): Query<AuditExportQuery>,
) -> Json<Vec<AuditRecordResponse>> {
    let Some(audit_storage) = state.audit_storage() else {
        return Json(vec![]);
    };

    let limit = query.limit.min(50000);
    let records = audit_storage
        .export(query.since.as_deref(), query.until.as_deref(), limit)
        .unwrap_or_default();

    Json(records.into_iter().map(AuditRecordResponse::from).collect())
}

/// Query params for audit cleanup
#[derive(Deserialize)]
pub struct AuditDeleteQuery {
    pub before: String,
}

/// Response for audit cleanup
#[derive(Serialize)]
pub struct AuditDeleteResponse {
    pub deleted_count: usize,
}

/// DELETE /audit — clean up old audit records
pub async fn delete_audit(
    State(state): State<Arc<AppState>>,
    Query(query): Query<AuditDeleteQuery>,
) -> Result<Json<AuditDeleteResponse>, StatusCode> {
    let Some(audit_storage) = state.audit_storage() else {
        return Err(StatusCode::SERVICE_UNAVAILABLE);
    };

    let deleted_count = audit_storage
        .delete_before(&query.before)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    Ok(Json(AuditDeleteResponse { deleted_count }))
}

/// GET /audit/stats — aggregate audit statistics
pub async fn audit_stats(
    State(state): State<Arc<AppState>>,
) -> Json<serde_json::Value> {
    let Some(audit_storage) = state.audit_storage() else {
        return Json(serde_json::json!({
            "total": 0,
            "by_event_type": {},
            "by_result": {},
        }));
    };

    match audit_storage.stats() {
        Ok(stats) => Json(serde_json::to_value(stats).unwrap_or_default()),
        Err(_) => Json(serde_json::json!({
            "total": 0,
            "by_event_type": {},
            "by_result": {},
        })),
    }
}

pub fn router() -> Router<Arc<AppState>> {
    Router::new()
        .route("/audit", get(list_audit).delete(delete_audit))
        .route("/audit/export", get(export_audit))
        .route("/audit/stats", get(audit_stats))
}
