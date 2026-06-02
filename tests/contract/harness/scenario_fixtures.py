"""Deny-path scenario fixtures for D138 skill-workflow enforcement tests.

Phase 7.1 T04 (CONTRACT-02 / D138). Each entry maps a scenario name →
mock-LLM response shape that exercises one of the 5 skill-workflow
xfail cases:

  - ``deny-non-required-tool``: LLM calls a tool NOT in ``required_tools``.
  - ``unknown-tool``: LLM calls a tool that exists in NO catalog.
  - ``multi-tool-permutation``: LLM calls a required tool first; the
    second call falls through to the script counter / default stop.
  - ``cross-session-skill-isolation``: skill loaded in session A must
    NOT bleed into session B (no LLM-side scenario needed; T05 asserts
    via the LoadSkill / InitializeRequest sequence).
  - ``load-skill-after-initialize-idempotent``: 2x LoadSkill of same
    skill MUST NOT duplicate state (no LLM-side scenario; T05 asserts
    via GetState).

The dicts here ship the OpenAI and Anthropic surface shapes. The mock
servers consume them in ``build_app(scenario_responses=...)`` and
route by the ``X-Test-Scenario`` request header (set on the outbound
HTTP request by the LLM provider after the runtime forwards
``UserMessage.metadata["x-test-scenario"]`` into a session-scoped
header value — see T05 for the wire path).
"""

from __future__ import annotations

from typing import Any


OPENAI_DENY_SCENARIOS: dict[str, dict[str, Any]] = {
    "deny-non-required-tool": {
        "kind": "tool_calls",
        "tool_name": "evil_tool",
        "arguments": {"x": 1},
        "tool_id": "call_evil_0",
    },
    "unknown-tool": {
        "kind": "tool_calls",
        "tool_name": "nonexistent_tool",
        "arguments": {},
        "tool_id": "call_nox_0",
    },
    "multi-tool-permutation": {
        # T05 may script TWO turns for this; this fixture handles the
        # FIRST of two calls. The second call falls through to the
        # script counter or to the default stop reply.
        "kind": "tool_calls",
        "tool_name": "file_write",
        "arguments": {"path": "/tmp/a"},
        "tool_id": "call_a_0",
    },
}


# Anthropic-shape equivalents for runtimes wired through the Anthropic mock.
ANTHROPIC_DENY_SCENARIOS: dict[str, dict[str, Any]] = {
    "deny-non-required-tool": {
        "shape": "tool_use",
        "name": "evil_tool",
        "input": {"x": 1},
    },
    "unknown-tool": {
        "shape": "tool_use",
        "name": "nonexistent_tool",
        "input": {},
    },
}
