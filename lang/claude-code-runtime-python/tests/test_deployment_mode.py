"""Phase 5.4 Plan 02 Task 08 — WATCH-04 D143 deployment-mode gate.

Per ADR-V2-019 §D2: when ``EAASP_DEPLOYMENT_MODE=per_session``, a second
``Initialize`` call to the same claude-code-runtime process must set
``grpc.StatusCode.RESOURCE_EXHAUSTED`` on the context. Shared mode (the
default) allows multi-Initialize so existing multi-session callers are
unaffected.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import grpc
import pytest

from claude_code_runtime._proto.eaasp.runtime.v2 import common_pb2, runtime_pb2
from claude_code_runtime.config import RuntimeConfig
from claude_code_runtime.service import RuntimeServiceImpl


def _make_init_request(user_id: str) -> runtime_pb2.InitializeRequest:
    """Construct a minimal v2 InitializeRequest sufficient for the gate path."""
    payload = common_pb2.SessionPayload(user_id=user_id, runtime_id="claude-code-runtime")
    return runtime_pb2.InitializeRequest(payload=payload)


def _mock_context() -> MagicMock:
    """A MagicMock matching grpc.aio.ServicerContext's signal surface."""
    ctx = MagicMock()
    ctx.set_code = MagicMock()
    ctx.set_details = MagicMock()
    return ctx


@pytest.mark.asyncio
async def test_shared_mode_multi_init(monkeypatch):
    """Shared mode (default + explicit) accepts repeated Initialize calls."""
    monkeypatch.setenv("EAASP_DEPLOYMENT_MODE", "shared")

    svc = RuntimeServiceImpl(RuntimeConfig())
    assert svc._deployment_mode == "shared"

    ctx1 = _mock_context()
    resp1 = await svc.Initialize(_make_init_request("user-A"), ctx1)
    # Successful Initialize returns an InitializeResponse with session_id set.
    assert resp1.session_id, "first Initialize should return a session_id"
    ctx1.set_code.assert_not_called()

    ctx2 = _mock_context()
    resp2 = await svc.Initialize(_make_init_request("user-B"), ctx2)
    assert resp2.session_id, "second Initialize OK under shared (multi-session)"
    ctx2.set_code.assert_not_called()


@pytest.mark.asyncio
async def test_per_session_mode_blocks(monkeypatch):
    """per_session: first Initialize succeeds, second is RESOURCE_EXHAUSTED."""
    monkeypatch.setenv("EAASP_DEPLOYMENT_MODE", "per_session")

    svc = RuntimeServiceImpl(RuntimeConfig())
    assert svc._deployment_mode == "per_session"

    # First Initialize lands.
    ctx1 = _mock_context()
    resp1 = await svc.Initialize(_make_init_request("only-user"), ctx1)
    assert resp1.session_id, "first Initialize should produce a session_id"
    ctx1.set_code.assert_not_called()

    # Second Initialize must be rejected.
    ctx2 = _mock_context()
    resp2 = await svc.Initialize(_make_init_request("would-be-second"), ctx2)
    # Gate sets RESOURCE_EXHAUSTED and returns an empty InitializeResponse.
    assert resp2.session_id == "", "rejected Initialize must not allocate a session_id"
    ctx2.set_code.assert_called_once_with(grpc.StatusCode.RESOURCE_EXHAUSTED)
    # The details string should mention the per-session contract.
    details_call = ctx2.set_details.call_args
    assert details_call is not None, "set_details should fire on rejection"
    details = details_call.args[0]
    assert "per-session" in details, f"unexpected details: {details!r}"
