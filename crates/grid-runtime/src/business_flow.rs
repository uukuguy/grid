//! EAASP Business Flow — vertical cross-layer business-context binding
//! for the L1 Rust runtime.
//!
//! Per OBSTACK_DESIGN.md §3.1 / §3.4. Mirror of
//! ``tools/eaasp-common/src/eaasp_common/business_flow.py`` — same
//! wire format, same field semantics, same per-task propagation rule.
//!
//! Differences from the Python module:
//! - Storage: `task_local!` (tokio) instead of Python's `contextvars`.
//!   tokio's `task_local` provides per-async-task isolation, which is
//!   the Rust equivalent of Python's contextvar for request-scoped
//!   context propagation. The accessor functions stay the same shape.
//! - Header parser: `X-Business-Key` is a single ASCII line. We parse
//!   it lazily from tonic `Metadata` extensions on the gRPC path.
//! - Error: Python `ValueError` → Rust `BusinessKeyError::Parse`; the
//!   upper layer maps that to gRPC `INVALID_ARGUMENT`.
//!
//! Wire format (identical to the Python module):
//!
//! ```text
//! <session_id>|<skill_id>|<business_object_id>
//! ```
//!
//! - `session_id` is required (non-empty).
//! - `skill_id` and `business_object_id` are optional (empty OK).
//! - Pipe (`|`) characters inside a field are rejected.

use std::cell::Cell;
use thiserror::Error;

pub const MAX_FIELD_LEN: usize = 256;

// ─── Domain model ───────────────────────────────────────────────────────────

/// Three-tuple that vertically binds one end-to-end business request
/// across L0–L5. Mirror of ``eaasp_common.business_flow.BusinessKey``.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct BusinessKey {
    pub session_id: String,
    pub skill_id: String,
    pub business_object_id: String,
}

#[derive(Debug, Error, PartialEq, Eq)]
pub enum BusinessKeyError {
    #[error("BusinessKey.session_id must be non-empty")]
    EmptySessionId,
    #[error("BusinessKey.{0} must be a String, got {1}")]
    NotAString(&'static str, String),
    #[error("BusinessKey.{0} length {1} exceeds max {2}")]
    TooLong(&'static str, usize, usize),
    #[error("BusinessKey.{0} must not contain '|' (reserved as wire separator)")]
    PipeInField(&'static str),
    #[error(
        "X-Business-Key must have 3 pipe-separated fields, got {0}"
    )]
    WrongFieldCount(usize),
}

impl BusinessKey {
    pub fn new(
        session_id: impl Into<String>,
        skill_id: impl Into<String>,
        business_object_id: impl Into<String>,
    ) -> Result<Self, BusinessKeyError> {
        let session_id = session_id.into();
        let skill_id = skill_id.into();
        let business_object_id = business_object_id.into();
        let key = Self {
            session_id,
            skill_id,
            business_object_id,
        };
        key.validate()?;
        Ok(key)
    }

    pub fn validate(&self) -> Result<(), BusinessKeyError> {
        validate_field("session_id", &self.session_id)?;
        validate_field("skill_id", &self.skill_id)?;
        validate_field(
            "business_object_id",
            &self.business_object_id,
        )?;
        Ok(())
    }

    /// True iff at least one of skill_id / business_object_id is set.
    pub fn is_meaningful(&self) -> bool {
        !self.skill_id.is_empty() || !self.business_object_id.is_empty()
    }

    /// Prefix-based matching (same semantics as Python's
    /// ``BusinessKey.matches``): non-empty fields must match exactly;
    /// empty fields are treated as wildcards. Lets a session start
    /// without a skill and acquire one later without breaking the
    /// timeline query.
    pub fn matches(&self, other: &BusinessKey) -> bool {
        if self.session_id != other.session_id {
            return false;
        }
        if !self.skill_id.is_empty()
            && !other.skill_id.is_empty()
            && self.skill_id != other.skill_id
        {
            return false;
        }
        if !self.business_object_id.is_empty()
            && !other.business_object_id.is_empty()
            && self.business_object_id != other.business_object_id
        {
            return false;
        }
        true
    }

