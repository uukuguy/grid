"""V316-L2L3L4-OBS-01 — assert L4 request handling actually records.

`test_observability.py` next door exercises the record_* helpers
directly. That proves they do not raise; it does not prove anything
calls them. Through v3.15.6 nothing did, and the 6h walkthrough
measured the consequence: zero `l4.*` records after a full live run,
while this package's observability tests were green.

These tests drive the real ASGI app and assert a recorder fired, and
`test_negative_control_unmatched_route_records_nothing` pins the
property that makes them worth having — that they can fail.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from eaasp_l4_orchestration import api as l4_api


class _Spy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def flow(self, **kw: Any) -> None:
        self.calls.append(("flow", kw))

    def session(self, **kw: Any) -> None:
        self.calls.append(("session", kw))

    def room(self, **kw: Any) -> None:
        self.calls.append(("room", kw))

    def event(self, **kw: Any) -> None:
        self.calls.append(("event", kw))

    def families(self) -> set[str]:
        return {name for name, _ in self.calls}


@pytest.fixture()
def spy(monkeypatch: pytest.MonkeyPatch) -> _Spy:
    """Patch the recorders where api.py bound them, not on the module.

    api.py does `from .observability import record_flow, ...`, so the
    names live in api's namespace. Patching `observability.record_flow`
    would leave that binding intact and the spy would never fire — a
    false pass, which is the failure mode this whole file exists to
    prevent.
    """
    s = _Spy()
    monkeypatch.setattr(l4_api, "record_flow", s.flow)
    monkeypatch.setattr(l4_api, "record_session", s.session)
    monkeypatch.setattr(l4_api, "record_room", s.room)
    monkeypatch.setattr(l4_api, "record_event", s.event)
    return s


@pytest.fixture()
def client(tmp_path: Any) -> Any:
    app = l4_api.create_app(str(tmp_path / "l4.db"))
    with TestClient(app) as c:
        yield c


def test_business_flow_request_records_flow(spy: _Spy, client: Any) -> None:
    """A /v1/business-flows/* request must emit an l4.flow sample."""
    client.get("/v1/business-flows/a%7Cb%7Cc/timeline")

    assert "flow" in spy.families(), (
        "a business-flows request completed but recorded no l4.flow sample "
        f"(saw: {spy.families() or 'nothing'}) — the middleware is not wired"
    )
    _, kw = next(c for c in spy.calls if c[0] == "flow")
    assert kw["status"] in {"ok", "error"}
    assert kw["duration_seconds"] >= 0.0


def test_sessions_request_records_session(spy: _Spy, client: Any) -> None:
    """A /v1/sessions request must emit an l4.session sample."""
    client.get("/v1/sessions")

    assert "session" in spy.families(), (
        f"expected an l4.session sample, saw: {spy.families() or 'nothing'}"
    )


def test_failing_request_is_still_recorded(spy: _Spy, client: Any) -> None:
    """An error response must be counted, with status=error.

    Uncounted failures are the worst case: the success rate reads clean
    exactly when the endpoint is broken.
    """
    r = client.get("/v1/sessions/does-not-exist-xyz")
    assert r.status_code >= 400

    statuses = [kw.get("status") for _, kw in spy.calls]
    assert "error" in statuses, (
        f"a {r.status_code} response recorded no error sample; statuses={statuses}"
    )


def test_negative_control_unmatched_route_records_nothing(
    spy: _Spy, client: Any
) -> None:
    """Unmatched paths must not create metric samples.

    This is the cardinality bound: `_record_for_route` keys off the
    matched route template, so an arbitrary URL has no template and is
    dropped. If someone changes it to use `request.url.path`, this test
    fails — which is the point, since that change would let any caller
    mint unbounded series (the L1 issue found in 6h).
    """
    for path in ("/definitely-not-a-route", "/v1/aaa", "/v1/bbb", "/x/../../etc"):
        client.get(path)

    assert not spy.calls, (
        "unmatched paths produced metric samples — op labels are being "
        f"derived from caller-controlled input: {spy.calls}"
    )


def test_health_is_not_counted(spy: _Spy, client: Any) -> None:
    """Liveness probes must stay out of the counters.

    /health is polled continuously by the boot script and any
    supervisor; counting it would bury real traffic.
    """
    client.get("/health")
    assert not spy.calls


def test_init_observability_is_called_by_lifespan() -> None:
    """Call sites are useless without the provider installed.

    Wiring recorders while leaving the meter as _NoopMeter looks correct
    on inspection and emits nothing at runtime — precisely the state
    L2/L3/L4 shipped in through v3.15.6.
    """
    import inspect

    src = inspect.getsource(l4_api.create_app)
    assert "init_observability()" in src, (
        "create_app does not call init_observability; every l4.* recorder "
        "will silently no-op"
    )
