"""Tests for flow_api.py — v3.15.4b business flow REST + SSE routes.

Covers:
- /timeline decodes the path key, calls the aggregator, returns events
- /summary returns the rollup
- /evaluation returns the evaluator report
- /events/stream is a StreamingResponse with text/event-stream
- Malformed business key returns 400
- Empty business key returns 400
- Reads layer readers from app.state.flow_layer_readers
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from eaasp_common.business_flow import BusinessKey
from eaasp_l4_orchestration.flow_api import router
from eaasp_l4_orchestration.flow_timeline import BusinessFlowEvent


# ─── Test scaffolding ──────────────────────────────────────────────────────


def _build_app(layer_readers: dict | None = None) -> FastAPI:
    """Build a fresh FastAPI app for each test with the flow router."""
    app = FastAPI()
    if layer_readers is not None:
        app.state.flow_layer_readers = layer_readers
    app.include_router(router)
    return app


def _wire_reader(events: list[BusinessFlowEvent]):
    """Build a LayerReader that returns the given events."""
    async def _impl(key: BusinessKey) -> list[BusinessFlowEvent]:
        del key
        return events
    return _impl


# ─── timeline ──────────────────────────────────────────────────────────────


def test_timeline_returns_events() -> None:
    reader = _wire_reader([
        BusinessFlowEvent(ts=1000, layer="L4", component="session", event_type="session.created", payload={"k": 1}),
        BusinessFlowEvent(ts=1500, layer="L4", component="session", event_type="session.closed", payload={"status": "closed"}),
    ])
    app = _build_app({"L4_sessions": reader})
    client = TestClient(app)
    key = BusinessKey(session_id="s1", skill_id="k1", business_object_id="d1").to_header()
    resp = client.get(f"/v1/business-flows/{key}/timeline")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert body["business_key"] == key
    assert [e["event_type"] for e in body["events"]] == ["session.created", "session.closed"]
    assert body["events"][0]["ts"] == 1000
    assert body["events"][0]["payload"] == {"k": 1}


def test_timeline_empty_when_no_readers() -> None:
    app = _build_app()
    client = TestClient(app)
    key = BusinessKey(session_id="s1").to_header()
    resp = client.get(f"/v1/business-flows/{key}/timeline")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["events"] == []


def test_timeline_malformed_key_returns_400() -> None:
    app = _build_app()
    client = TestClient(app)
    # Only one field — not three pipe-separated
    resp = client.get("/v1/business-flows/only_one_field/timeline")
    assert resp.status_code == 400
    assert "malformed business key" in resp.json()["detail"]


def test_timeline_empty_session_id_returns_400() -> None:
    """``||`` decodes to session_id="" which the BusinessKey validator rejects."""
    app = _build_app()
    client = TestClient(app)
    resp = client.get("/v1/business-flows/%7C%7C/timeline")
    assert resp.status_code == 400


# ─── summary ───────────────────────────────────────────────────────────────


def test_summary_returns_rollup() -> None:
    reader = _wire_reader([
        BusinessFlowEvent(ts=1000, layer="L4", component="session", event_type="session.created", payload={}),
        BusinessFlowEvent(ts=1500, layer="L4", component="session", event_type="session.closed", payload={"status": "closed"}),
    ])
    app = _build_app({"L4_sessions": reader})
    client = TestClient(app)
    key = BusinessKey(session_id="s1").to_header()
    resp = client.get(f"/v1/business-flows/{key}/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["status"] == "succeeded"
    assert body["summary"]["event_count"] == 2
    assert body["summary"]["total_duration_ms"] == 500
    assert body["summary"]["layer_counts"] == {"L4": 2}


# ─── evaluation ────────────────────────────────────────────────────────────


def test_evaluation_returns_report() -> None:
    reader = _wire_reader([
        BusinessFlowEvent(ts=1000, layer="L4", component="session", event_type="session.created", payload={}),
        BusinessFlowEvent(ts=1500, layer="L4", component="session", event_type="session.closed", payload={"status": "closed"}),
    ])
    app = _build_app({"L4_sessions": reader})
    client = TestClient(app)
    key = BusinessKey(session_id="s1").to_header()
    resp = client.get(f"/v1/business-flows/{key}/evaluation")
    assert resp.status_code == 200
    body = resp.json()
    # Single-flow evaluation: total_flows=1 < min_sample_size → info hint
    assert body["report"]["total_flows"] == 1
    assert any(h["severity"] == "info" for h in body["report"]["hints"])


# ─── SSE stream ────────────────────────────────────────────────────────────


def test_sse_stream_returns_streaming_response() -> None:
    """Verify the SSE route is registered with the right media type.

    We don't iterate the long-lived SSE generator (TestClient would
    block until the generator exits). Instead we look up the
    registered ``APIRoute`` and verify the endpoint source contains
    the expected ``StreamingResponse`` + ``text/event-stream``
    markers — a static check that's enough to confirm the contract.

    Per-event delivery is covered separately by ``test_flow_sse``.
    """
    import inspect

    from fastapi.routing import APIRoute

    route = None
    for r in router.routes:
        if isinstance(r, APIRoute) and r.path.endswith("/events/stream"):
            route = r
            break
    assert route is not None, "SSE route not registered"
    src = inspect.getsource(route.endpoint)
    assert "StreamingResponse" in src
    assert "text/event-stream" in src


def test_sse_stream_malformed_key_returns_400() -> None:
    app = _build_app()
    client = TestClient(app)
    resp = client.get("/v1/business-flows/just_one_part/events/stream")
    assert resp.status_code == 400


# ─── V315-BUSINESS-FLOW-02 (LayerReader wiring) ─────────────────────────────
#
# End-to-end check: build the default reader set via
# ``build_default_layer_readers`` (mirrors ``api.py`` lifespan), seed a
# tiny in-memory SQLite DB with rows across L4 / L3 / L2 layers tagged
# with the same ``business_key``, and confirm the timeline endpoint
# aggregates them all.


def test_timeline_aggregates_across_all_layers_via_real_readers() -> None:
    import asyncio
    import tempfile
    import os

    import aiosqlite

    from eaasp_l4_orchestration.flow_readers import build_default_layer_readers

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
        ts TEXT NOT NULL, business_key TEXT
    );
    CREATE TABLE telemetry_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL, agent_id TEXT NOT NULL,
        hook_id TEXT NOT NULL, phase TEXT NOT NULL,
        payload_json TEXT NOT NULL, received_at TEXT NOT NULL,
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

    wire = BusinessKey(
        session_id="sess-end-to-end",
        skill_id="threshold-calibration",
        business_object_id="Transformer-end-to-end",
    ).to_header()

    async def _seed() -> dict:
        # Build 3 ephemeral on-disk DBs (L4 / L3 / L2) so the readers'
        # aiosqlite.Connection has a real file to point at (in-memory
        # DBs are connection-local; readers hold their own connections).
        paths = {
            layer: tempfile.NamedTemporaryFile(suffix=f"-{layer}.db", delete=False).name
            for layer in ("l4", "l3", "l2")
        }
        l4 = await aiosqlite.connect(paths["l4"])
        l3 = await aiosqlite.connect(paths["l3"])
        l2 = await aiosqlite.connect(paths["l2"])
        for conn, schema in (
            (l4, L4_SCHEMA), (l3, L3_SCHEMA), (l2, L2_SCHEMA),
        ):
            conn.row_factory = aiosqlite.Row
            await conn.executescript(schema)
        # Seed: 1 L4 session, 1 L3 governance decision, 1 L2 memory.
        await l4.execute(
            "INSERT INTO sessions VALUES ('sess-end-to-end','i','skill','rt','u','active','{}',1000,NULL,?)",
            (wire,),
        )
        await l3.execute(
            "INSERT INTO governance_decisions "
            "(decision_id, session_id, hook_id, tool_name, risk_level, decision, ts, business_key) "
            "VALUES ('d1','sess-end-to-end','h','t','low','allow','1970-01-01 00:18:20',?)",
            (wire,),
        )
        await l2.execute(
            "INSERT INTO memory_files "
            "(memory_id, version, scope, category, content, status, created_at, updated_at, business_key) "
            "VALUES ('m1',1,'s','c','85','confirmed',1200,1200,?)",
            (wire,),
        )
        for conn in (l4, l3, l2):
            await conn.commit()
        await l4.close()
        await l3.close()
        await l2.close()
        return paths

    paths = asyncio.run(_seed())
    try:
        async def _build() -> tuple:
            l4 = await aiosqlite.connect(paths["l4"])
            l3 = await aiosqlite.connect(paths["l3"])
            l2 = await aiosqlite.connect(paths["l2"])
            for conn in (l4, l3, l2):
                conn.row_factory = aiosqlite.Row
            readers = build_default_layer_readers(
                l4_conn=l4, l3_conn=l3, l2_conn=l2,
            )
            return readers, (l4, l3, l2)

        async def _close_all(conns) -> None:
            for c in conns:
                await c.close()

        readers, conns = asyncio.run(_build())
        try:
            app = _build_app(readers)
            client = TestClient(app)
            key = BusinessKey(
                session_id="sess-end-to-end",
                skill_id="threshold-calibration",
                business_object_id="Transformer-end-to-end",
            ).to_header()
            resp = client.get(f"/v1/business-flows/{key}/timeline")
            assert resp.status_code == 200
            body = resp.json()
            layers = {e["layer"] for e in body["events"]}
            assert layers == {"L2", "L3", "L4"}, body
            assert body["count"] >= 3
        finally:
            asyncio.run(_close_all(conns))
    finally:
        for p in paths.values():
            try:
                os.unlink(p)
            except OSError:
                pass


# ─── V315-BUSINESS-FLOW-02 commit 2 — /sessions endpoint ────────────────────


def test_business_flow_sessions_endpoint_returns_matching_sessions() -> None:
    """The new /v1/business-flows/{key}/sessions endpoint returns the
    list of L4 sessions tagged with the same business_key.
    """
    import aiosqlite
    import asyncio
    import tempfile

    from eaasp_l4_orchestration.flow_api import router as flow_router
    from fastapi import FastAPI

    async def _seed() -> str:
        path = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
        conn = await aiosqlite.connect(path)
        conn.row_factory = aiosqlite.Row
        await conn.executescript(
            """
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY, intent_id TEXT, skill_id TEXT,
                runtime_id TEXT, user_id TEXT, status TEXT NOT NULL,
                payload_json TEXT NOT NULL, created_at INTEGER NOT NULL,
                closed_at INTEGER, business_key TEXT
            );
            """
        )
        wire = "sess_a|skill_x|object_z"
        await conn.execute(
            "INSERT INTO sessions VALUES ('sess_a','i','skill_x','rt','u','active','{}',1000,NULL,?)",
            (wire,),
        )
        await conn.execute(
            "INSERT INTO sessions VALUES ('sess_b','i','skill_x','rt','u','closed','{}',1100,1200,?)",
            (wire,),
        )
        await conn.execute(
            "INSERT INTO sessions VALUES ('sess_c','i','skill_x','rt','u','created','{}',900,NULL,?)",
            ("different|key|other",),
        )
        await conn.commit()
        await conn.close()
        return path

    async def _run() -> dict:
        path = await _seed()
        try:
            conn = await aiosqlite.connect(path)
            conn.row_factory = aiosqlite.Row
            app = FastAPI()
            app.state.l4_db_conn = conn
            app.include_router(flow_router)
            with TestClient(app) as client:
                key = BusinessKey(
                    session_id="sess_a", skill_id="skill_x",
                    business_object_id="object_z",
                ).to_header()
                resp = client.get(f"/v1/business-flows/{key}/sessions")
                assert resp.status_code == 200, resp.text
                return resp.json()
        finally:
            import os
            try:
                os.unlink(path)
            except OSError:
                pass

    body = asyncio.run(_run())
    assert body["count"] == 2
    session_ids = {s["session_id"] for s in body["session_ids"]}
    assert session_ids == {"sess_a", "sess_b"}


def test_business_flow_sessions_endpoint_no_l4_conn_returns_empty() -> None:
    """When app.state.l4_db_conn is None, return empty list (defensive)."""
    app = _build_app()
    client = TestClient(app)
    key = BusinessKey(
        session_id="sess_x", skill_id="skill_y", business_object_id="z",
    ).to_header()
    resp = client.get(f"/v1/business-flows/{key}/sessions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["session_ids"] == []


# ─── V3.16 list endpoint — latest-row rollup correctness ─────────────────


def test_list_business_flows_uses_latest_row_and_filters_before_limit() -> None:
    """List summaries use one deterministic latest row per flow.

    In particular, aggregate counts are historical, while status and timing
    belong to the latest session only.  Object filtering happens in SQL before
    LIMIT so an older matching flow cannot disappear behind newer non-matches.
    """
    import asyncio
    import os
    import tempfile

    import aiosqlite

    async def _run() -> tuple[dict, dict, dict]:
        path = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
        conn = await aiosqlite.connect(path)
        conn.row_factory = aiosqlite.Row
        try:
            await conn.executescript(
                """
                CREATE TABLE sessions (
                    session_id TEXT PRIMARY KEY, intent_id TEXT, skill_id TEXT,
                    runtime_id TEXT, user_id TEXT, status TEXT NOT NULL,
                    payload_json TEXT NOT NULL, created_at INTEGER NOT NULL,
                    closed_at INTEGER, business_key TEXT
                );
                """
            )
            main_key = "flow|skill|target"
            rows = [
                # Historical outcomes must affect counts, but not latest fields.
                ("older-closed", "closed", 100, 200, main_key),
                ("older-failed", "failed", 300, 400, main_key),
                ("newer-active", "active", 500, None, main_key),
                # Equal timestamps choose the stable ascending session_id.
                ("z-tie", "failed", 700, 710, "tie|skill|tie-object"),
                ("a-tie", "closed", 700, 720, "tie|skill|tie-object"),
                # Newer non-matches come before the exact wildcard-like object.
                ("newer-1", "active", 1000, None, "one|skill|other"),
                ("newer-2", "active", 990, None, "two|skill|other_thing"),
                ("needle", "closed", 980, 985, "needle|skill|%_\\needle"),
                ("near", "closed", 970, 975, "near|skill|%Xneedle"),
            ]
            await conn.executemany(
                "INSERT INTO sessions "
                "(session_id, intent_id, skill_id, runtime_id, user_id, status, "
                "payload_json, created_at, closed_at, business_key) "
                "VALUES (?, 'i', 'skill', 'rt', 'u', ?, '{}', ?, ?, ?)",
                rows,
            )
            await conn.commit()

            app = FastAPI()
            app.state.l4_db_conn = conn
            app.include_router(router)
            with TestClient(app) as client:
                all_flows = client.get("/v1/business-flows/list?limit=20")
                active_only = client.get("/v1/business-flows/list?status=active")
                exact_object = client.get(
                    "/v1/business-flows/list",
                    params={"limit": 1, "business_object_id": "%_\\needle"},
                )
                assert all_flows.status_code == 200, all_flows.text
                assert active_only.status_code == 200, active_only.text
                assert exact_object.status_code == 200, exact_object.text
                return all_flows.json(), active_only.json(), exact_object.json()
        finally:
            await conn.close()
            os.unlink(path)

    all_flows, active_only, exact_object = asyncio.run(_run())
    by_key = {flow["business_key"]: flow for flow in all_flows["flows"]}

    main = by_key["flow|skill|target"]
    assert main == {
        "business_key": "flow|skill|target",
        "business_object_id": "target",
        "skill_id": "skill",
        "session_id": "flow",
        "session_count": 3,
        "finished_count": 2,
        "failed_count": 1,
        "last_started_at": 500,
        "last_completed_at": None,
        "last_duration_ms": None,
        "status": "active",
    }
    # Status filtering is based on the latest row, not historical failures.
    assert {flow["business_key"] for flow in active_only["flows"]} >= {
        "flow|skill|target",
        "one|skill|other",
        "two|skill|other_thing",
    }
    assert "tie|skill|tie-object" not in {
        flow["business_key"] for flow in active_only["flows"]
    }

    tie = by_key["tie|skill|tie-object"]
    assert tie["status"] == "closed"
    assert tie["last_completed_at"] == 720
    assert tie["last_duration_ms"] == 20_000

    assert exact_object["total"] == 1
    assert [flow["business_key"] for flow in exact_object["flows"]] == [
        "needle|skill|%_\\needle"
    ]
