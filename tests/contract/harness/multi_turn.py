"""Multi-turn session replay framework for contract-v1 observability tests.

ENGINE/CONTRACT layer ownership: this module lives in
``tests/contract/harness/`` and consumes existing mock servers
(``mock_openai_server.py``, ``mock_anthropic_server.py``) plus the gRPC
stub exposed by ``runtime_grpc_stub`` (see ``tests/contract/conftest.py``).

A :class:`MultiTurnFixture` represents a SEQUENCE of (request -> expected
response chunks) entries. Each turn either scripts a tool_call (for the
OpenAI mock) or a terminal text reply. The runtime drives Send turns in
order; per-turn assertions can inspect the chunk stream observed.

Design rules (Phase 7.1 CONTEXT.md D-01 part 1):

- session_id reuse across turns: one Initialize -> N Send -> Terminate.
- Deterministic ordering: turns advance via the mock-server counter
  (same state machine that single-turn tests already use).
- No live LLM: ALL turn responses are pre-scripted via the mock's
  ``tool_script`` (extended to support text + tool turns).
- Multi-turn helpers MUST honor ``trust_env=False`` (Clash localhost
  quirk per MEMORY.md tool gotcha).

CONTRACT-01 / D137 — closes 3 CHUNK-channel xfails in T01 (T02 closes
the 2 EVENT-channel xfails, T03 closes the 5 MCP-bridge xfails).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TurnScript:
    """One scripted turn — declares what the LLM should return.

    ``kind`` is either ``"tool_call"`` (mock emits a tool_calls chunk
    followed by ``finish_reason=tool_calls``) or ``"text"`` (mock emits a
    text delta followed by ``finish_reason=stop``).
    """

    kind: str  # "tool_call" or "text"
    # tool_call fields
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    tool_id: str | None = None
    # text fields
    content: str = "mock response"


@dataclass
class MultiTurnFixture:
    """Scripted multi-turn replay over a single session.

    ``script`` orders the turns; turn N consumes the Nth mock-server
    response. ``user_messages`` are the SendRequest contents the test
    issues to drive the agent loop forward.

    Tests use this fixture by building it inline inside the test body,
    converting it via :meth:`to_tool_script` and feeding the resulting
    list to ``mock_openai_server.build_app(tool_script=...)`` OR by
    consuming :func:`drive_session` which scripts an Initialize -> N Send
    -> Terminate sequence against the existing session-scoped runtime
    fixture.
    """

    script: list[TurnScript]
    user_messages: list[str]

    def to_tool_script(self) -> list[dict[str, Any]]:
        """Convert TurnScript list -> mock_openai_server ``tool_script`` arg.

        Text turns produce a ``{"kind": "text", "content": ...}`` entry
        that the extended mock server interprets as "this idx is a text
        turn, use the script-supplied content for the stop reply". Tool
        turns produce the existing tool-call dict shape.
        """
        out: list[dict[str, Any]] = []
        for i, t in enumerate(self.script):
            if t.kind == "tool_call":
                assert t.tool_name, "tool_call turn must declare tool_name"
                out.append(
                    {
                        "tool_name": t.tool_name,
                        "arguments": t.arguments,
                        "id": t.tool_id or f"call_mt_{i}",
                    }
                )
            elif t.kind == "text":
                out.append(
                    {
                        "kind": "text",
                        "content": t.content,
                    }
                )
            else:
                raise ValueError(f"unknown TurnScript.kind: {t.kind!r}")
        return out


def drive_session(
    stub,  # runtime_pb2_grpc.RuntimeServiceStub
    proto_runtime,  # runtime_pb2
    proto_common,  # common_pb2
    fixture: MultiTurnFixture,
    *,
    runtime_id: str = "grid-contract-test",
    session_id: str = "multi-turn-session",
    user_id: str = "contract-mt-user",
    metadata_per_turn: list[dict[str, str]] | None = None,
    skill_instructions: Any = None,
) -> list[list[Any]]:
    """Drive a multi-turn session and return per-turn chunk lists.

    One Initialize call seeds the session; one Send call per
    ``fixture.user_messages[i]`` drives turn i; one Terminate call
    closes. Returns a list of length ``len(user_messages)``, each entry
    is the ordered list of SendResponse chunks observed for that turn.

    The Initialize call's ``session_id`` argument is a hint; the
    runtime is free to allocate its own and return it on
    InitializeResponse. We use the returned session_id for subsequent
    Send + Terminate calls (per
    ``crates/grid-runtime/src/service.rs::initialize``).

    ``metadata_per_turn`` (optional, T05 — D138): when provided, MUST be
    a list of dicts of the same length as ``user_messages``. Each dict
    is merged into ``UserMessage.metadata`` for that turn. Tests use
    this to drive the ``x-test-scenario`` header-forward path through
    the runtime without an env-var shim.

    Raises if the gRPC stream errors before chunks can be drained.
    """
    payload_kwargs: dict[str, Any] = {
        "session_id": session_id,
        "user_id": user_id,
        "runtime_id": runtime_id,
    }
    if skill_instructions is not None:
        payload_kwargs["skill_instructions"] = skill_instructions
    payload = proto_common.SessionPayload(**payload_kwargs)
    init_resp = stub.Initialize(
        proto_runtime.InitializeRequest(payload=payload)
    )
    actual_session_id = init_resp.session_id or session_id

    if metadata_per_turn is None:
        metadata_per_turn = [dict() for _ in fixture.user_messages]
    elif len(metadata_per_turn) != len(fixture.user_messages):
        raise ValueError(
            "metadata_per_turn length must match user_messages length"
        )

    per_turn: list[list[Any]] = []
    try:
        for msg_text, md in zip(fixture.user_messages, metadata_per_turn):
            send_req = proto_runtime.SendRequest(
                session_id=actual_session_id,
                message=proto_runtime.UserMessage(
                    content=msg_text, message_type="text", metadata=md
                ),
            )
            chunks: list[Any] = []
            stream = stub.Send(send_req)
            for chunk in stream:
                chunks.append(chunk)
            per_turn.append(chunks)
    finally:
        try:
            stub.Terminate(proto_common.Empty())
        except Exception:
            # Best-effort terminate — failures here would mask any
            # exception raised inside the Send loop. The session fixture
            # is session-scoped, so a lingering session is acceptable.
            pass
    return per_turn
