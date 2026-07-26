"""OPA backend adapter — production Rego decision backend for L3 governance.

Per ADR-V2-034 (Accepted 2026-07-26), EAASP L3 governance ships with a sidecar
Open Policy Agent (OPA) on ``http://127.0.0.1:18181``. This module is the
*adapter* — callers (PolicyEngine, API) wrap a request envelope and delegate
the actual risk-classification + allow/approval/deny decision computation to
OPA via the standard ``POST /v1/data/governance/decision`` REST endpoint.

Contract (frozen in ADR-V2-034 Decision §4):

- The HTTP envelope is a single JSON object (``request``) that contains the
  raw risk + tool + session context. OPA's Rego policy returns
  ``{allow, decision, reason, obligations}`` where ``decision`` is one of
  ``allow`` / ``approval`` / ``deny`` and ``obligations`` is a list of strings.
- Failure modes (connection refused, timeout, non-2xx, parse error, bundle
  not found) MUST trigger fail-closed: the adapter returns a synthesized
  deny result with ``infra_unavailable=True`` and a stable reason string,
  and emits a structured trace so the audit ledger can carry the
  ``infra_unavailable=true`` row per ADR-V2-034 §4.

Strict-by-default (per ADR-V2-028):

- ``L3_OPA_URL`` and ``L3_OPA_TIMEOUT_SECONDS`` are required env vars. If
  either is missing or unparseable, ``OPABackend.from_env()`` raises a
  clear ``RuntimeError`` (no silent fallback to in-process).
- ``L3_OPA_BUNDLE_DIR`` indicates the in-repo Rego bundle directory. The
  adapter does NOT load bundles itself (the OPA sidecar does at process
  start via its own ``--bundle`` flag or ``PUT /v1/policies/...``), but the
  path is validated to exist at construction so a misconfiguration is
  surfaced at startup.

The adapter is intentionally transport-thin: it does not own a circuit
breaker, does not cache decision results, and does not pre-warm the bundle.
Those concerns are deferred to 03.11.2 / 03.11.3.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx
from loguru import logger


# ─── Public surface — failure cause names (stable identifiers) ──────────────
# These are matched by the audit ledger and by the fail-closed tests. They
# are part of the public contract — DO NOT rename without bumping a version
# key in the audit row payload.

INFRA_UNAVAILABLE = "infra_unavailable"
DECISION_DENY = "deny"
DECISION_ALLOW = "allow"
DECISION_APPROVAL = "approval"

# Per-cause reason strings. Stable identifiers consumed by the audit ledger.
CAUSE_CONNECTION_REFUSED = "opa_connection_refused"
CAUSE_TIMEOUT = "opa_timeout"
CAUSE_NON_2XX = "opa_non_2xx"
CAUSE_PARSE_ERROR = "opa_parse_error"
CAUSE_BUNDLE_NOT_FOUND = "opa_bundle_not_found"
CAUSE_MISSING_FIELD = "opa_response_missing_field"


# ─── Configuration ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OPAConfig:
    """Resolved OPA backend configuration.

    All fields are required; missing values surface as ``RuntimeError`` from
    ``OPABackend.from_env()`` per ADR-V2-028 strict-by-default.
    """

    base_url: str
    timeout_seconds: float
    bundle_dir: str


def require_env(name: str) -> str:
    """Return the raw env-var value or raise ``RuntimeError`` per ADR-V2-028.

    ``os.environ`` lookup only — no fallback, no default discovery. The
    missing-name case is the most common misconfiguration and must surface a
    clear, actionable error: ``L3_OPA_URL is required (ADR-V2-028)``.
    """
    value = os.environ.get(name)
    if value is None or value == "":
        raise RuntimeError(
            f"{name} is required (ADR-V2-028 strict-by-default; "
            f"set it in .env or your shell environment)"
        )
    return value


def parse_timeout_seconds(raw: str) -> float:
    """Parse a ``L3_OPA_TIMEOUT_SECONDS`` value into a positive float.

    Defensive against:
    - Whitespace / non-numeric input (raises ``RuntimeError``).
    - Zero or negative values (raises ``RuntimeError``).
    - Scientific notation is supported (``1.5e+0``).

    Per ADR-V2-028 strict-by-default, an invalid value must fail closed
    (here: fail init) rather than silently coercing to a default.
    """
    try:
        value = float(raw.strip())
    except (AttributeError, ValueError) as exc:
        raise RuntimeError(
            f"L3_OPA_TIMEOUT_SECONDS must be a positive float, got {raw!r}"
        ) from exc
    if value <= 0:
        raise RuntimeError(
            f"L3_OPA_TIMEOUT_SECONDS must be > 0, got {value!r}"
        )
    return value


def normalize_base_url(raw: str) -> str:
    """Strip trailing slashes so callers can compose ``{base_url}/v1/data/...``.

    Mirrors the convention used by httpx + L2 memory engine ``L2_BASE_URL``.
    """
    return raw.rstrip("/")


# ─── Decision result ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OPADecision:
    """Normalized OPA decision result.

    Fields:
    - ``allow`` is the boolean the runtime path checks (True ⇒ proceed,
      False ⇒ block / gate / fail-closed).
    - ``decision`` is the named state (``allow`` / ``approval`` / ``deny``)
      used for SSE events and audit rows.
    - ``reason`` is a human-readable string (currently used for the rationale
      field in the audit ledger).
    - ``obligations`` is a list of obligation strings (OPA may emit
      ``"notify:admin"``, ``"redact:pii"`` etc.). The MVP consumer
      (PolicyEngine) records them in the audit row.
    - ``infra_unavailable`` is True IFF the adapter failed to reach OPA
      (timeout, connection refused, parse error, etc.) and the result is
      a synthesized deny. The audit row must carry this flag so operators
      can distinguish "policy denied" from "policy engine was down".
    - ``cause`` is one of the ``CAUSE_*`` constants above when
      ``infra_unavailable=True``; None otherwise. Stable identifier — DO
      NOT rename.
    - ``raw`` is the original OPA response body (or the synthesized body
      when fail-closed). Kept for diagnostics + tests.
    """

    allow: bool
    decision: str
    reason: str
    obligations: list[str] = field(default_factory=list)
    infra_unavailable: bool = False
    cause: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


# ─── Synthesized fail-closed payload ─────────────────────────────────────────


def _fail_closed(cause: str, detail: str) -> OPADecision:
    """Return a synthesized deny decision marked as infra-unavailable.

    The ``reason`` is a composite so the audit ledger surfaces both the
    stable ``cause`` identifier AND the human-readable detail. The detail
    is bounded to 200 chars to keep audit rows compact.
    """
    bounded_detail = detail[:200] if detail else ""
    reason = f"infra_unavailable:{cause}: {bounded_detail}".strip()
    return OPADecision(
        allow=False,
        decision=DECISION_DENY,
        reason=reason,
        obligations=[],
        infra_unavailable=True,
        cause=cause,
        raw={"fail_closed": True, "cause": cause, "detail": bounded_detail},
    )


# ─── Adapter ────────────────────────────────────────────────────────────────


class OPABackend:
    """Adaptive client for the L3 governance OPA sidecar.

    Usage (production):

    >>> backend = OPABackend.from_env()  # raises RuntimeError if env missing
    >>> result = await backend.evaluate(request_payload)
    >>> if result.infra_unavailable:
    ...     # audit row will carry infra_unavailable=true and result.cause
    ...     ...

    Usage (tests): pass an explicit ``OPAConfig`` and optionally an
    ``httpx.AsyncClient`` (e.g. a ``MockTransport``) to inject failure modes
    without touching real network.
    """

    def __init__(
        self,
        config: OPAConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout_seconds),
        )

    # ─── Construction ──────────────────────────────────────────────────────

    @classmethod
    def from_env(cls) -> "OPABackend":
        """Build an ``OPABackend`` from required env vars.

        Required:
        - ``L3_OPA_URL`` — base URL including scheme, e.g.
          ``http://127.0.0.1:18181``.
        - ``L3_OPA_TIMEOUT_SECONDS`` — positive float; total timeout for
          the per-request httpx call.
        - ``L3_OPA_BUNDLE_DIR`` — directory holding the in-repo Rego
          bundles. Existence is verified at construction; the bundle
          itself is loaded by OPA, not by this adapter.

        Per ADR-V2-028 strict-by-default, any missing or invalid env var
        raises ``RuntimeError`` — there is no silent fallback. Callers
        that want dev/test fallback should NOT use this constructor.
        """
        base_url = normalize_base_url(require_env("L3_OPA_URL"))
        timeout = parse_timeout_seconds(require_env("L3_OPA_TIMEOUT_SECONDS"))
        bundle_dir = require_env("L3_OPA_BUNDLE_DIR")
        if not os.path.isdir(bundle_dir):
            raise RuntimeError(
                f"L3_OPA_BUNDLE_DIR does not exist or is not a directory: "
                f"{bundle_dir!r}"
            )
        return cls(
            OPAConfig(
                base_url=base_url,
                timeout_seconds=timeout,
                bundle_dir=bundle_dir,
            )
        )

    @property
    def config(self) -> OPAConfig:
        return self._config

    async def aclose(self) -> None:
        """Close the underlying httpx client if we own it.

        Safe to call when the client was injected (no-op in that case).
        """
        if self._owns_client:
            await self._client.aclose()

    # ─── Public evaluation surface ─────────────────────────────────────────

    async def evaluate(self, request: dict[str, Any]) -> OPADecision:
        """Evaluate a governance decision via OPA.

        ``request`` is the input payload — the contract here is "whatever
        shape the Rego policy expects". For v3.11.1 we expect:

        .. code-block:: json

            {
              "session_id": "sess_...",
              "hook_id": "h_...",
              "tool_name": "scada_set_setpoint",
              "risk_level": "read" | "write_local" | "write_external",
              "action_preview": "...",
              "mode": "enforce" | "shadow",
              "agent_id": "...",
              "skill_id": "..."
            }

        Returns an ``OPADecision``. Any failure mode (connection refused,
        timeout, non-2xx, parse error, missing required field) returns a
        fail-closed decision with ``infra_unavailable=True``.
        """
        url = f"{self._config.base_url}/v1/data/governance/decision"
        headers = {"Content-Type": "application/json"}

        # OPA REST v1 contract: the request body is wrapped in
        # ``{"input": {...}}`` so the policy can use the ``input`` global.
        # We wrap here (rather than asking callers to do it) so the
        # adapter's external contract matches the request envelope we
        # document in the docstring.
        opa_envelope = {"input": request}
        try:
            response = await self._client.post(url, json=opa_envelope, headers=headers)
        except httpx.ConnectError as exc:
            logger.warning(
                "OPA backend connection refused",
                base_url=self._config.base_url,
                detail=str(exc),
            )
            return _fail_closed(CAUSE_CONNECTION_REFUSED, str(exc))
        except httpx.TimeoutException as exc:
            logger.warning(
                "OPA backend timeout",
                base_url=self._config.base_url,
                timeout_seconds=self._config.timeout_seconds,
                detail=str(exc),
            )
            return _fail_closed(CAUSE_TIMEOUT, str(exc))
        except httpx.HTTPError as exc:
            # Catch-all for any other transport-level error (read errors,
            # protocol errors, etc.). Keep the cause stable so the audit
            # ledger can pivot on it.
            logger.warning(
                "OPA backend transport error",
                base_url=self._config.base_url,
                detail=str(exc),
            )
            return _fail_closed(CAUSE_TIMEOUT, str(exc))

        if response.status_code < 200 or response.status_code >= 300:
            detail = (
                f"HTTP {response.status_code}: "
                f"{response.text[:200] if response.text else ''}"
            )
            logger.warning(
                "OPA backend non-2xx response",
                base_url=self._config.base_url,
                status_code=response.status_code,
                detail=detail,
            )
            return _fail_closed(CAUSE_NON_2XX, detail)

        try:
            payload = response.json()
        except (ValueError, TypeError) as exc:
            logger.warning(
                "OPA backend parse error",
                base_url=self._config.base_url,
                detail=str(exc),
            )
            return _fail_closed(CAUSE_PARSE_ERROR, str(exc))

        return _parse_opa_response(payload)

    # ─── Internals ─────────────────────────────────────────────────────────

    async def __aenter__(self) -> "OPABackend":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        await self.aclose()


def _parse_opa_response(payload: Any) -> OPADecision:
    """Normalize a parsed OPA JSON response into an ``OPADecision``.

    Response shape expected (per OPA REST API v1 + the v3.11.1 Rego bundle):

    .. code-block:: json

        {
          "result": {
            "allow": true|false,
            "decision": "allow"|"approval"|"deny",
            "reason": "...",
            "obligations": ["..."]
          }
        }

    A bare top-level ``{allow, decision, reason, obligations}`` is also
    accepted for ergonomics — the adapter extracts the ``result`` envelope
    if present, otherwise treats the top-level dict as the body.

    Unsupported / missing fields → fail-closed (do NOT silently coerce to
    a safe default — the audit trail must say "OPA returned bad data").
    """
    if not isinstance(payload, dict):
        return _fail_closed(
            CAUSE_PARSE_ERROR,
            f"OPA response is not a JSON object: {type(payload).__name__}",
        )

    # OPA REST v1 wraps the policy result under "result" when the query is
    # /v1/data/{path}; the {allow, decision, ...} live under that wrapper.
    body = payload.get("result", payload)
    if not isinstance(body, dict):
        return _fail_closed(
            CAUSE_PARSE_ERROR,
            "OPA response.result is not a JSON object",
        )

    # Required fields. Missing any of these → fail-closed.
    if "allow" not in body:
        return _fail_closed(
            CAUSE_MISSING_FIELD,
            "OPA response missing required field: allow",
        )
    if "decision" not in body:
        return _fail_closed(
            CAUSE_MISSING_FIELD,
            "OPA response missing required field: decision",
        )

    decision_raw = body["decision"]
    if decision_raw not in (DECISION_ALLOW, DECISION_APPROVAL, DECISION_DENY):
        return _fail_closed(
            CAUSE_MISSING_FIELD,
            f"OPA response decision must be one of "
            f"({DECISION_ALLOW!r}, {DECISION_APPROVAL!r}, {DECISION_DENY!r}); "
            f"got {decision_raw!r}",
        )

    allow_value = body["allow"]
    if not isinstance(allow_value, bool):
        return _fail_closed(
            CAUSE_MISSING_FIELD,
            f"OPA response allow must be boolean, got {type(allow_value).__name__}",
        )

    # Cross-field invariant: allow=True MUST imply decision="allow"
    # (OPA's "allow" boolean is the gate; the named state is for
    # audit/observability). If OPA returned allow=True with decision="deny"
    # we surface that as a fail-closed rather than silently re-shaping
    # the response. The reverse (allow=False, decision=approval|deny) is
    # legitimate — both block the action; approval asks for human review.
    if allow_value and decision_raw != DECISION_ALLOW:
        return _fail_closed(
            CAUSE_MISSING_FIELD,
            f"OPA response invariant violated: allow=True requires "
            f"decision='allow', got decision={decision_raw!r}",
        )

    reason = body.get("reason", "")
    if not isinstance(reason, str):
        reason = str(reason)

    obligations_raw = body.get("obligations", [])
    if not isinstance(obligations_raw, list):
        return _fail_closed(
            CAUSE_MISSING_FIELD,
            "OPA response obligations must be a list of strings",
        )
    obligations = [str(o) for o in obligations_raw if isinstance(o, (str, int, float))]

    return OPADecision(
        allow=allow_value,
        decision=decision_raw,
        reason=reason,
        obligations=obligations,
        infra_unavailable=False,
        cause=None,
        raw=body,
    )


__all__ = [
    "OPABackend",
    "OPADecision",
    "OPAConfig",
    "INFRA_UNAVAILABLE",
    "DECISION_ALLOW",
    "DECISION_APPROVAL",
    "DECISION_DENY",
    "CAUSE_CONNECTION_REFUSED",
    "CAUSE_TIMEOUT",
    "CAUSE_NON_2XX",
    "CAUSE_PARSE_ERROR",
    "CAUSE_BUNDLE_NOT_FOUND",
    "CAUSE_MISSING_FIELD",
    "parse_timeout_seconds",
    "normalize_base_url",
    "require_env",
]
