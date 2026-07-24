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

    // SECURITY-CONTRACT (AUDIT-02 hotfix — security review):
    //
    // Every /audit request MUST be tenant-scoped, unconditionally.
    // The query path never reaches an un-scoped `count`/`query` unless
    // the caller is Owner AND the explicit `cross_tenant=true` flag is
    // set. Without cross_tenant, the Owner sees only their own tenant.
    // Non-owner callers (Viewer/User/Admin) NEVER see another tenant's
    // data regardless of the flag.
    let cross_tenant_requested = query.cross_tenant.unwrap_or(false);

    // Derive role + tenant from claims (set by AuthMode::Full
    // middleware in 03.8.0). Absence of claims = AuthMode::None/
    // ApiKey; the tenant identity is implicit and we fall back to
    // the unscoped existing path (preserved for single-user mode per
    // D-08 of the v3.8.1 plan).
    let (role, tenant_id, user_id) = match claims.as_ref() {
        Some(c) => (Some(c.role.clone()), Some(c.tenant_id.clone()), Some(c.sub.clone())),
        None => (None, None, None),
    };

    let is_owner = role.as_deref() == Some("owner");
    let allow_cross_tenant = cross_tenant_requested && is_owner;

    // SECURITY-row audit for every cross_tenant attempt (whether Owner
    // or not), so operators can detect rejected attempts via the
    // regular tenant-scoped `/audit`.
    if cross_tenant_requested {
        if let Some(audit_storage) = state.audit_storage() {
            use grid_engine::audit::AuditEvent;
            let _ = audit_storage.log(AuditEvent {
                event_type: "security".to_string(),
                user_id: user_id.clone(),
                tenant_id: tenant_id.clone(),
                role: role.clone(),
                session_id: None,
                resource_id: None,
                action: "audit.cross_tenant_query".to_string(),
                result: if is_owner { "authorized" } else { "rejected" }.to_string(),
                metadata: Some(json!({"event_type": "audit.cross_tenant_query"})),
                ip_address: None,
            });
        }
        if !is_owner {
            return Err((
                StatusCode::FORBIDDEN,
                Json(json!({"error":"forbidden","message":"cross_tenant requires owner"})),
            ));
        }
    }

    // Get audit storage on-demand.
    let Some(audit_storage) = state.audit_storage() else {
        tracing::error!("Failed to create audit storage");
        return Ok(Json(AuditResponse {
            logs: vec![],
            total: 0,
        }));
    };

    // Branch on the path. Default (any caller without cross_tenant,
    // or any caller in single-user mode) is tenant-scoped. Owner +
    // cross_tenant is the only un-scoped path.
    let (total, logs_result) = if allow_cross_tenant {
        let total = audit_storage
            .count(query.event_type.as_deref(), query.user_id.as_deref())
            .unwrap_or(0);
        let logs = audit_storage.query(
            query.event_type.as_deref(),
            query.user_id.as_deref(),
            limit,
            offset,
        );
        (total, logs)
    } else if let Some(tenant) = tenant_id.as_deref() {
        // AuthMode::Full path: tenant-scoped.
        let total = audit_storage
            .count_for_tenant(
                tenant,
                query.event_type.as_deref(),
                query.user_id.as_deref(),
            )
            .unwrap_or(0);
        let logs = audit_storage.query_for_tenant(
            tenant,
            query.event_type.as_deref(),
            query.user_id.as_deref(),
            limit,
            offset,
        );
        (total, logs)
    } else {
        // AuthMode::None / ApiKey path (D-08 single-user mode): the
        // existing un-scoped path is the only choice (there's no
        // tenant claim to scope on).
        let total = audit_storage
            .count(query.event_type.as_deref(), query.user_id.as_deref())
            .unwrap_or(0);
        let logs = audit_storage.query(
            query.event_type.as_deref(),
            query.user_id.as_deref(),
            limit,
            offset,
        );
        (total, logs)
    };

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
