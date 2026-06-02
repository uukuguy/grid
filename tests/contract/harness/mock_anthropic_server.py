"""Minimal Anthropic-compatible mock used by contract tests.

Mirrors :mod:`tests.contract.harness.mock_openai_server` in purpose and
style: provides just enough of the Anthropic Messages API surface for
the claude-code-runtime's bundled ``claude`` CLI to receive a
deterministic non-error response when ``ANTHROPIC_BASE_URL`` is pointed
at a loopback port.

This mock intentionally does NOT script tool_use blocks. In the
claude-code-runtime architecture, scoped-hook dispatch happens on the
``OnToolCall`` / ``OnToolResult`` / ``OnStop`` RPCs — not inside the
``Send`` agent loop (which is a pure SDK passthrough for the Python
runtime). The HookProbe drives those RPCs directly after draining Send,
so all the mock needs to do here is keep ``Send`` from erroring out
with a DNS/TLS/auth failure against the real ``api.anthropic.com``.

Endpoints:

* ``POST /v1/messages`` — returns a minimal Anthropic-shaped assistant
  message (``content=[{"type":"text","text":"mock response"}]``,
  ``stop_reason="end_turn"``). No streaming.
* ``GET /health`` — liveness probe (always 200 ``{"status":"ok"}``).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from pydantic import BaseModel


class _MessagesRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    max_tokens: int | None = None
    stream: bool | None = False
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any = None
    system: Any = None


def build_app(
    scenario_responses: dict[str, dict[str, Any]] | None = None,
) -> FastAPI:
    """Return a FastAPI app implementing the minimum Anthropic surface.

    Args:
        scenario_responses: Phase 7.1 T04 (CONTRACT-02 / D138) — optional
            map of scenario name → Anthropic-shaped response fixture
            (``{"shape": "tool_use", "name": str, "input": dict}`` or
            ``{"shape": "text", "text": str}``). When the inbound
            request carries ``X-Test-Scenario: <name>`` and the name
            matches a key here, the mock returns the fixture instead of
            the default terminal-text reply.
    """
    app = FastAPI(title="contract-harness-mock-anthropic")
    scenarios: dict[str, dict[str, Any]] = dict(scenario_responses or {})
    observed_tool_choice: dict[str, Any] = {"value": None}

    @app.post("/v1/messages")
    async def messages(
        req: _MessagesRequest, request: Request
    ) -> dict[str, Any]:
        observed_tool_choice["value"] = req.tool_choice

        # T04 (CONTRACT-02 / D138): scenario header routes BEFORE the
        # default response. See OpenAI mock for the full path narrative.
        scenario = (
            request.headers.get("x-test-scenario")
            or request.headers.get("X-Test-Scenario")
        )
        if scenario and scenario in scenarios:
            fixture = scenarios[scenario]
            shape = fixture.get("shape", "text")
            if shape == "tool_use":
                return {
                    "id": "msg-mock-scenario",
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": fixture.get("id", "toolu_mock_0"),
                            "name": fixture.get("name", "unknown_tool"),
                            "input": fixture.get("input", {}),
                        }
                    ],
                    "model": req.model,
                    "stop_reason": "tool_use",
                    "stop_sequence": None,
                    "usage": {"input_tokens": 0, "output_tokens": 2},
                }
            return {
                "id": "msg-mock-scenario",
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "text", "text": fixture.get("text", "mock response")}
                ],
                "model": req.model,
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 2},
            }

        # Deterministic terminal-text response. The claude CLI parses this
        # into an AssistantMessage with a single TextBlock, which the
        # Python SDK wrapper then surfaces to Send as a text_delta chunk.
        return {
            "id": "msg-mock",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "mock response"}],
            "model": req.model,
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 2},
        }

    @app.get("/__test/last_tool_choice")
    async def last_tool_choice() -> dict[str, Any]:
        return {"tool_choice": observed_tool_choice["value"]}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
