"""Smoke tests for the contract-suite harness (plan §S0.T1 step 7)."""

from __future__ import annotations


def test_runtime_launcher_importable():
    from tests.contract.harness import runtime_launcher

    assert hasattr(runtime_launcher, "RuntimeLauncher")
    assert hasattr(runtime_launcher, "RuntimeConfig")


def test_mock_openai_server_importable():
    from tests.contract.harness import mock_openai_server

    assert hasattr(mock_openai_server, "build_app")
    app = mock_openai_server.build_app()
    # Minimal structural check: FastAPI routes include /v1/chat/completions.
    paths = {route.path for route in app.routes}  # type: ignore[attr-defined]
    assert "/v1/chat/completions" in paths
    assert "/health" in paths


def test_assertions_helpers_importable():
    from tests.contract.harness import assertions

    assert assertions.EVENT_TYPES_V1 == frozenset(
        {
            "CHUNK",
            "TOOL_CALL",
            "TOOL_RESULT",
            "STOP",
            "ERROR",
            "HOOK_FIRED",
            "PRE_COMPACT",
        }
    )
    assert assertions.HOOK_EVENTS_V1 == frozenset(
        {"PreToolUse", "PostToolUse", "Stop"}
    )


def test_runtime_config_dataclass_shape():
    from tests.contract.harness.runtime_launcher import RuntimeConfig

    cfg = RuntimeConfig(
        name="grid",
        launch_cmd=["cargo", "run", "-p", "grid-runtime"],
        grpc_port=50061,
    )
    assert cfg.name == "grid"
    assert cfg.grpc_port == 50061
    assert cfg.env == {}
    assert cfg.startup_timeout_s == 30.0


def test_hook_envelope_assertion_rejects_missing_field():
    from tests.contract.harness.assertions import assert_hook_envelope_required_fields

    bad_envelope = {
        "event": "PreToolUse",
        "session_id": "s1",
        # missing: skill_id, tool_name, tool_args, created_at
    }
    try:
        assert_hook_envelope_required_fields(bad_envelope, "PreToolUse")
    except AssertionError as err:
        msg = str(err)
        assert "skill_id" in msg
        assert "tool_name" in msg
        return
    raise AssertionError("expected AssertionError for incomplete envelope")


def test_grid_env_vars_assertion_rejects_missing():
    from tests.contract.harness.assertions import assert_grid_env_vars_present

    try:
        assert_grid_env_vars_present(
            {"GRID_SESSION_ID": "s1", "GRID_EVENT": "Stop"}, "Stop"
        )
    except AssertionError as err:
        msg = str(err)
        assert "GRID_TOOL_NAME" in msg
        assert "GRID_SKILL_ID" in msg
        return
    raise AssertionError("expected AssertionError for missing GRID_* vars")


def test_openai_mock_routes_scenario_header():
    """Phase 7.1 T04 (CONTRACT-02 / D138): the OpenAI mock MUST route by
    X-Test-Scenario header before walking the script counter, and the
    routed response MUST honor the scenario fixture shape.
    """
    from fastapi.testclient import TestClient

    from tests.contract.harness.mock_openai_server import build_app
    from tests.contract.harness.scenario_fixtures import OPENAI_DENY_SCENARIOS

    app = build_app(scenario_responses=OPENAI_DENY_SCENARIOS)
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "x"}],
            "stream": False,
        },
        headers={"X-Test-Scenario": "deny-non-required-tool"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    tool_calls = body["choices"][0]["message"].get("tool_calls", [])
    assert any(
        tc["function"]["name"] == "evil_tool" for tc in tool_calls
    ), f"expected `evil_tool` tool_call in response; got: {body}"


def test_openai_mock_captures_tool_choice():
    """Phase 7.1 T04 (CONTRACT-02 / D138): the OpenAI mock MUST capture
    inbound `tool_choice` so tests can assert the runtime forwarded the
    expected value via the `__test/last_tool_choice` endpoint.
    """
    from fastapi.testclient import TestClient
    from tests.contract.harness.mock_openai_server import build_app

    app = build_app()
    client = TestClient(app)
    client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "x"}],
            "stream": False,
            "tool_choice": "required",
        },
    )
    resp = client.get("/__test/last_tool_choice")
    assert resp.status_code == 200, resp.text
    assert resp.json()["tool_choice"] == "required"


def test_anthropic_mock_routes_scenario_header():
    """Phase 7.1 T04 (CONTRACT-02 / D138): Anthropic mock parity check
    for the X-Test-Scenario header routing path.
    """
    from fastapi.testclient import TestClient

    from tests.contract.harness.mock_anthropic_server import build_app
    from tests.contract.harness.scenario_fixtures import (
        ANTHROPIC_DENY_SCENARIOS,
    )

    app = build_app(scenario_responses=ANTHROPIC_DENY_SCENARIOS)
    client = TestClient(app)
    resp = client.post(
        "/v1/messages",
        json={
            "model": "claude-3-5-sonnet-20241022",
            "messages": [{"role": "user", "content": "x"}],
            "max_tokens": 16,
        },
        headers={"X-Test-Scenario": "deny-non-required-tool"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["stop_reason"] == "tool_use"
    assert any(
        block.get("type") == "tool_use" and block.get("name") == "evil_tool"
        for block in body["content"]
    ), f"expected tool_use block named `evil_tool`; got: {body}"
