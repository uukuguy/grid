"""Shared fixtures for the v3.15 OBSTACK business-flow integration tests.

Per OBSTACK_DESIGN.md §4.4 (Evaluate, planned) + V315-OPT-01 收敛:
  - tests/e2e/business_flow/test_timeline_e2e.py
  - tests/e2e/business_flow/test_interrupted.py
  - tests/e2e/business_flow/test_sse_subscribe.py
  - tests/e2e/business_flow/test_evaluator_integration.py

These 4 integration tests close the gap that was missing in the v3.15.5
ship cycle. The earlier ``tools/eaasp-l4-orchestration/tests/test_flow_api.py``
covers per-endpoint unit tests against the ASGI app; this directory
covers the cross-layer + multi-step + user-perspective integration
paths that the OBSTACK demo script was hand-crafting via
``/v1/events/ingest``.

LOCATION: ``tests/e2e/business_flow/`` (NOT ``tests/business_flow/``)
The .gitignore line ``/tests/*`` excludes the root-level ``tests/``
directory from git tracking — only ``tests/contract/`` and ``tests/e2e/``
are explicitly whitelisted. The v3.15.6 6b.1 plan originally wrote
``tests/business_flow/`` (per OBSTACK_DESIGN §4.4), but the project's
.gitignore comment makes it explicit: "Root-level temp tests only
(crates/*/tests/ are real integration tests, must be committed)".

WHY NOT import ``eaasp_l4_orchestration`` directly?
The 4 integration tests target the *user perspective* of OBSTACK: send
events through the public REST/SSE surface, see them aggregate into a
timeline, replay interrupted flows, watch live SSE. They do NOT need
the L4 FastAPI app at runtime — pure SQL + ``BusinessKey`` parsing
is enough. Importing the L4 package would force these tests to depend
on the L4 venv + ASGI transitive imports, which is precisely the
"dependency baggage" the v3.15 demo script was avoiding. Tests here
exercise the *data-layer* semantics; the L4 FastAPI binding is
exercised by ``tools/eaasp-l4-orchestration/tests/test_flow_api.py``.

WHY SYNC sqlite3 (NOT async aiosqlite)?
``pytest-asyncio==1.3.0`` with ``asyncio_mode=strict`` runs each
``@pytest.mark.asyncio`` test in its own event loop. A
``pytest_asyncio.fixture`` runs in *its own* event loop too. When the
test body opens a new ``aiosqlite.connect()`` it works in the test's
loop, but the temp-file paths that the fixture hands out were
written by the fixture's loop. Cross-loop handle passing can hang
under 3.12. Switching to stdlib ``sqlite3`` removes the dependency
on event-loop alignment entirely. SQL semantics are identical.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from eaasp_common.business_flow import BusinessKey


# ─── Schema definitions (mirror test_flow_api.py 178-231) ────────────────

L4_SCHEMA = """
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY, intent_id TEXT, skill_id TEXT,
    runtime_id TEXT, user_id TEXT, status TEXT NOT NULL,
    payload_json TEXT NOT NULL, created_at INTEGER NOT NULL,
    closed_at INTEGER, business_key TEXT
);
CREATE TABLE session_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
    event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
    created_at INTEGER NOT NULL, event_id TEXT, source TEXT,
    metadata_json TEXT DEFAULT '{}', cluster_id TEXT
);
CREATE TABLE event_room_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, room_id TEXT NOT NULL,
    session_id TEXT NOT NULL, event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL, created_at INTEGER NOT NULL,
    business_key TEXT
);
"""
# NOTE: ``session_events`` does NOT carry business_key directly in
# the v3.15 schema. The L4 reader joins it via ``sessions`` on
# ``session_id`` (see
# ``tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_readers.py``
# read_l4_session_events at line 146-164). The schema here mirrors
# that: the test timeline JOINs session_events to sessions and
# filters by sessions.business_key.

L3_SCHEMA = """
CREATE TABLE governance_decisions (
    decision_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
    hook_id TEXT NOT NULL, tool_name TEXT NOT NULL,
    risk_level TEXT NOT NULL, decision TEXT NOT NULL,
    approver TEXT, rationale TEXT NOT NULL, stage TEXT,
    ts TEXT NOT NULL DEFAULT (datetime('now')), business_key TEXT
);
CREATE TABLE telemetry_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
    created_at INTEGER NOT NULL, source TEXT,
    tiebreaker INTEGER NOT NULL DEFAULT 0, business_key TEXT
);
"""

L2_SCHEMA = """
CREATE TABLE memory_files (
    memory_id TEXT NOT NULL, version INTEGER NOT NULL,
    scope TEXT NOT NULL, category TEXT NOT NULL,
    content TEXT NOT NULL, evidence_refs TEXT,
    status TEXT NOT NULL, created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL, business_key TEXT,
    PRIMARY KEY (memory_id, version)
);
"""

L4_INTERRUPTED_SCHEMA = """
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY, intent_id TEXT, skill_id TEXT,
    runtime_id TEXT, user_id TEXT, status TEXT NOT NULL,
    payload_json TEXT NOT NULL, created_at INTEGER NOT NULL,
    closed_at INTEGER, business_key TEXT,
    last_event_layer TEXT, interrupted_at INTEGER
);
CREATE TABLE session_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
    event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
    created_at INTEGER NOT NULL, event_id TEXT, source TEXT,
    metadata_json TEXT DEFAULT '{}', cluster_id TEXT
);
CREATE TABLE event_room_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, room_id TEXT NOT NULL,
    session_id TEXT NOT NULL, event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL, created_at INTEGER NOT NULL,
    business_key TEXT
);
"""

L4_ABORTED_SCHEMA = """
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY, intent_id TEXT, skill_id TEXT,
    runtime_id TEXT, user_id TEXT, status TEXT NOT NULL,
    payload_json TEXT NOT NULL, created_at INTEGER NOT NULL,
    closed_at INTEGER, business_key TEXT
);
CREATE TABLE governance_decisions (
    decision_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
    hook_id TEXT NOT NULL, tool_name TEXT NOT NULL,
    risk_level TEXT NOT NULL, decision TEXT NOT NULL,
    approver TEXT, rationale TEXT, stage TEXT,
    created_at INTEGER NOT NULL, business_key TEXT
);
"""


@dataclass
class CrossLayerDB:
    """Holds the file paths to 3 ephemeral SQLite DBs (L4/L3/L2) seeded
    with the v3.15 business-flow schema. Tests use these paths to
    exercise the OBSTACK timeline / SSE / evaluator logic against real
    SELECT queries, not mocks.
    """

    l4: str
    l3: str
    l2: str
    business_key: BusinessKey

    @property
    def wire(self) -> str:
        return self.business_key.to_header()


def _build_db(schema: str, path: str) -> None:
    """Build a SQLite DB at ``path`` with ``schema``. Sync sqlite3
    is used (not aiosqlite) so the fixture is event-loop agnostic.
    """
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(schema)
    conn.commit()
    conn.close()


@pytest.fixture
def cross_layer_db() -> Iterator[CrossLayerDB]:
    """Build 3 ephemeral on-disk DBs (L4/L3/L2) seeded with the v3.15
    business-flow schema. The schema fields are typed nominally — there
    are no rows yet.

    The seeded business flow matches the OBSTACK demo shape:
        session_id  = ``sess-business-flow``
        skill_id    = ``threshold-calibration``
        object_id   = ``Transformer-sla``
    so the same wire format that the L4 ``/v1/business-flows/{key}``
    endpoints accept covers all 4 integration tests.
    """
    bk = BusinessKey(
        session_id="sess-business-flow",
        skill_id="threshold-calibration",
        business_object_id="Transformer-sla",
    )

    paths = {
        layer: tempfile.NamedTemporaryFile(
            suffix=f"-business_flow-{layer}.db", delete=False
        ).name
        for layer in ("l4", "l3", "l2")
    }
    for p in paths.values():
        os.chmod(p, 0o644)

    _build_db(L4_SCHEMA, paths["l4"])
    _build_db(L3_SCHEMA, paths["l3"])
    _build_db(L2_SCHEMA, paths["l2"])

    yield CrossLayerDB(l4=paths["l4"], l3=paths["l3"], l2=paths["l2"], business_key=bk)

    for p in paths.values():
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass


@pytest.fixture
def cross_layer_db_interrupted() -> Iterator[CrossLayerDB]:
    """Same as ``cross_layer_db`` but the L4 schema carries the
    ``last_event_layer`` + ``interrupted_at`` columns used by the
    interrupted-flow integration test (#2). Other columns are identical
    so the timeline query logic still works.
    """
    bk = BusinessKey(
        session_id="sess-interrupted",
        skill_id="threshold-calibration",
        business_object_id="Transformer-sla",
    )

    paths = {
        layer: tempfile.NamedTemporaryFile(
            suffix=f"-business_flow-interrupted-{layer}.db", delete=False
        ).name
        for layer in ("l4", "l3", "l2")
    }
    for p in paths.values():
        os.chmod(p, 0o644)

    _build_db(L4_INTERRUPTED_SCHEMA, paths["l4"])
    _build_db(L3_SCHEMA, paths["l3"])
    _build_db(L2_SCHEMA, paths["l2"])

    yield CrossLayerDB(l4=paths["l4"], l3=paths["l3"], l2=paths["l2"], business_key=bk)

    for p in paths.values():
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass


@pytest.fixture
def cross_layer_db_aborted() -> Iterator[CrossLayerDB]:
    """Same as ``cross_layer_db`` but only L4 sessions + L3 governance
    seeded. Used by the evaluator integration test (#4) which exercises
    the SLA-blocking path ("few memory writes, low completion rate")
    without needing L2 data.
    """
    bk = BusinessKey(
        session_id="sess-aborted-evaluator",
        skill_id="threshold-calibration",
        business_object_id="Transformer-sla",
    )

    paths = {
        layer: tempfile.NamedTemporaryFile(
            suffix=f"-business_flow-aborted-{layer}.db", delete=False
        ).name
        for layer in ("l4", "l3", "l2")
    }
    for p in paths.values():
        os.chmod(p, 0o644)

    _build_db(L4_ABORTED_SCHEMA, paths["l4"])
    _build_db(L3_SCHEMA, paths["l3"])
    _build_db(L2_SCHEMA, paths["l2"])

    yield CrossLayerDB(l4=paths["l4"], l3=paths["l3"], l2=paths["l2"], business_key=bk)

    for p in paths.values():
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass
