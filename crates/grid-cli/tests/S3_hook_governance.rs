//! S3: Hook-driven governance — integration test (hermetic).
//!
//! Validates that doctor now checks GRID_HOOKS_FILE (REQ-AUDIT-07) and that
//! quickstart S3 prints the actionable "GRID_HOOKS_FILE not set" message when
//! missing.

#[path = "common_scenarios.rs"]
mod common;

use common::grid_bin;

#[test]
fn s3_doctor_reports_hooks_file_status() {
    let out = grid_bin()
        .args(["doctor"])
        .output()
        .expect("failed to run grid doctor");
    let stdout = String::from_utf8_lossy(&out.stdout);
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(
        stdout.contains("Hooks File") || stderr.contains("Hooks File"),
        "grid doctor must include Hooks File check (REQ-AUDIT-07); got stdout:\n{}\nstderr:\n{}",
        stdout,
        stderr
    );
}

#[test]
fn s3_quickstart_without_hooks_file_prints_actionable_error() {
    // No GRID_HOOKS_FILE in test env; quickstart S3 should print actionable
    // message and exit non-zero.
    let out = grid_bin()
        .args(["quickstart", "S3"])
        .env_remove("GRID_HOOKS_FILE")
        .output()
        .expect("failed to run grid quickstart S3");
    let stderr = String::from_utf8_lossy(&out.stderr);
    let stdout = String::from_utf8_lossy(&out.stdout);
    // The S3 runner prints "GRID_HOOKS_FILE not set." and exits 1.
    // We only check that the messaging is present (exit code may vary since
    // doctor pre-flight may fail first if no OPENAI_API_KEY).
    let combined = format!("{}{}", stdout, stderr);
    assert!(
        combined.contains("GRID_HOOKS_FILE") || combined.contains("Hooks File"),
        "grid quickstart S3 must mention GRID_HOOKS_FILE; got:\n{}",
        combined
    );
}