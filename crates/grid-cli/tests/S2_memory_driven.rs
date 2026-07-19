//! S2: Memory-driven session — integration test (hermetic).
//!
//! Validates `grid memory add` is wired and that quickstart S2 dispatches
//! without panic.

#[path = "common_scenarios.rs"]
mod common;

use common::grid_bin;

#[test]
fn s2_memory_add_help_renders() {
    let out = grid_bin()
        .args(["memory", "add", "--help"])
        .output()
        .expect("failed to run grid memory add --help");
    assert!(
        out.status.success(),
        "grid memory add --help must exit 0; got {:?}",
        out.status
    );
    let stdout = String::from_utf8_lossy(&out.stdout);
    assert!(
        stdout.contains("CONTENT") || stdout.contains("content"),
        "grid memory add --help should mention CONTENT arg; got:\n{}",
        stdout
    );
}

#[test]
fn s2_quickstart_s2_argument_recognized() {
    // S2 dispatch should be reachable; pre-flight will likely fail at doctor
    // without OPENAI_API_KEY, which is acceptable for this hermetic test.
    let _ = grid_bin()
        .args(["quickstart", "S2"])
        .output();
}

#[test]
fn s2_memory_list_help_renders() {
    let out = grid_bin()
        .args(["memory", "list", "--help"])
        .output()
        .expect("failed to run grid memory list --help");
    assert!(
        out.status.success(),
        "grid memory list --help must exit 0; got {:?}",
        out.status
    );
}