    /// Render as the wire format used in ``X-Business-Key`` headers.
    pub fn to_header(&self) -> String {
        format!(
            "{}|{}|{}",
            self.session_id, self.skill_id, self.business_object_id
        )
    }

    /// Parse a wire-format ``X-Business-Key`` header.
    ///
    /// Returns `Ok(None)` when the header is missing or empty — this is
    /// the "not part of any business flow" case (per OBSTACK §3.8 #1,
    /// business_key is optional during migration).
    pub fn parse_header(raw: Option<&str>) -> Result<Option<Self>, BusinessKeyError> {
        match raw {
            None => Ok(None),
            Some("") => Ok(None),
            Some(s) => {
                let parts: Vec<&str> = s.splitn(3, '|').collect();
                if parts.len() != 3 {
                    return Err(BusinessKeyError::WrongFieldCount(parts.len()));
                }
                Self::new(parts[0], parts[1], parts[2]).map(Some)
            }
        }
    }
}

fn validate_field(name: &'static str, value: &str) -> Result<(), BusinessKeyError> {
    if name == "session_id" && value.is_empty() {
        return Err(BusinessKeyError::EmptySessionId);
    }
    if value.len() > MAX_FIELD_LEN {
        return Err(BusinessKeyError::TooLong(name, value.len(), MAX_FIELD_LEN));
    }
    if value.contains('|') {
        return Err(BusinessKeyError::PipeInField(name));
    }
    Ok(())
}

impl std::fmt::Display for BusinessKey {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.to_header())
    }
}

impl std::str::FromStr for BusinessKey {
    type Err = BusinessKeyError;
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match Self::parse_header(Some(s))? {
            Some(k) => Ok(k),
            None => Err(BusinessKeyError::EmptySessionId),
        }
    }
}

// ─── Per-task context propagation ──────────────────────────────────────────
//
// tokio's `task_local!` provides per-async-task storage. Each gRPC
// request runs in its own task, so setting the business key on entry
// and resetting it on exit gives us the same isolation guarantees as
// Python's `contextvars`. The default is `None` (no business flow).

tokio::task_local! {
    static BUSINESS_KEY: Cell<Option<BusinessKey>>;
}

/// Set the active business key for the current async task. Returns a
/// `TaskLocalFuture` that, when dropped, restores the prior value.
///
/// Mirror of Python's ``set_current_business_key`` + ``reset_*`` pair.
pub fn scope<F>(key: Option<BusinessKey>, fut: F) -> impl std::future::Future<Output = F::Output>
where
    F: std::future::Future,
{
    BUSINESS_KEY.scope(Cell::new(key), fut)
}

/// Read the active business key inside the scoped future.
///
/// Use `require()` instead when the key is mandatory for the calling
/// code path.
pub fn current() -> Option<BusinessKey> {
    BUSINESS_KEY
        .try_with(|c| c.take())
        .ok()
        .flatten()
}

/// Like `current()` but returns `BusinessKeyError::EmptySessionId`
/// when no key is bound. The error name is reused (`EmptySessionId`)
/// for symmetry with the constructor; callers that want a distinct
/// "missing key" signal should map accordingly.
pub fn require() -> Result<BusinessKey, BusinessKeyError> {
    current().ok_or(BusinessKeyError::EmptySessionId)
}

