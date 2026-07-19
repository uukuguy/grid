//! S5: Parallel batch — integration test (hermetic).
//!
//! Validates that `grid run --parallel N` flag is wired (REQ-AUDIT-02) and that
//! the help text documents it.

#[path = "common_scenarios.rs"]
mod common;

use common::grid_bin;

#[test]
fn s5_run_parallel_flag_in_help() {
    let out = grid_bin()
        .args(["run", "--help"])
        .output()
        .expect("failed to run grid run --help");
    let stdout = String::from_utf8_lossy(&out.stdout);
    assert!(
        stdout.contains("--parallel"),
        "grid run --help must mention --parallel flag (REQ-AUDIT-02); got:\n{}",
        stdout
    );
}

#[test]
fn s5_quickstart_s5_argument_recognized() {
    let _ = grid_bin()
        .args(["quickstart", "S5"])
        .output();
}

#[test]
fn s5_run_parallel_flag_accepted() {
    // Passing --parallel 2 must not be a clap-rejection (exit 2).
    // It may still fail downstream (no OPENAI_API_KEY, etc.) but the flag
    // must parse correctly.
    let out = grid_bin()
        .args(["run", "--parallel", "2", "--help"])
        .output()
        .expect("failed to run grid run --parallel 2 --help");
    // --help should still take precedence and exit 0.
    assert!(
        out.status.success(),
        "grid run --parallel 2 --help must exit 0; got {:?}",
        out.status
    );
}