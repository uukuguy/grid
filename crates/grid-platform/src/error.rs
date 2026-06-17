//! Structured error types for grid-platform API responses.
//!
//! Provides `ErrorCode` enum and `ErrorResponse` struct with consistent
//! error formatting across all API handlers.

use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorCode {
    Authentication,
    Authorization,
    Validation,
    NotFound,
    RateLimited,
    QuotaExceeded,
    Conflict,
    Internal,
}

impl ErrorCode {
    /// Lowercase string representation for the wire.
    pub fn as_str(&self) -> &'static str {
        match self {
            ErrorCode::Authentication => "authentication",
            ErrorCode::Authorization => "authorization",
            ErrorCode::Validation => "validation",
            ErrorCode::NotFound => "not_found",
            ErrorCode::RateLimited => "rate_limited",
            ErrorCode::QuotaExceeded => "quota_exceeded",
            ErrorCode::Conflict => "conflict",
            ErrorCode::Internal => "internal",
        }
    }

    /// Default HTTP status code for this error class.
    pub fn status(&self) -> StatusCode {
        match self {
            ErrorCode::Authentication => StatusCode::UNAUTHORIZED,
            ErrorCode::Authorization => StatusCode::FORBIDDEN,
            ErrorCode::Validation => StatusCode::BAD_REQUEST,
            ErrorCode::NotFound => StatusCode::NOT_FOUND,
            ErrorCode::RateLimited => StatusCode::TOO_MANY_REQUESTS,
            ErrorCode::QuotaExceeded => StatusCode::TOO_MANY_REQUESTS,
            ErrorCode::Conflict => StatusCode::CONFLICT,
            ErrorCode::Internal => StatusCode::INTERNAL_SERVER_ERROR,
        }
    }
}

#[derive(Debug, serde::Serialize)]
pub struct ErrorResponse {
    pub error: String,
    pub error_code: String,
}

impl ErrorResponse {
    pub fn new(code: ErrorCode, message: impl Into<String>) -> Self {
        Self {
            error: message.into(),
            error_code: code.as_str().to_string(),
        }
    }

    pub fn authentication(message: impl Into<String>) -> Self {
        Self::new(ErrorCode::Authentication, message)
    }

    pub fn authorization(message: impl Into<String>) -> Self {
        Self::new(ErrorCode::Authorization, message)
    }

    pub fn validation(message: impl Into<String>) -> Self {
        Self::new(ErrorCode::Validation, message)
    }

    pub fn not_found(message: impl Into<String>) -> Self {
        Self::new(ErrorCode::NotFound, message)
    }

    pub fn rate_limited(message: impl Into<String>) -> Self {
        Self::new(ErrorCode::RateLimited, message)
    }

    pub fn conflict(message: impl Into<String>) -> Self {
        Self::new(ErrorCode::Conflict, message)
    }

    pub fn internal(message: impl Into<String>) -> Self {
        Self::new(ErrorCode::Internal, message)
    }

    pub fn status(&self) -> StatusCode {
        ErrorCode::from(self.error_code.as_str()).status()
    }
}

impl IntoResponse for ErrorResponse {
    fn into_response(self) -> Response {
        (self.status(), Json(self)).into_response()
    }
}

impl From<&str> for ErrorCode {
    fn from(s: &str) -> Self {
        match s {
            "authentication" => ErrorCode::Authentication,
            "authorization" => ErrorCode::Authorization,
            "validation" => ErrorCode::Validation,
            "not_found" => ErrorCode::NotFound,
            "rate_limited" => ErrorCode::RateLimited,
            "quota_exceeded" => ErrorCode::QuotaExceeded,
            "conflict" => ErrorCode::Conflict,
            _ => ErrorCode::Internal,
        }
    }
}

impl From<&String> for ErrorCode {
    fn from(s: &String) -> Self {
        ErrorCode::from(s.as_str())
    }
}
