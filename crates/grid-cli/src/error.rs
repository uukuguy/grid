//! Error types and exit codes for the grid CLI.
//!
//! Exit code convention:
//! - 0: Success
//! - 1: General error
//! - 2: Invalid argument / subcommand / flag
//! - 3: Authentication failure
//! - 4: Session not found
//! - 5: Network/API error
//! - 6: Rate limited
//! - 7: Storage error

use serde::Serialize;
use serde_json::json;
use std::fmt;

/// Exit codes for the grid CLI.
/// These map to standard Unix exit code conventions.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ExitCode {
    /// 0: Success
    Ok = 0,
    /// 1: General error
    General = 1,
    /// 2: Invalid argument / subcommand / flag
    InvalidArg = 2,
    /// 3: Authentication failure
    AuthFailed = 3,
    /// 4: Session not found
    SessionNotFound = 4,
    /// 5: Network/API error
    NetworkError = 5,
    /// 6: Rate limited
    RateLimited = 6,
    /// 7: Storage error
    StorageError = 7,
    /// 73: Sync error (proto file mismatch, sync failures)
    SyncError = 73,
}

impl From<ExitCode> for i32 {
    fn from(code: ExitCode) -> Self {
        code as i32
    }
}

impl From<ExitCode> for std::process::ExitCode {
    fn from(code: ExitCode) -> Self {
        std::process::ExitCode::from(code as u8)
    }
}

impl fmt::Display for ExitCode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let s = match self {
            ExitCode::Ok => "0",
            ExitCode::General => "1",
            ExitCode::InvalidArg => "2",
            ExitCode::AuthFailed => "3",
            ExitCode::SessionNotFound => "4",
            ExitCode::NetworkError => "5",
            ExitCode::RateLimited => "6",
            ExitCode::StorageError => "7",
            ExitCode::SyncError => "73",
        };
        write!(f, "{}", s)
    }
}

/// Main error type for grid CLI operations.
#[derive(Debug, Clone, Serialize)]
pub enum GridError {
    /// Authentication failed
    AuthFailed(String),
    /// Session not found
    SessionNotFound(String),
    /// Network/API error
    NetworkError(String),
    /// Rate limited
    RateLimited(String),
    /// Storage error
    StorageError(String),
    /// Sync error (proto file mismatch)
    SyncError(String),
    /// Generic error with message
    Other(String),
}

impl fmt::Display for GridError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            GridError::AuthFailed(msg) => write!(f, "Authentication failed: {}", msg),
            GridError::SessionNotFound(id) => write!(f, "Session not found: {}", id),
            GridError::NetworkError(msg) => write!(f, "Network error: {}", msg),
            GridError::RateLimited(msg) => write!(f, "Rate limited: {}", msg),
            GridError::StorageError(msg) => write!(f, "Storage error: {}", msg),
            GridError::SyncError(msg) => write!(f, "Sync error: {}", msg),
            GridError::Other(msg) => write!(f, "{}", msg),
        }
    }
}

impl std::error::Error for GridError {}

impl From<GridError> for ExitCode {
    fn from(err: GridError) -> Self {
        match err {
            GridError::AuthFailed(_) => ExitCode::AuthFailed,
            GridError::SessionNotFound(_) => ExitCode::SessionNotFound,
            GridError::NetworkError(_) => ExitCode::NetworkError,
            GridError::RateLimited(_) => ExitCode::RateLimited,
            GridError::StorageError(_) => ExitCode::StorageError,
            GridError::SyncError(_) => ExitCode::SyncError,
            GridError::Other(_) => ExitCode::General,
        }
    }
}

impl GridError {
    /// Create an authentication error
    pub fn auth_failed(msg: impl Into<String>) -> Self {
        GridError::AuthFailed(msg.into())
    }

    /// Create a session not found error
    pub fn session_not_found(id: impl Into<String>) -> Self {
        GridError::SessionNotFound(id.into())
    }

    /// Create a network error
    pub fn network_error(msg: impl Into<String>) -> Self {
        GridError::NetworkError(msg.into())
    }

    /// Create a rate limited error
    pub fn rate_limited(msg: impl Into<String>) -> Self {
        GridError::RateLimited(msg.into())
    }

    /// Create a storage error
    pub fn storage_error(msg: impl Into<String>) -> Self {
        GridError::StorageError(msg.into())
    }

    /// Create a generic error
    pub fn other(msg: impl Into<String>) -> Self {
        GridError::Other(msg.into())
    }

