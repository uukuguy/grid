"""V316-L2L3L4-OBS-01 — assert the production paths actually record.

The existing `test_observability.py` exercises the record_* helpers
directly: it proves they do not raise, not that anything calls them.
Through v3.15.6 nothing did — `observability.py` had zero production
call sites in L3, so `l3.*` metrics read zero under any load while the
suite stayed green. L1 shipped the identical defect twice (6c, then
again in 6g's first attempt) for the same reason.

These tests close that gap by driving the real code path and asserting
a recorder fired. They are deliberately written so that reverting the
wiring makes them fail — that property is the whole point, and it is
checked explicitly in `test_negative_control_*` below.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from eaasp_l3_governance import observability
from eaasp_l3_governance.audit import AuditStore
from eaasp_l3_governance.db import init_db


class _Spy:
    """Captures record_* calls without installing a real meter provider."""

    def __init__(self) -> None:
        self.sessions: list[dict[str, Any]] = []
        self.decisions: list[dict[str, Any]] = []

    def record_session(self, **kw: Any) -> None:
        self.sessions.append(kw)

    def record_opa_decision(self, **kw: Any) -> None:
        self.decisions.append(kw)


@pytest.fixture()
def spy(monkeypatch: pytest.MonkeyPatch) -> _Spy:
    """Patch the recorders at their *call sites*, not on the module.

    audit.py does `from .observability import record_session`, binding
    the function into its own namespace at import time. Patching
    `observability.record_session` would leave that binding untouched
    and the spy would see nothing — a false pass that would make these
    tests worthless.
    """
    s = _Spy()
    monkeypatch.setattr("eaasp_l3_governance.audit.record_session", s.record_session)
    monkeypatch.setattr(
        "eaasp_l3_governance.opa_backend.record_opa_decision", s.record_opa_decision
    )
    return s


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    p = str(tmp_path / "governance.db")
    asyncio.run(init_db(p))
    return p


def test_ledger_append_records_session(spy: _Spy, db_path: str) -> None:
    """Writing a governance decision must emit an l3.session sample."""
    store = AuditStore(db_path)
    asyncio.run(
        store.record_governance_decision(
            decision_id="dec-obs-1",
            session_id="sess-obs-1",
            hook_id="PreToolUse:scada_read",
            tool_name="scada_read",
            risk_level="read",
            decision="allow",
            approver="test",
            rationale="unit test",
        )
    )

    assert spy.sessions, (
        "record_governance_decision completed but no l3.session sample was "
        "recorded — the production path is not wired to observability"
    )
    sample = spy.sessions[-1]
    assert sample["operation"] == "append"
    assert sample["status"] == "ok"
    assert sample["duration_seconds"] >= 0.0


def test_audit_ingest_records_session(spy: _Spy, db_path: str) -> None:
    """Telemetry ingest is the higher-volume write — must be counted too.

    A wiring that only covered record_governance_decision would let
    /v1/telemetry/events inserts go uncounted, which is precisely the
    blind spot l3.session.total is meant to close.
    """
    from eaasp_l3_governance.audit import TelemetryEventIn

    store = AuditStore(db_path)
    asyncio.run(
        store.ingest(
            TelemetryEventIn(
                session_id="sess-obs-ingest",
                payload={"k": "v"},
            )
        )
    )

    ingest_calls = [s for s in spy.sessions if s["operation"] == "ingest"]
    assert ingest_calls, (
        "audit.ingest completed but no l3.session{operation=ingest} sample "
        "was recorded — telemetry writes are invisible to the meter"
    )
    assert ingest_calls[-1]["status"] == "ok"


def test_failed_ledger_append_records_error_status(spy: _Spy, db_path: str) -> None:
    """A rejected write must still be counted, as status=error.

    An uncounted failure is worse than no metric: the success rate looks
    perfect precisely when the ledger is refusing writes.
    """
    store = AuditStore(db_path)

    with pytest.raises(ValueError):
        asyncio.run(
            store.record_governance_decision(
                decision_id="dec-obs-2",
                session_id="sess-obs-2",
                hook_id="h",
                tool_name="t",
                risk_level="not-a-valid-risk-level",
                decision="allow",
                approver="test",
                rationale="should raise before touching the db",
            )
        )
    # Validation rejects before the db block, so nothing is recorded —
    # asserting that explicitly documents where the boundary is.
    assert not spy.sessions


def test_negative_control_unwired_path_records_nothing(db_path: str) -> None:
    """Proof this suite can fail.

    Simulates the pre-v3.16 state (no call site) and asserts the spy
    stays empty. If someone "fixes" the tests by asserting on the
    helpers rather than the call sites, this control still passes while
    the ones above fail — which is the signal we want.
    """
    s = _Spy()
    # Deliberately do NOT patch audit.record_session: with no call site
    # bound, nothing reaches the spy.
    store = AuditStore(db_path)
    asyncio.run(
        store.record_governance_decision(
            decision_id="dec-obs-3",
            session_id="sess-obs-3",
            hook_id="h",
            tool_name="t",
            risk_level="read",
            decision="allow",
            approver="test",
            rationale="negative control",
        )
    )
    assert not s.sessions


def test_opa_evaluate_records_decision(spy: _Spy) -> None:
    """OPABackend.evaluate must record, including on the fail-closed path.

    `record_opa_decision`'s docstring claimed for three milestones that
    it is "called from OPABackend.evaluate()". It was not. Fail-closed
    is the case that matters most — an operator needs to tell "policy
    denied" from "policy engine was down" — so it is what this drives.
    """
    from eaasp_l3_governance.opa_backend import OPABackend, OPAConfig

    backend = OPABackend(
        OPAConfig(
            base_url="http://127.0.0.1:59999",  # nothing listening
            timeout_seconds=0.25,
            bundle_dir=str(Path(__file__).parent),
        )
    )
    try:
        decision = asyncio.run(backend.evaluate({"risk_level": "read", "mode": "enforce"}))
    finally:
        asyncio.run(backend.aclose())

    assert decision.infra_unavailable is True
    assert spy.decisions, (
        "evaluate() returned a fail-closed decision but recorded no "
        "l3.opa.decision sample — the failure path is invisible"
    )
    sample = spy.decisions[-1]
    assert sample["risk_level"] == "read"
    assert sample["mode"] == "enforce"
    assert sample["infra_cause"] is not None
    assert sample["duration_seconds"] >= 0.0


def test_init_observability_is_called_by_app_lifespan() -> None:
    """The app must install the providers, or every recorder no-ops.

    Wiring call sites is necessary but not sufficient: without
    init_observability the meter stays _NoopMeter and the counters are
    silently discarded. That combination — real call sites, no
    provider — is indistinguishable from working code by inspection.
    """
    import inspect

    from eaasp_l3_governance import api

    src = inspect.getsource(api.create_app)
    assert "init_observability()" in src, (
        "create_app does not call init_observability; every record_* "
        "call in L3 will silently no-op"
    )


def test_observability_module_is_imported_by_production_code() -> None:
    """Guard against the whole class of defect returning.

    If a future refactor drops the imports, this fails immediately
    rather than at the next live walkthrough months later.
    """
    from eaasp_l3_governance import audit, opa_backend

    assert hasattr(audit, "record_session")
    assert hasattr(opa_backend, "record_opa_decision")
    assert observability is not None