// ─── Tests ──────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> BusinessKey {
        BusinessKey::new("sess-A", "skill-thr", "Transformer-001")
            .expect("sample key is valid")
    }

    #[test]
    fn header_round_trip() {
        let k = sample();
        let header = k.to_header();
        let parsed = BusinessKey::parse_header(Some(&header))
            .expect("parse ok")
            .expect("non-None key");
        assert_eq!(parsed, k);
    }

    #[test]
    fn parse_header_missing_returns_none() {
        assert_eq!(BusinessKey::parse_header(None).unwrap(), None);
        assert_eq!(BusinessKey::parse_header(Some("")).unwrap(), None);
    }

    #[test]
    fn parse_header_rejects_too_few_fields() {
        let err = BusinessKey::parse_header(Some("only_one_field")).unwrap_err();
        assert_eq!(err, BusinessKeyError::WrongFieldCount(1));

        let err = BusinessKey::parse_header(Some("a|b")).unwrap_err();
        assert_eq!(err, BusinessKeyError::WrongFieldCount(2));
    }

    #[test]
    fn parse_header_rejects_pipe_in_field() {
        // `splitn(3, '|')` splits "a|b|c|d" into ["a", "b", "c|d"]; the
        // third field still contains a pipe, so validation must reject
        // it as PipeInField rather than silently accepting 3 fields.
        let err = BusinessKey::parse_header(Some("a|b|c|d")).unwrap_err();
        assert_eq!(err, BusinessKeyError::PipeInField("business_object_id"));

        // Pipe in field 0 (session_id) is caught directly.
        let err = BusinessKey::parse_header(Some("a|b|with|pipe"))
            .unwrap_err();
        // Splitn gives ["a", "b", "with|pipe"]; business_object_id has pipe.
        assert_eq!(err, BusinessKeyError::PipeInField("business_object_id"));
    }

    #[test]
    fn validate_rejects_empty_session_id() {
        assert_eq!(
            BusinessKey::new("", "skill", "obj").unwrap_err(),
            BusinessKeyError::EmptySessionId
        );
    }

    #[test]
    fn validate_rejects_oversize_field() {
        let big = "x".repeat(MAX_FIELD_LEN + 1);
        let err = BusinessKey::new("sess", big.clone(), "").unwrap_err();
        assert_eq!(err, BusinessKeyError::TooLong("skill_id", MAX_FIELD_LEN + 1, MAX_FIELD_LEN));
    }

    #[test]
    fn matches_is_prefix_based() {
        let a = BusinessKey::new("sess-A", "skill-thr", "Transformer-001").unwrap();
        let b = BusinessKey::new("sess-A", "skill-thr", "Transformer-001").unwrap();
        assert!(a.matches(&b));

        let c = BusinessKey::new("sess-A", "", "").unwrap(); // session-only
        assert!(c.matches(&a)); // session-only matches anything in same session

        let d = BusinessKey::new("sess-B", "skill-thr", "Transformer-001").unwrap();
        assert!(!a.matches(&d)); // different session

        let e = BusinessKey::new("sess-A", "skill-other", "Transformer-001").unwrap();
        assert!(!a.matches(&e)); // different skill
    }

    #[test]
    fn is_meaningful_requires_skill_or_object() {
        let session_only = BusinessKey::new("sess", "", "").unwrap();
        assert!(!session_only.is_meaningful());

        let with_skill = BusinessKey::new("sess", "skill", "").unwrap();
        assert!(with_skill.is_meaningful());

        let with_object = BusinessKey::new("sess", "", "obj").unwrap();
        assert!(with_object.is_meaningful());
    }

    #[tokio::test]
    async fn task_local_scope_isolates_keys() {
        let k = sample();

        // Inside scope: current key is `k`.
        scope(Some(k.clone()), async {
            let cur = current().expect("key set");
            assert_eq!(cur, k);

            // Nested scope with different key shadows outer (per task,
            // not per scope — this is the same task).
            let inner = BusinessKey::new("sess-B", "skill-other", "obj").unwrap();
            scope(Some(inner.clone()), async {
                let cur = current().expect("nested key set");
                assert_eq!(cur, inner);
            })
            .await;
        })
        .await;

        // After outer scope exits, no key is bound in this task.
        assert_eq!(current(), None);

        // Different task: independent state (per-task isolation is
        // the Rust equivalent of Python's contextvar).
        let k2 = sample();
        tokio::spawn(async move {
            scope(Some(k2.clone()), async {
                let cur = current().expect("key in spawned task");
                assert_eq!(cur, k2);
            })
            .await;
        })
        .await
        .expect("spawned task completed");
    }

    #[tokio::test]
    async fn require_returns_error_outside_scope() {
        // Outside any scope — current() is None, require() errors.
        assert_eq!(current(), None);
        let err = require().unwrap_err();
        assert_eq!(err, BusinessKeyError::EmptySessionId);
    }
}
