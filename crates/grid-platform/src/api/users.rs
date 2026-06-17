//! User API handlers
//!
//! Provides CRUD operations for user management with role-based authorization.

use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    Json,
};
use serde::Deserialize;

use crate::db::{PaginatedUsersResponse, UpdateUserRequest, UserResponse, UserRole};
use crate::{ArcAppState, AuthExtractor, ErrorCode, ErrorResponse};

/// Custom error type that can return different status codes
type ApiError = (StatusCode, Json<ErrorResponse>);

fn api_error(code: ErrorCode, status: StatusCode, message: &str) -> ApiError {
    (status, Json(ErrorResponse::new(code, message)))
}

/// Query parameters for listing users
#[derive(Debug, Deserialize)]
pub struct ListUsersQuery {
    #[serde(default = "default_page")]
    page: i64,
    #[serde(default = "default_per_page")]
    per_page: i64,
}

fn default_page() -> i64 {
    1
}

fn default_per_page() -> i64 {
    20
}

/// Request to update user role
#[derive(Debug, Deserialize)]
pub struct UpdateRoleRequest {
    pub role: String,
}

/// Check if current user is admin
fn is_admin(auth: &AuthExtractor) -> bool {
    auth.role.to_lowercase() == UserRole::Admin.to_string()
}

/// List all users (admin only)
pub async fn list_users(
    State(state): State<ArcAppState>,
    auth: AuthExtractor,
    Query(query): Query<ListUsersQuery>,
) -> Result<Json<PaginatedUsersResponse>, ApiError> {
    // Admin-only endpoint
    if !is_admin(&auth) {
        return Err(api_error(ErrorCode::Authorization, StatusCode::FORBIDDEN, "Admin access required"));
    }

    let page = query.page.max(1);
    let per_page = query.per_page.clamp(1, 100);

    state
        .db
        .list_users(&auth.tenant_id, page, per_page)
        .map_err(|_e| {
            api_error(ErrorCode::Internal, StatusCode::INTERNAL_SERVER_ERROR, "Internal error")
        })
        .map(Json)
}

/// Get a specific user by ID
pub async fn get_user(
    State(state): State<ArcAppState>,
    auth: AuthExtractor,
    Path(user_id): Path<String>,
) -> Result<Json<UserResponse>, ApiError> {
    // Admin can view any user, regular users can only view themselves
    if !is_admin(&auth) && auth.user_id != user_id {
        return Err(api_error(ErrorCode::Authorization, StatusCode::FORBIDDEN, "Cannot view other users"));
    }

    let user = state.db.get_user(&auth.tenant_id, &user_id).map_err(|_e| {
        api_error(ErrorCode::Internal, StatusCode::INTERNAL_SERVER_ERROR, "Internal error")
    })?;

    match user {
        Some(u) => Ok(Json(u)),
        None => Err(api_error(ErrorCode::NotFound, StatusCode::NOT_FOUND, "User not found")),
    }
}

