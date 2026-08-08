"""eaasp-collaboration-client tests — mirror the ObstackClient /
SessionsClient / McpClient / TasksClient test seam pattern.

Phase E.4. Tests don't hit grid-server; they use an injected
http_getter that returns the parsed wire shape.

E.4 test-suite emphasis — locks the two security-fix contracts
from commit 1787083e before they can regress on first write:

  1. The Bearer auth header must reach the wire on EVERY
     transport method (``_get`` / ``_post`` / ``_get_array``).
  2. The ``vote_on_proposal`` path segment must be percent-
     encoded so attacker-supplied ``proposal_id`` containing
     ``/`` cannot restructure the URL.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest

from eaasp_common import (
    CollaborationAgent,
    CollaborationClient,
    CollaborationClientError,
    CollaborationEvent,
    CollaborationStatus,
    CreateProposalRequest,
    Proposal,
    SharedStateEntry,
    SharedStateResponse,
    Vote,
    VoteRequest,
)


Handler = Callable[[str, str, dict[str, str], "dict | None"], Any]


def _make_fake_getter(responses: dict[str, Any]) -> Handler:
    """Return a 4-arg handler that maps (method, url, headers, body) → response.

    Mirrors the existing ObstackClient / SessionsClient / McpClient
    test seam (Phase D.4 + commit 27 + commit 28).
    """
    def fake_getter(method, url, headers, json_body):
        if url not in responses:
            raise KeyError(f"unexpected URL: {url}")
        return responses[url]
    return fake_getter


# ─── Model dataclasses parse correctly ─────────────────────────────


def test_status_from_dict() -> None:
    s = CollaborationStatus(
        id="collab-1",
        agent_count=3,
        active_agent="a1",
        pending_proposals=2,
        event_count=10,
        state_keys=["k1", "k2"],
    )
    assert s.id == "collab-1"
    assert s.agent_count == 3
    assert s.state_keys == ["k1", "k2"]


def test_agent_from_dict() -> None:
    a = CollaborationAgent(id="a1", name="worker-1", session_id="s1")
    assert a.session_id == "s1"
    assert a.capabilities == []


def test_proposal_from_dict() -> None:
    p = Proposal(
        id="p1",
        from_agent="a1",
        action="merge",
        description="merge plan",
        status="Pending",
        votes=[Vote(agent_id="a2", approve=True, reason=None)],
    )
    assert p.votes[0].agent_id == "a2"
    assert p.votes[0].approve is True


def test_shared_state_from_dict() -> None:
    r = SharedStateResponse(
        entries=[SharedStateEntry(key="x", value={"n": 1})],
    )
    assert r.entries[0].key == "x"


# ─── Endpoints ──────────────────────────────────────────────────────


def test_get_status_returns_status() -> None:
    body = {
        "id": "collab-1",
        "agent_count": 3,
        "active_agent": "a1",
        "pending_proposals": 0,
        "event_count": 5,
        "state_keys": ["k1"],
    }
    c = CollaborationClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/collaboration/status": body}
        ),
    )
    status = c.get_status()
    assert isinstance(status, CollaborationStatus)
    assert status.agent_count == 3


def test_list_agents_returns_typed_agents() -> None:
    body = [
        {"id": "a1", "name": "worker-1", "capabilities": ["bash", "read"], "session_id": "s1"},
        {"id": "a2", "name": "worker-2", "capabilities": [], "session_id": "s2"},
    ]
    c = CollaborationClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/collaboration/agents": body}
        ),
    )
    agents = c.list_agents()
    assert len(agents) == 2
    assert all(isinstance(a, CollaborationAgent) for a in agents)
    assert agents[0].capabilities == ["bash", "read"]


def test_list_events_preserves_flatten_shape() -> None:
    """Server uses ``#[serde(flatten)] event: Value`` — each
    row carries every event field at the top level, NOT
    nested under an ``event`` key. The Python mirror preserves
    the per-row dict verbatim so the TS client can do
    ``e.event ?? e`` (legacy UI pattern) without surprises.
    """
    body = [
        {"type": "AgentJoined", "ts": "2026-08-08T00:00:00Z", "agent_id": "a1"},
        {"type": "ProposalCreated", "ts": "2026-08-08T00:00:01Z", "proposal_id": "p1"},
    ]
    c = CollaborationClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/collaboration/events": body}
        ),
    )
    events = c.list_events()
    assert len(events) == 2
    assert all(isinstance(e, CollaborationEvent) for e in events)
    assert events[0].event["type"] == "AgentJoined"
    assert events[0].event["ts"] == "2026-08-08T00:00:00Z"


def test_list_proposals_unwraps_votes() -> None:
    body = [
        {"id": "p1", "from_agent": "a1", "action": "merge", "description": "merge plan", "status": "Pending", "votes": []},
        {"id": "p2", "from_agent": "a2", "action": "deploy", "description": "deploy", "status": "Accepted", "votes": [{"agent_id": "a1", "approve": True, "reason": "ok"}]},
    ]
    c = CollaborationClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/collaboration/proposals": body}
        ),
    )
    proposals = c.list_proposals()
    assert len(proposals) == 2
    assert all(isinstance(p, Proposal) for p in proposals)
    assert proposals[0].votes == []
    assert proposals[1].votes[0].agent_id == "a1"


def test_create_proposal_returns_persisted_row() -> None:
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["body"] = json_body
        captured["headers"] = headers
        return {
            "id": "p-new", "from_agent": json_body["from_agent"],
            "action": json_body["action"], "description": json_body["description"],
            "status": "Pending", "votes": [],
        }

    c = CollaborationClient("http://x", http_getter=getter)
    p = c.create_proposal(CreateProposalRequest(
        from_agent="a1", action="merge", description="x",
    ))
    assert p.id == "p-new"
    assert captured["body"] == {
        "from_agent": "a1", "action": "merge", "description": "x",
    }


def test_vote_on_proposal_returns_vote() -> None:
    body = {"agent_id": "user", "approve": True, "reason": None}
    c = CollaborationClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/collaboration/proposals/p1/vote": body}
        ),
    )
    v = c.vote_on_proposal("p1", VoteRequest(agent_id="user", approve=True))
    assert v.agent_id == "user"
    assert v.approve is True


def test_get_shared_state_unwraps_entries() -> None:
    body = {
        "entries": [
            {"key": "k1", "value": "v1"},
            {"key": "k2", "value": {"nested": 42}},
        ],
    }
    c = CollaborationClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/collaboration/shared-state": body}
        ),
    )
    state = c.get_shared_state()
    assert isinstance(state, SharedStateResponse)
    assert len(state.entries) == 2
    assert state.entries[1].value == {"nested": 42}


# ─── Security-fix contracts (Phase E.4 lesson from commit 1787083e)


def test_bearer_header_reaches_get_path() -> None:
    """Security fix: ``_get`` must inject the Bearer header
    on every call (E.3 lesson — commit aa6d2e20 shipped
    auth-bypass + we don't want to ship the same bug).
    """
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["headers"] = headers
        return {"id": "x", "agent_count": 0, "active_agent": None,
                "pending_proposals": 0, "event_count": 0, "state_keys": []}

    c = CollaborationClient("http://x", auth_token="SECRET", http_getter=getter)
    c.get_status()
    assert captured["headers"] == {"Authorization": "Bearer SECRET"}


def test_bearer_header_reaches_post_path() -> None:
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["headers"] = headers
        return {"id": "p", "from_agent": "a", "action": "x", "description": "y",
                "status": "Pending", "votes": []}

    c = CollaborationClient("http://x", auth_token="SECRET", http_getter=getter)
    c.create_proposal(CreateProposalRequest(from_agent="a", action="x", description="y"))
    assert captured["headers"] == {"Authorization": "Bearer SECRET"}


def test_bearer_header_reaches_get_array_path() -> None:
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["headers"] = headers
        return []

    c = CollaborationClient("http://x", auth_token="SECRET", http_getter=getter)
    c.list_proposals()
    assert captured["headers"] == {"Authorization": "Bearer SECRET"}


def test_vote_on_proposal_encodes_proposal_id() -> None:
    """Security fix: ``proposal_id`` is percent-encoded with
    ``safe=""`` so attacker-supplied ``/`` cannot restructure
    the URL (``/api/v1/collaboration/proposals/../vote`` or
    similar smuggling attempts).
    """
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["url"] = url
        return {"agent_id": "u", "approve": True, "reason": None}

    c = CollaborationClient("http://x", http_getter=getter)
    c.vote_on_proposal("../admin/users?force=1", VoteRequest(agent_id="u", approve=True))
    # The literal ``/vote`` suffix is the method's own segment
    # separator — never percent-encoded.
    assert captured["url"].endswith("/vote")
    # The two injected ``/`` characters (in ``../`` and after
    # ``users``) are percent-encoded. The third ``/`` is the
    # method's own separator (between the encoded segment and
    # ``/vote``) — kept literal.
    assert captured["url"].count("%2F") == 2
    # No literal ``?force`` query string leaks through (would
    # mean attacker-supplied input bypassed the encoder).
    assert "force=1" not in captured["url"]


def test_no_auth_token_results_in_empty_headers() -> None:
    """Negative test: when no auth_token is configured, the
    transport methods must still work — they just don't include
    the Authorization header. The pre-fix E.1 path passed
    empty ``{}`` accidentally because ``self.auth_token``
    was set but never sent; here we lock both branches so a
    refactor can't reintroduce the same bug.
    """
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["headers"] = headers
        return {"id": "x", "agent_count": 0, "active_agent": None,
                "pending_proposals": 0, "event_count": 0, "state_keys": []}

    c = CollaborationClient("http://x", http_getter=getter)
    c.get_status()
    assert captured["headers"] == {}


# ─── Error paths ────────────────────────────────────────────────────


def test_raises_collaboration_client_error_on_non_2xx() -> None:
    def getter(method, url, headers, json_body):
        import http.client
        import urllib.error
        msg = http.client.HTTPMessage()
        for k, v in headers.items():
            msg[k] = v
        raise urllib.error.HTTPError(url, 503, "Service Unavailable", msg, None)

    c = CollaborationClient("http://x", http_getter=getter)
    with pytest.raises(CollaborationClientError) as exc:
        c.get_status()
    assert exc.value.status == 503


def test_raises_collaboration_client_error_on_vote_failure() -> None:
    def getter(method, url, headers, json_body):
        import http.client
        import urllib.error
        msg = http.client.HTTPMessage()
        for k, v in headers.items():
            msg[k] = v
        raise urllib.error.HTTPError(url, 404, "Not Found", msg, None)

    c = CollaborationClient("http://x", http_getter=getter)
    with pytest.raises(CollaborationClientError) as exc:
        c.vote_on_proposal("missing", VoteRequest(agent_id="u", approve=True))
    assert exc.value.status == 404
