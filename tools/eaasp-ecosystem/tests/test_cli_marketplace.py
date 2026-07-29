"""Tests for the v3.14.2 MARKETPLACE-03 CLI subcommands.

The marketplace CLI (``eaasp-ecosystem marketplace {submit,promote,list,
stats,audit}``) is **HTTP-only** (per the v3.14.0 round-1 security review
that rejected a CLI in-process write path). These tests mock the
``L4 /v1/ecosystem/marketplace/*`` HTTP endpoints with ``respx`` and
assert that the CLI:

1. Forwards the right HTTP method + path + JSON body to each endpoint.
2. Maps the HTTP status code to the documented exit code (0 / 2 / 3 / 4).
3. Prints the JSON response body on success.
4. Prints ``HTTP <code>: <body>`` to stderr on failure.

The 66 backend tests in ``test_marketplace.py`` already cover the
in-process ``SkillMarketplace`` surface; the CLI does not duplicate it.
"""

from __future__ import annotations

import io
import json
import sys

import respx
from httpx import Response

from eaasp_ecosystem import cli as eaasp_cli


BASE_URL = "http://127.0.0.1:18087"
API_KEY = "dev-test-key-acme"


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    """Invoke ``eaasp_cli.main`` capturing stdout / stderr.

    ``argparse`` calls ``sys.exit(0)`` for ``--help`` — we translate
    that into a normal return so tests can assert exit code uniformly.
    """
    stdout = io.StringIO()
    stderr = io.StringIO()
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = stdout, stderr
    try:
        try:
            exit_code = eaasp_cli.main(argv)
        except SystemExit as exc:
            # argparse --help raises SystemExit(0); capture as exit code.
            exit_code = exc.code if isinstance(exc.code, int) else 0
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err
    return exit_code, stdout.getvalue(), stderr.getvalue()


# ─── submit ────────────────────────────────────────────────────────────


def test_marketplace_submit_forwards_payload_and_returns_skill_dict() -> None:
    skill = {
        "skill_id": "skill-cli-001",
        "name": "threshold-calibration",
        "version": "0.1.0",
        "current_stage": "draft",
    }
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post(
            "/v1/ecosystem/marketplace/skills/submit"
        ).mock(return_value=Response(201, json=skill))
        exit_code, stdout, stderr = _run_cli([
            "marketplace", "submit",
            "--api-key", API_KEY,
            "--base-url", BASE_URL,
            "--name", "threshold-calibration",
            "--summary", "Auto-tune LLM confidence",
            "--version", "0.1.0",
            "--manifest", '{"entrypoints":["calibrate"]}',
            "--scope", "tenant",
            "--tags", "eaasp,llm",
            "--author-principal", "apikey:abc",
        ])

    assert exit_code == 0, stderr
    body = json.loads(stdout)
    assert body["skill_id"] == "skill-cli-001"

    # The request must carry the exact JSON body the backend expects.
    sent = route.calls.last.request
    assert sent.method == "POST"
    sent_body = json.loads(sent.content)
    assert sent_body["name"] == "threshold-calibration"
    assert sent_body["scope"] == "tenant"
    assert sent_body["tags"] == ["eaasp", "llm"]
    assert sent_body["author_principal"] == "apikey:abc"
    # Bearer credential is forwarded via Authorization header.
    assert sent.headers["Authorization"] == f"Bearer {API_KEY}"
    # The CLI must NOT send X-Tenant-Id (rejected by v3.14.0 round-1 audit).
    assert "X-Tenant-Id" not in sent.headers


def test_marketplace_submit_401_returns_exit_code_3() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/v1/ecosystem/marketplace/skills/submit").mock(
            return_value=Response(401, json={"code": "missing_credentials"})
        )
        exit_code, _, stderr = _run_cli([
            "marketplace", "submit",
            "--api-key", API_KEY,
            "--base-url", BASE_URL,
            "--name", "x", "--summary", "x", "--version", "0.1.0",
            "--manifest", "{}",
            "--author-principal", "apikey:abc",
        ])
    assert exit_code == 3
    assert "401" in stderr


# ─── promote ───────────────────────────────────────────────────────────


