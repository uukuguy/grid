# Live Session Checkpoint

> Updated: 2026-08-27 19:25. **Session remains active — not a final handoff.**

## TL;DR

- v3.16 is shipped; the generic CI repair is verified green.
- Generic CI excludes `grid-desktop` and provisions `protoc`; dedicated Desktop CI remains the desktop system-dependency owner.
- Newly reachable workspace tests were repaired through runtime fixtures, hook wiring, WebSocket feature coverage, environment isolation, and stale API assertions.

## In-flight work

- CI run `33066127865` completed successfully: workspace check, RBAC audit, EAASP spec audit, and all workspace tests passed.
- Security policy test fix `97a97828` now verifies the implemented PUT contract and subsequent GET visibility; its focused suite passes 9/9.
- Hook fixture fix `1534c8b8` consumes the stdin envelope before exiting, so ADR-V2-006 broken-pipe fail-open cannot mask exit code 2; the deny path passed 50 consecutive runs and the crate passes 4/4.
- No generic CI repair remains in flight; the separate Phase 3 Contract Matrix Makefile target gap remains unchanged.

## Immediate next action

1. Commit and push the verified CI state reconciliation.
2. Confirm the docs-only HEAD also receives a green generic CI run.
3. Return to user-selected v3.17 scope; treat the Phase 3 Contract Matrix target gap as separate follow-on work.

## Ruled-out paths

- Do not install the complete GTK/WebKit desktop stack in generic CI; `desktop-ci.yml` already provisions and tests it on Linux, macOS, and Windows.
- Do not exclude Rust runtime crates requiring protobuf; they are core workspace coverage and must receive `protoc` instead.
- Do not make optional `BusinessKey` fixtures synthetic; `None` is the compatibility-preserving value for these tests.
- Do not revert threshold calibration to the shared scope; its isolated scope prevents the D11 namespace collision.
- Do not weaken `GridRoot` path assertions; the failure was cross-test process-environment mutation and is fixed by module-local serialization.
