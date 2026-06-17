<plan phase="A.5" name="grid-platform Hardening">
<objective>
Add structured error codes, wire rate limiting, and add body size limits to grid-platform. Fixes 3 P3 gaps identified in A.0 audit: String-based errors, disconnected quota middleware, missing rate limits.
</objective>

<review_protocol>none</review_protocol>

<tasks>
- [ ] T1: Structured Error System — create `src/error.rs` with `ErrorCode` enum (8 variants: Authentication, Authorization, Validation, NotFound, RateLimited, QuotaExceeded, Conflict, Internal) and `ErrorResponse` struct with `error_code` field. Update all handlers (main.rs auth, api/sessions, api/users, api/mcp, api/admin/tenants, ws.rs) to use typed constructors.
- [ ] T2: Rate Limiting — fix `quota_middleware` to use request extensions (instead of broken State/Extension extraction). Register via `route_layer(from_fn(...))` on the router. Add `RequestBodyLimitLayer` (5MB) to all routes.
- [ ] T3: Verify build and tests pass (17/17).
</tasks>

<verification>
- [ ] cargo build -p grid-platform passes with 0 errors
- [ ] cargo test -p grid-platform: 17/17 pass (5 unit + 3 agent_pool + 9 user_runtime)
</verification>

<notes>
**Design decisions:**
- Quota middleware uses request extensions to access AppState (same pattern as AuthExtractor), avoiding Axum middleware API complexity.
- Internal error messages are now sanitized to "Internal error" for DB-layer errors — no leaking implementation details to clients.
- No new integration tests added (auth/session/user/admin handler tests remain TODOs) — this phase focused on structural hardening (ErrorCode + rate limiting) over test coverage expansion.
- The ErrorCode enum is intentionally not wire-exposed as integers — uses semantic strings matching web/ and web-platform/ frontend patterns.
</notes>
</plan>
