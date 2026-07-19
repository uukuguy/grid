//! Shared helpers for Phase 3.7.1 scenario integration tests.
//!
//! Each scenario test:
//! 1. Allocates an isolated tmpdir for GRID_GLOBAL_ROOT (no ~/.grid pollution).
//! 2. Spawns the `grid` binary via CARGO_BIN_EXE_grid.
//! 3. Asserts on stdout/stderr/exit code.

#![allow(dead_code)]

// This file is included via `#[path = "common_scenarios.rs"] mod common;` from
// each scenario test file. Cargo's automatic integration test discovery also
// treats it as a standalone test target, but it has no #[test] functions.
// `cargo test --lib --tests` runs it as a no-op binary.
use std::path::PathBuf;
use std::process::Command;

pub fn grid_bin() -> Command {
    let path = env!("CARGO_BIN_EXE_grid");
    let mut cmd = Command::new(path);
    cmd.env_remove("NO_COLOR");
    cmd.env_remove("CLICOLOR");
    cmd.env_remove("CLICOLOR_FORCE");
    // Isolate from user ~/.grid:
    let tmp_root = std::env::temp_dir().join(format!(
        "grid-quickstart-test-{}-{}",
        std::process::id(),
        chrono_now_nanos()
    ));
    std::fs::create_dir_all(&tmp_root).expect("create tmp root");
    cmd.env("GRID_GLOBAL_ROOT", &tmp_root);
    cmd.env("GRID_DB_PATH", tmp_root.join("test.db"));
    cmd.env("OPENAI_NO_PROXY", "1"); // macOS Clash proxy safe
    cmd
}

pub fn isolated_tmpdir(label: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "grid-3.7.1-{}-{}-{}",
        label,
        std::process::id(),
        chrono_now_nanos()
    ));
    std::fs::create_dir_all(&dir).expect("create isolated tmpdir");
    dir
}

fn chrono_now_nanos() -> u128 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0)
}

/// Phase 3.7.1 Plan 03 S6 (REQ-AUDIT-04 hermetic test, per D-15).
/// Helper reserved for future tests that want a config-file-based spawn
/// path; the S6 test exercises StdioMcpClient directly (no JSON config).
#[allow(dead_code)]
pub struct McpServerConfigFixture {
    pub name: String,
    pub config_path: std::path::PathBuf,
    pub isolated_root: std::path::PathBuf,
}

#[allow(dead_code)]
pub fn spawn_fake_mcp_server_config(
    label: &str,
    script: &str,
) -> (String, std::path::PathBuf, McpServerConfigFixture) {
    let server_name = format!("fake-{}-{}", label, chrono_now_nanos());
    let dir = isolated_tmpdir(label);
    let config_path = dir.join("mcp.json");
    std::fs::write(
        &config_path,
        format!(
            r#"{{ "mcpServers": {{ "{}": {{ "command": "sh", "args": ["-c", {:?}], "env": {{}} }} }} }}"#,
            server_name, script,
        ),
    )
    .expect("write fake mcp config");
    (
        server_name.clone(),
        dir.clone(),
        McpServerConfigFixture {
            name: server_name,
            config_path,
            isolated_root: dir,
        },
    )
}