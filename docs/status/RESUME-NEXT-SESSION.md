# Live Session Checkpoint

> Updated: 2026-08-27 17:30. **Session remains active — not a final handoff.**

## TL;DR

- v3.16 is shipped; the generic CI repair is in active verification.
- Generic CI excludes `grid-desktop` and provisions `protoc`; dedicated Desktop CI remains the desktop system-dependency owner.
- Newly reachable workspace tests have been repaired through runtime fixtures, Goose fixtures, hook smoke coverage, and WebSocket feature wiring.

## In-flight work

- CI run `33057727325` passed install, workspace check, both audits, and the WebSocket feature compile point, then found a stale skill-scope assertion.
- Fix `4ac45ec6` aligns the assertion with the namespace-isolated scope introduced by `a6d75300`; its 10-test target passes locally.
- `main` is one code commit plus this checkpoint update ahead of `origin/main` until the next push.

## Immediate next action

1. Commit this active checkpoint and journal update, then push `main`.
2. Watch the new GitHub Actions CI run through workspace tests.
3. If green, reconcile stale planning-state CI concerns and record the verified result; otherwise fix the first real failure.

## Ruled-out paths

- Do not install the complete GTK/WebKit desktop stack in generic CI; `desktop-ci.yml` already provisions and tests it on Linux, macOS, and Windows.
- Do not exclude Rust runtime crates requiring protobuf; they are core workspace coverage and must receive `protoc` instead.
- Do not make optional `BusinessKey` fixtures synthetic; `None` is the compatibility-preserving value for these tests.
- Do not revert threshold calibration to the shared scope; its isolated scope prevents the D11 namespace collision.
