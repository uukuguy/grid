# Live Session Checkpoint

> Updated: 2026-08-27 19:47. **Session remains active — not a final handoff.**

## TL;DR

- v3.16 is shipped; the generic CI repair is verified green at the final repair HEAD.
- Generic CI excludes `grid-desktop` and provisions `protoc`; dedicated Desktop CI remains the desktop system-dependency owner.
- Newly reachable workspace tests were repaired through runtime fixtures, hook wiring, WebSocket feature coverage, environment isolation, and stale API assertions.

## In-flight work

- CI runs `33066127865` and `33068401739` completed successfully: workspace check, RBAC audit, EAASP spec audit, and all workspace tests passed.
- Cached run `33067332722` exposed and fix `99b65cb9` closed a `GRID_SANDBOXED` test race.
- Cached run `33067931336` then exposed a valid zero-millisecond result for an instant subprocess; fix `164083ab` gives the timing assertion a deliberate 10ms workload. The focused test passed 50 consecutive runs, the suite passes 9/9, and `grid-engine` checks cleanly.
- No generic CI repair remains in flight after `33068401739`; only the independent Phase 3 Contract Matrix target gap remains.
- The separate Phase 3 Contract Matrix Makefile target gap remains unchanged.

## Immediate next action

1. Commit and push this verified-state update.
2. Confirm the docs-only HEAD receives a green generic CI run without creating another status commit.
3. Return to user-selected v3.17 scope; treat the Phase 3 Contract Matrix target gap as separate follow-on work.

## Ruled-out paths

- Do not install the complete GTK/WebKit desktop stack in generic CI; `desktop-ci.yml` already provisions and tests it on Linux, macOS, and Windows.
- Do not exclude Rust runtime crates requiring protobuf; they are core workspace coverage and must receive `protoc` instead.
- Do not make optional `BusinessKey` fixtures synthetic; `None` is the compatibility-preserving value for these tests.
- Do not revert threshold calibration to the shared scope; its isolated scope prevents the D11 namespace collision.
- Do not weaken `GridRoot` path assertions; the failure was cross-test process-environment mutation and is fixed by module-local serialization.