def test_marketplace_promote_forwards_payload_and_returns_audit() -> None:
    audit = {
        "skill_id": "skill-cli-001",
        "lifecycle_id": "lc-1",
        "from_stage": "draft",
        "to_stage": "review",
        "actor_principal": "apikey:abc",
    }
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post(
            "/v1/ecosystem/marketplace/skills/promote"
        ).mock(return_value=Response(200, json=audit))
        exit_code, stdout, _ = _run_cli([
            "marketplace", "promote",
            "--api-key", API_KEY,
            "--base-url", BASE_URL,
            "--skill-id", "skill-cli-001",
            "--from-stage", "draft",
            "--to-stage", "review",
            "--rationale", "ready for review",
        ])

    assert exit_code == 0
    body = json.loads(stdout)
    assert body["to_stage"] == "review"
    sent = route.calls.last.request
    sent_body = json.loads(sent.content)
    assert sent_body["skill_id"] == "skill-cli-001"
    # Backend infers actor_principal + actor_role from the Bearer credential
    # via _require_principal; the CLI does NOT send them.
    assert "actor_principal" not in sent_body
    assert "actor_role" not in sent_body


def test_marketplace_promote_acl_denied_403_returns_exit_code_3() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/v1/ecosystem/marketplace/skills/promote").mock(
            return_value=Response(403, json={"code": "acl_forbidden"})
        )
        exit_code, _, _ = _run_cli([
            "marketplace", "promote",
            "--api-key", API_KEY,
            "--base-url", BASE_URL,
            "--skill-id", "skill-cli-001",
            "--from-stage", "draft",
            "--to-stage", "review",
            "--rationale", "test",
        ])
    assert exit_code == 3


def test_marketplace_promote_invalid_transition_400_returns_exit_code_2() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/v1/ecosystem/marketplace/skills/promote").mock(
            return_value=Response(400, json={"code": "promotion_error"})
        )
        exit_code, _, _ = _run_cli([
            "marketplace", "promote",
            "--api-key", API_KEY,
            "--base-url", BASE_URL,
            "--skill-id", "skill-cli-001",
            "--from-stage", "published",
            "--to-stage", "review",
            "--rationale", "test",
        ])
    assert exit_code == 2


# ─── list ──────────────────────────────────────────────────────────────


def test_marketplace_list_with_tag_filter() -> None:
    payload = {
        "tenant_id": "acme",
        "skills": [
            {"skill_id": "skill-001", "name": "x", "current_stage": "draft"}
        ],
    }
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get(
            "/v1/ecosystem/marketplace/skills/list"
        ).mock(return_value=Response(200, json=payload))
        exit_code, stdout, _ = _run_cli([
            "marketplace", "list",
            "--api-key", API_KEY,
            "--base-url", BASE_URL,
            "--tag", "eaasp",
        ])
    assert exit_code == 0
    assert route.calls.last.request.url.params["tag"] == "eaasp"
    body = json.loads(stdout)
    assert len(body["skills"]) == 1


# ─── stats + audit ─────────────────────────────────────────────────────


def test_marketplace_stats_unknown_skill_404_returns_exit_code_2() -> None:
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/v1/ecosystem/marketplace/skills/stats").mock(
            return_value=Response(404, json={"code": "skill_not_found"})
        )
        exit_code, _, _ = _run_cli([
            "marketplace", "stats",
            "--api-key", API_KEY,
            "--base-url", BASE_URL,
            "--skill-id", "ghost",
        ])
    assert exit_code == 2


def test_marketplace_audit_returns_history() -> None:
    payload = {
        "tenant_id": "acme",
        "skill_id": "skill-001",
        "audit": [{"to_stage": "draft"}, {"to_stage": "review"}],
    }
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get(
            "/v1/ecosystem/marketplace/skills/audit"
        ).mock(return_value=Response(200, json=payload))
        exit_code, stdout, _ = _run_cli([
            "marketplace", "audit",
            "--api-key", API_KEY,
            "--base-url", BASE_URL,
            "--skill-id", "skill-001",
        ])
    assert exit_code == 0
    assert route.calls.last.request.url.params["skill_id"] == "skill-001"
    body = json.loads(stdout)
    assert len(body["audit"]) == 2


# ─── Parser-level smoke ───────────────────────────────────────────────


def test_marketplace_subcommand_registered() -> None:
    """Locks that the ``marketplace`` parser is registered at startup.

    If the parser registration regresses, downstream subcommands become
    unreachable; this test asserts the parser accepts the marketplace
    verb and routes to one of the 5 subcommands without SystemExit.
    """
    # ``--help`` should not SystemExit(2) with 'unrecognized arguments'.
    exit_code, _, _ = _run_cli(["marketplace", "--help"])
    assert exit_code == 0
