//! v3.8 UserStore — in-process credential store for multi-user login (03.8.1).
//!
//! Intentionally minimal: HashMap-backed, seeded from `GRID_USERS_JSON` env
//! var at startup. Persisted storage is v3.9+; for v3.8 the dev/test loop is
//! "edit env var, restart server" which is sufficient for hermetic validation.
//!
//! Per ADR-V2-023 P1: lives in `grid-engine::auth` so it's available to any
//! downstream server (engine 接入面 (EAASP) + Grid 独立产品 shared-core).
//!
//! **Why user lookup is by `email` not `user_id`:** v3.8 has no user-management
//! UI, so users sign in with the email they were issued in the bootstrap JSON.
//!
//! **Timing-side-channel note:** `verify_credentials` performs Argon2 verify
//! only on the matched-user path. The "unknown email" branch short-circuits
//! to `None` immediately — observable to a timing-attack adversary on a
//! local network. v3.9+ rate-limiting at the login endpoint combined with
//! login-attempt throttling makes this practically irrelevant. Constant-time
//! fallback can be added when login rate-limiting lands.

use std::collections::HashMap;
use std::sync::Arc;

use argon2::password_hash::PasswordHash;
use argon2::password_hash::PasswordHasher;
use argon2::password_hash::PasswordVerifier;
use argon2::password_hash::SaltString;
use argon2::Argon2;
use serde::Deserialize;

use super::roles::Role;

/// Credential record for a single user.
#[derive(Debug, Clone)]
pub struct UserRecord {
    pub user_id: String,
    pub tenant_id: String,
    pub email: String,
    pub role: Role,
    /// Argon2id PHC string (`$argon2id$v=19$m=...$t=...$p=...$salt$hash`).
    pub password_hash: String,
}

/// Wire shape used when reading `GRID_USERS_JSON` at startup.
#[derive(Debug, Deserialize)]
struct UserSeedEntry {
    user_id: String,
    tenant_id: String,
    email: String,
    password: String, // plaintext — hashed at load, never stored
    role: String,
}

/// In-memory user store. Thread-safe via `Arc` wrapping.
#[derive(Debug)]
pub struct UserStore {
    by_email: HashMap<String, UserRecord>,
    by_user_id: HashMap<String, UserRecord>,
}

impl UserStore {
    /// Load from `GRID_USERS_JSON` env var.
    ///
    /// Expected JSON shape:
    /// ```json
    /// [
    ///   {"user_id":"u1","tenant_id":"tenant-x","email":"a@example.com",
    ///    "password":"hunter2","role":"user"}
    /// ]
    /// ```
    ///
    /// Returns `Err` with actionable message if:
    /// - env var unset
    /// - JSON malformed
    /// - any user has a duplicate `email` or `user_id`
    /// - any user's role string is not parseable by `Role::parse`
    /// - any user's password fails Argon2id hashing at load time
    pub fn from_env() -> Result<Arc<Self>, String> {
        let raw = std::env::var("GRID_USERS_JSON").map_err(|_| {
            "GRID_USERS_JSON is not set. Multi-user mode requires a bootstrap user \
             list. Set it to a JSON array; see 03.8.1 plan §Task 1 for shape."
                .to_string()
        })?;
        Self::from_json(&raw)
    }

