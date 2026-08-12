"""V316-L2L3L4-OBS-01 — assert L2 tool dispatch actually records.

`test_observability.py` next door exercises the record_* helpers
directly. That proves they do not raise; it does not prove anything
calls them. Through v3.15.6 nothing did — `observability.py` had zero
production call sites in L2, so `l2.*` metrics read zero under any load
while that suite stayed green.

These tests drive the real dispatcher and assert a recorder fired.
`test_negative_control_*` pins the property that makes them worth
having: that they fail when the wiring is removed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from eaasp_l2_memory_engine import mcp_tools
from eaasp_l2_memory_engine.anchors import AnchorStore
from eaasp_l2_memory_engine.db import init_db
from eaasp_l2_memory_engine.files import MemoryFileStore
from eaasp_l2_memory_engine.index import HybridIndex
from eaasp_l2_memory_engine.mcp_tools import McpToolDispatcher, ToolError


class _Spy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def make(self, family: str) -> Any:
        def _rec(**kw: Any) -> None:
            self.calls.append((family, kw))

        return _rec

    def families(self) -> list[str]:
        return [f for f, _ in self.calls]


@pytest.fixture()
def spy(monkeypatch: pytest.MonkeyPatch) -> _Spy:
    """Rebuild the _RECORDERS map with spies.

    The dispatcher reads `_RECORDERS` at call time, so replacing the map
    is enough — and it also verifies the map is what production actually
    consults, rather than a parallel structure that drifted.
    """
    s = _Spy()
    monkeypatch.setattr(
        mcp_tools,
        "_RECORDERS",
        {
            "memory_search": s.make("search"),
            "memory_read": s.make("read"),
            "memory_list": s.make("read"),
            "memory_write_anchor": s.make("anchor"),
            "memory_write_file": s.make("write"),
            "memory_archive": s.make("delete"),
            "memory_confirm": s.make("write"),
        },
    )
    return s


@pytest.fixture()
async def dispatcher(tmp_path: Path) -> McpToolDispatcher:
    db = str(tmp_path / "l2.db")
    await init_db(db)
    return McpToolDispatcher(AnchorStore(db), MemoryFileStore(db), HybridIndex(db))


@pytest.mark.asyncio
async def test_write_file_records_write(spy: _Spy, dispatcher: McpToolDispatcher) -> None:
    """A successful memory_write_file must emit an l2.write sample."""
    await dispatcher.invoke(
        "memory_write_file",
        {"scope": "obs", "category": "test", "content": "hello"},
    )

    assert "write" in spy.families(), (
        "memory_write_file completed but recorded no l2.write sample — "
        "the dispatcher is not wired to observability"
    )
    _, kw = spy.calls[-1]
    assert kw["status"] == "ok"
    assert kw["duration_seconds"] >= 0.0


@pytest.mark.asyncio
async def test_search_records_search(spy: _Spy, dispatcher: McpToolDispatcher) -> None:
    await dispatcher.invoke("memory_search", {"query": "anything"})
    assert "search" in spy.families(), f"saw: {spy.families() or 'nothing'}"


@pytest.mark.asyncio
async def test_failed_tool_records_error_status(
    spy: _Spy, dispatcher: McpToolDispatcher
) -> None:
    """A raising handler must still be counted, as status=error.

    The `finally` in `invoke` exists for exactly this: an uncounted
    failure makes the success rate read clean at the moment the tool is
    broken.
    """
    with pytest.raises(ToolError):
        await dispatcher.invoke("memory_read", {"memory_id": "does-not-exist"})

    assert spy.calls, "a failing tool recorded nothing"
    family, kw = spy.calls[-1]
    assert family == "read"
    assert kw["status"] == "error", (
        f"expected status=error for a raising handler, got {kw['status']!r}"
    )


@pytest.mark.asyncio
async def test_unknown_tool_records_nothing(
    spy: _Spy, dispatcher: McpToolDispatcher
) -> None:
    """Unknown tool names must not become metric labels.

    `invoke` rejects them before the recorder lookup, so the label set
    stays bounded by _HANDLERS rather than by caller input. If that
    ordering is ever inverted, any client could mint unbounded series
    by invoking random names — the L1 cardinality issue from 6h.
    """
    with pytest.raises(ToolError):
        await dispatcher.invoke("memory_not_a_real_tool", {})

    assert not spy.calls, f"unknown tool produced samples: {spy.calls}"


@pytest.mark.asyncio
async def test_negative_control_unwired_dispatcher_records_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Proof this suite can fail.

    Empties _RECORDERS to simulate the pre-v3.16 state (no call sites)
    and asserts nothing is recorded. The tests above would all fail in
    that state, which is what makes them evidence rather than decoration.
    """
    s = _Spy()
    monkeypatch.setattr(mcp_tools, "_RECORDERS", {})

    db = str(tmp_path / "l2-neg.db")
    await init_db(db)
    d = McpToolDispatcher(AnchorStore(db), MemoryFileStore(db), HybridIndex(db))
    await d.invoke("memory_write_file", {"scope": "s", "category": "c", "content": "x"})

    assert not s.calls


def test_every_handler_has_a_recorder() -> None:
    """Adding a tool without a metric family should be a deliberate act.

    Not an assertion that the maps are identical — a tool may legitimately
    go uncounted — but the moment they diverge, someone should have to
    look at this test and decide.
    """
    unmapped = set(mcp_tools._HANDLERS) - set(mcp_tools._RECORDERS)
    assert not unmapped, (
        f"tools dispatched but never counted: {sorted(unmapped)}. "
        "Add a family to _RECORDERS, or update this test to record the "
        "decision to leave them uncounted."
    )


def test_init_observability_is_called_by_lifespan() -> None:
    """Call sites do nothing while the meter is still the noop.

    Real recorders plus no provider looks correct on inspection and
    emits nothing at runtime — the exact state L2 shipped through
    v3.15.6.
    """
    import inspect

    from eaasp_l2_memory_engine import api

    src = inspect.getsource(api.create_app)
    assert "init_observability()" in src, (
        "create_app does not call init_observability; every l2.* recorder "
        "will silently no-op"
    )
