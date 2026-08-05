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


def test_list_active_returns_sessions() -> None:
    body = {
        "sessions": [
            {"id": "s1", "created_at": "t1", "status": "running"},
            {"id": "s2", "created_at": "t2", "status": "stopped"},
        ]
    }
    c = SessionsClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/sessions/active": body}
        ),
    )
    resp = c.list_active()
    assert isinstance(resp, ActiveSessionsResponse)
    assert len(resp.sessions) == 2
    assert resp.sessions[0].id == "s1"


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