/// Update a user
pub async fn update_user(
    State(state): State<ArcAppState>,
    auth: AuthExtractor,
    Path(user_id): Path<String>,
    Json(req): Json<UpdateUserRequest>,
) -> Result<Json<UserResponse>, ApiError> {
    // Validate email if provided
    if let Some(ref email) = req.email {
        let email = email.trim();
        if email.is_empty() {
            return Err(api_error(ErrorCode::Validation, StatusCode::BAD_REQUEST, "Email cannot be empty"));
        }
        if !email.contains('@') {
            return Err(api_error(ErrorCode::Validation, StatusCode::BAD_REQUEST, "Invalid email format"));
        }
        if email.len() > 255 {
            return Err(api_error(ErrorCode::Validation, StatusCode::BAD_REQUEST, "Email cannot exceed 255 characters"));
        }
    }

    // Validate display_name if provided
    if let Some(ref display_name) = req.display_name {
        let display_name = display_name.trim();
        if display_name.is_empty() {
            return Err(api_error(ErrorCode::Validation, StatusCode::BAD_REQUEST, "Display name cannot be empty"));
        }
        if display_name.len() > 100 {
            return Err(api_error(ErrorCode::Validation, StatusCode::BAD_REQUEST, "Display name cannot exceed 100 characters"));
        }
    }

    // Admin can update any user, regular users can only update their own profile
    // Non-admins can only update display_name
    if !is_admin(&auth) {
        if auth.user_id != user_id {
            return Err(api_error(ErrorCode::Authorization, StatusCode::FORBIDDEN, "Cannot update other users"));
        }

        // Non-admins can only update display_name
        if req.email.is_some() || req.role.is_some() {
            return Err(api_error(ErrorCode::Authorization, StatusCode::FORBIDDEN, "Cannot update email or role"));
        }
    }

    // Validate role if provided
    if let Some(ref role) = req.role {
        let valid_role = matches!(role.to_lowercase().as_str(), "admin" | "member" | "viewer");
        if !valid_role {
            return Err(api_error(ErrorCode::Validation, StatusCode::BAD_REQUEST, "Invalid role. Must be admin, member, or viewer"));
        }
    }

    let user = state
        .db
        .update_user(&auth.tenant_id, &user_id, &req)
        .map_err(|_e| {
            api_error(ErrorCode::Internal, StatusCode::INTERNAL_SERVER_ERROR, "Internal error")
        })?;

    match user {
        Some(u) => {
            tracing::info!("User updated: {}", user_id);
            Ok(Json(u))
        }
        None => Err(api_error(ErrorCode::NotFound, StatusCode::NOT_FOUND, "User not found")),
    }
}

/// Delete a user (admin only)
pub async fn delete_user(
    State(state): State<ArcAppState>,
    auth: AuthExtractor,
    Path(user_id): Path<String>,
) -> Result<StatusCode, ApiError> {
    // Admin-only endpoint
    if !is_admin(&auth) {
        return Err(api_error(ErrorCode::Authorization, StatusCode::FORBIDDEN, "Admin access required"));
    }

    // Prevent admin from deleting themselves
    if auth.user_id == user_id {
        return Err(api_error(ErrorCode::Authorization, StatusCode::FORBIDDEN, "Cannot delete yourself"));
    }

    let deleted = state
        .db
        .delete_user(&auth.tenant_id, &user_id)
        .map_err(|_e| {
            api_error(ErrorCode::Internal, StatusCode::INTERNAL_SERVER_ERROR, "Internal error")
        })?;

    if deleted {
        tracing::info!("User deleted: {}", user_id);
        Ok(StatusCode::NO_CONTENT)
    } else {
        Err(api_error(ErrorCode::NotFound, StatusCode::NOT_FOUND, "User not found"))
    }
}

/// Update user role (admin only)
pub async fn update_user_role(
    State(state): State<ArcAppState>,
    auth: AuthExtractor,
    Path(user_id): Path<String>,
    Json(req): Json<UpdateRoleRequest>,
) -> Result<Json<UserResponse>, ApiError> {
    // Admin-only endpoint
    if !is_admin(&auth) {
        return Err(api_error(ErrorCode::Authorization, StatusCode::FORBIDDEN, "Admin access required"));
    }

    // Validate role
    let valid_role = matches!(
        req.role.to_lowercase().as_str(),
        "admin" | "member" | "viewer"
    );

    if !valid_role {
        return Err(api_error(ErrorCode::Validation, StatusCode::BAD_REQUEST, "Invalid role. Must be admin, member, or viewer"));
    }

    let update_req = UpdateUserRequest {
        email: None,
        display_name: None,
        role: Some(req.role),
    };

    let user = state
        .db
        .update_user(&auth.tenant_id, &user_id, &update_req)
        .map_err(|_e| {
            api_error(ErrorCode::Internal, StatusCode::INTERNAL_SERVER_ERROR, "Internal error")
        })?;

    match user {
        Some(u) => {
            tracing::info!("User role updated: {} -> {}", user_id, u.role);
            Ok(Json(u))
        }
        None => Err(api_error(ErrorCode::NotFound, StatusCode::NOT_FOUND, "User not found")),
    }
}
