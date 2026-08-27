# Live Session Checkpoint

> Updated: 2026-08-27 20:41. **Session remains active — not a final handoff.**

## TL;DR

- v3.16 is shipped; generic CI and the Phase 3 Contract Matrix are both remotely green.
- All workflow-referenced Make targets and runner dependencies are present; Grid and Claude primary jobs pass.
- Runtime closure includes immediate DONE termination, configured compaction wiring, OpenAI streaming usage, workspace-relative paths, and reproducible Python startup.

## In-flight work

- No CI recovery work remains in flight.
- Generic CI run `33068401739` is green; final Phase 3 run `33072602355` is green at `160e1659`.
- Make targets landed at `7c2f4884`, runtime/contract closure at `b8980481`, and clean-runner Python dependencies at `0136fb49`.
- Grid and Claude primary jobs pass; sample/reference failures are limited to ADR-V2-025-permitted hook capability gaps, not runner startup or missing infrastructure.

## Immediate next action

1. Commit and push this verified recovery state.
2. Confirm the branch is clean and synchronized with `origin/main`.
3. Return to the user-selected v3.17 scope.

## Ruled-out paths

- Do not install the complete GTK/WebKit desktop stack in generic CI; `desktop-ci.yml` already provisions and tests it on Linux, macOS, and Windows.
- Do not exclude Rust runtime crates requiring protobuf; they are core workspace coverage and must receive `protoc` instead.
- Do not make optional `BusinessKey` fixtures synthetic; `None` is the compatibility-preserving value for these tests.
- Do not revert threshold calibration to the shared scope; its isolated scope prevents the D11 namespace collision.
- Do not weaken `GridRoot` path assertions; the failure was cross-test process-environment mutation and is fixed by module-local serialization.
