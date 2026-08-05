"""Pytest fixtures — CliRunner + httpx.MockTransport-backed ServiceClient factory."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from eaasp_cli_v2 import main as cli_main
from eaasp_cli_v2.client import ServiceClient

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def install_mock(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[Handler], httpx.AsyncClient]:
    """Install a MockTransport-backed httpx.AsyncClient into the CLI factory slot.

    Phase D.4 — also seed ``cli_main._obstack_http_getter`` with a
    function that delegates to the same MockTransport. That way,
    tests for ``cmd_flow`` (which switched to the shared
    ``eaasp_common.ObstackClient``) get the same fake response
    the legacy ``ServiceClient`` tests get.
    """

    def _install(handler: Handler) -> httpx.AsyncClient:
        transport = httpx.MockTransport(handler)
        mock_client = httpx.AsyncClient(transport=transport)
        monkeypatch.setattr(
            cli_main,
            "_client_factory",
            lambda cfg: ServiceClient.from_httpx(mock_client),
        )

        # Mirror the transport into a plain-callable HTTP getter
        # that the new ObstackClient (which uses urllib, not httpx)
        # can consume. ObstackClient expects a parsed dict back, so
        # we use the httpx Response's .json() method (parses the
        # body and returns a dict).
        def _obstack_getter(url: str, headers: dict[str, str]) -> Any:
            req = httpx.Request("GET", url, headers=headers)
            resp = handler(req)
            # Raise on non-2xx (matches urllib's HTTPError behavior that
            # ObstackClient already converts to ObstackClientError).
            if resp.status_code >= 400:
                import urllib.error
                raise urllib.error.HTTPError(
                    url, resp.status_code, resp.reason_phrase, dict(resp.headers), None,
                )
            return resp.json()

        monkeypatch.setattr(cli_main, "_obstack_http_getter", _obstack_getter)

        return mock_client

    return _install


def json_response(status: int, body: Any) -> httpx.Response:
    return httpx.Response(
        status,
        content=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json"},
    )
