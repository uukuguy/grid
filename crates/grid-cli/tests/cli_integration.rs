//! CLI smoke tests (Phase 5.2 T-01.19).
//!
//! Each test invokes the built `grid` binary via `Command::new`. Cargo sets
//! `CARGO_BIN_EXE_grid` to the binary path when running integration tests,
//! so we don't have to hunt for it.
//!
//! Scope: surface-level contract checks. We are NOT testing:
//! - actual agent execution (would need a live LLM provider)
//! - session storage side effects against the user's home dir (would
//!   pollute `~/.grid/`)
//!
//! What we lock:
//! 1. `grid ask --help` renders (exit 0, contains `Usage`).
//! 2. `grid invalid-subcommand` exits with code 2 (clap convention).
//! 3. `grid ask` without args exits with code 2 (clap missing required arg).
//! 4. `grid doctor` runs all checks and exits with a documented code
//!    (0 on clean / no proto-sync issues; 73 if proto sync detects mismatch).
//! 5. `NO_COLOR=1 grid --help` produces zero ANSI escape codes.
//!
//! Each test runs in <500ms; the whole suite is well under a wall-clock second.

#![cfg(feature = "studio")]

use std::process::Command;

fn grid_bin() -> Command {
    let path = env!("CARGO_BIN_EXE_grid");
    let mut cmd = Command::new(path);
    // Insulate the smoke tests from any user-level config / env that might
    // make `grid doctor` fail (e.g. missing config.yaml in the test cwd) or
    // shorten/lengthen output. We let the binary discover its own GridRoot.
    cmd.env_remove("NO_COLOR");
    cmd.env_remove("CLICOLOR");
    cmd.env_remove("CLICOLOR_FORCE");
    cmd
}

#[test]
fn ask_help_renders_and_exits_zero() {
    let out = grid_bin()
        .args(["ask", "--help"])
        .output()
        .expect("failed to run grid ask --help");
    assert!(out.status.success(), "grid ask --help must exit 0, got {:?}", out.status);
    let stdout = String::from_utf8_lossy(&out.stdout);
    assert!(
        stdout.contains("Usage:") && stdout.contains("grid ask"),
        "grid ask --help must print clap usage; got:\n{}",
        stdout
    );
    assert!(
        stdout.contains("--session") || stdout.contains("MESSAGE"),
        "grid ask --help must document the required MESSAGE arg / --session flag"
    );
}

#[test]
fn invalid_subcommand_exits_two() {
    let out = grid_bin()
        .arg("definitely-not-a-real-subcommand")
        .output()
        .expect("failed to run grid with invalid subcommand");
    let code = out.status.code().expect("process must exit, not be signalled");
    assert_eq!(
        code, 2,
        "invalid subcommand must exit 2 (clap convention); got {}, stderr:\n{}",
        code,
        String::from_utf8_lossy(&out.stderr)
    );
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(
        stderr.contains("unrecognized") || stderr.contains("error:"),
        "stderr must signal the error; got:\n{}",
        stderr
    );
}

#[test]
fn ask_without_message_exits_two() {
    let out = grid_bin()
        .arg("ask")
        .output()
        .expect("failed to run grid ask without args");
    let code = out.status.code().expect("process must exit, not be signalled");
    assert_eq!(
        code, 2,
        "grid ask without MESSAGE must exit 2 (clap missing-required-arg); got {}",
        code
    );
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(
        stderr.contains("required") || stderr.contains("MESSAGE"),
        "stderr must explain the missing arg; got:\n{}",
        stderr
    );
}

#[test]
fn doctor_runs_and_exits_with_documented_code() {
    let out = grid_bin()
        .arg("doctor")
        .output()
        .expect("failed to run grid doctor");
    let code = out.status.code().expect("process must exit, not be signalled");
    // T-01.17 contract: 0 on clean state; 73 (EXIT_SYNC) if any proto sync
    // check fails. Anything else is undocumented and should fail this test.
    assert!(
        code == 0 || code == 73,
        "grid doctor must exit 0 or 73; got {} with stderr:\n{}\nstdout:\n{}",
        code,
        String::from_utf8_lossy(&out.stderr),
        String::from_utf8_lossy(&out.stdout)
    );
    let stdout = String::from_utf8_lossy(&out.stdout);
    assert!(
        stdout.contains("Grid Doctor") && stdout.contains("Summary:"),
        "grid doctor must print banner + summary line; got:\n{}",
        stdout
    );
    // Lock that the checks T-01.17 added are all wired (PASS or FAIL label
    // for each — we don't care which, only that they ran).
    for required_check in &["Proto Sync", "Session Integrity", "Shell Completion"] {
        assert!(
            stdout.contains(required_check),
            "grid doctor must include '{}' check (T-01.17); stdout:\n{}",
            required_check,
            stdout
        );
    }
}

#[test]
fn no_color_env_produces_zero_ansi_codes() {
    // Use `--help` rather than `doctor` so this test is hermetic — `doctor`
    // depends on env / db / config presence. `grid --help` is pure clap.
    let out = grid_bin()
        .env("NO_COLOR", "1")
        .arg("--help")
        .output()
        .expect("failed to run grid --help under NO_COLOR");
    assert!(out.status.success(), "grid --help must exit 0 under NO_COLOR");
    let stdout = String::from_utf8_lossy(&out.stdout);
    let stderr = String::from_utf8_lossy(&out.stderr);
    // ANSI CSI escape sequences start with ESC `[`. Any presence is a regression.
    for (label, body) in &[("stdout", &stdout), ("stderr", &stderr)] {
        assert!(
            !body.contains('\x1b'),
            "NO_COLOR=1 must produce zero ANSI ESC bytes in {}; got:\n{:?}",
            label,
            body
        );
    }
}

// Phase 5.5 NEW-A3 regression: `grid session kill <missing-id>` must exit with
// ExitCode::SessionNotFound (= 4), not the generic exit 1 that anyhow!() produces.
// Fix lands in Task 01.B1 (commands/session.rs::kill_session + main.rs downcast).
#[test]
fn test_kill_nonexistent_session_exits_4() {
    let out = grid_bin()
        .args(["session", "kill", "does-not-exist-xyz"])
        .output()
        .expect("failed to run grid session kill");
    assert_eq!(
        out.status.code(),
        Some(4),
        "kill_session on missing id should exit 4 (SessionNotFound), got {:?}; stderr: {}",
        out.status.code(),
        String::from_utf8_lossy(&out.stderr)
    );
}
