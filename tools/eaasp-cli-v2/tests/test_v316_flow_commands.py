"""Acceptance tests for the v3.16 business-flow CLI queries."""

from __future__ import annotations

import httpx
import pytest
from typer.testing import CliRunner

from eaasp_cli_v2 import main as cli_main

from tests.conftest import json_response


def _flow(
    key: str,
    *,
    status: str = "closed",
    failed_count: int = 0,
    last_started_at: int | None = 100,
    last_duration_ms: int | None = 10,
) -> dict[str, object]:
    return {
        "business_key": key,
        "business_object_id": f"object-{key}",
        "skill_id": "skill-1",
        "session_id": f"session-{key}",
        "session_count": 1,
        "finished_count": 1,
        "failed_count": failed_count,
        "last_started_at": last_started_at,
        "last_completed_at": last_started_at,
        "last_duration_ms": last_duration_ms,
        "status": status,
    }


def test_list_forwards_filters_and_renders_rows(runner: CliRunner, install_mock) -> None:
    captured: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured.update(dict(req.url.params))
        return json_response(200, {"flows": [_flow("listed")], "total": 1})

    install_mock(handler)
    result = runner.invoke(
        cli_main.app,
        [
            "flow", "list", "--limit", "7", "--status", "active",
            "--business-object-id", "object-listed",
        ],
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    assert captured == {
        "limit": "7",
        "status": "active",
        "business_object_id": "object-listed",
    }
    assert "listed" in result.stdout


def test_top_failed_fetches_maximum_candidates_and_ranks_then_limits(
    runner: CliRunner, install_mock
) -> None:
    captured: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured.update(dict(req.url.params))
        return json_response(
            200,
            {
                "flows": [
                    _flow("older-many", status="failed", failed_count=3, last_started_at=10),
                    _flow("newer-many", status="failed", failed_count=3, last_started_at=20),
                    _flow("few", status="failed", failed_count=1, last_started_at=30),
                ],
                "total": 3,
            },
        )

    install_mock(handler)
    result = runner.invoke(cli_main.app, ["flow", "top-failed", "--limit", "2"])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert captured == {"limit": "200", "status": "failed"}
    assert result.stdout.index("newer-many") < result.stdout.index("older-many")
    assert "few" not in result.stdout


def test_top_slow_fetches_maximum_candidates_and_ranks_then_limits(
    runner: CliRunner, install_mock
) -> None:
    captured: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured.update(dict(req.url.params))
        return json_response(
            200,
            {
                "flows": [
                    _flow("medium", last_duration_ms=100),
                    _flow("slowest", last_duration_ms=300),
                    _flow("unknown", last_duration_ms=None),
                ],
                "total": 3,
            },
        )

    install_mock(handler)
    result = runner.invoke(cli_main.app, ["flow", "top-slow", "--limit", "1"])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert captured == {"limit": "200"}
    assert "slowest" in result.stdout
    assert "medium" not in result.stdout
    assert "unknown" not in result.stdout


@pytest.mark.parametrize(
    ("command", "message"),
    [
        (["list"], "(no business flows)"),
        (["top-failed"], "(no failed flows)"),
        (["top-slow"], "(no slow flows)"),
    ],
)
def test_flow_queries_make_empty_results_explicit(
    runner: CliRunner, install_mock, command: list[str], message: str
) -> None:
    install_mock(lambda _: json_response(200, {"flows": [], "total": 0}))

    result = runner.invoke(cli_main.app, ["flow", *command])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert message in result.stdout


@pytest.mark.parametrize("command", ["list", "top-failed", "top-slow"])
@pytest.mark.parametrize("limit", ["0", "201"])
def test_flow_queries_reject_limits_outside_bounded_window(
    runner: CliRunner, command: str, limit: str
) -> None:
    result = runner.invoke(cli_main.app, ["flow", command, "--limit", limit])

    assert result.exit_code != 0


@pytest.mark.parametrize("command", ["list", "top-failed", "top-slow"])
def test_flow_queries_surface_shared_client_errors(
    runner: CliRunner, install_mock, command: str
) -> None:
    install_mock(lambda _: json_response(500, {"detail": "backend failed"}))

    result = runner.invoke(cli_main.app, ["flow", command])

    assert result.exit_code != 0
    assert "error" in result.stderr.lower()
