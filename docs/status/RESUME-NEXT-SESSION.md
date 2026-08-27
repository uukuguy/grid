# Live Session Checkpoint

> Updated: 2026-08-27 18:20. **Session remains active — not a final handoff.**

## TL;DR

- v3.16 is shipped; the generic CI repair is in active verification.
- Generic CI excludes `grid-desktop` and provisions `protoc`; dedicated Desktop CI remains the desktop system-dependency owner.
- Newly reachable workspace tests have been repaired through runtime fixtures, hook wiring, WebSocket feature coverage, and environment isolation.

## In-flight work

- CI run `33061310123` passed install, workspace check, RBAC audit, and EAASP spec audit; workspace tests reached 1632 PASS before exposing a `GridRoot` env race.
- Fix `1af9e59a` serializes every `GRID_*`-mutating test in `root.rs`; 15 focused tests passed 21 consecutive 16-thread runs, and `grid-engine` checks cleanly.
- Scoped-hook compatibility fix `96c023fe` also replaced the scheduler-sensitive handler-presence assertion with a real deny-path execution check.
- `main` is one code commit plus this checkpoint update ahead of `origin/main` until the next push.

## Immediate next action

1. Commit this active checkpoint and journal update, then push `main`.
2. Watch the new GitHub Actions CI run through all workspace tests.
3. If green, reconcile stale planning-state CI concerns and record the verified result; otherwise fix the first real failure.

## Ruled-out paths

- Do not install the complete GTK/WebKit desktop stack in generic CI; `desktop-ci.yml` already provisions and tests it on Linux, macOS, and Windows.
- Do not exclude Rust runtime crates requiring protobuf; they are core workspace coverage and must receive `protoc` instead.
- Do not make optional `BusinessKey` fixtures synthetic; `None` is the compatibility-preserving value for these tests.
- Do not revert threshold calibration to the shared scope; its isolated scope prevents the D11 namespace collision.
- Do not weaken `GridRoot` path assertions; the failure was cross-test process-environment mutation and is fixed by module-local serialization.
