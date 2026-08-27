# Live Session Checkpoint

> Updated: 2026-08-27 19:08. **Session remains active — not a final handoff.**

## TL;DR

- v3.16 is shipped; the generic CI repair is in active verification.
- Generic CI excludes `grid-desktop` and provisions `protoc`; dedicated Desktop CI remains the desktop system-dependency owner.
- Newly reachable workspace tests have been repaired through runtime fixtures, hook wiring, WebSocket feature coverage, environment isolation, and stale API assertions.

## In-flight work

- CI run `33064910792` passed install, workspace check, RBAC audit, and EAASP spec audit before exposing a scoped-hook fixture race.
- Security policy test fix `97a97828` now verifies the implemented PUT contract and subsequent GET visibility; its focused suite passes 9/9.
- Hook fixture fix `1534c8b8` consumes the stdin envelope before exiting, so ADR-V2-006 broken-pipe fail-open cannot mask exit code 2; the deny path passed 50 consecutive runs and the crate passes 4/4.
- `main` is one code commit plus this checkpoint update ahead of `origin/main` until the next push.

## Immediate next action

1. Commit this active checkpoint and journal update, then push `main`.
2. Watch the next GitHub Actions CI run through all workspace tests.
3. If green, reconcile stale planning-state CI concerns and record the verified result; otherwise fix the first real failure.

## Ruled-out paths

- Do not install the complete GTK/WebKit desktop stack in generic CI; `desktop-ci.yml` already provisions and tests it on Linux, macOS, and Windows.
- Do not exclude Rust runtime crates requiring protobuf; they are core workspace coverage and must receive `protoc` instead.
- Do not make optional `BusinessKey` fixtures synthetic; `None` is the compatibility-preserving value for these tests.
- Do not revert threshold calibration to the shared scope; its isolated scope prevents the D11 namespace collision.
- Do not weaken `GridRoot` path assertions; the failure was cross-test process-environment mutation and is fixed by module-local serialization.
