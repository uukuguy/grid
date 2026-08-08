"""eaasp-memories-client tests — mirror the ObstackClient /
SessionsClient / McpClient / TasksClient / CollaborationClient
test seam pattern.

Phase E.5. Tests don't hit grid-server; they use an injected
http_getter. E.5 test-suite emphasis — locks the Bearer-
header contract from commit 1787083e on first write (no need
for a follow-up "security fix" commit like E.3 needed).
"""

from __future__ import annotations

from typing import Any, Callable

import pytest

from eaasp_common import (
    ListMemoriesParams,
    ListMemoriesResponse,
    MemoriesClient,
    MemoriesClientError,
    WorkingMemoryBlock,
    WorkingMemoryResponse,
)


Handler = Callable[[str, str, dict[str, str], "dict | None"], Any]


def _make_fake_getter(responses: dict[str, Any]) -> Handler:
    """Return a 4-arg handler that maps (method, url, headers, body) → response.

    Mirrors the Phase D.4 + commit 27 / 28 / 92f2b8d8 test
    seam (ObstackClient / SessionsClient / McpClient /
    TasksClient / CollaborationClient).
    """
    def fake_getter(method, url, headers, json_body):
        if url not in responses:
            raise KeyError(f"unexpected URL: {url}")
        return responses[url]
    return fake_getter


def _wm_block(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "b1",
        "kind": "system",
        "label": "User",
        "value": "alice",
        "priority": 5,
        "char_limit": 1000,
        "is_readonly": False,
    }
    base.update(overrides)
    return base


# ─── Model dataclasses parse correctly ─────────────────────────────


def test_working_memory_block_from_dict() -> None:
    b = WorkingMemoryBlock(**_wm_block(value="alice"))
    assert b.id == "b1"
    assert b.value == "alice"
    assert b.is_readonly is False


# ─── Endpoints ──────────────────────────────────────────────────────


def test_list_memories_returns_results() -> None:
    body = {"results": [{"id": "m1", "content": "hello"}]}
    c = MemoriesClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/memories?limit=100": body}
        ),
    )
    resp = c.list_memories()
    assert isinstance(resp, ListMemoriesResponse)
    assert resp.results == [{"id": "m1", "content": "hello"}]


def test_list_memories_default_limit_always_in_url() -> None:
    """Wire shape: even when ``params=None`` the URL carries
    ``?limit=N`` (matches the SessionsClient /
    TasksClient / ObstackClient pattern).
    """
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["url"] = url
        return {"results": []}

    c = MemoriesClient("http://x", http_getter=getter)
    c.list_memories()  # no params
    assert captured["url"] == "http://x/api/v1/memories?limit=100"


def test_list_memories_custom_limit_propagates() -> None:
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["url"] = url
        return {"results": []}

    c = MemoriesClient("http://x", http_getter=getter)
    c.list_memories(ListMemoriesParams(limit=42))
    assert "limit=42" in captured["url"]


def test_list_memories_optional_filters_omitted_when_none() -> None:
    """Only ``session_id`` / ``q`` are added to the URL when
    explicitly set — matches the legacy UI's behavior of
    passing ``session_id`` only when the user picked one.
    """
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["url"] = url
        return {"results": []}

    c = MemoriesClient("http://x", http_getter=getter)
    c.list_memories(ListMemoriesParams(limit=10))
    assert "session_id" not in captured["url"]
    assert "q=" not in captured["url"]


def test_list_memories_session_id_filter_encodes_value() -> None:
    """``urllib.parse.urlencode`` defaults to the
    ``application/x-www-form-urlencoded`` format (RFC 1866)
    — spaces become ``+``, not ``%20``. The server uses
    ``axum::extract::Query`` which expects this convention
    on the wire, so the client must match. Any other unsafe
    character (e.g. ``/``) is still percent-encoded with
    ``%xx`` per RFC 3986.
    """
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["url"] = url
        return {"results": []}

    c = MemoriesClient("http://x", http_getter=getter)
    c.list_memories(ListMemoriesParams(session_id="s 1 with spaces"))
    # Spaces → ``+`` (form-encoded). ``/`` would be %-encoded.
    assert "session_id=s+1+with+spaces" in captured["url"]


