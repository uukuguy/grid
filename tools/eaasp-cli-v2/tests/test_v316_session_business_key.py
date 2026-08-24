"""CLI rendering coverage for session business-key metadata."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
from typer.testing import CliRunner

from eaasp_cli_v2 import main as cli_main


def test_session_list_displays_business_keys_verbatim(
    runner: CliRunner,
    install_mock: Callable,
) -> None:
    business_key = "s|k|o"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/sessions":
            return httpx.Response(
                200,
                content=json.dumps(
                    {
                        "sessions": [
                            {
                                "session_id": "sess_key",
                                "status": "active",
                                "skill_id": "skill",
                                "runtime_id": "grid",
                                "created_at": 1,
                                "business_key": business_key,
                            },
                            {
                                "session_id": "sess_null",
                                "status": "closed",
                                "skill_id": "legacy",
                                "runtime_id": "grid",
                                "created_at": 0,
                                "business_key": None,
                            },
                        ]
                    }
                ).encode(),
                headers={"content-type": "application/json"},
            )
        return httpx.Response(404)

    install_mock(handler)
    result = runner.invoke(cli_main.app, ["session", "list"])

    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert "business_key" in result.stdout
    assert business_key in result.stdout
    assert "sess_null" in result.stdout


def test_session_show_displays_business_key_verbatim(
    runner: CliRunner,
    install_mock: Callable,
) -> None:
    business_key = "s|k|o"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/sessions/sess_with_key":
            return httpx.Response(
                200,
                json={
                    "session_id": "sess_with_key",
                    "status": "active",
                    "created_at": 1700000000,
                    "business_key": business_key,
                },
            )
        if request.url.path == "/v1/sessions/sess_with_key/events":
            return httpx.Response(200, json={"events": []})
        return httpx.Response(404)

    install_mock(handler)
    result = runner.invoke(cli_main.app, ["session", "show", "sess_with_key"])

    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert "business_key" in result.stdout
    assert business_key in result.stdout


def test_session_list_passes_null_business_key_to_table(
    runner: CliRunner,
    install_mock: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = {
        "session_id": "sess_null",
        "status": "closed",
        "skill_id": "legacy",
        "runtime_id": "grid",
        "created_at": 0,
        "business_key": None,
    }
    captured: list[tuple[str, list[object], list[str]]] = []

    def capture_table(title: str, rows: list[object], columns: list[str]) -> None:
        captured.append((title, rows, columns))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/sessions":
            return httpx.Response(200, json={"sessions": [session]})
        return httpx.Response(404)

    monkeypatch.setattr("eaasp_cli_v2.cmd_session.print_table", capture_table)
    install_mock(handler)
    result = runner.invoke(cli_main.app, ["session", "list"])

    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert captured == [
        (
            "Sessions",
            [session],
            [
                "session_id",
                "status",
                "skill_id",
                "runtime_id",
                "created_at",
                "business_key",
            ],
        )
    ]
    assert captured[0][1][0]["business_key"] is None


def test_session_show_passes_null_business_key_to_table(
    runner: CliRunner,
    install_mock: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = {
        "session_id": "sess_null",
        "status": "closed",
        "created_at": 0,
        "business_key": None,
    }
    captured: list[tuple[str, list[object], list[str]]] = []

    def capture_table(title: str, rows: list[object], columns: list[str]) -> None:
        captured.append((title, rows, columns))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/sessions/sess_null":
            return httpx.Response(200, json=session)
        if request.url.path == "/v1/sessions/sess_null/events":
            return httpx.Response(200, json={"events": []})
        return httpx.Response(404)

    monkeypatch.setattr("eaasp_cli_v2.cmd_session.print_table", capture_table)
    install_mock(handler)
    result = runner.invoke(cli_main.app, ["session", "show", "sess_null"])

    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert captured[0] == (
        "Session",
        [session],
        ["session_id", "status", "created_at", "business_key"],
    )
    assert captured[0][1][0]["business_key"] is None
