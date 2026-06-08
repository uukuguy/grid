"""Unit tests for eaasp_common.errors.sanitize_errors()."""

from eaasp_common.errors import sanitize_errors


def test_empty_list_returns_empty() -> None:
    assert sanitize_errors([]) == []


def test_normal_errors_pass_through() -> None:
    errors = [{"loc": ["body"], "msg": "required", "type": "missing"}]
    result = sanitize_errors(errors)
    assert result == errors
    # Verify no mutation — result is a new list
    assert result is not errors


def test_ctx_with_exception_is_stringified() -> None:
    """Error with `ctx` containing a ValueError → exception stringified."""
    errors = [{"loc": [], "ctx": {"error": ValueError("test")}}]
    result = sanitize_errors(errors)
    assert result == [{"loc": [], "ctx": {"error": "test"}}]


def test_nested_base_exception_stringified() -> None:
    """Direct BaseException value at top level is stringified."""
    errors = [{"msg": ValueError("direct")}]
    result = sanitize_errors(errors)
    assert result == [{"msg": "direct"}]


def test_mixed_errors() -> None:
    """Mixture of normal fields, exception ctx values, and direct exceptions."""
    errors = [
        {
            "type": "missing",
            "loc": ["field"],
            "ctx": {"error": ValueError("bad")},
            "input": None,
        },
        {
            "msg": "broken",
            "cause": RuntimeError("boom"),
        },
    ]
    result = sanitize_errors(errors)
    assert result == [
        {
            "type": "missing",
            "loc": ["field"],
            "ctx": {"error": "bad"},
            "input": None,
        },
        {
            "msg": "broken",
            "cause": "boom",
        },
    ]
