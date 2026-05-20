//! Phase 5.4 Plan 02 Task 02 — multi-process migrate() race regression
//! (NEW-A2 integration + T-02 full mitigation).
//!
//! Spawns 4 concurrent processes each running `grid-engine`'s test-only
//! `migrate-tester` binary against the same SQLite file. With the
//! BEGIN EXCLUSIVE + double-check fix landed in Task 5.4-02-01, all 4
//! processes succeed and converge on `user_version == CURRENT_VERSION`.
//!
//! Original race trace (NEW-A1 forensics 2026-05-16):
//!   "duplicate column name: user_id" — emitted when two processes both
//!   read user_version=0 before either bumps it, then both try the same
//!   ALTER TABLE.
//!
//! Note: the test binary lives in the `grid-engine` package (not this one);
//! cargo's `CARGO_BIN_EXE_<name>` env var only fires for same-package tests,
//! so we resolve the binary path via the workspace target dir at runtime.

use std::path::PathBuf;
use std::process::{Command, Stdio};

/// Locate the workspace target dir + the `migrate-tester` binary.
///
/// `CARGO_MANIFEST_DIR` is `<repo>/crates/grid-server`; the workspace target
/// dir is `<repo>/target`. Profile defaults to `debug` unless cargo set
/// `PROFILE=release` (which it does when `cargo test --release` runs).
fn resolve_migrate_tester() -> PathBuf {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let workspace_root = manifest_dir
        .parent()
        .and_then(|p| p.parent())
        .expect("workspace root from CARGO_MANIFEST_DIR")
        .to_path_buf();

    // Cargo sets PROFILE=debug or release for test targets; fall back to debug.
    let profile = std::env::var("PROFILE").unwrap_or_else(|_| "debug".to_string());

    let mut candidates = vec![
        workspace_root.join("target").join(&profile).join("migrate-tester"),
        // Fallback: cargo may have built into either profile dir; try both.
        workspace_root.join("target").join("release").join("migrate-tester"),
        workspace_root.join("target").join("debug").join("migrate-tester"),
    ];
    candidates.dedup();

    for c in &candidates {
        if c.exists() {
            return c.clone();
        }
    }

    // Build it on demand if missing (CI may run this test before any other
    // target triggered the bin compile).
    let status = Command::new(env!("CARGO"))
        .args([
            "build",
            "-p",
            "grid-engine",
            "--bin",
            "migrate-tester",
        ])
        .status()
        .expect("spawn cargo build for migrate-tester");
    assert!(status.success(), "cargo build of migrate-tester failed");

    for c in &candidates {
        if c.exists() {
            return c.clone();
        }
    }
    panic!(
        "migrate-tester binary not found in any candidate path: {:?}",
        candidates
    );
}

#[test]
fn migrate_no_race_under_concurrent_processes() {
    let tmp = tempfile::tempdir().expect("create tempdir");
    let db_path = tmp.path().join("race.db");

    let binary = resolve_migrate_tester();

    // Spawn 4 concurrent processes against the same db file.
    let handles: Vec<_> = (0..4)
        .map(|_| {
            Command::new(&binary)
                .arg(&db_path)
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .spawn()
                .expect("spawn migrate-tester")
        })
        .collect();

    let mut all_success = true;
    let mut stderr_collected = String::new();
    let mut stdout_collected = String::new();
    for h in handles {
        let out = h.wait_with_output().expect("wait_with_output");
        if !out.status.success() {
            all_success = false;
        }
        stderr_collected.push_str(&String::from_utf8_lossy(&out.stderr));
        stdout_collected.push_str(&String::from_utf8_lossy(&out.stdout));
    }

    assert!(
        all_success,
        "At least one migrate-tester process failed. stderr:\n{}",
        stderr_collected
    );
    assert!(
        !stderr_collected.contains("duplicate column"),
        "Race regression: 'duplicate column' surfaced in stderr:\n{}",
        stderr_collected
    );

    // Final state check
    let conn = rusqlite::Connection::open(&db_path).expect("open final db");
    let version: u32 = conn
        .pragma_query_value(None, "user_version", |row| row.get(0))
        .expect("read final user_version");
    assert_eq!(
        version,
        grid_engine::db::CURRENT_VERSION,
        "Final user_version mismatch: got {}, expected {}",
        version,
        grid_engine::db::CURRENT_VERSION
    );

    // Sanity: every process reported the same user_version on its stdout
    // (each invocation prints `user_version=<N>`).
    let expected_line = format!("user_version={}", grid_engine::db::CURRENT_VERSION);
    assert!(
        stdout_collected.contains(&expected_line),
        "Expected stdout to contain '{}', got:\n{}",
        expected_line,
        stdout_collected
    );
}
