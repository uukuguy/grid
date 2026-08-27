# Live Session Checkpoint

> Updated: 2026-08-27 16:07. **Session remains active — not a final handoff.**

## TL;DR

- v3.16 is shipped; `main` was synchronized through `ed921890` before this CI repair cycle.
- Generic CI no longer builds `grid-desktop`; the dedicated cross-platform Desktop CI remains its owner.
- The next exposed runner failure was missing `protoc`; fix `bae1ee62` provisions `protobuf-compiler` for Rust runtime build scripts.

## In-flight work

- `bae1ee62` and the corresponding journal/checkpoint state are not yet pushed.
- Prior verification: local `cargo check --workspace --exclude grid-desktop` passed.
- Prior remote run `33052368570` proved the GLib failure was removed, then failed because `protoc` was absent.

## Immediate next action

1. Commit this active checkpoint and journal update.
2. Push `main`.
3. Watch the new GitHub Actions CI run through workspace check, RBAC audit, spec audit, and workspace tests; fix any newly exposed failure.

## Ruled-out paths

- Do not install the complete GTK/WebKit desktop stack in generic CI; `desktop-ci.yml` already provisions and tests it on Linux, macOS, and Windows.
- Do not exclude Rust runtime crates requiring protobuf; they are core workspace coverage and must receive `protoc` instead.
