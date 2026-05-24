"""Contract v1 — HookEvent.oneof event whitelist gate across 7 runtimes.

Mirror of ``test_chunk_type_contract.py`` for the Phase 5.3 CONTRACT-02
HookEvent additions (SubagentStart=19, TaskCheckpoint=20). The proto
``HookEvent`` message lives in ``hook.proto`` and its ``oneof event``
block enumerates every variant a conformant L1 runtime may emit when
sending hook events to the L3 HookBridge.

Schema-level guards (`test_hook_event_oneof_matches_adr` and
`test_new_event_field_numbers`) lock the proto descriptor against drift.
They run unconditionally regardless of which runtime CI selects via
``--runtime``.

Live-runtime probes are split per-runtime via parametrize so the CI
matrix can hit them tier-by-tier per ADR-V2-025. SubagentStart and
TaskCheckpoint live-emission probes are deferred until the appropriate
fixtures land — for now those parametrized cases skip with a clear
"fixture TBD" message so the case structure is visible at
``pytest --collect-only`` time and ready for a follow-up commit.

Phase 5.3 Task 5.3-01-07.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Same proto-stub sys.path hack as conftest.py — see its module docstring.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_CCRUNTIME_SRC = _REPO_ROOT / "lang" / "claude-code-runtime-python" / "src"
if str(_CCRUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(_CCRUNTIME_SRC))

from claude_code_runtime._proto.eaasp.runtime.v2 import (  # noqa: E402
    hook_pb2,
)

pytestmark = pytest.mark.contract_v1


# ADR-V2-025 §Decision 主表 — 7 active runtimes (hermes frozen, skipped at CI level).
ADR_V2_025_ACTIVE_RUNTIMES = [
    "grid",
    "claude-code",
    "nanobot",
    "pydantic-ai",
    "goose",
    "claw-code",
    "ccb",
]

# Per ADR-V2-025, only these are 主力/样板 — MUST PASS:
TIER_MUST_PASS = {"grid", "claude-code", "nanobot", "pydantic-ai"}
TIER_REFERENCE = {"goose", "claw-code", "ccb"}  # selective xfail allowed


# ---------------------------------------------------------------------------
# ADR-V2-006 §2 + Phase 5.3 CONTRACT-02 — canonical oneof field whitelist.
# When ADR-V2-006 amendments add a hook event, update both this set and
# the proto. The drift guard `test_hook_event_oneof_matches_adr` enforces
# parity.
# ---------------------------------------------------------------------------

ALLOWED_HOOK_EVENT_FIELDS = frozenset(
    {
        "pre_tool_call",
        "post_tool_result",
        "stop",
        "session_start",
        "session_end",
        "pre_policy_deploy",
        "pre_approval",
        "event_received",
        "pre_compact",
        # Phase 5.3 (contract-v1.2.0, ADR-V2-006 amendment):
        "subagent_start",
        "task_checkpoint",
    }
)


# ---------------------------------------------------------------------------
# Guard tests — lock proto descriptor against drift. Run unconditionally.
# ---------------------------------------------------------------------------


def test_hook_event_oneof_matches_adr() -> None:
    """ADR-V2-006 §2 + Phase 5.3 — HookEvent.oneof event MUST match table.

    If a developer adds a oneof variant in ``hook.proto`` without
    updating ``ALLOWED_HOOK_EVENT_FIELDS`` (which mirrors the ADR table),
    this test fails and forces the ADR amendment back in scope.
    """
    oneof = hook_pb2.HookEvent.DESCRIPTOR.oneofs_by_name["event"]
    actual = frozenset(field.name for field in oneof.fields)
    assert actual == ALLOWED_HOOK_EVENT_FIELDS, (
        f"HookEvent.oneof drift detected.\n"
        f"In proto but not ADR table: {actual - ALLOWED_HOOK_EVENT_FIELDS}\n"
        f"In ADR table but not proto: {ALLOWED_HOOK_EVENT_FIELDS - actual}"
    )


def test_new_event_field_numbers() -> None:
    """Pitfall 2 (no-renumber) guard: 5.3 new variants use field 19/20.

    The ADR-V2-021 closed-enum invariant extends to hook.proto oneof
    field numbers — additive only, no renumber. Lock the two 5.3
    additions at their assigned wire numbers.
    """
    oneof = hook_pb2.HookEvent.DESCRIPTOR.oneofs_by_name["event"]
    by_name = {f.name: f.number for f in oneof.fields}
    assert by_name["subagent_start"] == 19, (
        f"subagent_start MUST be wire field 19; got {by_name['subagent_start']}"
    )
    assert by_name["task_checkpoint"] == 20, (
        f"task_checkpoint MUST be wire field 20; got {by_name['task_checkpoint']}"
    )


def test_existing_event_field_numbers_unchanged() -> None:
    """Phase 5.3 additive-only — existing oneof field numbers MUST be stable.

    Pin every pre-5.3 variant's field number so any accidental renumber
    breaks this test long before it ships to runtimes.
    """
    oneof = hook_pb2.HookEvent.DESCRIPTOR.oneofs_by_name["event"]
    by_name = {f.name: f.number for f in oneof.fields}
    assert by_name["pre_tool_call"] == 10
    assert by_name["post_tool_result"] == 11
    assert by_name["stop"] == 12
    assert by_name["session_start"] == 13
    assert by_name["session_end"] == 14
    assert by_name["pre_policy_deploy"] == 15
    assert by_name["pre_approval"] == 16
    assert by_name["event_received"] == 17
    assert by_name["pre_compact"] == 18


# ---------------------------------------------------------------------------
# Payload-shape guards — SubagentStartHook + TaskCheckpointHook MUST be
# top-level flat-struct messages per ADR-V2-006 §2.3 (no nested payload.*).
# ---------------------------------------------------------------------------


def test_subagent_start_hook_has_top_level_fields() -> None:
    """ADR-V2-006 §2.3 — SubagentStartHook payload is top-level flat struct.

    All 5 fields (parent_session_id, subagent_id, subagent_name,
    purpose, depth) must be at the top of the message; there must be no
    nested ``payload`` field that would force consumers to drill in.
    """
    descriptor = hook_pb2.SubagentStartHook.DESCRIPTOR
    field_names = {f.name for f in descriptor.fields}
    expected = {
        "parent_session_id",
        "subagent_id",
        "subagent_name",
        "purpose",
        "depth",
    }
    assert expected.issubset(field_names), (
        f"SubagentStartHook missing required top-level fields: "
        f"{expected - field_names}"
    )
    assert "payload" not in field_names, (
        "SubagentStartHook MUST NOT nest fields under payload.* — "
        "ADR-V2-006 §2.3 mandates flat-struct shape"
    )


def test_task_checkpoint_hook_has_top_level_fields() -> None:
    """ADR-V2-006 §2.3 — TaskCheckpointHook payload is top-level flat struct."""
    descriptor = hook_pb2.TaskCheckpointHook.DESCRIPTOR
    field_names = {f.name for f in descriptor.fields}
    expected = {
        "reason",
        "rounds_completed",
        "total_tool_calls",
        "completed_tools",
        "snapshot_uri",
    }
    assert expected.issubset(field_names), (
        f"TaskCheckpointHook missing required top-level fields: "
        f"{expected - field_names}"
    )
    assert "payload" not in field_names, (
        "TaskCheckpointHook MUST NOT nest fields under payload.* — "
        "ADR-V2-006 §2.3 mandates flat-struct shape"
    )


# ---------------------------------------------------------------------------
# Live-runtime probes — split per runtime via parametrize so the CI matrix
# can run them tier-by-tier. SubagentStart + TaskCheckpoint live-emission
# fixtures land in a follow-up commit; current cases skip with a clear
# message so the inventory is visible at --collect-only time.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("expected_runtime", ADR_V2_025_ACTIVE_RUNTIMES)
def test_subagent_start_envelope_live(
    request: pytest.FixtureRequest,
    expected_runtime: str,
) -> None:
    """ADR-V2-006 §2.3 — SubagentStart envelope shape over live runtime.

    Live-emission verification requires a fixture that triggers a
    sub-agent spawn (e.g., a manifest declaring a subagent task) — that
    fixture is not in scope for Phase 5.3 Task 5.3-01-07. Until the
    fixture lands the descriptor-level guards above are the operative
    contract; this case is parametrized + skipped so the case inventory
    is discoverable.
    """
    cli_runtime = request.config.getoption("--runtime")
    if cli_runtime is None:
        pytest.skip(
            "--runtime not supplied; ADR-V2-025 tier matrix requires --runtime"
        )
    if cli_runtime != expected_runtime:
        pytest.skip(
            f"parametrized expected_runtime={expected_runtime!r} does not match "
            f"CI --runtime={cli_runtime!r}"
        )
    if expected_runtime in TIER_REFERENCE:
        pytest.xfail(
            f"ADR-V2-025 reference tier runtime {expected_runtime!r} may not "
            f"implement subagent spawning — selective xfail allowed"
        )
    pytest.skip(
        "fixture trigger-subagent-spawn TBD; descriptor + payload-shape "
        "guards in this file remain the operative contract for 5.3 MVP"
    )


@pytest.mark.parametrize("expected_runtime", ADR_V2_025_ACTIVE_RUNTIMES)
def test_task_checkpoint_envelope_live(
    request: pytest.FixtureRequest,
    expected_runtime: str,
) -> None:
    """ADR-V2-006 §2.3 — TaskCheckpoint envelope shape over live runtime.

    Same fixture-pending status as ``test_subagent_start_envelope_live``.
    """
    cli_runtime = request.config.getoption("--runtime")
    if cli_runtime is None:
        pytest.skip(
            "--runtime not supplied; ADR-V2-025 tier matrix requires --runtime"
        )
    if cli_runtime != expected_runtime:
        pytest.skip(
            f"parametrized expected_runtime={expected_runtime!r} does not match "
            f"CI --runtime={cli_runtime!r}"
        )
    if expected_runtime in TIER_REFERENCE:
        pytest.xfail(
            f"ADR-V2-025 reference tier runtime {expected_runtime!r} may not "
            f"emit TaskCheckpoint — selective xfail allowed"
        )
    pytest.skip(
        "fixture trigger-task-checkpoint TBD; descriptor + payload-shape "
        "guards in this file remain the operative contract for 5.3 MVP"
    )
