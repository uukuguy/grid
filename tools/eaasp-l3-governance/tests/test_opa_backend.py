"""Unit tests for the OPA backend adapter (v3.11.1 / ADR-V2-034).

Coverage matrix (per spec / D-19..D-22):

- Happy path: POST /v1/data/governance/decision returns a 200 with the
 4-field envelope → adapter normalizes to OPADecision and returns it.
- Fail-closed modes (5):
    1. connection refused (httpx.ConnectError)
    2. timeout (httpx.TimeoutException)
    3. non-2xx (HTTP 500)
    4. parse error (invalid JSON body)
    5. missing required field (no "allow" in body)
- Strict-by-default (ADR-V2-028):
    - L3_OPA_URL missing → RuntimeError
    - L3_OPA_TIMEOUT_SECONDS missing → RuntimeError
    - L3_OPA_TIMEOUT_SECONDS zero / negative / non-numeric → RuntimeError
    - L3_OPA_BUNDLE_DIR pointing at a non-existent path → RuntimeError
- Environment-independent parse helpers (parse_timeout_seconds, etc.).
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
import pytest

from eaasp_l3_governance.opa_backend import (
    CAUSE_CONNECTION_REFUSED,
    CAUSE_MISSING_FIELD,
    CAUSE_NON_2XX,
    CAUSE_PARSE_ERROR,
    CAUSE_TIMEOUT,
    DECISION_ALLOW,
    DECISION_APPROVAL,
    DECISION_DENY,
    DEFAULT_OPA_ALLOWED_HOSTS,
    OPABackend,
    OPAConfig,
    OPADecision,
    normalize_base_url,
    parse_timeout_seconds,
    require_env,
    sanitized_origin,
    validate_opa_url,
)


# ─── Helpers ────────────────────────────────────────────────────────────────


def _mock_transport(handler):  # type: ignore[no-untyped-def]
    """Build an httpx.AsyncClient wired to a synchronous ``handler`` callable.

    The handler receives an httpx.Request and returns either an
    httpx.Response (for 2xx / non-2xx paths) or raises an exception (for
    connection-refused / timeout paths).
    """
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _ok_response(payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json=payload)


def _err_response(status: int, body: str = "boom") -> httpx.Response:
    return httpx.Response(status, text=body)


def _make_backend(handler):  # type: ignore[no-untyped-def]
    cfg = OPAConfig(
        base_url="http://127.0.0.1:18181",
        timeout_seconds=2.0,
        bundle_dir="/tmp",
    )
    return OPABackend(cfg, client=_mock_transport(handler))


# ─── Happy path ─────────────────────────────────────────────────────────────


async def test_evaluate_happy_path_allow() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        # OPA REST v1 path
        assert req.url.path == "/v1/data/governance/decision"
        assert req.method == "POST"
        return _ok_response(
            {
                "result": {
                    "allow": True,
                    "decision": "allow",
                    "reason": "read risk auto-allowed",
                    "obligations": [],
                }
            }
        )

    backend = _make_backend(handler)
    result = await backend.evaluate(
        {
            "session_id": "sess_1",
            "hook_id": "h_1",
            "tool_name": "scada_read_snapshot",
            "risk_level": "read",
            "action_preview": "read xfmr-042",
            "mode": "enforce",
        }
    )
    assert isinstance(result, OPADecision)
    assert result.allow is True
    assert result.decision == DECISION_ALLOW
    assert result.reason == "read risk auto-allowed"
    assert result.obligations == []
    assert result.infra_unavailable is False
    assert result.cause is None
    assert result.raw["allow"] is True
    await backend.aclose()


async def test_evaluate_happy_path_approval_with_obligations() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        return _ok_response(
            {
                "result": {
                    "allow": False,
                    "decision": "approval",
                    "reason": "write_external requires human approval",
                    "obligations": ["notify:admin", "redact:pii"],
                }
            }
        )

    backend = _make_backend(handler)
    result = await backend.evaluate(
        {
            "session_id": "sess_1",
            "hook_id": "h_1",
            "tool_name": "scada_set_setpoint",
            "risk_level": "write_external",
            "action_preview": "xfmr-042/temperature_limit_c=70.0",
            "mode": "enforce",
        }
    )
    assert result.allow is False
    assert result.decision == DECISION_APPROVAL
    assert result.obligations == ["notify:admin", "redact:pii"]
    assert result.infra_unavailable is False
    await backend.aclose()


async def test_evaluate_happy_path_deny() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        return _ok_response(
            {
                "result": {
                    "allow": False,
                    "decision": "deny",
                    "reason": "tool blocked by deny-list",
                    "obligations": ["log:incident"],
                }
            }
        )

    backend = _make_backend(handler)
    result = await backend.evaluate(
        {
            "tool_name": "rm_rf",
            "risk_level": "write_external",
            "action_preview": "rm -rf /",
            "mode": "enforce",
        }
    )
    assert result.decision == DECISION_DENY
    assert result.reason == "tool blocked by deny-list"
    await backend.aclose()


async def test_evaluate_bare_top_level_body_accepted() -> None:
    """OPA may return a flat {allow, decision, reason, obligations} without
    the 'result' wrapper (e.g. when queried via a different REST endpoint).
    The adapter MUST normalize both shapes."""
    async def handler(req: httpx.Request) -> httpx.Response:
        return _ok_response(
            {
                "allow": True,
                "decision": "allow",
                "reason": "bare body",
                "obligations": [],
            }
        )

    backend = _make_backend(handler)
    result = await backend.evaluate({"tool_name": "x"})
    assert result.decision == DECISION_ALLOW
    assert result.reason == "bare body"
    await backend.aclose()


# ─── 5 failure modes ────────────────────────────────────────────────────────


async def test_fail_closed_connection_refused() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=req)

    backend = _make_backend(handler)
    result = await backend.evaluate({"tool_name": "x"})
    assert result.infra_unavailable is True
    assert result.cause == CAUSE_CONNECTION_REFUSED
    assert result.allow is False
    assert result.decision == DECISION_DENY
    assert "infra_unavailable" in result.reason
    assert result.cause in result.reason
    assert result.obligations == []
    await backend.aclose()


async def test_fail_closed_timeout() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out", request=req)

    backend = _make_backend(handler)
    result = await backend.evaluate({"tool_name": "x"})
    assert result.infra_unavailable is True
    assert result.cause == CAUSE_TIMEOUT
    assert result.allow is False
    assert result.decision == DECISION_DENY
    assert "timeout" in result.reason.lower()
    await backend.aclose()


async def test_fail_closed_non_2xx_http_500() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        return _err_response(500, "internal error")

    backend = _make_backend(handler)
    result = await backend.evaluate({"tool_name": "x"})
    assert result.infra_unavailable is True
    assert result.cause == CAUSE_NON_2XX
    assert result.allow is False
    assert result.decision == DECISION_DENY
    assert "500" in result.reason
    await backend.aclose()


async def test_fail_closed_non_2xx_http_404() -> None:
    """Bundle not found (404) is an ADR-V2-034 §4 fail-closed case."""
    async def handler(req: httpx.Request) -> httpx.Response:
        return _err_response(404, "policies bundle not found")

    backend = _make_backend(handler)
    result = await backend.evaluate({"tool_name": "x"})
    assert result.infra_unavailable is True
    assert result.cause == CAUSE_NON_2XX
    assert "404" in result.reason
    await backend.aclose()


async def test_fail_closed_parse_error() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        # Return 200 with body that is NOT valid JSON.
        return httpx.Response(200, content=b"not-json-body")

    backend = _make_backend(handler)
    result = await backend.evaluate({"tool_name": "x"})
    assert result.infra_unavailable is True
    assert result.cause == CAUSE_PARSE_ERROR
    assert result.allow is False
    assert result.decision == DECISION_DENY
    await backend.aclose()


async def test_fail_closed_missing_field_allow() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        # 200 with valid JSON but missing "allow" — adapter must fail-closed.
        return _ok_response(
            {
                "result": {
                    "decision": "deny",
                    "reason": "missing allow",
                    "obligations": [],
                }
            }
        )

    backend = _make_backend(handler)
    result = await backend.evaluate({"tool_name": "x"})
    assert result.infra_unavailable is True
    assert result.cause == CAUSE_MISSING_FIELD
    assert "allow" in result.reason
    await backend.aclose()


async def test_fail_closed_missing_field_decision() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        return _ok_response(
            {
                "result": {
                    "allow": False,
                    "reason": "missing decision",
                    "obligations": [],
                }
            }
        )

    backend = _make_backend(handler)
    result = await backend.evaluate({"tool_name": "x"})
    assert result.infra_unavailable is True
    assert result.cause == CAUSE_MISSING_FIELD
    assert "decision" in result.reason
    await backend.aclose()


async def test_fail_closed_invalid_decision_value() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        return _ok_response(
            {
                "result": {
                    "allow": False,
                    "decision": "unknown_state",
                    "reason": "OPA emitted an unsupported decision",
                    "obligations": [],
                }
            }
        )

    backend = _make_backend(handler)
    result = await backend.evaluate({"tool_name": "x"})
    assert result.infra_unavailable is True
    assert result.cause == CAUSE_MISSING_FIELD
    assert "unknown_state" in result.reason
    await backend.aclose()


async def test_fail_closed_allow_true_with_non_allow_decision() -> None:
    """Cross-field invariant: allow=True ⇔ decision='allow' (forward direction).

    OPA returning allow=True with decision="deny" is treated as a
    malformed response — fail-closed with infra_unavailable=true so the
    PolicyEngine sees it as a deniable infrastructure outcome.
    Security review [Issue 2 / HIGH]: this is one half of the
    bidirectional invariant — see also ``test_fail_closed_allow_false_with_allow_decision``
    for the reverse direction.
    """
    async def handler(req: httpx.Request) -> httpx.Response:
        return _ok_response(
            {
                "result": {
                    "allow": True,
                    "decision": "deny",
                    "reason": "invalid: allow=True with decision=deny",
                    "obligations": [],
                }
            }
        )

    backend = _make_backend(handler)
    result = await backend.evaluate({"tool_name": "x"})
    assert result.infra_unavailable is True
    assert result.cause == CAUSE_MISSING_FIELD
    assert "invariant" in result.reason
    assert "allow=True" in result.reason
    await backend.aclose()


async def test_fail_closed_allow_false_with_allow_decision() -> None:
    """Security review [Issue 2 / HIGH] regression: allow=False ⇔ decision='allow'.

    OPA returning allow=False with decision='allow' is the symmetric
    half of the bidirectional invariant. Previously this slipped
    through silently — the agent thought it had been authorized
    (decision='allow') but the gate was closed (allow=False). Now it
    is fail-closed with infra_unavailable=true so the PolicyEngine's
    authorize gate (``decision=='allow' AND allow is True``) sees a
    deniable infrastructure outcome.
    """
    async def handler(req: httpx.Request) -> httpx.Response:
        return _ok_response(
            {
                "result": {
                    "allow": False,
                    "decision": "allow",
                    "reason": "symmetric invariant violation: allow=False but decision='allow'",
                    "obligations": [],
                }
            }
        )

    backend = _make_backend(handler)
    result = await backend.evaluate({"tool_name": "x"})
    # Bidirectional check fires: fail-closed with the missing-field cause.
    assert result.infra_unavailable is True
    assert result.cause == CAUSE_MISSING_FIELD
    assert "invariant" in result.reason
    assert "allow=False" in result.reason
    await backend.aclose()


async def test_fail_closed_response_not_object() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["just", "a", "list"])

    backend = _make_backend(handler)
    result = await backend.evaluate({"tool_name": "x"})
    assert result.infra_unavailable is True
    assert result.cause == CAUSE_PARSE_ERROR
    await backend.aclose()


# ─── Strict-by-default (ADR-V2-028) ─────────────────────────────────────────


def test_require_env_returns_value_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("L3_OPA_URL", "http://127.0.0.1:18181")
    assert require_env("L3_OPA_URL") == "http://127.0.0.1:18181"


def test_require_env_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("L3_OPA_URL", raising=False)
    with pytest.raises(RuntimeError, match="L3_OPA_URL"):
        require_env("L3_OPA_URL")


def test_require_env_raises_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("L3_OPA_URL", "")
    with pytest.raises(RuntimeError, match="L3_OPA_URL"):
        require_env("L3_OPA_URL")


def test_parse_timeout_seconds_accepts_float_str() -> None:
    assert parse_timeout_seconds("2.0") == 2.0
    assert parse_timeout_seconds("0.5") == 0.5
    assert parse_timeout_seconds("1.5e+0") == 1.5
    assert parse_timeout_seconds("  3.0  ") == 3.0  # whitespace tolerant


def test_parse_timeout_seconds_rejects_non_numeric() -> None:
    with pytest.raises(RuntimeError, match="positive float"):
        parse_timeout_seconds("two")
    with pytest.raises(RuntimeError, match="positive float"):
        parse_timeout_seconds("")
    with pytest.raises(RuntimeError, match="positive float"):
        parse_timeout_seconds("2x0")


def test_parse_timeout_seconds_rejects_zero_or_negative() -> None:
    with pytest.raises(RuntimeError, match="> 0"):
        parse_timeout_seconds("0")
    with pytest.raises(RuntimeError, match="> 0"):
        parse_timeout_seconds("-1.0")


def test_normalize_base_url_strips_trailing_slash() -> None:
    assert normalize_base_url("http://127.0.0.1:18181") == "http://127.0.0.1:18181"
    assert normalize_base_url("http://127.0.0.1:18181/") == "http://127.0.0.1:18181"
    assert (
        normalize_base_url("http://127.0.0.1:18181///")
        == "http://127.0.0.1:18181"
    )


def test_from_env_raises_when_url_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("L3_OPA_URL", raising=False)
    monkeypatch.setenv("L3_OPA_TIMEOUT_SECONDS", "2.0")
    monkeypatch.setenv("L3_OPA_BUNDLE_DIR", "/tmp")
    with pytest.raises(RuntimeError, match="L3_OPA_URL"):
        OPABackend.from_env()


def test_from_env_raises_when_timeout_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("L3_OPA_URL", "http://127.0.0.1:18181")
    monkeypatch.delenv("L3_OPA_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("L3_OPA_BUNDLE_DIR", "/tmp")
    with pytest.raises(RuntimeError, match="L3_OPA_TIMEOUT_SECONDS"):
        OPABackend.from_env()


def test_from_env_raises_when_bundle_dir_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("L3_OPA_URL", "http://127.0.0.1:18181")
    monkeypatch.setenv("L3_OPA_TIMEOUT_SECONDS", "2.0")
    nonexistent = str(tmp_path / "does-not-exist-anywhere")
    monkeypatch.setenv("L3_OPA_BUNDLE_DIR", nonexistent)
    with pytest.raises(RuntimeError, match="L3_OPA_BUNDLE_DIR"):
        OPABackend.from_env()


def test_from_env_raises_when_timeout_invalid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("L3_OPA_URL", "http://127.0.0.1:18181")
    monkeypatch.setenv("L3_OPA_TIMEOUT_SECONDS", "not-a-number")
    monkeypatch.setenv("L3_OPA_BUNDLE_DIR", str(tmp_path))
    with pytest.raises(RuntimeError, match="L3_OPA_TIMEOUT_SECONDS"):
        OPABackend.from_env()


def test_from_env_succeeds_with_all_envs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("L3_OPA_URL", "http://127.0.0.1:18181/")
    monkeypatch.setenv("L3_OPA_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("L3_OPA_BUNDLE_DIR", str(tmp_path))
    backend = OPABackend.from_env()
    assert backend.config.base_url == "http://127.0.0.1:18181"  # trailing / stripped
    assert backend.config.timeout_seconds == 2.5
    assert backend.config.bundle_dir == str(tmp_path)


# ─── Constructor / lifecycle ────────────────────────────────────────────────


async def test_aclose_is_noop_when_client_injected() -> None:
    """When the caller injects an httpx client, aclose() must NOT close it."""
    async def handler(req: httpx.Request) -> httpx.Response:
        return _ok_response({"result": {"allow": True, "decision": "allow", "reason": "x", "obligations": []}})

    injected = _mock_transport(handler)
    backend = OPABackend(
        OPAConfig("http://x", 1.0, "/tmp"),
        client=injected,
    )
    await backend.aclose()
    # Client still usable — proves we did not close it.
    resp = await injected.get("http://x/health")
    assert resp.status_code == 200


async def test_aclose_closes_owned_client() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        return _ok_response({"result": {"allow": True, "decision": "allow", "reason": "x", "obligations": []}})

    backend = _make_backend(handler)
    await backend.aclose()
    # Calling again must be safe (no double-close crash).
    await backend.aclose()


async def test_evaluate_payload_includes_risk_level_and_mode() -> None:
    captured: dict[str, Any] = {}

    async def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.content)
        return _ok_response({"result": {"allow": True, "decision": "allow", "reason": "x", "obligations": []}})

    backend = _make_backend(handler)
    await backend.evaluate(
        {
            "session_id": "sess_xyz",
            "hook_id": "h_42",
            "tool_name": "scada_read_snapshot",
            "risk_level": "read",
            "action_preview": "read xfmr-042",
            "mode": "shadow",
            "agent_id": "agent_42",
            "skill_id": "skill_42",
        }
    )
    await backend.aclose()
    # OPA REST v1 contract: the request body is wrapped in ``{"input": ...}``
    # so the policy can use the ``input`` global. The adapter wraps the
    # caller's envelope; the test verifies the wrapping is in place and
    # the input fields are forwarded verbatim.
    assert "input" in captured["body"], f"expected OPA input envelope; got {captured['body']!r}"
    inner = captured["body"]["input"]
    assert inner["session_id"] == "sess_xyz"
    assert inner["risk_level"] == "read"
    assert inner["mode"] == "shadow"
    assert inner["agent_id"] == "agent_42"
    assert inner["skill_id"] == "skill_42"



# ─── Security [Issue 3 / MEDIUM] — URL guard + sanitized origin ─────────────


def test_validate_opa_url_accepts_loopback() -> None:
    """The default loopback allowlist accepts both 127.0.0.1 and localhost.

    Both forms are the canonical sidecar reach path per ADR-V2-034.
    """
    assert validate_opa_url("http://127.0.0.1:18181") == "http://127.0.0.1:18181"
    assert validate_opa_url("http://localhost:18181") == "http://localhost:18181"
    assert validate_opa_url("http://localhost:18181/") == "http://localhost:18181"
    assert validate_opa_url("https://127.0.0.1:18181") == "https://127.0.0.1:18181"


def test_validate_opa_url_rejects_userinfo() -> None:
    """Userinfo (user:pass@host) MUST be rejected — credentials in URLs
    are commonly exfiltrated to logs."""
    with pytest.raises(RuntimeError, match="userinfo"):
        validate_opa_url("http://admin:secret@127.0.0.1:18181")


def test_validate_opa_url_rejects_query_string() -> None:
    """Query string MUST be rejected — OPA REST v1 takes the path in the
    URL, not the query."""
    with pytest.raises(RuntimeError, match="query"):
        validate_opa_url("http://127.0.0.1:18181?token=abc")


def test_validate_opa_url_rejects_fragment() -> None:
    """Fragment MUST be rejected — fragments are client-side and
    commonly carry tokens."""
    with pytest.raises(RuntimeError, match="fragment"):
        validate_opa_url("http://127.0.0.1:18181#token")


def test_validate_opa_url_rejects_disallowed_scheme() -> None:
    """Only http/https are accepted; file:// / ftp:// etc. are blocked."""
    for bad in ("file:///etc/passwd", "ftp://127.0.0.1", "javascript:alert(1)"):
        with pytest.raises(RuntimeError, match="scheme"):
            validate_opa_url(bad)


