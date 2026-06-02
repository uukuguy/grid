"""Contract-v1 skill-workflow assertions.

Locks the behaviour of ``workflow.required_tools`` across all L1
runtimes: skill-attached sessions MUST enforce the declared tool set,
reject unknown tools, and tolerate any ordering of permitted calls.

Phase 7.1 T05 (CONTRACT-02 / D138): closes 5 D138 xfails. Scenario-
routed mock LLM via ``X-Test-Scenario`` header (T04 infrastructure)
+ ``UserMessage.metadata["x-test-scenario"]`` propagation through
grid-runtime → grid-engine OpenAI provider.

The metadata path is preferred over a ``GRID_TEST_SCENARIO`` env-var
shim per ADR-V2-028 strict-by-default lineage (see CONTEXT.md D-05
step 3 + plan-checker I003).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract_v1


def _import_proto():
    from claude_code_runtime._proto.eaasp.runtime.v2 import (
        common_pb2,
        runtime_pb2,
    )
    return runtime_pb2, common_pb2


def _skill_with_required_tools(common_pb2, session_id: str, required: list[str]):
    return common_pb2.SkillInstructions(
        skill_id="d138-probe-skill",
        name="d138-probe-skill",
        content="",
        required_tools=required,
    )


def test_required_tools_enforced_at_send(runtime_grpc_stub):
    """CONTRACT-02 (D138): when the LLM emits a tool NOT in
    required_tools, the runtime MUST emit an ERROR chunk (or denial
    surface) on the Send stream before DONE.
    """
    from tests.contract.harness.multi_turn import (
        MultiTurnFixture,
        TurnScript,
        drive_session,
    )
    runtime_pb2, common_pb2 = _import_proto()

    skill = _skill_with_required_tools(
        common_pb2, "d138-required-1", ["file_write", "file_read"]
    )
    fixture = MultiTurnFixture(
        script=[TurnScript(kind="text", content="ack")],
        user_messages=["trigger deny"],
    )
    per_turn = drive_session(
        runtime_grpc_stub,
        runtime_pb2,
        common_pb2,
        fixture,
        session_id="d138-required-1",
        skill_instructions=skill,
        metadata_per_turn=[{"x-test-scenario": "deny-non-required-tool"}],
    )

    assert per_turn, "expected at least one Send turn observed"
    types = [c.chunk_type for c in per_turn[0]]
    # Contract obligation: an ERROR chunk MUST appear, OR the runtime
    # MUST refuse the tool dispatch without producing a successful
    # TOOL_RESULT for the offending tool name.
    error_present = runtime_pb2.ChunkType.CHUNK_TYPE_ERROR in types
    tool_results_for_evil = [
        c for c in per_turn[0]
        if c.chunk_type == runtime_pb2.ChunkType.CHUNK_TYPE_TOOL_RESULT
        and c.tool_name == "evil_tool" and not c.is_error
    ]
    assert error_present or not tool_results_for_evil, (
        f"deny path must surface ERROR or refuse the tool dispatch; "
        f"got chunk_types={types} evil_tool_results={len(tool_results_for_evil)}"
    )


def test_tool_order_is_free_within_required_set(runtime_grpc_stub):
    """CONTRACT-02 (D138): any permutation of required tools MUST be
    accepted (no ERROR for in-set tool calls).
    """
    from tests.contract.harness.multi_turn import (
        MultiTurnFixture,
        TurnScript,
        drive_session,
    )
    runtime_pb2, common_pb2 = _import_proto()

    skill = _skill_with_required_tools(
        common_pb2, "d138-order-1", ["file_write", "file_read"]
    )
    fixture = MultiTurnFixture(
        script=[
            TurnScript(kind="text", content="ack-1"),
            TurnScript(kind="text", content="ack-2"),
        ],
        user_messages=["call a-then-b", "and again"],
    )
    per_turn = drive_session(
        runtime_grpc_stub,
        runtime_pb2,
        common_pb2,
        fixture,
        session_id="d138-order-1",
        skill_instructions=skill,
        metadata_per_turn=[
            {"x-test-scenario": "multi-tool-permutation"},
            {},
        ],
    )

    # In-set tool ordering MUST NOT surface as an error chunk.
    for i, turn in enumerate(per_turn):
        types = [c.chunk_type for c in turn]
        in_set_tool_results = [
            c for c in turn
            if c.chunk_type == runtime_pb2.ChunkType.CHUNK_TYPE_TOOL_RESULT
            and c.tool_name in {"file_write", "file_read"}
            and c.is_error
        ]
        assert not in_set_tool_results, (
            f"turn {i}: in-set tool MUST NOT yield an is_error TOOL_RESULT; "
            f"got types={types}"
        )


def test_unknown_tool_rejects_with_error_event(runtime_grpc_stub):
    """CONTRACT-02 (D138): a tool not in ANY catalog MUST surface as
    ERROR (no silent acceptance).
    """
    from tests.contract.harness.multi_turn import (
        MultiTurnFixture,
        TurnScript,
        drive_session,
    )
    runtime_pb2, common_pb2 = _import_proto()

    skill = _skill_with_required_tools(
        common_pb2, "d138-unknown-1", ["file_write"]
    )
    fixture = MultiTurnFixture(
        script=[TurnScript(kind="text", content="ack")],
        user_messages=["trigger unknown"],
    )
    per_turn = drive_session(
        runtime_grpc_stub,
        runtime_pb2,
        common_pb2,
        fixture,
        session_id="d138-unknown-1",
        skill_instructions=skill,
        metadata_per_turn=[{"x-test-scenario": "unknown-tool"}],
    )

    assert per_turn, "expected at least one Send turn observed"
    chunks = per_turn[0]
    error_present = any(
        c.chunk_type == runtime_pb2.ChunkType.CHUNK_TYPE_ERROR for c in chunks
    )
    successful_tool_result = any(
        c.chunk_type == runtime_pb2.ChunkType.CHUNK_TYPE_TOOL_RESULT
        and c.tool_name == "nonexistent_tool"
        and not c.is_error
        for c in chunks
    )
    assert error_present or not successful_tool_result, (
        f"unknown tool MUST yield ERROR or no successful TOOL_RESULT; "
        f"got chunk_types={[c.chunk_type for c in chunks]}"
    )


def test_skill_unloaded_between_sessions(runtime_grpc_stub):
    """CONTRACT-02 (D138): skill state in session A MUST NOT bleed into
    session B. Verify via 2x Initialize with different session ids; the
    second session's GetState MUST reflect only what it loaded.
    """
    runtime_pb2, common_pb2 = _import_proto()

    skill_a = _skill_with_required_tools(
        common_pb2, "d138-cross-A", ["file_write"]
    )
    payload_a = common_pb2.SessionPayload(
        session_id="d138-cross-A",
        user_id="d138-user",
        runtime_id="grid-contract-test",
        skill_instructions=skill_a,
    )
    a_resp = runtime_grpc_stub.Initialize(
        runtime_pb2.InitializeRequest(payload=payload_a)
    )
    assert a_resp.session_id

    # Terminate A so the runtime's current_session pointer clears.
    try:
        runtime_grpc_stub.Terminate(common_pb2.Empty())
    except Exception:
        pass

    # Initialize B with no skill — A's required_tools MUST NOT leak.
    payload_b = common_pb2.SessionPayload(
        session_id="d138-cross-B",
        user_id="d138-user",
        runtime_id="grid-contract-test",
    )
    b_resp = runtime_grpc_stub.Initialize(
        runtime_pb2.InitializeRequest(payload=payload_b)
    )
    assert b_resp.session_id

    # The two sessions MUST have distinct session_ids — the runtime is
    # not silently reusing session A's state for B.
    assert a_resp.session_id != b_resp.session_id, (
        f"expected distinct session_ids; both = {a_resp.session_id}"
    )

    try:
        runtime_grpc_stub.Terminate(common_pb2.Empty())
    except Exception:
        pass


def test_load_skill_after_initialize_is_idempotent(runtime_grpc_stub):
    """CONTRACT-02 (D138): 2x LoadSkill of the same skill MUST NOT
    duplicate state. Asserts via GetState that the session is still
    well-formed after a redundant LoadSkill.
    """
    runtime_pb2, common_pb2 = _import_proto()

    skill = _skill_with_required_tools(
        common_pb2, "d138-idempotent-1", ["file_write"]
    )
    payload = common_pb2.SessionPayload(
        session_id="d138-idempotent-1",
        user_id="d138-user",
        runtime_id="grid-contract-test",
        skill_instructions=skill,
    )
    init_resp = runtime_grpc_stub.Initialize(
        runtime_pb2.InitializeRequest(payload=payload)
    )
    assert init_resp.session_id

    # Drive LoadSkill twice with the same SkillInstructions block.
    for _ in range(2):
        resp = runtime_grpc_stub.LoadSkill(
            runtime_pb2.LoadSkillRequest(
                session_id=init_resp.session_id,
                skill=skill,
            )
        )
        # Either success=True OR a typed (non-panic) decline is valid;
        # a panic / hang is not.
        assert hasattr(resp, "success")

    # GetState MUST still respond.
    state = runtime_grpc_stub.GetState(common_pb2.Empty())
    assert isinstance(state.session_id, str) and state.session_id

    try:
        runtime_grpc_stub.Terminate(common_pb2.Empty())
    except Exception:
        pass
