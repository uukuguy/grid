"""EAASP Business Flow — vertical cross-layer business-context binding.

Per v3.15.1 design (PLATFORM_OBSERVABILITY_DESIGN.md §3.1 / §3.4). The
business flow is the **logical spine** of platform observability: a
single end-to-end business request binds together every cross-layer
event (LLM call, tool call, governance decision, memory write, SSE
chunk) under a stable ``(session_id, skill_id, business_object_id)``
key.

Two parallel IDs coexist on every event:

- ``trace_id`` (W3C) — solves "where in the call chain is the slow part".
- ``business_key`` — solves "where in the business flow did it break".

This module provides:

1. ``BusinessKey`` — frozen dataclass + validation.
2. ``BusinessFlowContext`` — contextvar-based per-task / per-request
   context. All EAASP Python tools can read the active business key
   without threading it through every function signature.
3. ``serialize_business_key`` / ``parse_business_key_header`` — wire
   format for the ``X-Business-Key`` HTTP/gRPC header.
4. ``require_business_key_from_request`` — FastAPI dependency that
   pulls the business key from the request headers and stashes it in
   the contextvar for downstream handlers.

The module is intentionally **dependency-free** (stdlib only) so every
EAASP tool (L2 / L3 / L4 / L5) can import it without taking on extra
deps. The HTTP/gRPC middleware lives in each tool (so the common
package stays transport-agnostic).

Wire format
-----------

The ``X-Business-Key`` header is a single line::

    <session_id>|<skill_id>|<business_object_id>

- ``session_id`` is required; empty header is rejected.
- ``skill_id`` and ``business_object_id`` are optional (empty string OK).
- Pipe (``|``) characters inside a field are not allowed; the parser
  rejects the header rather than silently truncating.

The choice of pipe-with-empty-allowed keeps the wire format
human-readable in debug output while still being parseable by a
single ``str.split('|', 2)`` call.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Iterator

# Max length for any single field — keeps the header bounded and
# guards against pathological inputs (DoS via huge header).
_MAX_FIELD_LEN = 256

# ─── Domain model ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BusinessKey:
    """Vertical cross-layer business-context binding key.

    All three fields are strings. ``session_id`` is mandatory (v3.15
    sets it as the primary join key for cross-table timeline queries);
    the other two are optional — at least one of them should be set
    for the key to be meaningful as a business identifier.

    Validation enforces non-empty ``session_id``, no pipe characters,
    and bounded length on every field. The validator raises ``ValueError``
    on violation (caller decides whether to log-and-drop, return HTTP
    400, etc.).
    """

    session_id: str
    skill_id: str = ""
    business_object_id: str = ""

    def __post_init__(self) -> None:
        if not self.session_id:
            raise ValueError("BusinessKey.session_id must be non-empty")
        for field_name in ("session_id", "skill_id", "business_object_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str):
                raise ValueError(
                    f"BusinessKey.{field_name} must be a str, got {type(value).__name__}"
                )
            if len(value) > _MAX_FIELD_LEN:
                raise ValueError(
                    f"BusinessKey.{field_name} length {len(value)} exceeds max {_MAX_FIELD_LEN}"
                )
            if "|" in value:
                raise ValueError(
                    f"BusinessKey.{field_name} must not contain '|' (reserved as wire separator)"
                )

    # ─── Convenience predicates ────────────────────────────────────────────

    @property
    def is_meaningful(self) -> bool:
        """True iff at least one of skill_id / business_object_id is set.

        A key with only ``session_id`` still routes events to the same
        session timeline but doesn't bind to a business object — useful
        for "infrastructure" flows (health checks, etc.).
        """
        return bool(self.skill_id or self.business_object_id)

    def matches(self, other: "BusinessKey") -> bool:
        """Return True iff both keys refer to the same business flow.

        Matching is prefix-based: a key with empty skill_id matches
        any other key with the same session_id. This lets a session
        start without a skill and acquire one later without breaking
        the timeline query.
        """
        if self.session_id != other.session_id:
            return False
        if self.skill_id and other.skill_id and self.skill_id != other.skill_id:
            return False
        if (
            self.business_object_id
            and other.business_object_id
            and self.business_object_id != other.business_object_id
        ):
            return False
        return True

    def to_header(self) -> str:
        """Render as the wire format used in ``X-Business-Key`` headers.

        Always emits three pipe-separated fields; empty fields are
        emitted as empty strings. Round-trips through
        ``parse_business_key_header``.
        """
        return f"{self.session_id}|{self.skill_id}|{self.business_object_id}"

    def to_dict(self) -> dict[str, str]:
        return {
            "session_id": self.session_id,
            "skill_id": self.skill_id,
            "business_object_id": self.business_object_id,
        }

    def __str__(self) -> str:
        return self.to_header()


# ─── Wire format ────────────────────────────────────────────────────────────


def parse_business_key_header(raw: str | None) -> BusinessKey | None:
    """Parse a wire-format ``X-Business-Key`` header.

    Returns None when:
    - ``raw`` is None or empty (header missing — caller treats as "not
      part of any business flow"; per v3.15.1 design, business_key is
      optional).

    Raises ``ValueError`` when the header is malformed (wrong number
    of fields, invalid characters, length > max). Callers should log
    + drop the header (do not raise to the user) — bad headers are
    treated as missing keys for resilience.
    """
    if raw is None or raw == "":
        return None
    parts = raw.split("|", 2)
    if len(parts) != 3:
        raise ValueError(
            f"X-Business-Key must have 3 pipe-separated fields, got {len(parts)}"
        )
    return BusinessKey(
        session_id=parts[0],
        skill_id=parts[1],
        business_object_id=parts[2],
    )


def serialize_business_key(key: BusinessKey) -> str:
    """Render a ``BusinessKey`` to wire format. Inverse of ``parse_*``."""
    return key.to_header()


# ─── Context propagation ────────────────────────────────────────────────────
#
# A single contextvar holds the *active* business key for the current
# asyncio task. Middleware sets it on request entry and resets it on
# exit. Library code can read it via ``get_current_business_key()``
# without needing the key passed in every function signature.

_business_key_var: contextvars.ContextVar[BusinessKey | None] = contextvars.ContextVar(
    "eaasp_business_key", default=None
)


def set_current_business_key(key: BusinessKey | None) -> contextvars.Token:
    """Set the active business key. Returns the token for ``reset()``."""
    return _business_key_var.set(key)


def reset_current_business_key(token: contextvars.Token) -> None:
    """Restore the prior business key. Call in a ``finally`` after middleware."""
    _business_key_var.reset(token)


def get_current_business_key() -> BusinessKey | None:
    """Return the active business key, or None if none is bound."""
    return _business_key_var.get()


def require_current_business_key() -> BusinessKey:
    """Return the active business key or raise ``LookupError``.

    Use in code paths that REQUIRE a business key to function (e.g.
    cross-layer event tagging). Library code that should still work
    for non-business-flow events uses ``get_current_business_key()``.
    """
    key = _business_key_var.get()
    if key is None:
        raise LookupError("no active business key (set via set_current_business_key)")
    return key


# ─── Helper context manager ────────────────────────────────────────────────


class business_key_scope:
    """Context manager that binds a ``BusinessKey`` for the duration of a block.

    Usage::

        with business_key_scope(my_key):
            ...  # downstream code can call get_current_business_key()
    """

    def __init__(self, key: BusinessKey | None) -> None:
        self._key = key
        self._token: contextvars.Token | None = None

    def __enter__(self) -> "business_key_scope":
        self._token = set_current_business_key(self._key)
        return self

    def __exit__(self, *exc: object) -> None:
        del exc  # unused; context-manager protocol requires this signature
        if self._token is not None:
            reset_current_business_key(self._token)
            self._token = None

    # Make the class async-context-manager compatible too — the
    # asynccontextmanager decorator wraps this class when needed.
    async def __aenter__(self) -> "business_key_scope":
        return self.__enter__()

    async def __aexit__(self, *exc: object) -> None:
        self.__exit__(*exc)


def iter_business_key_contexts() -> Iterator[BusinessKey | None]:
    """Yield the active business key once. Helper for tests."""
    yield get_current_business_key()