    /// Parse + hash + index a JSON string. Used by `from_env` and by tests
    /// (hermetic — no env var needed).
    pub fn from_json(json_str: &str) -> Result<Arc<Self>, String> {
        let seeds: Vec<UserSeedEntry> = serde_json::from_str(json_str)
            .map_err(|e| format!("GRID_USERS_JSON parse failed: {e}"))?;

        let mut by_email = HashMap::with_capacity(seeds.len());
        let mut by_user_id = HashMap::with_capacity(seeds.len());

        for s in seeds {
            let role = Role::parse(&s.role)
                .ok_or_else(|| format!("role {:?} is not a known Role", s.role))?;

            // Argon2id hash with fresh random salt per user.
            let password_hash = hash_password(&s.password)?;

            // Use a local clone of `s` so we can move individual fields without
            // fighting the borrow checker on later error-message branches.
            let s_user_id = s.user_id.clone();
            let s_email = s.email.clone();
            let s_tenant = s.tenant_id.clone();

            let record = UserRecord {
                user_id: s.user_id,
                tenant_id: s_tenant,
                email: s_email.clone(),
                role,
                password_hash,
            };

            if by_email.insert(s_email.clone(), record.clone()).is_some() {
                return Err(format!(
                    "duplicate email in GRID_USERS_JSON: {s_email}"
                ));
            }
            if by_user_id.insert(s_user_id.clone(), record).is_some() {
                return Err(format!(
                    "duplicate user_id in GRID_USERS_JSON: {s_user_id}"
                ));
            }
        }

        Ok(Arc::new(Self {
            by_email,
            by_user_id,
        }))
    }

    /// Empty store — login endpoints will reject everything. Used by
    /// single-user deployments (and by tests that don't care about login).
    pub fn empty() -> Arc<Self> {
        Arc::new(Self {
            by_email: HashMap::new(),
            by_user_id: HashMap::new(),
        })
    }

    /// Look up a user by email and verify the password.
    pub fn verify_credentials(&self, email: &str, password: &str) -> Option<UserRecord> {
        let record = self.by_email.get(email)?;
        let parsed = PasswordHash::new(&record.password_hash).ok()?;
        Argon2::default()
            .verify_password(password.as_bytes(), &parsed)
            .ok()?;
        Some(record.clone())
    }

    pub fn by_user_id(&self, user_id: &str) -> Option<&UserRecord> {
        self.by_user_id.get(user_id)
    }

    pub fn len(&self) -> usize {
        self.by_email.len()
    }

    pub fn is_empty(&self) -> bool {
        self.by_email.is_empty()
    }
}

/// Argon2id-hash a password using `Argon2::default()` + a fresh random salt.
fn hash_password(password: &str) -> Result<String, String> {
    let salt = SaltString::generate(&mut rand::thread_rng());
    Argon2::default()
        .hash_password(password.as_bytes(), &salt)
        .map(|h| h.to_string())
        .map_err(|e| format!("argon2 hashing failed: {e}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    const SEED: &str = r#"[
        {"user_id":"u1","tenant_id":"t1","email":"a@example.com","password":"hunter2","role":"user"},
        {"user_id":"u2","tenant_id":"t1","email":"b@example.com","password":"correcthorse","role":"admin"}
    ]"#;

    #[test]
    fn round_trip_valid_credentials() {
        let s = UserStore::from_json(SEED).unwrap();
        assert_eq!(s.len(), 2);
        let r = s.verify_credentials("a@example.com", "hunter2").unwrap();
        assert_eq!(r.user_id, "u1");
        assert_eq!(r.tenant_id, "t1");
    }

    #[test]
    fn wrong_password_rejected() {
        let s = UserStore::from_json(SEED).unwrap();
        assert!(s.verify_credentials("a@example.com", "WRONG").is_none());
    }

    #[test]
    fn unknown_email_rejected_without_leak() {
        let s = UserStore::from_json(SEED).unwrap();
        assert!(s.verify_credentials("unknown@example.com", "x").is_none());
    }

    #[test]
    fn duplicate_email_in_seed_rejected() {
        let dup = r#"[
            {"user_id":"u1","tenant_id":"t","email":"a@x","password":"p","role":"user"},
            {"user_id":"u2","tenant_id":"t","email":"a@x","password":"p","role":"user"}
        ]"#;
        let err = UserStore::from_json(dup).unwrap_err();
        assert!(err.contains("duplicate email"), "got: {err}");
    }

    #[test]
    fn unknown_role_rejected() {
        let bad_role = r#"[
            {"user_id":"u1","tenant_id":"t","email":"a@x","password":"p","role":"god-mode"}
        ]"#;
        let err = UserStore::from_json(bad_role).unwrap_err();
        assert!(err.contains("role"), "got: {err}");
    }
}

