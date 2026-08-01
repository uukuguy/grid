"""CLI tests for ``eaasp flow``.

Per OBSTACK_DESIGN.md §3.5 / §3.6. Exercises the
``timeline`` / ``summary`` / ``evaluate`` subcommands end-to-end
via the project's ``install_mock`` fixture (httpx MockTransport
plugged into the existing ``ServiceClient`` factory). The ``watch``
subcommand is left to the live walkthrough (v3.15.5) since it
requires a real SSE server; here we only verify it has help text.
"""

from __future__ import annotations

import httpx
from typer.testing import CliRunner

from eaasp_cli_v2 import main as cli_main

from tests.conftest import json_response


# ─── _key_callback (no network needed) ──────────────────────────────────────


def test_key_callback_rejects_empty() -> None:
    import pytest
    import typer

    from eaasp_cli_v2 import cmd_flow

    with pytest.raises(typer.BadParameter):
        cmd_flow._key_callback("")


def test_key_callback_trims_whitespace() -> None:
    from eaasp_cli_v2 import cmd_flow

    assert cmd_flow._key_callback("  s1|k1|d1  ") == "s1|k1|d1"


# ─── timeline ──────────────────────────────────────────────────────────────


def test_timeline_prints_events(runner: CliRunner, install_mock) -> None:
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["path"] = req.url.path
        return json_response(
            200,
            {
                "business_key": "s1",
                "count": 2,
                "events": [
                    {
                        "ts": 1000, "layer": "L4", "component": "session",
                        "event_type": "session.created", "duration_ms": None, "error": None,
                    },
                    {
                        "ts": 1500, "layer": "L4", "component": "session",
                        "event_type": "session.closed", "duration_ms": 500, "error": None,
                    },
                ],
            },
        )

    install_mock(handler)
    result = runner.invoke(cli_main.app, ["flow", "timeline", "--key", "s1"])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert captured["path"] == "/v1/business-flows/s1/timeline"
    # Table renders; the event type column should be visible.
    assert "session.created" in result.stdout


def test_timeline_empty(runner: CliRunner, install_mock) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return json_response(
            200, {"business_key": "s1", "count": 0, "events": []},
        )

    install_mock(handler)
    result = runner.invoke(cli_main.app, ["flow", "timeline", "--key", "s1"])
    assert result.exit_code == 0
    assert "(no events" in result.stdout


def test_timeline_error_returns_nonzero(runner: CliRunner, install_mock) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return json_response(500, {"detail": "boom"})

    install_mock(handler)
    result = runner.invoke(cli_main.app, ["flow", "timeline", "--key", "s1"])
    assert result.exit_code != 0


# ─── summary ───────────────────────────────────────────────────────────────


def test_summary(runner: CliRunner, install_mock) -> None:
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["path"] = req.url.path
        return json_response(
            200,
            {
                "business_key": "s1",
                "summary": {
                    "status": "succeeded",
                    "event_count": 3,
                    "total_duration_ms": 1500,
                    "layer_counts": {"L4": 3},
                },
            },
        )

    install_mock(handler)
    result = runner.invoke(cli_main.app, ["flow", "summary", "--key", "s1"])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert captured["path"] == "/v1/business-flows/s1/summary"
    assert "succeeded" in result.stdout


# ─── evaluate ──────────────────────────────────────────────────────────────


def test_evaluate(runner: CliRunner, install_mock) -> None:
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["path"] = req.url.path
        return json_response(
            200,
            {
                "business_key": "s1",
                "report": {
                    "total_flows": 1,
                    "completion_rate": 0.0,
                    "hints": [
                        {"severity": "info", "metric": "sample_size", "recommendation": "x"}
                    ],
                },
            },
        )

    install_mock(handler)
    result = runner.invoke(cli_main.app, ["flow", "evaluate", "--key", "s1"])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert captured["path"] == "/v1/business-flows/s1/evaluation"
    assert "sample_size" in result.stdout


# ─── watch (smoke) ─────────────────────────────────────────────────────────


def test_watch_help(runner: CliRunner) -> None:
    result = runner.invoke(cli_main.app, ["flow", "watch", "--help"])
    assert result.exit_code == 0
    out = result.stdout.lower()
    assert "subscribe" in out or "ctrl-c" in out
