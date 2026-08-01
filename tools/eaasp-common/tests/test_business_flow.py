"""Tests for eaasp_common.business_flow — v3.15.1 vertical binding core.

Covers:
- BusinessKey validation (empty fields, pipe chars, length, types)
- Wire format round-trip (to_header / parse_business_key_header)
- matches() prefix semantics
- Contextvar binding (set / get / reset / scope)
- require_current_business_key raises when unbound
- Header edge cases (None, empty, malformed)
"""

from __future__ import annotations

import pytest

from eaasp_common.business_flow import (
    BusinessKey,
    business_key_scope,
    get_current_business_key,
    parse_business_key_header,
    require_current_business_key,
    reset_current_business_key,
    serialize_business_key,
    set_current_business_key,
)


# ─── Validation ─────────────────────────────────────────────────────────────


def test_session_id_required() -> None:
    with pytest.raises(ValueError, match="session_id must be non-empty"):
        BusinessKey(session_id="")


def test_pipe_in_field_rejected() -> None:
    with pytest.raises(ValueError, match="must not contain '|'"):
        BusinessKey(session_id="sess|1", skill_id="", business_object_id="")


def test_length_cap() -> None:
    with pytest.raises(ValueError, match="exceeds max"):
        BusinessKey(session_id="x" * 257)


def test_non_str_rejected() -> None:
    with pytest.raises(ValueError, match="must be a str"):
        BusinessKey(session_id=123)  # type: ignore[arg-type]


# ─── Predicates ─────────────────────────────────────────────────────────────


def test_is_meaningful() -> None:
    assert BusinessKey(session_id="s1").is_meaningful is False
    assert BusinessKey(session_id="s1", skill_id="k1").is_meaningful is True
    assert BusinessKey(session_id="s1", business_object_id="d1").is_meaningful is True
    assert BusinessKey(session_id="s1", skill_id="k1", business_object_id="d1").is_meaningful is True


def test_matches_same_session() -> None:
    a = BusinessKey(session_id="s1", skill_id="k1", business_object_id="d1")
    b = BusinessKey(session_id="s1", skill_id="k1", business_object_id="d1")
    assert a.matches(b)


def test_matches_different_session() -> None:
    a = BusinessKey(session_id="s1")
    b = BusinessKey(session_id="s2")
    assert not a.matches(b)


def test_matches_prefix_semantics() -> None:
    """Empty skill_id / object_id matches anything in that field."""
    a = BusinessKey(session_id="s1")
    b = BusinessKey(session_id="s1", skill_id="k1", business_object_id="d1")
    assert a.matches(b)
    assert b.matches(a)


def test_matches_different_skill() -> None:
    a = BusinessKey(session_id="s1", skill_id="k1")
    b = BusinessKey(session_id="s1", skill_id="k2")
    assert not a.matches(b)


# ─── Wire format ────────────────────────────────────────────────────────────


def test_to_header_three_fields() -> None:
    k = BusinessKey(session_id="s1", skill_id="k1", business_object_id="d1")
    assert k.to_header() == "s1|k1|d1"


def test_to_header_empty_optional() -> None:
    k = BusinessKey(session_id="s1")
    assert k.to_header() == "s1||"


def test_parse_header_round_trip() -> None:
    original = BusinessKey(session_id="s1", skill_id="k1", business_object_id="d1")
    parsed = parse_business_key_header(original.to_header())
    assert parsed == original


def test_parse_header_missing() -> None:
    assert parse_business_key_header(None) is None
    assert parse_business_key_header("") is None


def test_parse_header_malformed_raises() -> None:
    with pytest.raises(ValueError, match="3 pipe-separated"):
        parse_business_key_header("only_one_field")
    with pytest.raises(ValueError, match="3 pipe-separated"):
        parse_business_key_header("a|b")  # only 2 fields


def test_serialize_business_key_helper() -> None:
    k = BusinessKey(session_id="s1", skill_id="k1", business_object_id="d1")
    assert serialize_business_key(k) == "s1|k1|d1"


# ─── Context propagation ────────────────────────────────────────────────────


def test_get_current_returns_none_by_default() -> None:
    # Default contextvar value is None.
    assert get_current_business_key() is None


def test_set_and_reset() -> None:
    key = BusinessKey(session_id="s1", skill_id="k1")
    token = set_current_business_key(key)
    try:
        assert get_current_business_key() == key
    finally:
        reset_current_business_key(token)
    assert get_current_business_key() is None


def test_business_key_scope() -> None:
    key = BusinessKey(session_id="s1", business_object_id="d1")
    assert get_current_business_key() is None
    with business_key_scope(key):
        assert get_current_business_key() == key
        # Nested scope replaces the parent (contextvar semantics).
        nested = BusinessKey(session_id="s1", skill_id="other")
        with business_key_scope(nested):
            assert get_current_business_key() == nested
    # After exit, back to None.
    assert get_current_business_key() is None


def test_business_key_scope_restores_parent() -> None:
    outer = BusinessKey(session_id="s-outer", skill_id="k-outer")
    inner = BusinessKey(session_id="s-inner", skill_id="k-inner")
    with business_key_scope(outer):
        with business_key_scope(inner):
            assert get_current_business_key() == inner
        assert get_current_business_key() == outer


def test_business_key_scope_none_clears() -> None:
    """``business_key_scope(None)`` clears any active key for the block."""
    with business_key_scope(BusinessKey(session_id="s1")):
        with business_key_scope(None):
            assert get_current_business_key() is None
        assert get_current_business_key() is not None


def test_require_raises_when_unbound() -> None:
    # Ensure clean state.
    assert get_current_business_key() is None
    with pytest.raises(LookupError, match="no active business key"):
        require_current_business_key()


def test_require_returns_when_bound() -> None:
    key = BusinessKey(session_id="s1", skill_id="k1")
    with business_key_scope(key):
        assert require_current_business_key() == key


# ─── Edge: 256-char boundary ────────────────────────────────────────────────


def test_length_at_max_is_ok() -> None:
    """A field exactly at the length cap is accepted (boundary)."""
    k = BusinessKey(session_id="x" * 256)
    assert len(k.session_id) == 256


def test_length_just_over_max_rejected() -> None:
    with pytest.raises(ValueError, match="exceeds max"):
        BusinessKey(session_id="x" * 257)
