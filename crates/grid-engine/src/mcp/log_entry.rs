//! Per-line log entry captured from a running MCP server's stderr.
//!
//! `McpManager` buffers a bounded ring of these per server and broadcasts
//! new entries to subscribers. Level is inferred from the line prefix
//! (best-effort heuristic; see [`LogLevel::from_line_prefix`]).

use chrono::{DateTime, Utc};
use serde::Serialize;

/// Log severity. Server output is best-effort classified by line prefix.
#[derive(Debug, Clone, Copy, Serialize, PartialEq, Eq)]
pub enum LogLevel {
    Info,
    Warn,
    Error,
}

impl LogLevel {
    /// Classify a single stderr line by its prefix. Recognises bare and
    /// bracketed forms (case-insensitive on the bracketed form).
    pub fn from_line_prefix(line: &str) -> LogLevel {
        let trimmed = line.trim_start();
        let head = trimmed
            .split_whitespace()
            .next()
            .unwrap_or("")
            .trim_end_matches(':');
        let head_upper = head.to_ascii_uppercase();
        let head_bracketed = head.trim_start_matches('[').trim_end_matches(']');
        let head_bracketed_upper = head_bracketed.to_ascii_uppercase();
        match (head_upper.as_str(), head_bracketed_upper.as_str()) {
            (h, _) if h == "ERROR" || h == "ERR" || h == "FATAL" => LogLevel::Error,
            (_, b) if b == "ERROR" || b == "ERR" => LogLevel::Error,
            (h, _) if h == "WARN" || h == "WARNING" => LogLevel::Warn,
            (_, b) if b == "WARN" || b == "WARNING" => LogLevel::Warn,
            _ => LogLevel::Info,
        }
    }
}

/// A single captured log line.
#[derive(Debug, Clone, Serialize)]
pub struct LogEntry {
    pub timestamp: DateTime<Utc>,
    pub level: LogLevel,
    pub message: String,
}

impl LogEntry {
    pub fn now(message: String) -> Self {
        Self {
            timestamp: Utc::now(),
            level: LogLevel::from_line_prefix(&message),
            message,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn level_info_default() {
        assert_eq!(LogLevel::from_line_prefix("hello world"), LogLevel::Info);
        assert_eq!(LogLevel::from_line_prefix("Server started"), LogLevel::Info);
    }

    #[test]
    fn level_error_prefixes() {
        assert_eq!(LogLevel::from_line_prefix("ERROR: bad thing"), LogLevel::Error);
        assert_eq!(LogLevel::from_line_prefix("ERR: oops"), LogLevel::Error);
        assert_eq!(LogLevel::from_line_prefix("FATAL: nope"), LogLevel::Error);
        assert_eq!(LogLevel::from_line_prefix("[error] bad"), LogLevel::Error);
    }

    #[test]
    fn level_warn_prefixes() {
        assert_eq!(LogLevel::from_line_prefix("WARN: careful"), LogLevel::Warn);
        assert_eq!(LogLevel::from_line_prefix("WARNING: hot"), LogLevel::Warn);
        assert_eq!(LogLevel::from_line_prefix("[warn] careful"), LogLevel::Warn);
    }
}
