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

The fixture pattern (3 ephemeral SQLite DBs + L4/L3/L2 schema + business_key
seed) is borrowed from
``tools/eaasp-l4-orchestration/tests/test_flow_api.py`` lines 178-280
factored into a reusable asyncio helper so the 4 tests share the same
seed-data shape and only diverge on the assertion surface.

LOCATION: ``tests/e2e/business_flow/`` (NOT ``tests/business_flow/``)
The .gitignore line ``/tests/*`` excludes the root-level ``tests/``
directory from git tracking — only ``tests/contract/`` and ``tests/e2e/``
are explicitly whitelisted. The v3.15.6 6b.1 plan originally wrote
``tests/business_flow/`` (per OBSTACK_DESIGN §4.4), but the project's
.gitignore comment makes it explicit: "Root-level temp tests only
(crates/*/tests/ are real integration tests, must be committed)".
The remaining 4 tests obey this rule by living under the existing
``tests/e2e/`` whitelist.

WHY NOT import ``eaasp_l4_orchestration`` directly?
The 4 integration tests target the *user perspective* of OBSTACK: send
events through the public REST/SSE surface, see them aggregate into a
timeline, replay interrupted flows, watch live SSE. They do NOT need
the L4 FastAPI app at runtime — pure SQLite + ``BusinessKey`` parsing
is enough. Importing the L4 package would force these tests to depend
on the L4 venv + ASGI transitive imports, which is precisely the
"dependency baggage" the v3.15 demo script was avoiding. Tests here
exercise the *data-layer* semantics; the L4 FastAPI binding is
exercised by ``tools/eaasp-l4-orchestration/tests/test_flow_api.py``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from dataclasses import dataclass

import aiosqlite
import pytest_asyncio

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

L3_SCHEMA = """
CREATE TABLE governance_decisions (
    decision_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
    hook_id TEXT NOT NULL, tool_name TEXT NOT NULL,
    risk_level TEXT NOT NULL, decision TEXT NOT NULL,
    approver TEXT, rationale TEXT, stage TEXT,
    created_at INTEGER NOT NULL, business_key TEXT
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
    closed_at INTEGER, business_key TEXT, last_event_layer TEXT,
    interrupted_at INTEGER
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


@pytest_asyncio.fixture
async def cross_layer_db() -> AsyncIterator[CrossLayerDB]:
    """Build 3 ephemeral on-disk DBs (L4/L3/L2) seeded with the v3.15
    business-flow schema. ``aiosqlite`` requires on-disk DBs because
    follow-up transactions in the test body hold their own connections
    (in-memory DBs are connection-local).

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

    l4 = await aiosqlite.connect(paths["l4"])
    l3 = await aiosqlite.connect(paths["l3"])
    l2 = await aiosqlite.connect(paths["l2"])
    for conn, schema in ((l4, L4_SCHEMA), (l3, L3_SCHEMA), (l2, L2_SCHEMA)):
        conn.row_factory = aiosqlite.Row
        await conn.executescript(schema)
    await l4.commit()
    await l3.commit()
    await l2.commit()
    await l4.close()
    await l3.close()
    await l2.close()

    yield CrossLayerDB(l4=paths["l4"], l3=paths["l3"], l2=paths["l2"], business_key=bk)

    for p in paths.values():
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass


@pytest_asyncio.fixture
async def cross_layer_db_interrupted() -> AsyncIterator[CrossLayerDB]:
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

    l4 = await aiosqlite.connect(paths["l4"])
    l3 = await aiosqlite.connect(paths["l3"])
    l2 = await aiosqlite.connect(paths["l2"])
    l4.row_factory = aiosqlite.Row
    l3.row_factory = aiosqlite.Row
    l2.row_factory = aiosqlite.Row
    await l4.executescript(L4_INTERRUPTED_SCHEMA)
    await l3.executescript(L3_SCHEMA)
    await l2.executescript(L2_SCHEMA)
    await l4.commit()
    await l3.commit()
    await l2.commit()
    await l4.close()
    await l3.close()
    await l2.close()

    yield CrossLayerDB(l4=paths["l4"], l3=paths["l3"], l2=paths["l2"], business_key=bk)

    for p in paths.values():
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass


@pytest_asyncio.fixture
async def cross_layer_db_aborted() -> AsyncIterator[CrossLayerDB]:
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

    l4 = await aiosqlite.connect(paths["l4"])
    l3 = await aiosqlite.connect(paths["l3"])
    l2 = await aiosqlite.connect(paths["l2"])
    l4.row_factory = aiosqlite.Row
    l3.row_factory = aiosqlite.Row
    l2.row_factory = aiosqlite.Row
    await l4.executescript(L4_ABORTED_SCHEMA)
    await l3.executescript(L3_SCHEMA)
    await l2.executescript(L2_SCHEMA)
    await l4.commit()
    await l3.commit()
    await l2.commit()
    await l4.close()
    await l3.close()
    await l2.close()

    yield CrossLayerDB(l4=paths["l4"], l3=paths["l3"], l2=paths["l2"], business_key=bk)

    for p in paths.values():
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass
