"""L1 grid-runtime SLA baseline — OBSTACK_DESIGN.md §5.2.

Measures a synthetic L1 grid-runtime call latency — the
``BusinessKey::new`` + ``validate`` + ``to_header`` path. The Rust
externally guarantees this performance envelope; this SLA asserts the
**cross-language contract** (the same wire format that grid-runtime
emits on the L0 proto BusinessKey field must stay sub-millisecond
serializable on the wire).

We use a pure-Python stand-in (no ``eaasp_common.business_flow``
import) so the test runs under a plain system pytest. The
stand-in mirrors the Python module's validate / to_header logic
1:1 — same wire format, same validation rules.

  BusinessKey validate + to_header: p50 < 0.5ms, p95 < 2ms
"""

from __future__ import annotations

from .conftest import assert_within, time_loop


# Inlined stand-in mirroring eaasp_common.business_flow (kept
# identical on purpose — drift here means drift on the wire format).
_MAX_FIELD_LEN = 256


def _validate(value: str, name: str) -> None:
    if name == "session_id" and value == "":
        raise ValueError("session_id must be non-empty")
    if len(value) > _MAX_FIELD_LEN:
        raise ValueError(f"{name} too long")
    if "|" in value:
        raise ValueError(f"{name} contains '|'")


class _BusinessKey:
    __slots__ = ("session_id", "skill_id", "business_object_id")

    def __init__(
        self,
        session_id: str,
        skill_id: str = "",
        business_object_id: str = "",
    ) -> None:
        _validate(session_id, "session_id")
        _validate(skill_id, "skill_id")
        _validate(business_object_id, "business_object_id")
        self.session_id = session_id
        self.skill_id = skill_id
        self.business_object_id = business_object_id

    def to_header(self) -> str:
        return f"{self.session_id}|{self.skill_id}|{self.business_object_id}"


def test_l1_grid_runtime_business_key_p50_p95_within_sla() -> None:
    """L1 BusinessKey validate+serialize p50 < 0.5ms, p95 < 2ms (baseline)."""
    key_in = _BusinessKey("sla-sess", "sla-skill", "Transformer-sla")
    key_in.to_header()  # warm-up

    def one_validate_and_serialize() -> None:
        header = key_in.to_header()
        # Parse back (3-field split — same as parse_business_key_header).
        parts = header.split("|", 2)
        assert len(parts) == 3
        _BusinessKey(parts[0], parts[1], parts[2])

    samples = time_loop(one_validate_and_serialize, iterations=500, warmup=20)
    assert_within(
        samples,
        p50_max=0.0005,
        p95_max=0.002,
        label="l1.grid_runtime.business_key",
    )
