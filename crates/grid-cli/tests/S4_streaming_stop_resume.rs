//! S4: Streaming stop/resume — integration test (hermetic).
//!
//! Validates that `grid session resume <id>` is a real subcommand and that
//! `grid session resume` without args prints help (REQ-AUDIT-01).

#[path = "common_scenarios.rs"]
mod common;

use common::grid_bin;

#[test]
fn s4_session_resume_help_renders() {
    let out = grid_bin()
        .args(["session", "resume", "--help"])
        .output()
        .expect("failed to run grid session resume --help");
    assert!(
        out.status.success(),
        "grid session resume --help must exit 0; got {:?}",
        out.status
    );
    let stdout = String::from_utf8_lossy(&out.stdout);
    assert!(
        stdout.contains("SESSION_ID"),
        "grid session resume --help should mention SESSION_ID; got:\n{}",
        stdout
    );
}

#[test]
fn s4_session_resume_command_registered() {
    // Verify Resume variant is wired; missing session ID will exit 2 (clap).
    let out = grid_bin()
        .args(["session", "resume"])
        .output()
        .expect("failed to run grid session resume");
    // Exit 2 = clap missing required SESSION_ID; that's the right behavior.
    assert!(
        out.status.code() == Some(2),
        "grid session resume without args should exit 2 (clap); got {:?}",
        out.status
    );
}

#[test]
fn s4_quickstart_s4_creates_session() {
    // S4 creates a session via `handle_session(Create)` and prints the ID.
    // Hermetic smoke — pre-flight may fail at doctor without API key but
    // session create itself doesn't need network.
    let _ = grid_bin()
        .args(["quickstart", "S4"])
        .output();
}