def test_list_memories_session_id_filter_encodes_unsafe_chars() -> None:
    """Slash characters in the session_id filter do NOT
    restructure the URL — they get percent-encoded.
    """
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["url"] = url
        return {"results": []}

    c = MemoriesClient("http://x", http_getter=getter)
    c.list_memories(ListMemoriesParams(session_id="../admin"))
    # The injected ``/`` is percent-encoded; the URL prefix
    # (``http://x/api/v1/memories``) is preserved verbatim.
    assert "%2F" in captured["url"]
    assert captured["url"].startswith("http://x/api/v1/memories?limit=")


def test_working_memory_returns_typed_blocks() -> None:
    body = {"blocks": [_wm_block(id="b1"), _wm_block(id="b2", value="bob")]}
    c = MemoriesClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/memories/working": body}
        ),
    )
    resp = c.working_memory()
    assert isinstance(resp, WorkingMemoryResponse)
    assert len(resp.blocks) == 2
    assert resp.blocks[0].id == "b1"
    assert resp.blocks[1].value == "bob"


def test_working_memory_handles_empty_envelope() -> None:
    """Server falls through to ``{"blocks": []}`` on
    error paths (per memories.rs line 99). The client
    must accept the empty case without crashing.
    """
    c = MemoriesClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/memories/working": {"blocks": []}}
        ),
    )
    resp = c.working_memory()
    assert resp.blocks == []


# ─── Security-fix contracts (Phase E.4 lesson — first write) ────────


def test_bearer_header_reaches_list_memories() -> None:
    """Security fix: Bearer must reach the wire on every
    transport method (E.3 lesson — commit aa6d2e20
    shipped auth-bypass + we don't want to ship the same
    bug a fourth time).
    """
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["headers"] = headers
        return {"results": []}

    c = MemoriesClient("http://x", auth_token="SECRET", http_getter=getter)
    c.list_memories()
    assert captured["headers"] == {"Authorization": "Bearer SECRET"}


def test_bearer_header_reaches_working_memory() -> None:
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["headers"] = headers
        return {"blocks": []}

    c = MemoriesClient("http://x", auth_token="SECRET", http_getter=getter)
    c.working_memory()
    assert captured["headers"] == {"Authorization": "Bearer SECRET"}


def test_no_auth_token_results_in_empty_headers() -> None:
    """Negative test: when no auth_token is configured, the
    transport method must still work — it just doesn't
    include the Authorization header. Locks both branches
    so a refactor can't reintroduce the E.1 bug.
    """
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["headers"] = headers
        return {"results": []}

    c = MemoriesClient("http://x", http_getter=getter)
    c.list_memories()
    assert captured["headers"] == {}


# ─── Error paths ────────────────────────────────────────────────────


def test_raises_memories_client_error_on_non_2xx() -> None:
    def getter(method, url, headers, json_body):
        import http.client
        import urllib.error
        msg = http.client.HTTPMessage()
        for k, v in headers.items():
            msg[k] = v
        raise urllib.error.HTTPError(url, 500, "Server Error", msg, None)

    c = MemoriesClient("http://x", http_getter=getter)
    with pytest.raises(MemoriesClientError) as exc:
        c.list_memories()
    assert exc.value.status == 500


def test_raises_memories_client_error_on_working_memory() -> None:
    def getter(method, url, headers, json_body):
        import http.client
        import urllib.error
        msg = http.client.HTTPMessage()
        for k, v in headers.items():
            msg[k] = v
        raise urllib.error.HTTPError(url, 401, "Unauthorized", msg, None)

    c = MemoriesClient("http://x", http_getter=getter)
    with pytest.raises(MemoriesClientError) as exc:
        c.working_memory()
    assert exc.value.status == 401