    /// Per D-06: classify this error for retryable/permanent distinction.
    /// Network / quota / transient errors are retryable; config / permission /
    /// hook-reject errors are permanent.
    pub fn classify(&self) -> ErrorClass {
        match self {
            GridError::NetworkError(_) | GridError::RateLimited(_) | GridError::SyncError(_) => {
                ErrorClass::Retryable
            }
            GridError::AuthFailed(_)
            | GridError::SessionNotFound(_)
            | GridError::StorageError(_)
            | GridError::Other(_) => ErrorClass::Permanent,
        }
    }

    /// Convenience: is this error retryable?
    pub fn is_retryable(&self) -> bool {
        matches!(self.classify(), ErrorClass::Retryable)
    }

    /// Per D-05: human-readable fix hint. Empty string means "no specific fix".
    pub fn fix_hint(&self) -> &'static str {
        match self {
            GridError::AuthFailed(_) => "grid auth login (set OPENAI_API_KEY or ANTHROPIC_API_KEY)",
            GridError::SessionNotFound(_) => {
                "grid session list (then resume a valid session id)"
            }
            GridError::NetworkError(_) => "grid doctor --repair",
            GridError::RateLimited(_) => "wait, or grid quickstart --retry",
            GridError::StorageError(_) => "grid doctor --repair",
            GridError::SyncError(_) => "grid doctor --repair",
            GridError::Other(_) => "",
        }
    }

    /// Per D-07: machine-parseable JSON serialization for non-TTY stderr.
    /// Returns `{"class": "...", "message": "...", "fix": "...", "code": <i32>}`.
    pub fn to_json(&self) -> serde_json::Value {
        let class = match self.classify() {
            ErrorClass::Retryable => "retryable",
            ErrorClass::Permanent => "permanent",
        };
        let code: i32 = ExitCode::from(self.clone()).into();
        json!({
            "class": class,
            "message": self.to_string(),
            "fix": self.fix_hint(),
            "code": code,
        })
    }
}

/// Per D-06: classify errors for retryable/permanent distinction.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub enum ErrorClass {
    /// network / quota / transient — use --retry
    Retryable,
    /// config / permission / hook reject — use --repair
    Permanent,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_exit_code_conversion() {
        assert_eq!(i32::from(ExitCode::Ok), 0);
        assert_eq!(i32::from(ExitCode::AuthFailed), 3);
        assert_eq!(i32::from(ExitCode::SessionNotFound), 4);
    }

    #[test]
    fn test_exit_code_display() {
        assert_eq!(ExitCode::Ok.to_string(), "0");
        assert_eq!(ExitCode::AuthFailed.to_string(), "3");
        assert_eq!(ExitCode::SessionNotFound.to_string(), "4");
    }

    #[test]
    fn test_error_display() {
        assert_eq!(
            GridError::auth_failed("bad key").to_string(),
            "Authentication failed: bad key"
        );
        assert_eq!(
            GridError::session_not_found("sess123").to_string(),
            "Session not found: sess123"
        );
    }

    #[test]
    fn test_error_to_exit_code() {
        let err: ExitCode = GridError::AuthFailed("test".into()).into();
        assert_eq!(err, ExitCode::AuthFailed);

        let err: ExitCode = GridError::SessionNotFound("test".into()).into();
        assert_eq!(err, ExitCode::SessionNotFound);
    }

    #[test]
    fn test_error_classify_retryable() {
        assert_eq!(
            GridError::network_error("timeout").classify(),
            ErrorClass::Retryable
        );
        assert_eq!(
            GridError::rate_limited("429").classify(),
            ErrorClass::Retryable
        );
        assert_eq!(
            GridError::SyncError("proto mismatch".to_string()).classify(),
            ErrorClass::Retryable
        );
        assert!(GridError::network_error("").is_retryable());
    }

    #[test]
    fn test_error_classify_permanent() {
        assert_eq!(
            GridError::auth_failed("bad key").classify(),
            ErrorClass::Permanent
        );
        assert_eq!(
            GridError::session_not_found("s1").classify(),
            ErrorClass::Permanent
        );
        assert_eq!(
            GridError::storage_error("disk full").classify(),
            ErrorClass::Permanent
        );
        assert_eq!(
            GridError::other("oops").classify(),
            ErrorClass::Permanent
        );
    }

    #[test]
    fn test_error_to_json_shape() {
        let j = GridError::network_error("timeout").to_json();
        assert_eq!(j["class"], "retryable");
        assert_eq!(j["code"], 5);
        assert!(j["message"].as_str().unwrap().contains("timeout"));
        assert!(!j["fix"].as_str().unwrap().is_empty());

        let j = GridError::auth_failed("bad key").to_json();
        assert_eq!(j["class"], "permanent");
        assert_eq!(j["code"], 3);

        let j = GridError::other("misc").to_json();
        assert_eq!(j["class"], "permanent");
        assert_eq!(j["code"], 1);
        assert_eq!(j["fix"], "");
    }
}