def test_validate_opa_url_rejects_disallowed_host() -> None:
    """Default loopback allowlist blocks arbitrary hosts."""
    with pytest.raises(RuntimeError, match="allowed-host"):
        validate_opa_url("http://example.com:18181")
    with pytest.raises(RuntimeError, match="allowed-host"):
        validate_opa_url("http://192.168.1.1:18181")


def test_validate_opa_url_accepts_extended_allowlist() -> None:
    """Operators can extend the allowlist via the ``allowed_hosts`` kwarg
    (L3_OPA_ALLOWED_HOSTS env var in production)."""
    extended = frozenset({"127.0.0.1", "localhost", "opa.internal.example.com"})
    assert validate_opa_url(
        "http://opa.internal.example.com:18181", allowed_hosts=extended
    ) == "http://opa.internal.example.com:18181"
    # Default still rejects the extended host.
    with pytest.raises(RuntimeError, match="allowed-host"):
        validate_opa_url("http://opa.internal.example.com:18181")


def test_default_allowed_hosts_is_loopback_only() -> None:
    """The default allowlist is exactly the loopback set per ADR-V2-034."""
    assert DEFAULT_OPA_ALLOWED_HOSTS == frozenset({"127.0.0.1", "localhost"})


def test_sanitized_origin_drops_userinfo_query_fragment() -> None:
    """The sanitized-origin helper is the safe way to log the URL."""
    assert sanitized_origin("http://127.0.0.1:18181") == "http://127.0.0.1:18181"
    assert sanitized_origin("http://localhost:18181") == "http://localhost:18181"
    # Even if a credentials-bearing URL slipped through ``validate_opa_url``,
    # ``sanitized_origin`` still drops userinfo / query / fragment.
    assert (
        sanitized_origin("http://admin:secret@127.0.0.1:18181?token=abc#frag")
        == "http://127.0.0.1:18181"
    )
    # Unparseable input → safe placeholder, never the raw input.
    assert sanitized_origin(":::not a url") == "<unparseable>"
