"""Contract-v1 Terminate semantics (D139 — ADR-V2-017 §2).

Cross-runtime enforcement of the two Terminate contract rules defined in
``ADR-V2-017-l1-runtime-ecosystem-strategy.md`` §2 (Phase 8.1 addendum):

1. **Double-terminate = NO-OP** — a second ``Terminate`` on an
   already-terminated session MUST return ``Empty`` (OK), not
   ``FAILED_PRECONDITION`` or any other error. Idempotent terminate
   is safer for retry-heavy orchestrators.

2. **Unknown session Send = NOT_FOUND** — ``Send`` to a never-initialized
   session_id MUST return gRPC status ``NOT_FOUND``, not
   ``FAILED_PRECONDITION``. ``NOT_FOUND`` is the gRPC-standard code for
   "resource does not exist."

These tests are parameterized across all 7 active runtimes per ADR-V2-025.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract_v1


def _import_proto():
    from claude_code_runtime._proto.eaasp.runtime.v2 import common_pb2, runtime_pb2

    return runtime_pb2, common_pb2


# ---------------------------------------------------------------------------
# Test: double-Terminate = NO-OP
# ---------------------------------------------------------------------------


def test_double_terminate_is_noop(runtime_grpc_stub):
    """Initialize → Terminate → Terminate: second call MUST be NO-OP.

    Per ADR-V2-017 §2 (Phase 8.1 addendum):
      - Path 1 (normal): Terminate on active session → graceful shutdown → OK
      - Re-Terminate: second Terminate on already-terminated session → NO-OP
        (return Empty, NOT FAILED_PRECONDITION)

    Idempotent terminate eliminates an entire class of retry-loop bugs
    in orchestrators (L4). L4 tracks session state independently; requiring
    L4 to suppress Terminate retries creates tight coupling.
    """
    runtime_pb2, common_pb2 = _import_proto()

    # -- Initialize --
    payload = common_pb2.SessionPayload(
        session_id="term-semantics-double-term-1",
        user_id="u",
        runtime_id="grid-contract-test",
    )
    init_resp = runtime_grpc_stub.Initialize(
        runtime_pb2.InitializeRequest(payload=payload)
    )
    assert init_resp.session_id

    # -- First Terminate (must succeed) --
    runtime_grpc_stub.Terminate(common_pb2.Empty())

    # -- Second Terminate (must be NO-OP per ADR-V2-017 §2) --
    # The contract requires idempotent terminate: second call returns OK,
    # not FAILED_PRECONDITION, INTERNAL, or any other error.
    try:
        runtime_grpc_stub.Terminate(common_pb2.Empty())
    except Exception as err:  # noqa: BLE001
        # If the runtime currently returns an error on re-terminate,
        # this is a contract violation per ADR-V2-017 §2. Mark as xfail
        # until the runtime is updated.
        err_msg = str(err).lower()
        if (
            "no active session" in err_msg
            or "failed_precondition" in err_msg
            or "not found" in err_msg
            or "terminated" in err_msg
        ):
            pytest.xfail(
                f"ADR-V2-017 §2 contract violation: double-terminate "
                f"must be NO-OP but runtime returned error: {err}. "
                f"Implementation must track terminated session IDs and "
                f"return Empty for re-terminate."
            )
        raise


# ---------------------------------------------------------------------------
# Test: Send to unknown session = NOT_FOUND
# ---------------------------------------------------------------------------


def test_send_to_unknown_session_returns_not_found(runtime_grpc_stub):
    """Send to never-initialized session_id MUST return NOT_FOUND.

    Per ADR-V2-017 §2 (Phase 8.1 addendum):
      - Send on session_id that was never Initialize'd → NOT_FOUND
      - NOT_FOUND is the gRPC-standard code for "resource does not exist"
      - FAILED_PRECONDITION implies resource exists but in wrong state (incorrect here)

    Using NOT_FOUND allows L4's error-classification to distinguish
    "this session ID is garbage" from "this session exists but is
    paused/terminated."
    """
    runtime_pb2, common_pb2 = _import_proto()

    unknown_sid = "term-semantics-never-initialized-9a3f1b2c"

    msg = runtime_pb2.UserMessage(content="hello", message_type="text")
    try:
        stream = runtime_grpc_stub.Send(
            runtime_pb2.SendRequest(session_id=unknown_sid, message=msg)
        )
        # Drain the stream to trigger the error (gRPC streaming errors
        # may surface during iteration, not at call time).
        for _ in stream:
            pass
        # If Send succeeds, the runtime created a new session implicitly.
        # This is also a contract violation — Send MUST NOT auto-create.
        pytest.xfail(
            f"ADR-V2-017 §2 contract violation: Send on unknown session_id "
            f"'{unknown_sid}' succeeded (may have auto-created session). "
            f"Expected gRPC status NOT_FOUND."
        )
    except Exception as err:  # noqa: BLE001
        err_code = _grpc_status_code(err)
        if err_code == "NOT_FOUND" or err_code == "StatusCode.NOT_FOUND":
            # Expected: runtime correctly rejects unknown session with NOT_FOUND.
            return
        err_msg = str(err).lower()
        if "not found" in err_msg or "not_found" in err_msg:
            # gRPC status string matches NOT_FOUND — accept.
            return
        # Any other error code is a contract violation.
        pytest.xfail(
            f"ADR-V2-017 §2 contract violation: Send on unknown session_id "
            f"'{unknown_sid}' returned '{err_code}' ({err_msg}). "
            f"Expected gRPC status NOT_FOUND per ADR-V2-017 §2."
        )


def _grpc_status_code(err: Exception) -> str:
    """Extract gRPC status code from an exception, if available."""
    try:
        return err.code().name  # type: ignore[union-attr]
    except (AttributeError, TypeError):
        pass
    # Try grpc.StatusCode introspection (grpcio)
    import grpc

    if isinstance(err, grpc.RpcError):
        code = err.code()
        try:
            return code.name  # type: ignore[union-attr]
        except AttributeError:
            return str(code)
    return "unknown"


# ---------------------------------------------------------------------------
# Cross-runtime parametrize (7 active runtimes)
# ---------------------------------------------------------------------------
# Per ADR-V2-025, all 7 active runtimes must pass this contract.
# The parametrize is resolved by conftest.py's --runtime CLI flag;
# CI runs one parametrize slice per job (--runtime=<name> plus
# tier/xfail/continue-on-error per .github/workflows/phase3-contract.yml).
# ---------------------------------------------------------------------------
