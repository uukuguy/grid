//! CONTRACT-05 (D55) — proto3 submessage presence parity test (Rust side).
//!
//! Phase 7.1 Plan 01, Task 08.
//!
//! Prost-generated proto3 submessage fields are `Option<T>`. Presence
//! is `Option::is_some()` / `is_none()`, NOT `if msg.field { ... }`
//! truthy fallback (which doesn't compile for `Option<T>` anyway —
//! but the equivalent `T::default()`-equality check is equally
//! fragile because a present-but-empty submessage compares equal to
//! the default).
//!
//! This test pins the absence semantics for `SessionPayload`
//! P-blocks (P1 PolicyContext, P4 SkillInstructions, P5
//! UserPreferences). Mirrored in:
//!
//!   - tests/contract/contract_v1/test_proto3_hasfield_parity.py (Python)
//!   - lang/ccb-runtime-ts/tests/proto3-hasfield-parity.test.ts (TS)
//!
//! Mechanically prevents the truthy-fallback anti-pattern from
//! re-emerging at zero ongoing maintenance cost — if a future
//! refactor switches a presence check back to `if msg.field { ... }`,
//! this test fails.

use grid_runtime::proto;

#[test]
fn session_payload_p1_absent_by_default() {
    let p = proto::SessionPayload::default();
    assert!(
        p.policy_context.is_none(),
        "default SessionPayload must have policy_context = None"
    );
}

#[test]
fn session_payload_p1_present_after_assignment() {
    let mut p = proto::SessionPayload::default();
    p.policy_context = Some(proto::PolicyContext {
        org_unit: "t1".into(),
        ..Default::default()
    });
    assert!(p.policy_context.is_some());
}

#[test]
fn session_payload_p4_absent_by_default() {
    let p = proto::SessionPayload::default();
    assert!(p.skill_instructions.is_none());
}

#[test]
fn session_payload_p4_present_after_assignment() {
    let mut p = proto::SessionPayload::default();
    p.skill_instructions = Some(proto::SkillInstructions {
        skill_id: "x".into(),
        ..Default::default()
    });
    assert!(p.skill_instructions.is_some());
}

#[test]
fn session_payload_p5_absent_by_default() {
    let p = proto::SessionPayload::default();
    assert!(p.user_preferences.is_none());
}

#[test]
fn session_payload_p5_present_after_assignment() {
    let mut p = proto::SessionPayload::default();
    p.user_preferences = Some(proto::UserPreferences {
        user_id: "u".into(),
        ..Default::default()
    });
    assert!(p.user_preferences.is_some());
}
