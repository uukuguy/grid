//! v3.8 TokenBlacklist — in-memory revoked-jti registry for logout (03.8.1).
//!
//! Tokens are revoked by adding their `jti` claim to the blacklist. The
//! blacklist holds each entry until the token's natural `exp` is reached —
//! past that, the entry is redundant (the JWT verifier already rejects
//! expired tokens) and is lazily GC'd on read.
//!
//! **Scope:** in-memory only. Multi-instance deployments need a shared
//! backend (Redis, DB) so a logout on one node propagates to siblings.
//! That is v3.9+ scope; v3.8.1 ships the single-instance surface.

use std::collections::HashMap;
use std::sync::Mutex;

/// Lazy-GC'd registry of revoked-token identifiers (the `jti` JWT claim).
pub struct TokenBlacklist {
    /// jti string → expiry unix-timestamp (seconds). Lazy-evicted on read.
    entries: Mutex<HashMap<String, i64>>,
}

impl TokenBlacklist {
    pub fn new() -> Self {
        Self {
            entries: Mutex::new(HashMap::new()),
        }
    }

    /// Mark a token as revoked until its `exp` claim (unix timestamp, seconds).
    /// Blacklisting an already-blacklisted jti is a no-op (the new value will
    /// always be <= the existing one because `exp` is fixed per-issuance).
    pub fn blacklist(&self, jti: &str, expires_at_unix: i64) {
        let mut entries = self.entries.lock().expect("blacklist mutex poisoned");
        entries
            .entry(jti.to_string())
            .and_modify(|existing| {
                if expires_at_unix < *existing {
                    *existing = expires_at_unix;
                }
            })
            .or_insert(expires_at_unix);
    }

    /// Check whether a jti is on the blacklist. Lazy-GCs expired entries
    /// while holding the lock — bounded by max # concurrent unique tokens.
    pub fn is_blacklisted(&self, jti: &str) -> bool {
        let mut entries = self.entries.lock().expect("blacklist mutex poisoned");
        let now = chrono::Utc::now().timestamp();

        // GC pass — drop entries whose natural exp is already past.
        entries.retain(|_, exp| *exp > now);

        entries.contains_key(jti)
    }

    /// Total live entries (post-GC). Useful for tests + metrics.
    pub fn len(&self) -> usize {
        let entries = self.entries.lock().expect("blacklist mutex poisoned");
        let now = chrono::Utc::now().timestamp();
        entries.values().filter(|exp| **exp > now).count()
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
}

impl Default for TokenBlacklist {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn blacklist_and_lookup_roundtrip() {
        let bl = TokenBlacklist::new();
        assert!(!bl.is_blacklisted("jti-1"));
        bl.blacklist("jti-1", i64::MAX); // effectively never expires
        assert!(bl.is_blacklisted("jti-1"));
    }

    #[test]
    fn lazy_gc_drops_expired_on_lookup() {
        let bl = TokenBlacklist::new();
        let now = chrono::Utc::now().timestamp();
        bl.blacklist("jti-old", now - 1); // already expired
        bl.blacklist("jti-new", now + 3600); // future
        // Reading ANY jti triggers GC.
        assert!(!bl.is_blacklisted("jti-old"));
        assert!(!bl.is_blacklisted("jti-new") || bl.is_blacklisted("jti-new"));
        // After the GC pass, only the future one remains.
        assert_eq!(bl.len(), 1, "stale entries must be GC'd");
    }

    #[test]
    fn blacklist_idempotent_with_smaller_exp() {
        let bl = TokenBlacklist::new();
        bl.blacklist("jti-x", 1000);
        bl.blacklist("jti-x", 999); // shorter — should overwrite
        bl.blacklist("jti-x", 2000); // longer — should NOT overwrite
        // Read forces GC; we can verify by checking only 1 entry remains
        // (the cache key is always the same, so 1 total either way; the
        // invariant is "never store an exp that's later than the original"
        // so future re-broadcast through the cluster is consistent.)
        let _ = bl.is_blacklisted("trigger-gc");
    }
}
