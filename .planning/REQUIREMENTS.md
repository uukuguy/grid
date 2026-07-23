# Requirements: Grid — v3.8 grid-server multi-user login (Tenant + RBAC + JWT)

**Defined:** 2026-07-23
**Milestone:** v3.8 (climb — autonomous bootstrap)
**Core Value:** Grid 作为 substitutable L1 runtime,通过 gRPC contract 被 EAASP L2-L4 调用,且任何符合 `contract-v1.2.0` 的对比 runtime 都能替换它。

## v3.8 Requirements

Requirements grouped by category. REQ-IDs use v3.8 numbering — continue from v3.7.5 (no REQ-MULTI- prior).

### AUTH — JWT + Login

- [ ] **AUTH-01**: User can POST credentials to `/api/v1/auth/login` and receive a signed JWT with `sub`, `tenant_id`, `role`, `iat`, `exp` claims
- [ ] **AUTH-02**: User can POST `/api/v1/auth/refresh` with a valid refresh token to mint a new short-lived JWT
- [ ] **AUTH-03**: User can POST `/api/v1/auth/logout` to invalidate their session (server-side token blacklist)
- [ ] **AUTH-04**: Failed login attempts (bad credentials, expired token, tampered signature) return 401 with a structured error body, never leak whether the user exists
- [ ] **AUTH-05**: Token signing uses HMAC-SHA256 with `GRID_JWT_SECRET` (REQUIRED env, fail-fast if missing in `mode=full`, ADR-V2-028 strict-by-default); tokens signed with the legacy default secret are rejected

### RBAC — Role / Permission enforcement

- [ ] **RBAC-01**: Existing `Role { Viewer, User, Admin, Owner }` × `Action { Read, CreateSession, RunAgent, ManageMcp, ManageSkills, ManageUsers, ManageBilling }` matrix in `crates/grid-engine/src/auth/roles.rs` is now enforced at the route handler layer via a `requires(Action)` middleware annotation
- [ ] **RBAC-02**: `POST /api/v1/users` requires `ManageUsers`; non-Admin callers receive 403
- [ ] **RBAC-03**: `GET /api/v1/audit` requires `ManageUsers` or `Owner`; lower roles receive 403
- [ ] **RBAC-04**: `Owner` always succeeds (superuser); `Viewer` cannot call any write endpoint; `User` can call read + create + run; `Admin` extends to ManageMcp / ManageSkills

### TENANT — Multi-tenant scoping

- [ ] **TENANT-01**: Every authenticated request resolves a `TenantContext { tenant_id, user_id, role }` from the JWT claims, populated by `TenantContext::for_multi_user` (replaces `for_single_user` default for `AuthMode::Full`)
- [ ] **TENANT-02**: `GRID_MODE=multi_user` selects `TenantContext::for_multi_user`; default `single_user` keeps `for_single_user` for backward compatibility (no migration required for existing single-user deployments)
- [ ] **TENANT-03**: Cross-tenant data access — User A in Tenant X calling `GET /api/v1/sessions/<id>` for a session owned by User B in Tenant Y — returns 403 with body `tenant_mismatch`; the underlying data is never serialized into the response

### SESSION — Cross-user isolation

- [ ] **SESSION-01**: `SessionStore` enforces ownership: a session row carries `tenant_id` + `user_id`; reads/writes require matching claims
- [ ] **SESSION-02**: Direct ID enumeration (e.g. `GET /api/v1/sessions?ids=a,b,c,d`) without ownership scope returns only the caller's own sessions — never another tenant's data
- [ ] **SESSION-03**: Concurrent sessions from two distinct users in two distinct tenants sharing the same `grid-server` instance cannot read each other's `messages[]` or `agents[]`

### AUDIT — Multi-tenant trail

- [ ] **AUDIT-01**: Existing audit middleware in `crates/grid-server/src/middleware/audit.rs` stamps every record with the current `tenant_id`, `user_id`, `role` (when available)
- [ ] **AUDIT-02**: `GET /api/v1/audit?tenant_id=<x>` is tenant-scoped; `Owner` may cross tenants only when an explicit `?cross_tenant=true` flag is present (logged as a SECURITY event)

### TEST — Hermetic validation

- [ ] **TEST-01**: Integration test that mints two JWTs (User A in Tenant X, User B in Tenant Y), runs concurrent requests, asserts isolation
- [ ] **TEST-02**: Integration test for role escalation: `Viewer` JWT calling `POST /api/v1/users` returns 403
- [ ] **TEST-03**: Integration test for JWT expiry: stale token returns 401, refresh path returns new token
- [ ] **TEST-04**: Integration test for missing claim: tampered token missing `tenant_id` returns 401
- [ ] **TEST-05**: Hermetic S8 walkthrough doc with 5 scenarios: (1) login, (2) cross-tenant block, (3) role escalation block, (4) refresh, (5) logout — UAT 5/5 PASS
- [ ] **TEST-06**: All existing v3.7.1/v3.7.2 single-user tests still PASS — `GRID_MODE=single_user` path is unchanged for the default deployment (no regression)

### DOC — Operator-facing docs

- [ ] **DOC-01**: `USER_GUIDE.md` §11 multi-user mode (login flow, JWT mint, refresh, logout, RBAC matrix reference)
- [ ] **DOC-02**: Operator env-var reference updated: `GRID_MODE`, `GRID_JWT_SECRET` (required if `mode=full`), `GRID_TOKEN_TTL_SECS`, `GRID_REFRESH_TTL_SECS`
- [ ] **DOC-03**: `PRODUCTION_USABILITY_2026-07-2X.md` dated walkthrough for v3.8 (5 scenarios + 1 UAT sweep)

## Future Requirements (deferred)

- **SSO / SAML / OIDC** — defer to v3.9+; v3.8 is JWT-only (local creds + JWT mint)
- **Cross-tenant agent sharing** — defer; not in user scope
- **`web-platform/` multi-tenant UI** wiring — separate milestone; v3.8 ends at API boundary
- **OPA integration on top of RBAC** — separate item from v3.7.3 in-process gate

## Out of Scope

- **EAASP v2.0 Phase 3-6** (production OPA / A2A / L5 / Phase 6 ecosystem) — untouched
- **`web-platform/` Quality 7.5→9.0** — separate milestone
- **`grid-desktop` Quality 6.5→9.0** — separate milestone
- **OAuth2 / Authorization Code flow** — JWT-only this milestone
- **Migrating single-user tenants** — `GRID_MODE=single_user` remains the default; no breaking change

## Traceability

> Filled by roadmapper when phases are created. Each REQ-ID maps to exactly one phase.

| Phase | REQ-IDs |
|-------|---------|
| _TBD_ | _all 21 requirements_ |
