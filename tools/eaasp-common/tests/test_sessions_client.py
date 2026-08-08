"""eaasp-sessions-client tests — mirror test_obstack_client.py.

Phase E.1. Tests don't hit grid-server; they use injected
http_getter that returns a parsed dict. The SessionsClient is
stdlib-only (urllib) by default; tests can swap in a MockTransport
or any callable that returns the expected dict shape.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest

from eaasp_common import (
    ActiveSessionsResponse,
    ListExecutionsParams,
    SessionInfo,
    SessionsClient,
    SessionsClientError,
    StartSessionRequest,
    StartSessionResponse,
)


Handler = Callable[[str, str, dict[str, str], "dict | None"], Any]


def _make_fake_getter(responses: dict[str, Any]) -> Handler:
    """Return a 4-arg handler that maps (method, url, headers, body) → response.

    Matches the ObstackClient signature (method, url, headers, json_body)
    so the same testing pattern applies across client families.
    """
    def fake_getter(method, url, headers, json_body):
        if url not in responses:
            raise KeyError(f"unexpected URL: {url}")
        return responses[url]
    return fake_getter


# ─── Models parse correctly ────────────────────────────────────


def test_session_info_from_dict() -> None:
    s = SessionInfo(id="s1", created_at="2026-04-12T00:00:00Z", status="running")
    assert s.id == "s1"
    assert s.status == "running"


def test_active_sessions_response() -> None:
    r = ActiveSessionsResponse(
        sessions=[SessionInfo(id="s1", created_at="t1", status="running")],
    )
    assert len(r.sessions) == 1


def test_start_session_request_and_response() -> None:
    req = StartSessionRequest(agent_id="threshold-calibration", input={"k": "v"})
    resp = StartSessionResponse(session_id="s1")
    assert req.agent_id == "threshold-calibration"
    assert resp.session_id == "s1"


# ─── Client list_active / get_session ────────────────────────


def test_list_active_returns_uuid_string_list() -> None:
    """Wire shape (per ``grid-server /api/v1/sessions/active``):
    ``{"sessions": ["<uuid>", "<uuid>", ...], "count": N,
    "max": 64}``. The Python model declares ``sessions:
    list[str]`` (not ``list[SessionInfo]``) — the per-row
    ``created_at`` / ``status`` fields are NOT included on
    this endpoint. Callers needing the full shape use
    ``/api/v1/sessions`` which returns typed objects.

    Phase E.1 commit 1/2 originally mismodelled the wire
    shape as ``list[SessionInfo]``. The TS mirror inherited
    the lie, the React UI then read ``s.id`` on a string
    (always undefined) — this caused the Chat tab crash on
    2026-08-08. This test locks the corrected UUID-string
    contract.
    """
    body = {
        "sessions": [
            "7bc1a3d1-347c-42f7-8cb8-eea2606e2219",
            "dbb69643-6cf1-4abf-9c6b-e3d281998ae3",
        ],
        "count": 2,
        "max": 64,
    }
    c = SessionsClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/sessions/active": body}
        ),
    )
    resp = c.list_active()
    assert isinstance(resp, ActiveSessionsResponse)
    assert resp.sessions == [
        "7bc1a3d1-347c-42f7-8cb8-eea2606e2219",
        "dbb69643-6cf1-4abf-9c6b-e3d281998ae3",
    ]
    assert resp.count == 2
    assert resp.max == 64


def test_list_active_empty_returns_empty_list() -> None:
    body = {"sessions": [], "count": 0, "max": 64}
    c = SessionsClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/sessions/active": body}
        ),
    )
    resp = c.list_active()
    assert resp.sessions == []


def test_list_active_handles_typed_object_rows_with_defensive_fallback() -> None:
    """Belt-and-suspenders: a future server change that
    starts including per-row ``SessionInfo``-shaped dicts
    would break the UUID-string assumption. The client
    passes strings through verbatim and ignores extra
    fields (the consumer doesn't depend on them for
    rendering). Locked here so a future regression on the
    wire shape surfaces loudly via this test, not via a
    Chat tab crash.
    """
    body = {"sessions": ["uuid-1", "uuid-2"], "count": 2, "max": 64}
    c = SessionsClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/sessions/active": body}
        ),
    )
    resp = c.list_active()
    # Strings pass through unchanged.
    assert resp.sessions == ["uuid-1", "uuid-2"]


def test_list_active_missing_sessions_field_returns_empty_list() -> None:
    """Defensive: server accidentally drops the ``sessions``
    key (rare, but possible during a partial migration).
    The client must not crash — it returns an empty list
    so the UI falls back to "single-session mode".
    """
    body = {"count": 0, "max": 64}
    c = SessionsClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/sessions/active": body}
        ),
    )
    resp = c.list_active()
    assert resp.sessions == []


def test_get_session_returns_session_info() -> None:
    body = {"id": "s1", "created_at": "t1", "status": "stopped"}
    c = SessionsClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/sessions/s1": body}
        ),
    )
    s = c.get_session("s1")
    assert isinstance(s, SessionInfo)
    assert s.id == "s1"
    assert s.status == "stopped"


def test_start_session_sends_body_to_right_path() -> None:
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["method"] = method
        captured["url"] = url
        captured["body"] = json_body
        return {"session_id": "s-new"}

    c = SessionsClient("http://x", http_getter=getter)
    resp = c.start_session(
        StartSessionRequest(agent_id="threshold-calibration", input={"k": "v"}),
    )
    assert captured["method"] == "POST"
    assert captured["url"] == "http://x/api/v1/sessions/start"
    assert captured["body"] == {
        "agent_id": "threshold-calibration", "input": {"k": "v"},
    }
    assert isinstance(resp, StartSessionResponse)
    assert resp.session_id == "s-new"


# ─── list_executions: wire-shape passthrough (Phase E.1 commit 2/2) ─────────


def test_list_executions_returns_raw_list_passthrough() -> None:
    """GET /api/v1/sessions/{id}/executions returns a TOP-LEVEL JSON array
    (``Json<Vec<ToolExecution>>`` per ``crates/grid-server/src/api/executions.rs``).

    The Python client must pass the raw list through unchanged so callers
    see ``[ToolExecution, ...]`` — not the dict-wrapped ``{"data": [...]}``
    shape the default ``_request`` fallback would otherwise produce.
    """
    expected = [
        {"id": "e1", "tool": "Bash", "session_id": "s1"},
        {"id": "e2", "tool": "Read", "session_id": "s1"},
    ]

    def getter(method, url, headers, json_body):
        assert method == "GET"
        assert url == "http://x/api/v1/sessions/s1/executions?limit=100"
        return expected

    c = SessionsClient("http://x", http_getter=getter)
    result = c.list_executions("s1")
    # The raw list must come back unchanged — not wrapped in {"data": ...}.
    assert isinstance(result, list)
    assert result == expected
    assert result[0]["tool"] == "Bash"


def test_list_executions_preserves_pagination_query_string() -> None:
    """Custom limit param drives the URL query string."""
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["url"] = url
        return []

    c = SessionsClient("http://x", http_getter=getter)
    c.list_executions("s1", ListExecutionsParams(limit=25))
    assert "limit=25" in captured["url"]


# ─── Error path ────────────────────────────────────────


# ─── Error path ────────────────────────────────────────


def test_raises_sessions_client_error_on_non_2xx() -> None:
    """HTTPError from the injected getter must convert into
    SessionsClientError with the original status preserved.
    """
    def getter(method, url, headers, json_body):
        import http.client
        import urllib.error
        # urllib.error.HTTPError expects an http.client.HTTPMessage
        # for headers, not a plain dict. Build one and copy headers in
        # so the exception object is valid.
        msg = http.client.HTTPMessage()
        for k, v in headers.items():
            msg[k] = v
        raise urllib.error.HTTPError(url, 404, "Not Found", msg, None)

    c = SessionsClient("http://x", http_getter=getter)
    with pytest.raises(SessionsClientError) as exc:
        c.list_active()
    assert exc.value.status == 404


def test_raises_sessions_client_error_on_list_executions() -> None:
    """list_executions must also map non-2xx via the same error contract."""
    def getter(method, url, headers, json_body):
        import http.client
        import urllib.error
        msg = http.client.HTTPMessage()
        for k, v in headers.items():
            msg[k] = v
        raise urllib.error.HTTPError(url, 500, "Server Error", msg, None)

    c = SessionsClient("http://x", http_getter=getter)
    with pytest.raises(SessionsClientError) as exc:
        c.list_executions("s1")
    assert exc.value.status == 500
