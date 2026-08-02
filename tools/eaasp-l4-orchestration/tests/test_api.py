"""End-to-end API tests (in-process ASGI + respx for L2/L3 mocks)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import respx

L2_DEFAULT = "http://127.0.0.1:18085"
L3_DEFAULT = "http://127.0.0.1:18083"


# ─── D8 / L3-04 RBAC: fail-closed X-Session-Scope enforcement ─────────────
# Regression tests for the security review finding
# (commit a6d75300 follow-up: broken-access-control-fail-open +
# missing-auth-on-session-create).
#
# Invariants enforced:
#   1. Missing X-Session-Scope → 403 missing_scope (NOT wildcard fallback)
#   2. Caller scope must MATCH skill's registered access_scope (no
#      impersonation of arbitrary scopes)
#   3. Wildcard "*" is rejected when skill declares a non-wildcard scope


@respx.mock
async def test_create_session_missing_scope_header_403(
    app_client: httpx.AsyncClient,
) -> None:
    """No X-Session-Scope header → 403 missing_scope (fail-closed).

    Regression: prior implementation fell back to "*" wildcard when the
    header was missing, which let any unauthenticated caller pass scope
    checks. This test pins the new fail-closed behavior.
    """
    # Even with L2+L3 mocks succeeding, missing header must short-circuit.
    respx.post(f"{L2_DEFAULT}/api/v1/memory/search").mock(
        return_value=httpx.Response(200, json={"hits": []})
    )
    respx.post(url__regex=rf"{L3_DEFAULT}/v1/sessions/.*/validate").mock(
        return_value=httpx.Response(
            200,
            json={
                "session_id": "x",
                "hooks_to_attach": [],
                "managed_settings_version": 1,
                "validated_at": "2026-04-12",
                "runtime_tier": "strict",
            },
        )
    )

    resp = await app_client.post(
        "/v1/sessions/create",
        headers={"_skip_scope_inject": "1"},  # opt out of auto-injection
        json={
            "intent_text": "x",
            "skill_id": "skill.test",
            "runtime_pref": "strict",
        },
        # NO X-Session-Scope header (asserted below)
    )
    # The _skip_scope_inject marker is stripped by the test fixture
    # before the request hits the ASGI app, so we don't assert on its
    # presence in resp.request.headers (httpx preserves it client-side
    # but it's gone server-side). The important invariant is that
    # X-Session-Scope was NOT injected alongside it.
    assert (
        "X-Session-Scope" not in resp.request.headers
    ), f"X-Session-Scope should not have been injected, got: {dict(resp.request.headers)}"
    assert resp.status_code == 403, resp.text
    detail = resp.json()["detail"]
    assert detail["code"] == "missing_scope"
    assert "X-Session-Scope" in detail["message"]


@respx.mock
async def test_create_session_scope_mismatch_403(
    app_client: httpx.AsyncClient,
) -> None:
    """Caller scope that doesn't match the skill's registered scope → 403.

    This test asserts the high-level invariant via the running service
    stack (verified end-to-end in evidence-phase-3-4.md scenario 2):
    sending X-Session-Scope=org:admin against a skill whose registered
    access_scope is org:eaasp-verify-2026-07-30 returns 403 scope_mismatch.

    For the in-process unit test we verify the helper function logic
    directly via _resolve_skill_bound_scope below — testing the full
    orchestrator path requires mocking L2 + L3 + skill_registry and is
    exercised by the evidence-based run captured in
    .grid/verify-2026-07-30/.
    """
    # Ensure dev-mode scope-binding bypass is OFF so the helper enforces
    # the binding (the test fixture sets this for app-level tests but we
    # call the helper directly here).
    import os
    os.environ.pop("EAASP_DEV_DISABLE_SCOPE_BINDING", None)

    from eaasp_l4_orchestration.api import _resolve_skill_bound_scope
    from eaasp_l4_orchestration.session_orchestrator import SessionOrchestrator

    # Use a typed stub matching the orchestrator shape (skill_registry
    # attribute with read_skill async method).
    class _StubRegistry:
        @staticmethod
        async def read_skill(skill_id: str) -> dict[str, Any]:
            return {"parsed_v2": {"access_scope": "org:eaasp-mvp"}}

    class _StubOrchestrator(SessionOrchestrator):
        def __init__(self) -> None:
            # Skip real init; only need skill_registry attribute
            self.skill_registry = _StubRegistry()

    orch: SessionOrchestrator = _StubOrchestrator()

    # Mismatch → None (handler raises 403)
    result = await _resolve_skill_bound_scope(
        orch, skill_id="skill.test", caller_scope="org:different",
    )
    assert result is None

    # Match → returns the registered scope
    result = await _resolve_skill_bound_scope(
        orch, skill_id="skill.test", caller_scope="org:eaasp-mvp",
    )
    assert result == "org:eaasp-mvp"

    # Wildcard caller for a non-public skill → None (no impersonation)
    result = await _resolve_skill_bound_scope(
        orch, skill_id="skill.test", caller_scope="*",
    )
    assert result is None


@respx.mock
async def test_resolve_skill_bound_scope_fail_closed_paths() -> None:
    """Commit security review round-2: fail-closed paths.

    Three fail-closed paths must return None (handler raises 403):
      1. skill_registry is None (no ground truth available)
      2. skill_registry.read_skill raises (transient registry failure)
      3. skill's parsed_v2 has no access_scope declared (configuration gap)

    Prior commit (3398d567) had fallbacks in all three cases which the
    review correctly flagged as fail-open-state-drift and
    fail-open-default. This test pins the new strict behavior.
    """
    # Ensure dev-mode bypass is OFF
    import os
    os.environ.pop("EAASP_DEV_DISABLE_SCOPE_BINDING", None)

    from eaasp_l4_orchestration.api import _resolve_skill_bound_scope
    from eaasp_l4_orchestration.session_orchestrator import SessionOrchestrator

    # Case 1: skill_registry None → fail-closed
    class _StubOrchNoRegistry(SessionOrchestrator):
        def __init__(self) -> None:
            self.skill_registry = None

    orch_no_reg = _StubOrchNoRegistry()
    result = await _resolve_skill_bound_scope(
        orch_no_reg, skill_id="skill.x", caller_scope="org:eaasp-mvp",
    )
    assert result is None, "skill_registry=None must fail-closed, not fall back"

    # Case 2: read_skill raises → fail-closed
    class _StubRegistryRaises:
        @staticmethod
        async def read_skill(skill_id: str) -> dict[str, Any]:
            raise ConnectionError("skill-registry down")

    class _StubOrchRaises(SessionOrchestrator):
        def __init__(self) -> None:
            self.skill_registry = _StubRegistryRaises()

    orch_raises = _StubOrchRaises()
    result = await _resolve_skill_bound_scope(
        orch_raises, skill_id="skill.x", caller_scope="org:eaasp-mvp",
    )
    assert result is None, "registry exception must fail-closed, not fall back"

    # Case 3: skill with no access_scope declared → fail-closed
    class _StubRegistryNoScope:
        @staticmethod
        async def read_skill(skill_id: str) -> dict[str, Any]:
            return {"parsed_v2": {}}  # no access_scope key

    class _StubOrchNoScope(SessionOrchestrator):
        def __init__(self) -> None:
            self.skill_registry = _StubRegistryNoScope()

    orch_no_scope = _StubOrchNoScope()
    result = await _resolve_skill_bound_scope(
        orch_no_scope, skill_id="skill.x", caller_scope="org:eaasp-mvp",
    )
    assert result is None, (
        "skill with no declared access_scope must fail-closed, not "
        "default to '*' (prev fail-open-default)"
    )


async def test_resolve_skill_bound_scope_dev_bypass_explicit() -> None:
    """EAASP_DEV_DISABLE_SCOPE_BINDING=1 short-circuits to caller scope.

    This is the only escape hatch from the strict fail-closed behavior,
    intended for dev/test environments only. Production must NEVER set
    this flag (logged WARNING when active).
    """
    import os

    from eaasp_l4_orchestration.api import _resolve_skill_bound_scope
    from eaasp_l4_orchestration.session_orchestrator import SessionOrchestrator

    os.environ["EAASP_DEV_DISABLE_SCOPE_BINDING"] = "1"
    try:
        class _StubOrch(SessionOrchestrator):
            def __init__(self) -> None:
                self.skill_registry = None  # would normally fail-closed

        orch = _StubOrch()
        # Dev bypass → returns caller's scope (no ground-truth check)
        result = await _resolve_skill_bound_scope(
            orch, skill_id="skill.x", caller_scope="any-scope-at-all",
        )
        assert result == "any-scope-at-all"
    finally:
        os.environ.pop("EAASP_DEV_DISABLE_SCOPE_BINDING", None)


async def test_health(app_client: httpx.AsyncClient) -> None:
    resp = await app_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@respx.mock
async def test_create_session_happy_path(app_client: httpx.AsyncClient) -> None:
    respx.post(f"{L2_DEFAULT}/api/v1/memory/search").mock(
        return_value=httpx.Response(
            200,
            json={"hits": [{"memory_id": "m1", "memory_type": "anchor"}]},
        )
    )
    respx.post(url__regex=rf"{L3_DEFAULT}/v1/sessions/.*/validate").mock(
        return_value=httpx.Response(
            200,
            json={
                "session_id": "placeholder",
                "hooks_to_attach": [],
                "managed_settings_version": 1,
                "validated_at": "2026-04-12 02:00:00",
                "runtime_tier": "strict",
            },
        )
    )
    # D8 / L3-04 RBAC: per-skill scope binding requires the orchestrator
    # to read the skill from skill-registry. Mock that endpoint so the
    # resolve_skill_bound_scope helper succeeds with scope="*".
    respx.post("http://127.0.0.1:18081/tools/skill_read/invoke").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"id": "skill.test"},
                "frontmatter_yaml": "",
                "prose": "",
                "skill_dir": "/tmp",
                "parsed_v2": {"access_scope": "*"},
            },
        )
    )

    resp = await app_client.post(
        "/v1/sessions/create",
        headers={"X-Session-Scope": "*"},
        json={
            "intent_text": "do the thing",
            "skill_id": "skill.test",
            "runtime_pref": "strict",
            "user_id": "u-1",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "active"  # Phase 0.5: L1 Initialize succeeds → active
    sid = body["session_id"]

    # GET /v1/sessions/{id} returns the persisted row.
    get_resp = await app_client.get(f"/v1/sessions/{sid}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "active"


@respx.mock
async def test_create_session_l2_unavailable(app_client: httpx.AsyncClient) -> None:
    respx.post(f"{L2_DEFAULT}/api/v1/memory/search").mock(
        side_effect=httpx.ConnectError("no l2")
    )
    resp = await app_client.post(
        "/v1/sessions/create",
        json={
            "intent_text": "x",
            "skill_id": "skill.s",
            "runtime_pref": "strict",
        },
    )
    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert detail["code"] == "upstream_unavailable"
    assert detail["service"] == "l2"


@respx.mock
async def test_create_session_l3_no_policy(app_client: httpx.AsyncClient) -> None:
    respx.post(f"{L2_DEFAULT}/api/v1/memory/search").mock(
        return_value=httpx.Response(200, json={"hits": []})
    )
    respx.post(url__regex=rf"{L3_DEFAULT}/v1/sessions/.*/validate").mock(
        return_value=httpx.Response(
            404, json={"detail": {"code": "no_policy", "message": "empty"}}
        )
    )
    resp = await app_client.post(
        "/v1/sessions/create",
        json={
            "intent_text": "x",
            "skill_id": "skill.s",
            "runtime_pref": "strict",
        },
    )
    assert resp.status_code == 424
    assert resp.json()["detail"]["code"] == "no_policy"


@respx.mock
async def test_send_message_happy_path(app_client: httpx.AsyncClient) -> None:
    respx.post(f"{L2_DEFAULT}/api/v1/memory/search").mock(
        return_value=httpx.Response(200, json={"hits": []})
    )
    respx.post(url__regex=rf"{L3_DEFAULT}/v1/sessions/.*/validate").mock(
        return_value=httpx.Response(
            200,
            json={
                "session_id": "placeholder",
                "hooks_to_attach": [],
                "managed_settings_version": 1,
                "validated_at": "2026-04-12 02:00:00",
                "runtime_tier": "strict",
            },
        )
    )
    created = await app_client.post(
        "/v1/sessions/create",
        json={"intent_text": "x", "skill_id": "skill.s", "runtime_pref": "strict"},
    )
    sid = created.json()["session_id"]

    resp = await app_client.post(
        f"/v1/sessions/{sid}/message", json={"content": "hello"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["session_id"] == sid
    assert "response_text" in body  # Phase 0.5: real L1 Send returns text
    assert len(body["events"]) > 0


async def test_send_message_unknown_session_404(app_client: httpx.AsyncClient) -> None:
    resp = await app_client.post(
        "/v1/sessions/sess_ghost/message", json={"content": "hi"}
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "session_not_found"


@respx.mock
async def test_list_events_range(app_client: httpx.AsyncClient) -> None:
    respx.post(f"{L2_DEFAULT}/api/v1/memory/search").mock(
        return_value=httpx.Response(200, json={"hits": []})
    )
    respx.post(url__regex=rf"{L3_DEFAULT}/v1/sessions/.*/validate").mock(
        return_value=httpx.Response(
            200,
            json={
                "session_id": "placeholder",
                "hooks_to_attach": [],
                "managed_settings_version": 1,
                "validated_at": "2026-04-12 02:00:00",
                "runtime_tier": "strict",
            },
        )
    )
    created = await app_client.post(
        "/v1/sessions/create",
        json={"intent_text": "x", "skill_id": "skill.s", "runtime_pref": "strict"},
    )
    sid = created.json()["session_id"]
    await app_client.post(f"/v1/sessions/{sid}/message", json={"content": "hi-1"})
    await app_client.post(f"/v1/sessions/{sid}/message", json={"content": "hi-2"})

    resp = await app_client.get(f"/v1/sessions/{sid}/events")
    assert resp.status_code == 200
    events = resp.json()["events"]
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs)
    assert (
        len(events) >= 4
    )  # SESSION_CREATED + RUNTIME_INITIALIZE_STUBBED + 2x(USER+STUB)


async def test_list_events_limit_over_cap_422(app_client: httpx.AsyncClient) -> None:
    resp = await app_client.get("/v1/sessions/sess_x/events?limit=501")
    assert resp.status_code == 422


async def test_get_session_unknown_404(app_client: httpx.AsyncClient) -> None:
    resp = await app_client.get("/v1/sessions/sess_ghost")
    assert resp.status_code == 404


# ── S4.T2 (D84) — events SSE follow endpoint ─────────────────────────────


async def test_stream_events_unknown_session_404(app_client: httpx.AsyncClient) -> None:
    """Unknown session on SSE endpoint should 404 before stream starts."""
    resp = await app_client.get("/v1/sessions/sess_ghost/events/stream")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "session_not_found"


async def _collect_sse_data(
    client: httpx.AsyncClient, url: str, expected_data_count: int
) -> str:
    """Open an SSE stream, collect ``expected_data_count`` data lines, return them.

    ASGITransport doesn't honor httpx read-timeouts (in-memory transport with
    no socket), so we rely on ``asyncio.wait_for`` as a hard termination fence
    and ``break`` as the happy-path exit.
    """
    import asyncio

    async def _inner() -> list[str]:
        collected: list[str] = []
        async with client.stream("GET", url) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            async for line in resp.aiter_lines():
                collected.append(line)
                data_count = sum(1 for line_ in collected if line_.startswith("data: "))
                if data_count >= expected_data_count:
                    break
        return collected

    collected = await asyncio.wait_for(_inner(), timeout=5.0)
    return "\n".join(collected)


async def test_stream_events_replays_existing(
    app_client: httpx.AsyncClient,
    tmp_db_path: str,
    seed_session,
) -> None:
    """SSE stream replays pre-existing events in ascending seq order."""
    from eaasp_l4_orchestration.event_stream import SessionEventStream

    sid = await seed_session("sess_sse_replay")
    stream = SessionEventStream(tmp_db_path)
    await stream.append(sid, "SESSION_START", {"runtime_id": "grid-runtime"})
    await stream.append(sid, "PRE_TOOL_USE", {"tool_name": "scada_read"})
    await stream.append(sid, "STOP", {"reason": "complete"})

    blob = await _collect_sse_data(
        app_client,
        f"/v1/sessions/{sid}/events/stream?from=1&poll_interval_ms=50&max_idle_polls=1",
        expected_data_count=3,
    )
    assert "SESSION_START" in blob
    assert "PRE_TOOL_USE" in blob
    assert "STOP" in blob
    # Ordering: SESSION_START appears before PRE_TOOL_USE appears before STOP.
    assert blob.index("SESSION_START") < blob.index("PRE_TOOL_USE") < blob.index("STOP")


async def test_stream_events_from_seq_filters(
    app_client: httpx.AsyncClient,
    tmp_db_path: str,
    seed_session,
) -> None:
    """?from=N must skip events with seq < N."""
    from eaasp_l4_orchestration.event_stream import SessionEventStream

    sid = await seed_session("sess_sse_from")
    stream = SessionEventStream(tmp_db_path)
    await stream.append(sid, "SESSION_START", {})
    await stream.append(sid, "PRE_TOOL_USE", {"tool_name": "a"})
    await stream.append(sid, "POST_TOOL_USE", {"tool_name": "a"})

    blob = await _collect_sse_data(
        app_client,
        f"/v1/sessions/{sid}/events/stream?from=2&poll_interval_ms=50&max_idle_polls=1",
        expected_data_count=2,
    )
    # seq=1 (SESSION_START) must be skipped; 2+3 must appear.
    assert "SESSION_START" not in blob
    assert "PRE_TOOL_USE" in blob
    assert "POST_TOOL_USE" in blob


@respx.mock
async def test_list_sessions(app_client: httpx.AsyncClient) -> None:
    """GET /v1/sessions returns all sessions, newest first."""
    # Empty at start.
    resp = await app_client.get("/v1/sessions")
    assert resp.status_code == 200
    assert resp.json()["sessions"] == []

    # Create two sessions.
    respx.post(f"{L2_DEFAULT}/api/v1/memory/search").mock(
        return_value=httpx.Response(200, json={"hits": []})
    )
    respx.post(url__regex=rf"{L3_DEFAULT}/v1/sessions/.*/validate").mock(
        return_value=httpx.Response(
            200,
            json={
                "session_id": "placeholder",
                "hooks_to_attach": [],
                "managed_settings_version": 1,
                "validated_at": "2026-04-12 02:00:00",
                "runtime_tier": "strict",
            },
        )
    )
    r1 = await app_client.post(
        "/v1/sessions/create",
        json={"intent_text": "a", "skill_id": "skill.a", "runtime_pref": "strict"},
    )
    r2 = await app_client.post(
        "/v1/sessions/create",
        json={"intent_text": "b", "skill_id": "skill.b", "runtime_pref": "strict"},
    )
    sid1 = r1.json()["session_id"]
    sid2 = r2.json()["session_id"]

    # List all — both should be present.
    resp = await app_client.get("/v1/sessions")
    assert resp.status_code == 200
    sessions = resp.json()["sessions"]
    assert len(sessions) == 2
    returned_ids = {s["session_id"] for s in sessions}
    assert returned_ids == {sid1, sid2}

    # Filter by status.
    resp_active = await app_client.get("/v1/sessions?status=active")
    assert resp_active.status_code == 200
    for s in resp_active.json()["sessions"]:
        assert s["status"] == "active"

    # Limit.
    resp_limit = await app_client.get("/v1/sessions?limit=1")
    assert resp_limit.status_code == 200
    assert len(resp_limit.json()["sessions"]) == 1


async def test_create_session_missing_field_422(app_client: httpx.AsyncClient) -> None:
    resp = await app_client.post(
        "/v1/sessions/create",
        json={"intent_text": "x", "runtime_pref": "strict"},  # missing skill_id
    )
    assert resp.status_code == 422


# ─── SSE streaming tests ────────────────────────────────────────────────────


@respx.mock
async def test_send_message_stream_sse(app_client: httpx.AsyncClient) -> None:
    """POST /message/stream should return text/event-stream with SSE events."""
    respx.post(f"{L2_DEFAULT}/api/v1/memory/search").mock(
        return_value=httpx.Response(200, json={"hits": []})
    )
    respx.post(url__regex=rf"{L3_DEFAULT}/v1/sessions/.*/validate").mock(
        return_value=httpx.Response(
            200,
            json={
                "session_id": "placeholder",
                "hooks_to_attach": [],
                "managed_settings_version": 1,
                "validated_at": "2026-04-12 02:00:00",
                "runtime_tier": "strict",
            },
        )
    )
    created = await app_client.post(
        "/v1/sessions/create",
        json={"intent_text": "x", "skill_id": "skill.s", "runtime_pref": "strict"},
    )
    sid = created.json()["session_id"]

    resp = await app_client.post(
        f"/v1/sessions/{sid}/message/stream", json={"content": "hello sse"}
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")

    # Parse SSE events from the response body.
    lines = resp.text.strip().split("\n")
    sse_events: list[dict] = []
    current_event = "chunk"
    for line in lines:
        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            data = json.loads(line[6:])
            sse_events.append({"event": current_event, "data": data})
            current_event = "chunk"

    # Should have chunk events and a done event.
    chunk_events = [e for e in sse_events if e["event"] == "chunk"]
    done_events = [e for e in sse_events if e["event"] == "done"]
    assert len(chunk_events) >= 1
    assert len(done_events) == 1
    assert done_events[0]["data"]["session_id"] == sid


async def test_send_message_stream_unknown_session_404(
    app_client: httpx.AsyncClient,
) -> None:
    resp = await app_client.post(
        "/v1/sessions/sess_ghost/message/stream", json={"content": "hi"}
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "session_not_found"


# ── D28: Exception handler tests ────────────────────────────────────────────


async def test_unhandled_exception_returns_500_not_traceback(
    app_client: httpx.AsyncClient,
):
    """D28: Unhandled exceptions must return structured JSON, not tracebacks."""
    # Trigger a parse error that exercises the exception handler path.
    resp = await app_client.post(
        "/v1/sessions/sess_test000001/message",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )
    # FastAPI's built-in JSON parsing returns 422 for malformed JSON,
    # which exercises the validation handler path.
    assert resp.status_code in (422, 500)
    if resp.status_code == 500:
        body = resp.json()
        assert "error" in body
        assert "detail" in body
        # Must NOT contain Python traceback patterns.
        assert "Traceback (most recent call last)" not in str(body)


# ── D29: Path validation tests ─────────────────────────────────────────────


async def test_session_id_with_special_chars_422(app_client: httpx.AsyncClient):
    """D29: Malformed session_id with spaces, script tags, or injection chars must be rejected at boundary.

    Note: ../ path traversal is caught at the HTTP routing layer (ASGI normalizes
    the URL before our regex runs), not at our regex boundary. 404 for those is
    correct behavior — path traversal is prevented by the protocol layer.
    """
    import urllib.parse

    bad_ids = [
        "sess test",  # space — not in [a-zA-Z0-9_-]
        "sess<script>",  # angle brackets — not in [a-zA-Z0-9_-]
        "sess;drop",  # semicolon — not in [a-zA-Z0-9_-]
    ]
    for bad_id in bad_ids:
        encoded = urllib.parse.quote(bad_id, safe="")
        resp = await app_client.get(f"/v1/sessions/{encoded}")
        assert resp.status_code == 422, (
            f"Expected 422 for bad session_id={bad_id!r}, got {resp.status_code}"
        )


async def test_valid_session_id_accepted(app_client: httpx.AsyncClient):
    """D29: Valid session_id format (alphanumeric + underscore + hyphen) passes validation."""
    valid_id = "sess_test000001"
    resp = await app_client.get(f"/v1/sessions/{valid_id}")
    # Should NOT be 422 — either 404 (not found) or 200 (exists).
    assert resp.status_code != 422, (
        f"Valid session_id {valid_id!r} was rejected: {resp.text}"
    )


# ── D31: Loguru initialization test ────────────────────────────────────────


def test_loguru_initialized_in_lifespan():
    """D31: loguru must be initialized — stdlib logging removed from api.py."""
    import ast
    from pathlib import Path

    api_path = (
        Path(__file__).parent.parent / "src" / "eaasp_l4_orchestration" / "api.py"
    )
    with open(api_path) as f:
        tree = ast.parse(f.read())
    # Verify no stdlib logging import.
    has_logging_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "logging":
                    has_logging_import = True
        elif isinstance(node, ast.ImportFrom):
            if node.module == "logging":
                has_logging_import = True
    assert not has_logging_import, "stdlib logging import found — should use loguru"
    # Verify loguru import exists.
    has_loguru = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "loguru":
            has_loguru = True
    assert has_loguru, "loguru import not found"


# ─── V315-BUSINESS-FLOW-02 commit 2 — X-Business-Key header persistence ────


@respx.mock
async def test_create_session_persists_business_key_header(
    app_client: httpx.AsyncClient,
) -> None:
    """When ``X-Business-Key`` is set on ``/v1/sessions/create``, the value
    is persisted to ``sessions.business_key`` so the timeline aggregator
    can join L2/L3/L4 events to this session.
    """
    import sqlite3

    respx.post(f"{L2_DEFAULT}/api/v1/memory/search").mock(
        return_value=httpx.Response(200, json={"hits": []})
    )
    respx.post(url__regex=rf"{L3_DEFAULT}/v1/sessions/.*/validate").mock(
        return_value=httpx.Response(
            200,
            json={
                "session_id": "placeholder",
                "hooks_to_attach": [],
                "managed_settings_version": 1,
                "validated_at": "2026-08-03 00:00:00",
                "runtime_tier": "strict",
            },
        )
    )
    respx.post("http://127.0.0.1:18081/tools/skill_read/invoke").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"id": "threshold-calibration"},
                "frontmatter_yaml": "",
                "prose": "",
                "skill_dir": "/tmp",
                "parsed_v2": {"access_scope": "*"},
            },
        )
    )
    resp = await app_client.post(
        "/v1/sessions/create",
        json={
            "intent_text": "calibrate Transformer-1",
            "skill_id": "threshold-calibration",
            "runtime_pref": "grid-runtime",
            "user_id": "demo",
            "intent_id": "demo-intent-001",
        },
        headers={
            "X-Session-Scope": "*",
            "X-Business-Key": "sess_demo|threshold-calibration|Transformer-1",
        },
    )
    assert resp.status_code == 200, resp.text
    session_id = resp.json()["session_id"]
    # Confirm by reading the L4 DB directly via the tmpfile pattern
    # used by conftest.py:tmp_db_path.
    import tempfile
    from pathlib import Path

    db_files = list(Path(tempfile.gettempdir()).glob("tmp*.db"))
    target = None
    for db in db_files:
        try:
            conn = sqlite3.connect(str(db))
            cur = conn.execute(
                "SELECT business_key FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            row = cur.fetchone()
            conn.close()
            if row is not None:
                target = row
                break
        except sqlite3.DatabaseError:
            continue
    assert target is not None, f"Session {session_id} not found in any tmp DB"
    assert target[0] == "sess_demo|threshold-calibration|Transformer-1"


@respx.mock
async def test_create_session_without_business_key_persists_null(
    app_client: httpx.AsyncClient,
) -> None:
    """Backward compat: missing X-Business-Key still works (NULL persisted)."""
    import sqlite3
    import tempfile
    from pathlib import Path

    respx.post(f"{L2_DEFAULT}/api/v1/memory/search").mock(
        return_value=httpx.Response(200, json={"hits": []})
    )
    respx.post(url__regex=rf"{L3_DEFAULT}/v1/sessions/.*/validate").mock(
        return_value=httpx.Response(
            200,
            json={
                "session_id": "placeholder",
                "hooks_to_attach": [],
                "managed_settings_version": 1,
                "validated_at": "2026-08-03 00:00:00",
                "runtime_tier": "strict",
            },
        )
    )
    respx.post("http://127.0.0.1:18081/tools/skill_read/invoke").mock(
        return_value=httpx.Response(
            200,
            json={
                "meta": {"id": "threshold-calibration"},
                "frontmatter_yaml": "",
                "prose": "",
                "skill_dir": "/tmp",
                "parsed_v2": {"access_scope": "*"},
            },
        )
    )
    resp = await app_client.post(
        "/v1/sessions/create",
        json={
            "intent_text": "no business key",
            "skill_id": "threshold-calibration",
            "runtime_pref": "grid-runtime",
            "user_id": "demo",
        },
        headers={"X-Session-Scope": "*"},
    )
    assert resp.status_code == 200, resp.text
    session_id = resp.json()["session_id"]
    db_files = list(Path(tempfile.gettempdir()).glob("tmp*.db"))
    target = None
    for db in db_files:
        try:
            conn = sqlite3.connect(str(db))
            cur = conn.execute(
                "SELECT business_key FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            row = cur.fetchone()
            conn.close()
            if row is not None:
                target = row
                break
        except sqlite3.DatabaseError:
            continue
    assert target is not None
    assert target[0] is None  # NULL when no X-Business-Key header
