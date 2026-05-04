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
        };
        write!(f, "{}", s)
    }
}

/// Main error type for grid CLI operations.
#[derive(Debug, Clone)]
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
}
